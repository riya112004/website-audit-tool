"""
Main web crawler — full-site BFS crawler with:
- deque-based BFS queue
- Canonical URL deduplication
- Sitemap pre-populate
- asyncio.Semaphore concurrency (Playwright is async, not ThreadPoolExecutor)
- Host normalization (www. strip)
- Per-page error handling (failed pages don't stop crawl)
- Navbar-aware priority crawling
- Crawl summary with pages_attempted, pages_crawled, pages_failed, time_taken
"""

import asyncio
import json
import os
import time
from collections import deque
from urllib.parse import urlparse, urlencode, parse_qs, urlunparse

from playwright.async_api import async_playwright, Page

from app import db

DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data")

TRACKING_PARAMS = {
    "utm_source", "utm_medium", "utm_campaign", "utm_term", "utm_content",
    "fbclid", "gclid", "mc_cid", "mc_eid", "ref", "source", "spm",
    "from", "share_id", "_ga", "_gl", "yclid", "msclkid", "twclid",
}

CLICKABLE_ROLES = {"button", "link", "tab", "menuitem", "option", "checkbox", "radio", "switch"}

SKIP_EXTENSIONS = {".pdf", ".doc", ".docx", ".xls", ".xlsx", ".ppt", ".pptx",
                   ".zip", ".rar", ".tar", ".gz", ".mp3", ".mp4", ".avi",
                   ".mov", ".wmv", ".flv", ".jpg", ".jpeg", ".png", ".gif",
                   ".svg", ".ico", ".css", ".js", ".xml", ".json", ".txt"}

CRAWL_TIMEOUT = 600
PAGE_GOTO_TIMEOUT = 25000
MAX_CONCURRENT = 5


# ─── URL Utilities ────────────────────────────────────────

def normalize_url(url: str) -> str:
    parsed = urlparse(url)
    scheme = parsed.scheme or "https"
    netloc = parsed.netloc.lower().rstrip(".")
    # Strip www. prefix for consistent dedup
    if netloc.startswith("www."):
        netloc = netloc[4:]
    path = parsed.path.rstrip("/") or "/"
    qs = parse_qs(parsed.query, keep_blank_values=False)
    for param in TRACKING_PARAMS:
        qs.pop(param, None)
    sorted_qs = urlencode(sorted(qs.items()), doseq=True)
    # Strip fragment (#) — same page, different anchor
    return urlunparse((scheme, netloc, path, "", sorted_qs, ""))


def normalize_host(host: str) -> str:
    h = host.lower()
    return h[4:] if h.startswith("www.") else h


def _is_same_origin(url: str, origin: str) -> bool:
    return normalize_host(urlparse(url).netloc) == normalize_host(urlparse(origin).netloc)


def _is_crawlable_url(url: str) -> bool:
    path = urlparse(url).path.lower()
    return not any(path.endswith(ext) for ext in SKIP_EXTENSIONS)


# ─── Accessibility ────────────────────────────────────────

async def _get_accessibility_nodes(page: Page) -> list[dict]:
    try:
        cdp = await page.context.new_cdp_session(page)
        result = await cdp.send("Accessibility.getFullAXTree")
        nodes = []
        for node in result.get("nodes", []):
            role_obj = node.get("role", {})
            role = role_obj.get("value", "") if isinstance(role_obj, dict) else str(role_obj)
            name_obj = node.get("name", {})
            name = name_obj.get("value", "") if isinstance(name_obj, dict) else str(name_obj)
            if role in CLICKABLE_ROLES and name:
                nodes.append({"role": role, "accessible_name": name})
        await cdp.detach()
        return nodes
    except Exception:
        return []


def _unique_nodes(nodes: list[dict]) -> list[dict]:
    seen = set()
    result = []
    for n in nodes:
        key = (n["role"], n["accessible_name"])
        if key not in seen:
            seen.add(key)
            result.append(n)
    return result


def _build_selector(role: str, name: str) -> str:
    if name:
        escaped = name.replace('"', '\\"')
        return f'[role="{role}"][aria-label="{escaped}"]'
    return f'[role="{role}"]'


