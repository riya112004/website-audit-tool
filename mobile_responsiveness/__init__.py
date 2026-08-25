"""
Mobile Responsiveness Audit — 8 categories, 5 breakpoints, real browser measurements.

Breakpoints: 320, 375, 390, 414, 768px
Categories:
  1. Viewport & Overflow     — 20%
  2. Responsive Layout       — 20%
  3. Typography & Content    — 15%
  4. Images & Media          — 10%
  5. Navigation              — 15%
  6. Touch & Interaction     — 10%
  7. Fixed/Sticky Elements   —  5%
  8. Mobile Visual Quality   —  5%
"""

import asyncio
from playwright.async_api import async_playwright, Page, BrowserContext


BREAKPOINTS = [320, 375, 390, 414, 768]
PAGE_GOTO_TIMEOUT = 25000


# ── JS evaluation scripts ──────────────────────────────────────────────────

JS_VIEWPORT_OVERFLOW = """() => {
    const d = document.documentElement;
    return {
        has_hscroll: d.scrollWidth > d.clientWidth,
        overflow_px: d.scrollWidth - d.clientWidth,
        body_hscroll: document.body.scrollWidth > document.body.clientWidth,
    };
}"""

JS_FIXED_WIDTH_ELEMENTS = """() => {
    const els = document.querySelectorAll('*');
    let count = 0;
    for (const el of els) {
        const s = getComputedStyle(el);
        if (s.width && !s.width.includes('%') && !s.width.includes('auto') &&
            !s.width.includes('vw') && !s.width.includes('min') && !s.width.includes('max') &&
            parseFloat(s.width) > window.innerWidth) {
            count++;
        }
    }
    return count;
}"""

JS_OVERFLOW_ELEMENTS = """() => {
    const els = document.querySelectorAll('*');
    let count = 0;
    for (const el of els) {
        const r = el.getBoundingClientRect();
        if (r.right > window.innerWidth + 5 || r.left < -5) count++;
    }
    return count;
}"""

JS_META_VIEWPORT = """() => {
    const meta = document.querySelector('meta[name="viewport"]');
    return meta ? meta.getAttribute('content') : null;
}"""

JS_TEXT_CLIPPING = """() => {
    const els = document.querySelectorAll('p, h1, h2, h3, h4, h5, h6, span, a, li, td, th, label, button');
    let count = 0;
    for (const el of els) {
        if (el.scrollWidth > el.clientWidth + 2 && el.textContent.trim().length > 0) count++;
    }
    return count;
}"""

JS_SMALL_FONT = """() => {
    const els = document.querySelectorAll('p, span, a, li, td, th, label, button, h1, h2, h3, h4, h5, h6');
    let count = 0;
    for (const el of els) {
        const s = getComputedStyle(el);
        const size = parseFloat(s.fontSize);
        if (size > 0 && size < 12) count++;
    }
    return count;
}"""

JS_LINE_HEIGHT_READABILITY = """() => {
    const els = document.querySelectorAll('p, li, td, th, span');
    let count = 0;
    for (const el of els) {
        const s = getComputedStyle(el);
        const lh = parseFloat(s.lineHeight);
        const fs = parseFloat(s.fontSize);
        if (fs > 0 && lh > 0) {
            const ratio = lh / fs;
            if (ratio < 1.2 || ratio > 2.5) count++;
        }
    }
    return count;
}"""

JS_HIDDEN_CONTENT = """() => {
    const els = document.querySelectorAll('h1, h2, h3, h4, h5, h6, p, a, button, label');
    let count = 0;
    for (const el of els) {
        const s = getComputedStyle(el);
        const r = el.getBoundingClientRect();
        if (r.width > 0 && r.height > 0) {
            if (s.overflow === 'hidden' || s.textOverflow === 'ellipsis') {
                if (el.scrollWidth > el.clientWidth + 2) count++;
            }
        }
    }
    return count;
}"""

JS_IMAGES_CHECK = """() => {
    const imgs = document.querySelectorAll('img');
    let no_max_width = 0;
    let broken_aspect = 0;
    let oversized = 0;
    for (const img of imgs) {
        const s = getComputedStyle(img);
        if (s.maxWidth !== '100%' && s.maxWidth !== '100vw') no_max_width++;
        if (img.naturalWidth > 0 && img.naturalHeight > 0) {
            const display_w = img.getBoundingClientRect().width;
            if (display_w > 0 && Math.abs(img.naturalWidth / img.naturalHeight - display_w / img.getBoundingClientRect().height) > 0.5) broken_aspect++;
        }
        if (img.getBoundingClientRect().width > window.innerWidth * 1.5) oversized++;
    }
    const iframes = document.querySelectorAll('iframe, video');
    let non_resp_media = 0;
    for (const m of iframes) {
        const s = getComputedStyle(m);
        if (s.maxWidth !== '100%' && s.maxWidth !== '100vw' && parseFloat(s.width) > window.innerWidth) non_resp_media++;
    }
    return { no_max_width, broken_aspect, oversized, non_resp_media, total: imgs.length };
}"""

