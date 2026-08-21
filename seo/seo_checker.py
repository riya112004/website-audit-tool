import os
from urllib.parse import urlparse

import httpx
from bs4 import BeautifulSoup

from app import db
from seo.recommendations import RECOMMENDATIONS

CATEGORY = "seo"


def _load_html(raw_html_path: str | None) -> BeautifulSoup | None:
    if not raw_html_path or not os.path.exists(raw_html_path):
        return None
    with open(raw_html_path, "r", encoding="utf-8") as f:
        return BeautifulSoup(f.read(), "html.parser")


def _add(scan_id, check_name, severity, message, page_id=None, recommendation=None):
    rec = recommendation or RECOMMENDATIONS.get(check_name, "")
    db.insert_finding(
        scan_id=scan_id,
        category=CATEGORY,
        check_name=check_name,
        severity=severity,
        message=message,
        page_id=page_id,
        recommendation=rec,
    )


def _is_crawlable(p: dict) -> bool:
    status = p.get("status_code")
    html_path = p.get("raw_html_path")
    if not status or status < 200 or status >= 300:
        return False
    if not html_path or not os.path.exists(html_path):
        return False
    return True


# ─── Severity Levels ──────────────────────────────────────
# error    = must fix, directly hurts SEO
# warning  = should fix, may impact SEO
# info     = recommendation, best practice


# ─── Crawl Access Layer ───────────────────────────────────

def check_crawl_access(scan_id: int, pages: list[dict]):
    for p in pages:
        status = p.get("status_code")
        if not status:
            _add(scan_id, "crawl_failed", "error",
                 f"Crawler could not reach page: {p['url']}",
                 page_id=p["id"])
        elif status == 403:
            _add(scan_id, "crawl_access_blocked", "warning",
                 f"Access blocked (HTTP 403): {p['url']}. SEO checks skipped — verify manually.",
                 page_id=p["id"])
        elif status == 401:
            _add(scan_id, "crawl_access_blocked", "warning",
                 f"Authentication required (HTTP 401): {p['url']}. SEO checks skipped.",
                 page_id=p["id"])
        elif status == 404:
            _add(scan_id, "page_not_found", "error",
                 f"Page does not exist (HTTP 404): {p['url']}",
                 page_id=p["id"])
        elif status >= 500:
            _add(scan_id, "server_error", "error",
                 f"Server error (HTTP {status}): {p['url']}",
                 page_id=p["id"])


# ─── Title Checks ─────────────────────────────────────────

def check_titles(scan_id: int, pages: list[dict]):
    seen_titles: dict[str, list[str]] = {}

    for p in pages:
        if not _is_crawlable(p):
            continue
        soup = _load_html(p.get("raw_html_path"))
        if not soup:
            continue

        title_tag = soup.title
        title_text = title_tag.get_text(strip=True) if title_tag else ""

        if not title_text:
            _add(scan_id, "missing_title", "error",
                 f"No <title> tag: {p['url']}",
                 page_id=p["id"])
        else:
            length = len(title_text)
            if length < 20:
                _add(scan_id, "short_title", "info",
                     f"Title is short ({length} chars): \"{title_text}\" — {p['url']}",
                     page_id=p["id"])
            elif length > 60:
                _add(scan_id, "long_title", "info",
                     f"Title may truncate in SERPs ({length} chars): \"{title_text[:60]}...\" — {p['url']}",
                     page_id=p["id"])

            if title_text not in seen_titles:
                seen_titles[title_text] = []
            seen_titles[title_text].append(p["url"])

    for title_text, urls in seen_titles.items():
        if len(urls) > 1:
            pages_str = ", ".join(urls[:5])
            _add(scan_id, "duplicate_title", "warning",
                 f"Same title on {len(urls)} pages: \"{title_text}\" — {pages_str}")


# ─── Meta Description Checks ──────────────────────────────