# ─── Navbar Detection ─────────────────────────────────────

async def _extract_navbar_links(pg: Page) -> list[str]:
    try:
        selectors = (
            'nav a[href], header a[href], '
            '[role="navigation"] a[href], '
            '.navbar a[href], .nav a[href], .menu a[href], '
            '.main-menu a[href], .primary-menu a[href], '
            '#menu a[href], #nav a[href], #navigation a[href], '
            '.site-header a[href]'
        )
        return await pg.eval_on_selector_all(selectors, "els => els.map(e => e.href)")
    except Exception:
        return []


# ─── Single Page Crawl ───────────────────────────────────

async def _crawl_one_page(
    pg: Page, url: str, scan_id: int, site_id: int,
    page_no: int, origin: str
) -> dict:
    """Crawl one page: load, extract data, save to DB. Returns result dict."""
    console_errors = []
    pg.on("console", lambda msg: console_errors.append(msg.text) if msg.type == "error" else None)

    try:
        resp = await pg.goto(url, wait_until="domcontentloaded", timeout=PAGE_GOTO_TIMEOUT)
    except Exception as e:
        return {"error": f"[{url}] {e}"}

    status_code = resp.status if resp else None
    resp_headers = dict(resp.headers) if resp else {}
    title = await pg.title()

    # Core Web Vitals: inject PerformanceObserver before full load
    await pg.evaluate("""() => {
        window.__cwv = { lcp: 0, cls: 0, inp: 0, lcp_entries: [], cls_entries: [] };
        try {
            new PerformanceObserver((list) => {
                for (const entry of list.getEntries()) {
                    if (entry.startTime > window.__cwv.lcp) {
                        window.__cwv.lcp = Math.round(entry.startTime);
                        window.__cwv.lcp_entries.push({ element: entry.element?.tagName || 'unknown', size: entry.size, url: entry.url || '' });
                    }
                }
            }).observe({ type: 'largest-contentful-paint', buffered: true });
        } catch(e) {}
        try {
            new PerformanceObserver((list) => {
                for (const entry of list.getEntries()) {
                    if (!entry.hadRecentInput) {
                        window.__cwv.cls += entry.value;
                        window.__cwv.cls_entries.push({ value: Math.round(entry.value * 1000) / 1000, element: entry.element?.tagName || 'unknown' });
                    }
                }
            }).observe({ type: 'layout-shift', buffered: true });
        } catch(e) {}
    }""")

    raw_html = await pg.content()
    html_dir = os.path.join(DATA_DIR, "html", f"scan{scan_id}")
    os.makedirs(html_dir, exist_ok=True)
    html_path = os.path.join(html_dir, f"page_{page_no}.html")
    with open(html_path, "w", encoding="utf-8") as f:
        f.write(raw_html)

    screenshot_dir = os.path.join(html_dir, "screenshots")
    os.makedirs(screenshot_dir, exist_ok=True)
    screenshot_path = os.path.join(screenshot_dir, f"page_{page_no}.png")
    try:
        await pg.screenshot(path=screenshot_path, full_page=False)
    except Exception:
        screenshot_path = None

    page_obj = db.insert_page(
        scan_id=scan_id, site_id=site_id,
        url=url, normalized_url=normalize_url(url),
        title=title, depth=0,
        status_code=status_code,
        screenshot_path=screenshot_path,
        raw_html_path=html_path,
        response_headers=json.dumps(resp_headers),
    )

    raw_nodes = await _get_accessibility_nodes(pg)
    nodes = _unique_nodes(raw_nodes)
    for node in nodes:
        selector = _build_selector(node["role"], node["accessible_name"])
        db.insert_element(
            page_id=page_obj["id"],
            role=node["role"], accessible_name=node["accessible_name"],
            selector=selector, first_seen_scan_id=scan_id,
        )

    all_links = await pg.eval_on_selector_all("a[href]", "els => els.map(e => e.href)")

    navbar_links = await _extract_navbar_links(pg)
    navbar_set = set(normalize_url(u) for u in navbar_links) if navbar_links else set()

    # Canonical
    canonical = None
    try:
        canonical = await pg.eval_on_selector(
            'link[rel="canonical"]', "el => el.href"
        )
    except Exception:
        pass
    canonical_norm = normalize_url(canonical) if canonical else normalize_url(url)

    # Read Core Web Vitals after page settle
    cwv = await pg.evaluate("""() => {
        const w = window.__cwv || {};
        return {
            lcp: w.lcp || 0,
            cls: Math.round((w.cls || 0) * 1000) / 1000,
            lcp_entries: w.lcp_entries || [],
            cls_entries: w.cls_entries || [],
        };
    }""")

    for href in all_links:
        db.insert_edge(page_obj["id"], href, None)

    return {
        "url": url,
        "page_obj": page_obj,
        "elements_count": len(nodes),
        "all_links": all_links,
        "navbar_set": navbar_set,
        "canonical": canonical_norm,
        "status_code": status_code,
        "error": None,
        "console_errors": console_errors,
        "dom_size": await pg.evaluate("() => document.querySelectorAll('*').length"),
        "viewport": {"width": 1280, "height": 720},
        "screenshot_path": screenshot_path,
        "word_count": await pg.evaluate("() => document.body ? document.body.innerText.split(/\\s+/).filter(w => w.length > 0).length : 0"),
        "section_count": await pg.evaluate("() => document.querySelectorAll('section, article, .section, [class*=section]').length"),
        "form_count": await pg.evaluate("() => document.querySelectorAll('form').length"),
        "image_count": await pg.evaluate("() => document.querySelectorAll('img').length"),
        "heading_counts": await pg.evaluate("() => ({ h1: document.querySelectorAll('h1').length, h2: document.querySelectorAll('h2').length, h3: document.querySelectorAll('h3').length, h4: document.querySelectorAll('h4').length, h5: document.querySelectorAll('h5').length, h6: document.querySelectorAll('h6').length })"),
        "button_count": await pg.evaluate("() => document.querySelectorAll('button, [role=button], input[type=submit], input[type=button]').length"),
        "link_count": len(all_links),
        "meta_description": await pg.evaluate("() => { const m = document.querySelector('meta[name=description]'); return m ? m.content : ''; }"),
        "viewport_meta": await pg.evaluate("() => !!document.querySelector('meta[name=viewport]')"),
        "lang_attr": await pg.evaluate("() => document.documentElement.lang || ''"),
        "core_web_vitals": cwv,
        "rendered_styles": await pg.evaluate("""() => {
            const cs = (el) => window.getComputedStyle(el);
            const px = (v) => parseFloat(v) || 0;

            // Heading styles (limit 8)
            const headings = [];
            document.querySelectorAll('h1,h2,h3,h4,h5,h6').forEach(h => {
                if (headings.length >= 8) return;
                const s = cs(h);
                const r = h.getBoundingClientRect();
                headings.push({
                    tag: h.tagName.toLowerCase(),
                    text: h.innerText.trim().slice(0, 60),
                    fontSize: px(s.fontSize),
                    fontWeight: parseInt(s.fontWeight) || 0,
                    lineHeight: px(s.lineHeight),
                    color: s.color,
                    marginTop: px(s.marginTop),
                    marginBottom: px(s.marginBottom),
                    top: Math.round(r.top),
                    visible: r.height > 0 && s.visibility !== 'hidden' && s.display !== 'none',
                });
            });

            // Body text samples — use only <p> instead of p/li/td/span/a (avoids iterating thousands)
            const bodyTexts = [];
            document.querySelectorAll('p').forEach(el => {
                if (bodyTexts.length >= 10) return;
                const s = cs(el);
                const txt = el.innerText.trim();
                if (!txt || txt.length < 5) return;
                bodyTexts.push({
                    tag: 'p',
                    fontSize: px(s.fontSize),
                    fontWeight: parseInt(s.fontWeight) || 0,
                    lineHeight: px(s.lineHeight),
                    color: s.color,
                });
            });

            // CTA elements (limit 4)
            const ctas = [];
            const ctaSelector = 'button, a.btn, a.button, [role=button], input[type=submit]';
            document.querySelectorAll(ctaSelector).forEach(el => {
                if (ctas.length >= 4) return;
                const s = cs(el);
                const r = el.getBoundingClientRect();
                ctas.push({
                    tag: el.tagName.toLowerCase(),
                    text: el.innerText.trim().slice(0, 40),
                    fontSize: px(s.fontSize),
                    fontWeight: parseInt(s.fontWeight) || 0,
                    color: s.color,
                    backgroundColor: s.backgroundColor,
                    padding: px(s.paddingTop) + px(s.paddingBottom),
                    top: Math.round(r.top),
                    width: Math.round(r.width),
                    height: Math.round(r.height),
                });
            });

            // Section spacing (limit 6)
            const sections = [];
            document.querySelectorAll('section, article, main').forEach(el => {
                if (sections.length >= 6) return;
                const s = cs(el);
                const r = el.getBoundingClientRect();
                sections.push({
                    tag: el.tagName.toLowerCase(),
                    className: (el.className || '').toString().slice(0, 50),
                    paddingTop: px(s.paddingTop),
                    paddingBottom: px(s.paddingBottom),
                    marginTop: px(s.marginTop),
                    marginBottom: px(s.marginBottom),
                    height: Math.round(r.height),
                    top: Math.round(r.top),
                    backgroundColor: s.backgroundColor,
                });
            });

            // Viewport info
            const body = document.body;
            const bodyStyle = body ? cs(body) : null;
            const bodyBg = bodyStyle ? bodyStyle.backgroundColor : 'rgb(255,255,255)';

            return {
                headings: headings,
                bodyTexts: bodyTexts,
                ctas: ctas,
                sections: sections,
                bodyBackground: bodyBg,
                viewportHeight: window.innerHeight,
            };
        }"""),
    }


