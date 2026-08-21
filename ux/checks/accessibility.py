from app import db
from ux.engine import _add


def run(context):
    scan_id = context["scan_id"]
    pages = context["pages"]
    all_elements = context["all_elements"]
    page_htmls = context["page_htmls"]

    _check_focusable_no_outline(scan_id, pages, page_htmls)
    _check_poor_heading_hierarchy(scan_id, pages, page_htmls)
    _check_missing_skip_nav(scan_id, pages, page_htmls)
    _check_landmark_structure(scan_id, pages, page_htmls)


def _check_focusable_no_outline(scan_id, pages, page_htmls):
    for p in pages:
        soup = page_htmls.get(p["url"])
        if not soup:
            continue
        focusable = soup.find_all(["a", "button", "input", "select", "textarea"])
        for elem in focusable:
            style = elem.get("style", "")
            if "outline: none" in style or "outline:none" in style:
                _add(scan_id, "focusable_no_outline", "warning",
                     f"Focusable element has outline removed: {p['url']}",
                     page_id=p["id"])
                break


def _check_poor_heading_hierarchy(scan_id, pages, page_htmls):
    for p in pages:
        soup = page_htmls.get(p["url"])
        if not soup:
            continue
        headings = soup.find_all(["h1", "h2", "h3", "h4", "h5", "h6"])
        prev_level = 0
        skip_found = False
        for h in headings:
            level = int(h.name[1])
            if prev_level > 0 and level > prev_level + 1:
                skip_found = True
                break
            prev_level = level
        if skip_found:
            _add(scan_id, "poor_heading_hierarchy_a11y", "warning",
                 f"Heading levels skip — poor hierarchy: {p['url']}",
                 page_id=p["id"])


def _check_missing_skip_nav(scan_id, pages, page_htmls):
    for p in pages:
        soup = page_htmls.get(p["url"])
        if not soup:
            continue
        nav = soup.find("nav")
        if not nav:
            continue
        skip_link = soup.find("a", href="#main")
        if not skip_link:
            skip_link = soup.find("a", href="#content")
        if not skip_link:
            _add(scan_id, "missing_skip_nav", "info",
                 f"No skip navigation link found: {p['url']}",
                 page_id=p["id"])


def _check_landmark_structure(scan_id, pages, page_htmls):
    for p in pages:
        soup = page_htmls.get(p["url"])
        if not soup:
            continue
        has_header = soup.find("header") or soup.find(attrs={"role": "banner"})
        has_nav = soup.find("nav") or soup.find(attrs={"role": "navigation"})
        has_main = soup.find("main") or soup.find(attrs={"role": "main"})
        has_footer = soup.find("footer") or soup.find(attrs={"role": "contentinfo"})
        missing = []
        if not has_main:
            missing.append("main")
        if not has_nav and not has_header:
            missing.append("header/nav")
        if missing:
            _add(scan_id, "landmark_structure_missing", "info",
                 f"Missing landmarks ({', '.join(missing)}): {p['url']}",
                 page_id=p["id"])
