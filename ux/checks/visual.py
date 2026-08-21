from app import db
from ux.engine import _add


def run(context):
    scan_id = context["scan_id"]
    pages = context["pages"]
    page_htmls = context["page_htmls"]

    _check_images_no_dimensions(scan_id, pages, page_htmls)
    _check_empty_sections(scan_id, pages, page_htmls)


def _check_images_no_dimensions(scan_id, pages, page_htmls):
    for p in pages:
        soup = page_htmls.get(p["url"])
        if not soup:
            continue
        imgs = soup.find_all("img")
        missing = 0
        for img in imgs:
            if not img.get("width") and not img.get("height"):
                css_style = img.get("style", "")
                if "width" not in css_style and "height" not in css_style:
                    missing += 1
        if missing > 0:
            _add(scan_id, "images_no_dimensions", "info",
                 f"{missing}/{len(imgs)} images missing explicit dimensions: {p['url']}",
                 page_id=p["id"])


def _check_empty_sections(scan_id, pages, page_htmls):
    for p in pages:
        soup = page_htmls.get(p["url"])
        if not soup:
            continue
        for section in soup.find_all("section"):
            text = section.get_text(strip=True)
            has_img = section.find("img")
            has_video = section.find("video")
            has_iframe = section.find("iframe")
            if not text and not has_img and not has_video and not has_iframe:
                _add(scan_id, "empty_sections", "info",
                     f"Empty <section> found: {p['url']}",
                     page_id=p["id"])
                break
