import os
from bs4 import BeautifulSoup
from ux.engine import _add
from app import db


def run(context):
    scan_id = context["scan_id"]
    pages = context["pages"]
    page_htmls = context["page_htmls"]
    ux_data = context.get("ux_data", {})

    for p in pages:
        if p["status_code"] and p["status_code"] >= 400:
            continue
        soup = page_htmls.get(p["url"])
        if not soup:
            continue

        _check_slow_initial_render(scan_id, p)
        _check_missing_loading_indicators(scan_id, p, soup)
        _check_large_images(scan_id, p, soup)


def _check_slow_initial_render(scan_id, page):
    raw_path = page.get("raw_html_path")
    if not raw_path or not os.path.isfile(raw_path):
        return
    size = os.path.getsize(raw_path)
    if size > 512000:
        size_kb = round(size / 1024)
        _add(scan_id, "slow_initial_render", "warning",
             f"Slow initial render - page payload is {size_kb}KB: {page['url']}",
             page_id=page["id"])


def _check_missing_loading_indicators(scan_id, page, soup):
    count = 0
    for form in soup.find_all("form"):
        has_submit = form.find(
            ["button"],
            attrs={"type": "submit"},
        ) or form.find(
            "input", attrs={"type": "submit"}
        )
        if not has_submit:
            continue
        has_onsubmit = form.get("onsubmit")
        if not has_onsubmit:
            continue
        outer_html = str(form)
        loading_classes = [
            "loading",
            "spinner",
            "progress",
            "btn-loading",
            "is-loading",
            "disabled-after",
        ]
        has_indicator = False
        for cls in loading_classes:
            if cls in outer_html.lower():
                has_indicator = True
                break
        if not has_indicator:
            has_loading_js = (
                "loading" in outer_html.lower()
                or "spinner" in outer_html.lower()
                or "disable" in outer_html.lower()
            )
            if not has_loading_js:
                count += 1
    if count > 0:
        _add(scan_id, "missing_loading_indicators", "warning",
             f"Missing loading indicators ({count} violations): {page['url']}",
             page_id=page["id"])


def _check_large_images(scan_id, page, soup):
    count = 0
    for img in soup.find_all("img"):
        src = img.get("src", "")
        if not src:
            count += 1
            continue
        large_extensions = [".png", ".bmp", ".tiff", ".tif", ".webp"]
        src_lower = src.lower().split("?")[0]
        has_large_ext = any(src_lower.endswith(ext) for ext in large_extensions)
        has_lazy = img.get("loading") == "lazy"
        if has_large_ext and not has_lazy:
            count += 1
        elif not has_lazy and (src_lower.endswith(".jpg") or src_lower.endswith(".jpeg")):
            count += 1
    if count > 0:
        _add(scan_id, "large_images", "warning",
             f"Images missing lazy loading ({count} violations): {page['url']}",
             page_id=page["id"])
