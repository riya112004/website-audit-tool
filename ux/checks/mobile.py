from app import db
from ux.engine import _add


def run(context):
    scan_id = context["scan_id"]
    pages = context["pages"]
    ux_data = context["ux_data"]

    for p in pages:
        url = p["url"]
        page_ux = ux_data.get(url, {})
        mobile_data = page_ux.get("mobile", {})

        if mobile_data.get("has_horizontal_overflow"):
            _add(scan_id, "mobile_horizontal_overflow", "warning",
                 f"Horizontal overflow detected on mobile: {url}",
                 page_id=p["id"])

        if mobile_data.get("small_text_found"):
            _add(scan_id, "mobile_small_text", "warning",
                 f"Small text detected on mobile (<14px): {url}",
                 page_id=p["id"])

        if mobile_data.get("tiny_touch_targets"):
            count = mobile_data["tiny_touch_targets"]
            _add(scan_id, "mobile_tiny_touch_targets", "warning",
                 f"{count} touch targets smaller than 44x44px: {url}",
                 page_id=p["id"])

        if mobile_data.get("content_outside_viewport"):
            _add(scan_id, "mobile_content_outside_viewport", "warning",
                 f"Content outside mobile viewport: {url}",
                 page_id=p["id"])

        if mobile_data.get("fixed_element_blocking"):
            _add(scan_id, "mobile_fixed_element_blocking", "info",
                 f"Fixed element blocks content on mobile: {url}",
                 page_id=p["id"])