JS_NAVIGATION_CHECK = """() => {
    const nav = document.querySelector('nav, [role="navigation"], .navbar, .nav, .menu, .mobile-menu, .hamburger');
    const hamburger = document.querySelector('.hamburger, .menu-toggle, .navbar-toggler, [aria-label*="menu"], [aria-label*="Menu"], .burger, button[class*="menu"], .mobile-nav-toggle');
    const nav_items = document.querySelectorAll('nav a, [role="navigation"] a, .navbar a, .nav a, .menu a');
    let overlapping = 0;
    const rects = [];
    for (const item of nav_items) {
        const r = item.getBoundingClientRect();
        if (r.width > 0 && r.height > 0) {
            for (const prev of rects) {
                if (!(r.right < prev.left || r.left > prev.right || r.bottom < prev.top || r.top > prev.bottom)) overlapping++;
            }
            rects.push(r);
        }
    }
    const sticky_headers = document.querySelectorAll('header, nav, .header, .navbar');
    let sticky_covers = 0;
    for (const h of sticky_headers) {
        const s = getComputedStyle(h);
        if (s.position === 'fixed' || s.position === 'sticky') {
            if (h.getBoundingClientRect().height > 60) sticky_covers++;
        }
    }
    return {
        has_nav: !!nav,
        has_hamburger: !!hamburger,
        nav_item_count: nav_items.length,
        overlapping_items: overlapping,
        sticky_covers_content: sticky_covers,
    };
}"""

JS_TOUCH_TARGETS = """() => {
    const clickables = document.querySelectorAll('a, button, [role="button"], input[type="submit"], input[type="checkbox"], input[type="radio"], select, label');
    let too_small = 0;
    let overlapping = 0;
    const rects = [];
    for (const el of clickables) {
        const r = el.getBoundingClientRect();
        if (r.width > 0 && r.height > 0) {
            if (r.width < 44 || r.height < 44) too_small++;
            for (const prev of rects) {
                if (!(r.right < prev.left || r.left > prev.right || r.bottom < prev.top || r.top > prev.bottom)) {
                    overlapping++;
                    break;
                }
            }
            rects.push(r);
        }
    }
    return { too_small_targets: too_small, overlapping_clickables: overlapping, total: clickables.length };
}"""

JS_FORMS_FIT = """() => {
    const inputs = document.querySelectorAll('input, select, textarea');
    let overflow = 0;
    for (const inp of inputs) {
        const r = inp.getBoundingClientRect();
        if (r.right > window.innerWidth + 2) overflow++;
    }
    return { overflow_inputs: overflow, total: inputs.length };
}"""

JS_FIXED_ELEMENTS = """() => {
    const els = document.querySelectorAll('*');
    const results = [];
    for (const el of els) {
        const s = getComputedStyle(el);
        if (s.position === 'fixed' || s.position === 'sticky') {
            const r = el.getBoundingClientRect();
            if (r.width > 50 && r.height > 50) {
                const tag = el.tagName.toLowerCase();
                const cls = el.className.toString().substring(0, 60);
                let type = 'other';
                if (tag === 'header' || tag === 'nav' || cls.includes('header') || cls.includes('nav')) type = 'navigation';
                else if (cls.includes('chat') || cls.includes('widget')) type = 'chat-widget';
                else if (cls.includes('cookie') || cls.includes('consent') || cls.includes('banner')) type = 'cookie-banner';
                else if (cls.includes('cta') || cls.includes('sticky') || cls.includes('float')) type = 'sticky-cta';
                else if (tag === 'button' || cls.includes('btn') || cls.includes('fab')) type = 'floating-button';
                results.push({ type, width: round(r.width), height: round(r.height), top: round(r.top), left: round(r.left) });
            }
        }
    }
    function round(v) { return Math.round(v); }
    return results;
}"""

JS_LAYOUT_COLUMNS = """() => {
    const containers = document.querySelectorAll('.container, .container-fluid, main, article, .content, .wrapper, [class*="grid"], [class*="row"]');
    let broken = 0;
    for (const c of containers) {
        const children = c.children;
        if (children.length >= 2) {
            const r = c.getBoundingClientRect();
            if (r.width > window.innerWidth + 10) broken++;
        }
    }
    return { broken_containers: broken };
}"""

JS_VISUAL_QUALITY = """() => {
    const body = document.body;
    const sections = document.querySelectorAll('section, div, article');
    let excessive_gap = 0;
    let broken_alignment = 0;
    for (const s of sections) {
        const r = s.getBoundingClientRect();
        const style = getComputedStyle(s);
        const mt = parseFloat(style.marginTop);
        const mb = parseFloat(style.marginBottom);
        if (mt > 100 || mb > 100) excessive_gap++;
    }
    return { excessive_gap };
}"""


