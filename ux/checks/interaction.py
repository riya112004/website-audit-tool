from bs4 import BeautifulSoup

from ux.engine import _add, _load_html, _is_crawlable
from app import db


def _get_html(context, page):
    url = page["url"]
    if url in context["page_htmls"]:
        return context["page_htmls"][url]
    soup = _load_html(page.get("raw_html_path"))
    if soup:
        context["page_htmls"][url] = soup
    return soup


def _get_click_target_text(tag):
    text = tag.get_text(strip=True)
    if text:
        return text
    if tag.get("aria-label"):
        return tag["aria-label"]
    if tag.get("title"):
        return tag["title"]
    if tag.get("alt"):
        return tag["alt"]
    for img in tag.find_all("img"):
        if img.get("alt"):
            return img["alt"]
    return ""


def run(context):
    scan_id = context["scan_id"]
    pages = context["pages"]
    all_elements = context["all_elements"]
    ux_data = context["ux_data"]

    unlabeled_buttons(context, pages)
    tiny_click_targets(context, pages, ux_data)
    disabled_visible_buttons(context, pages)
    missing_accessible_names(context, pages, all_elements)
    horizontal_scroll(context, pages, ux_data)
    dead_links(context, pages)


def unlabeled_buttons(context, pages):
    scan_id = context["scan_id"]
    for page in pages:
        soup = _get_html(context, page)
        if not soup:
            continue
        count = 0
        for btn in soup.find_all("button"):
            if _get_click_target_text(btn):
                continue
            count += 1
        for el in soup.find_all(attrs={"role": "button"}):
            if el.name == "button":
                continue
            if _get_click_target_text(el):
                continue
            count += 1
        if count > 0:
            _add(
                scan_id,
                "unlabeled_buttons",
                "high",
                f"Unlabeled buttons ({count} violations): {page['url']}",
                page_id=page["id"],
            )


def tiny_click_targets(context, pages, ux_data):
    scan_id = context["scan_id"]
    if not ux_data:
        return
    for page in pages:
        page_data = ux_data.get(page["url"], {})
        bounding_boxes = page_data.get("bounding_boxes", [])
        if not bounding_boxes:
            continue
        count = 0
        for box in bounding_boxes:
            width = box.get("width", 0)
            height = box.get("height", 0)
            tag = box.get("tag", "")
            if tag.lower() in ("a", "button", "input", "select", "textarea", "label"):
                if (width > 0 and width < 24) or (height > 0 and height < 24):
                    count += 1
        if count > 0:
            _add(
                scan_id,
                "tiny_click_targets",
                "high",
                f"Tiny click targets ({count} violations, min 24px): {page['url']}",
                page_id=page["id"],
            )


def disabled_visible_buttons(context, pages):
    scan_id = context["scan_id"]
    for page in pages:
        soup = _get_html(context, page)
        if not soup:
            continue
        count = 0
        for btn in soup.find_all(["button", "input"]):
            if btn.has_attr("disabled"):
                if btn.get("style"):
                    style = btn["style"].lower()
                    if "pointer" in style or "cursor" in style:
                        count += 1
                        continue
                classes = " ".join(btn.get("class", [])).lower()
                if any(kw in classes for kw in ("active", "enabled", "clickable")):
                    count += 1
        for el in soup.find_all(attrs={"aria-disabled": "false"}):
            count += 1
        if count > 0:
            _add(
                scan_id,
                "disabled_visible_buttons",
                "warning",
                f"Disabled elements styled as clickable ({count} violations): {page['url']}",
                page_id=page["id"],
            )


def missing_accessible_names(context, pages, all_elements):
    scan_id = context["scan_id"]
    interactive_roles = {"button", "link", "tab", "menuitem", "option", "checkbox", "radio", "switch"}
    for page in pages:
        elements = all_elements.get(page["url"], [])
        count = 0
        for el in elements:
            role = (el.get("role") or "").lower()
            if role not in interactive_roles:
                continue
            name = (el.get("accessible_name") or "").strip()
            if not name:
                count += 1
        if count > 0:
            _add(
                scan_id,
                "missing_accessible_names",
                "high",
                f"Interactive elements without accessible names ({count} violations): {page['url']}",
                page_id=page["id"],
            )


def horizontal_scroll(context, pages, ux_data):
    scan_id = context["scan_id"]
    if not ux_data:
        for page in pages:
            soup = _get_html(context, page)
            if not soup:
                continue
            found = False
            for tag in soup.find_all(style=True):
                style = tag["style"].lower()
                if "overflow-x" in style and ("scroll" in style or "auto" in style):
                    _add(
                        scan_id,
                        "horizontal_scroll",
                        "warning",
                        f"Potential horizontal scroll (overflow-x): {page['url']}",
                        page_id=page["id"],
                    )
                    found = True
                    break
        return
    for page in pages:
        page_data = ux_data.get(page["url"], {})
        viewport = page_data.get("viewport_width", 0)
        body_width = page_data.get("body_width", 0)
        if viewport > 0 and body_width > 0 and body_width > viewport * 1.05:
            _add(
                scan_id,
                "horizontal_scroll",
                "warning",
                f"Horizontal scroll detected (body {body_width}px > viewport {viewport}px): {page['url']}",
                page_id=page["id"],
            )


def dead_links(context, pages):
    scan_id = context["scan_id"]
    for page in pages:
        soup = _get_html(context, page)
        if not soup:
            continue
        page_ids = set()
        for tag in soup.find_all(id=True):
            page_ids.add(tag["id"].lower())
        count = 0
        for a in soup.find_all("a", href=True):
            href = a["href"].strip()
            if not href.startswith("#") or href == "#":
                continue
            anchor = href[1:].strip()
            if anchor and anchor.lower() not in page_ids:
                count += 1
        if count > 0:
            _add(
                scan_id,
                "dead_links",
                "high",
                f"Broken anchor links ({count} violations): {page['url']}",
                page_id=page["id"],
            )