# ─── Main Crawl Orchestrator ─────────────────────────────

async def crawl_site(scan_id: int):
    """
    Full-site BFS crawl following WebCrawler reference patterns:
    - deque queue with (url, source) tuples
    - visited, visited_canonical, failed, seen_raw sets
    - Sitemap pre-populate
    - Per-page error handling
    - Navbar priority
    - Crawl summary
    """
    scan = db.get_scan(scan_id)
    if not scan:
        return

    db.update_scan(scan_id, status="running", started_at=db.datetime.now(db.timezone.utc).isoformat())

    site = db.get_conn().execute("SELECT * FROM sites WHERE id = ?", (scan["site_id"],)).fetchone()
    origin = site["origin"]
    max_pages = scan["max_pages"]

    # ─── Shared state (reference pattern) ──────────────────
    visited: set[str] = set()
    visited_canonical: set[str] = set()
    failed: set[str] = set()
    seen_raw: set[str] = set()
    all_links: set[str] = set()

    queue: deque[tuple[str, str]] = deque()
    semaphore = asyncio.Semaphore(MAX_CONCURRENT)

    pages_crawled = 0
    pages_attempted = 0
    elements_found = 0
    start_time = time.time()
    page_ux_data = {}

    # ─── Step 1: Pre-populate from sitemap ─────────────────
    from app.sitemap_parser import fetch_sitemap
    sitemap_urls = fetch_sitemap(origin)
    for surl in sitemap_urls:
        surl_norm = normalize_url(surl)
        if surl_norm not in seen_raw:
            seen_raw.add(surl_norm)
            queue.append((surl, "sitemap"))

    # Start URL at front
    start_norm = normalize_url(scan["start_url"])
    if start_norm not in seen_raw:
        seen_raw.add(start_norm)
        queue.appendleft((scan["start_url"], "start"))

    # sitemap info logged silently, not stored in error field

    # ─── Step 2: Launch browser ───────────────────────────
    async with async_playwright() as pw:
        browser = await pw.chromium.launch(headless=True)

        async def _crawl_with_semaphore(url: str, page_no: int):
            """Crawl one page with semaphore concurrency control."""
            ctx = await browser.new_context(viewport={"width": 1280, "height": 720})
            pg = await ctx.new_page()
            try:
                async with semaphore:
                    return await _crawl_one_page(pg, url, scan_id, scan["site_id"], page_no, origin)
            finally:
                try:
                    await pg.close()
                    await ctx.close()
                except Exception:
                    pass

        # ─── Step 3: BFS crawl loop ──────────────────────
        pending_tasks = []

        while queue and pages_crawled < max_pages:
            elapsed = time.time() - start_time
            if elapsed > CRAWL_TIMEOUT:
                break

            # Collect a batch of URLs to crawl concurrently
            batch = []
            while queue and len(batch) < MAX_CONCURRENT and pages_crawled + len(batch) < max_pages:
                url, source = queue.popleft()
                url_norm = normalize_url(url)

                if url_norm in visited:
                    continue
                if not _is_same_origin(url, origin):
                    continue
                if not _is_crawlable_url(url):
                    continue

                visited.add(url_norm)
                pages_attempted += 1
                batch.append((url, pages_attempted))

            if not batch:
                break

            # Crawl batch concurrently
            tasks = [_crawl_with_semaphore(url, pno) for url, pno in batch]
            results = await asyncio.gather(*tasks, return_exceptions=True)

            for (url, page_no), result in zip(batch, results):
                if isinstance(result, Exception):
                    failed.add(url)
                    continue

                if result is None or result.get("error"):
                    failed.add(url)
                    continue

                # Store UX data for this page
                page_ux_data[url] = {
                    "console_errors": result.get("console_errors", []),
                    "dom_size": result.get("dom_size", 0),
                    "viewport": result.get("viewport", {}),
                    "screenshot_path": result.get("screenshot_path"),
                    "word_count": result.get("word_count", 0),
                    "section_count": result.get("section_count", 0),
                    "form_count": result.get("form_count", 0),
                    "image_count": result.get("image_count", 0),
                    "heading_counts": result.get("heading_counts", {}),
                    "button_count": result.get("button_count", 0),
                    "link_count": result.get("link_count", 0),
                    "meta_description": result.get("meta_description", ""),
                    "viewport_meta": result.get("viewport_meta", False),
                    "lang_attr": result.get("lang_attr", ""),
                    "rendered_styles": result.get("rendered_styles", {}),
                    "core_web_vitals": result.get("core_web_vitals", {}),
                }

                # Canonical dedup
                canonical = result["canonical"]
                if canonical in visited_canonical:
                    continue
                visited_canonical.add(canonical)

                pages_crawled += 1
                elements_found += result["elements_count"]

                # Enqueue discovered links
                for href in result["all_links"]:
                    href_norm = normalize_url(href)
                    if href_norm in seen_raw:
                        continue
                    if not _is_same_origin(href, origin):
                        continue
                    if not _is_crawlable_url(href):
                        continue

                    seen_raw.add(href_norm)
                    all_links.add(href_norm)

                    if href_norm in result["navbar_set"]:
                        queue.appendleft((href, "navbar"))
                    else:
                        queue.append((href, "page"))

            # Progress update
            db.update_scan(scan_id, pages_crawled=pages_crawled, elements_found=elements_found)

        await browser.close()

    # ─── Step 3b: Save UX data ───────────────────────────
    if page_ux_data:
        ux_dir = os.path.join(DATA_DIR, "html", f"scan{scan_id}")
        os.makedirs(ux_dir, exist_ok=True)
        ux_file = os.path.join(ux_dir, "ux_data.json")
        with open(ux_file, "w", encoding="utf-8") as f:
            json.dump(page_ux_data, f, indent=2)

    # ─── Step 4: Mobile viewport re-check (first 5 pages) ─
    mobile_ux_results = {}
    pages_list = db.get_pages(scan_id)
    pages_to_check_mobile = [p for p in pages_list if p.get("status_code") and 200 <= p["status_code"] < 400][:5]

    if pages_to_check_mobile:
        async with async_playwright() as pw2:
            mobile_browser = await pw2.chromium.launch(headless=True)
            for p in pages_to_check_mobile:
                try:
                    ctx = await mobile_browser.new_context(
                        viewport={"width": 375, "height": 812},
                        user_agent="Mozilla/5.0 (iPhone; CPU iPhone OS 16_0 like Mac OS X)"
                    )
                    pg = await ctx.new_page()
                    try:
                        await pg.goto(p["url"], wait_until="domcontentloaded", timeout=PAGE_GOTO_TIMEOUT)
                        has_hscroll = await pg.evaluate("document.documentElement.scrollWidth > document.documentElement.clientWidth")
                        overflow_elements = await pg.evaluate("""() => {
                            const els = document.querySelectorAll('*');
                            let count = 0;
                            for (const el of els) {
                                const r = el.getBoundingClientRect();
                                if (r.right > window.innerWidth + 5) count++;
                            }
                            return count;
                        }""")
                        small_buttons = await pg.evaluate("""() => {
                            const btns = document.querySelectorAll('a, button, [role="button"], input[type="submit"]');
                            let count = 0;
                            for (const b of btns) {
                                const r = b.getBoundingClientRect();
                                if (r.width > 0 && r.height > 0 && (r.width < 44 || r.height < 44)) count++;
                            }
                            return count;
                        }""")
                        fixed_elements = await pg.evaluate("""() => {
                            const els = document.querySelectorAll('*');
                            let count = 0;
                            for (const el of els) {
                                const s = getComputedStyle(el);
                                if (s.position === 'fixed' || s.position === 'sticky') count++;
                            }
                            return count;
                        }""")
                        mobile_ux_results[p["url"]] = {
                            "has_horizontal_overflow": has_hscroll,
                            "overflow_elements": overflow_elements,
                            "small_touch_targets": small_buttons,
                            "fixed_elements": fixed_elements,
                        }
                    except Exception:
                        pass
                    finally:
                        await pg.close()
                        await ctx.close()
                except Exception:
                    pass
            await mobile_browser.close()

    if mobile_ux_results:
        ux_dir = os.path.join(DATA_DIR, "html", f"scan{scan_id}")
        ux_file = os.path.join(ux_dir, "ux_data.json")
        existing = {}
        if os.path.exists(ux_file):
            with open(ux_file, "r", encoding="utf-8") as f:
                existing = json.load(f)
        for url, data in mobile_ux_results.items():
            if url in existing:
                existing[url]["mobile"] = data
            else:
                existing[url] = {"mobile": data}
        with open(ux_file, "w", encoding="utf-8") as f:
            json.dump(existing, f, indent=2)

    # ─── Step 4: Finalize ─────────────────────────────────
    elapsed = time.time() - start_time
    summary = {
        "start_url": scan["start_url"],
        "pages_attempted": pages_attempted,
        "pages_crawled": pages_crawled,
        "pages_failed": len(failed),
        "total_links_found": len(all_links),
        "time_taken": f"{int(elapsed // 60)}m {int(elapsed % 60)}s",
    }

    db.update_scan(
        scan_id,
        status="completed",
        finished_at=db.datetime.now(db.timezone.utc).isoformat(),
        pages_crawled=pages_crawled,
        elements_found=elements_found,
        interactions_run=0,
    )


def run_crawl_in_thread(scan_id: int):
    """Run crawl in a new event loop (called from main.py background task)."""
    import asyncio as _ai
    if __import__("sys").platform == "win32":
        _ai.set_event_loop_policy(_ai.WindowsProactorEventLoopPolicy())
    loop = _ai.new_event_loop()
    _ai.set_event_loop(loop)
    try:
        loop.run_until_complete(crawl_site(scan_id))
    finally:
        loop.close()