# ── Main audit function ────────────────────────────────────────────────────

async def run_mobile_checks(pages: list[dict], max_pages: int = 10) -> dict:
    """Run mobile responsiveness checks on pages at 5 breakpoints.

    Returns dict: {
        page_url: {
            breakpoint_width: { check_results },
            ...
        },
        ...
    }
    """
    pages_to_check = [p for p in pages if p.get("status_code") and 200 <= p["status_code"] < 400][:max_pages]

    if not pages_to_check:
        print("[Mobile] No valid pages to check")
        return {}

    print(f"[Mobile] Launching browser for {len(pages_to_check)} pages × {len(BREAKPOINTS)} breakpoints...")
    results = {}

    async with async_playwright() as pw:
        browser = await pw.chromium.launch(headless=True)

        for page in pages_to_check:
            url = page["url"]
            page_id = page["id"]
            print(f"[Mobile] Checking: {url}")
            results[url] = {"page_id": page_id}

            for width in BREAKPOINTS:
                try:
                    ctx = await browser.new_context(
                        viewport={"width": width, "height": 812},
                        user_agent="Mozilla/5.0 (iPhone; CPU iPhone OS 16_0 like Mac OS X) AppleWebKit/605.1.15"
                    )
                    pg = await ctx.new_page()
                    try:
                        await pg.goto(url, wait_until="domcontentloaded", timeout=PAGE_GOTO_TIMEOUT)
                        await pg.wait_for_timeout(1000)

                        bp_results = {}

                        # 1. Viewport & Overflow (20%)
                        overflow = await pg.evaluate(JS_VIEWPORT_OVERFLOW)
                        fixed_width = await pg.evaluate(JS_FIXED_WIDTH_ELEMENTS)
                        overflow_els = await pg.evaluate(JS_OVERFLOW_ELEMENTS)
                        meta_vp = await pg.evaluate(JS_META_VIEWPORT)
                        bp_results["viewport_overflow"] = {
                            "has_hscroll": overflow["has_hscroll"],
                            "overflow_px": overflow["overflow_px"],
                            "body_hscroll": overflow["body_hscroll"],
                            "fixed_width_elements": fixed_width,
                            "overflow_elements": overflow_els,
                            "has_meta_viewport": meta_vp is not None,
                            "meta_viewport": meta_vp,
                        }

                        # 2. Responsive Layout (20%)
                        layout = await pg.evaluate(JS_LAYOUT_COLUMNS)
                        bp_results["responsive_layout"] = {
                            "broken_containers": layout["broken_containers"],
                        }

                        # 3. Typography & Content (15%)
                        text_clip = await pg.evaluate(JS_TEXT_CLIPPING)
                        small_font = await pg.evaluate(JS_SMALL_FONT)
                        line_height = await pg.evaluate(JS_LINE_HEIGHT_READABILITY)
                        hidden = await pg.evaluate(JS_HIDDEN_CONTENT)
                        bp_results["typography"] = {
                            "text_clipping": text_clip,
                            "small_font_elements": small_font,
                            "line_height_issues": line_height,
                            "hidden_content": hidden,
                        }

                        # 4. Images & Media (10%)
                        images = await pg.evaluate(JS_IMAGES_CHECK)
                        bp_results["images_media"] = images

                        # 5. Navigation (15%)
                        nav = await pg.evaluate(JS_NAVIGATION_CHECK)
                        bp_results["navigation"] = nav

                        # 6. Touch & Interaction (10%)
                        touch = await pg.evaluate(JS_TOUCH_TARGETS)
                        forms = await pg.evaluate(JS_FORMS_FIT)
                        bp_results["touch_interaction"] = {
                            "too_small_targets": touch["too_small_targets"],
                            "overlapping_clickables": touch["overlapping_clickables"],
                            "total_clickables": touch["total"],
                            "overflow_inputs": forms["overflow_inputs"],
                            "total_inputs": forms["total"],
                        }

                        # 7. Fixed/Sticky Elements (5%)
                        fixed = await pg.evaluate(JS_FIXED_ELEMENTS)
                        bp_results["fixed_elements"] = fixed

                        # 8. Visual Quality (5%)
                        visual = await pg.evaluate(JS_VISUAL_QUALITY)
                        bp_results["visual_quality"] = visual

                        results[url][width] = bp_results

                    except Exception as e:
                        print(f"  [Mobile] Error at {width}px: {e}")
                        results[url][width] = {"error": str(e)}
                    finally:
                        await pg.close()
                        await ctx.close()
                except Exception as e:
                    print(f"  [Mobile] Context error at {width}px: {e}")
                    results[url][width] = {"error": str(e)}

        await browser.close()

    print(f"[Mobile] Checks complete for {len(results)} pages")
    return results