def check_meta_descriptions(scan_id: int, pages: list[dict]):
    seen: dict[str, list[str]] = {}

    for p in pages:
        if not _is_crawlable(p):
            continue
        soup = _load_html(p.get("raw_html_path"))
        if not soup:
            continue

        meta = soup.find("meta", {"name": "description"})
        content = meta.get("content", "").strip() if meta else ""

        if not content:
            _add(scan_id, "missing_meta_description", "warning",
                 f"No meta description: {p['url']}",
                 page_id=p["id"])
        else:
            length = len(content)
            if length < 70:
                _add(scan_id, "short_meta_description", "info",
                     f"Meta description short ({length} chars): {p['url']}",
                     page_id=p["id"])
            elif length > 160:
                _add(scan_id, "long_meta_description", "info",
                     f"Meta description may truncate ({length} chars): {p['url']}",
                     page_id=p["id"])

            if content not in seen:
                seen[content] = []
            seen[content].append(p["url"])

    for desc, urls in seen.items():
        if len(urls) > 1:
            pages_str = ", ".join(urls[:5])
            _add(scan_id, "duplicate_meta_description", "warning",
                 f"Same meta description on {len(urls)} pages — {pages_str}")


# ─── Heading Checks ───────────────────────────────────────

def check_headings(scan_id: int, pages: list[dict]):
    for p in pages:
        if not _is_crawlable(p):
            continue
        soup = _load_html(p.get("raw_html_path"))
        if not soup:
            continue

        h1s = soup.find_all("h1")
        if len(h1s) == 0:
            _add(scan_id, "missing_h1", "warning",
                 f"No <h1> tag: {p['url']}",
                 page_id=p["id"])
        elif len(h1s) > 1:
            _add(scan_id, "multiple_h1s", "warning",
                 f"Multiple <h1> tags ({len(h1s)}): {p['url']}",
                 page_id=p["id"])

        headings = soup.find_all(["h1", "h2", "h3", "h4", "h5", "h6"])
        violations = []
        prev_level = 0
        for h in headings:
            level = int(h.name[1])
            if prev_level > 0 and level > prev_level + 1:
                violations.append({"from": prev_level, "to": level})
            prev_level = level

        if violations:
            _add(scan_id, "heading_order_broken", "info",
                 f"Heading level skips ({len(violations)} violations): {p['url']}",
                 page_id=p["id"])


# ─── Image Checks ─────────────────────────────────────────

def check_images(scan_id: int, pages: list[dict]):
    for p in pages:
        if not _is_crawlable(p):
            continue
        soup = _load_html(p.get("raw_html_path"))
        if not soup:
            continue

        imgs = soup.find_all("img")
        missing = [img for img in imgs if not img.get("alt")]
        if missing:
            _add(scan_id, "images_missing_alt", "warning",
                 f"{len(missing)}/{len(imgs)} images missing alt text: {p['url']}",
                 page_id=p["id"])


# ─── Canonical Check ──────────────────────────────────────

def check_canonical(scan_id: int, pages: list[dict]):
    for p in pages:
        if not _is_crawlable(p):
            continue
        soup = _load_html(p.get("raw_html_path"))
        if not soup:
            continue

        canonical = soup.find("link", {"rel": "canonical"})
        if not canonical or not canonical.get("href"):
            _add(scan_id, "missing_canonical", "info",
                 f"No canonical tag: {p['url']}",
                 page_id=p["id"])


# ─── Structured Data Check ────────────────────────────────

def check_structured_data(scan_id: int, pages: list[dict]):
    for p in pages:
        if not _is_crawlable(p):
            continue
        soup = _load_html(p.get("raw_html_path"))
        if not soup:
            continue

        ld_json = soup.find_all("script", {"type": "application/ld+json"})
        if not ld_json:
            _add(scan_id, "no_structured_data", "info",
                 f"No JSON-LD structured data: {p['url']}",
                 page_id=p["id"])


# ─── Viewport Check ───────────────────────────────────────

def check_viewport(scan_id: int, pages: list[dict]):
    for p in pages:
        if not _is_crawlable(p):
            continue
        soup = _load_html(p.get("raw_html_path"))
        if not soup:
            continue

        viewport = soup.find("meta", {"name": "viewport"})
        if not viewport:
            _add(scan_id, "missing_viewport", "warning",
                 f"No viewport meta tag: {p['url']}",
                 page_id=p["id"])


# ─── Link Text Check ──────────────────────────────────────

def check_link_text(scan_id: int, pages: list[dict]):
    vague = {"click here", "read more", "here", "learn more", "link"}
    for p in pages:
        if not _is_crawlable(p):
            continue
        soup = _load_html(p.get("raw_html_path"))
        if not soup:
            continue

        vague_links = []
        for a in soup.find_all("a"):
            text = a.get_text(strip=True).lower()
            if text in vague:
                vague_links.append(a.get_text(strip=True))

        if vague_links:
            _add(scan_id, "non_descriptive_link_text", "info",
                 f"Non-descriptive link text ({len(vague_links)} links): {p['url']}",
                 page_id=p["id"])


# ─── HTTPS Check ──────────────────────────────────────────

def check_https(scan_id: int, pages: list[dict]):
    for p in pages:
        if not p["url"].startswith("https://"):
            _add(scan_id, "not_https", "warning",
                 f"Not HTTPS: {p['url']}",
                 page_id=p["id"])


# ─── Broken Links ─────────────────────────────────────────

def check_broken_links(scan_id: int, pages: list[dict]):
    for p in pages:
        status = p.get("status_code")
        if not status:
            continue
        if status == 404:
            _add(scan_id, "broken_link", "error",
                 f"Broken link (404): {p['url']}",
                 page_id=p["id"])
        elif status >= 500:
            _add(scan_id, "broken_link", "error",
                 f"Server error ({status}): {p['url']}",
                 page_id=p["id"])


# ─── Robots & Sitemap ─────────────────────────────────────

def check_robots_and_sitemap(scan_id: int, origin: str):
    for path in ["/robots.txt", "/sitemap.xml"]:
        check_name = f"missing_{path.strip('/').replace('.', '_')}"
        try:
            resp = httpx.get(f"{origin}{path}", follow_redirects=True, timeout=10)
            if resp.status_code == 404:
                _add(scan_id, check_name, "warning",
                     f"{path} not found (404): {origin}")
            elif resp.status_code == 403:
                _add(scan_id, f"blocked_{path.strip('/').replace('.', '_')}", "info",
                     f"{path} exists but blocked (403): {origin} — verify manually")
            elif resp.status_code >= 500:
                _add(scan_id, f"error_{path.strip('/').replace('.', '_')}", "warning",
                     f"{path} server error ({resp.status_code}): {origin}")
        except Exception:
            _add(scan_id, check_name, "info",
                 f"Could not fetch {path} from {origin}")


# ─── Main Runner ──────────────────────────────────────────

def run_seo_checks(scan_id: int):
    db.delete_findings(scan_id, CATEGORY)

    pages = db.get_pages(scan_id)
    if not pages:
        return

    scan = db.get_scan(scan_id)
    origin = ""
    if scan:
        site = db.get_conn().execute("SELECT * FROM sites WHERE id = ?", (scan["site_id"],)).fetchone()
        if site:
            origin = site["origin"]

    check_crawl_access(scan_id, pages)
    check_titles(scan_id, pages)
    check_meta_descriptions(scan_id, pages)
    check_headings(scan_id, pages)
    check_images(scan_id, pages)
    check_canonical(scan_id, pages)
    check_structured_data(scan_id, pages)
    check_viewport(scan_id, pages)
    check_link_text(scan_id, pages)
    check_broken_links(scan_id, pages)
    check_https(scan_id, pages)

    if origin:
        check_robots_and_sitemap(scan_id, origin)

    return db.get_findings(scan_id, CATEGORY)
