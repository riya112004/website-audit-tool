import os
from bs4 import BeautifulSoup
from ux.engine import _add
from app import db


def run(context):
    scan_id = context["scan_id"]
    pages = context["pages"]
    page_htmls = context["page_htmls"]
    ux_data = context.get("ux_data", {})
    all_elements = context.get("all_elements", {})
    edges = context["edges"]
    origin = context["origin"]

    for p in pages:
        if p["status_code"] and p["status_code"] >= 400:
            continue
        soup = page_htmls.get(p["url"])
        if not soup:
            continue

        _check_console_errors(scan_id, p, ux_data)
        _check_broken_images(scan_id, p, soup)
        _check_missing_error_messages(scan_id, p, soup)
        _check_missing_success_messages(scan_id, p, soup)


def _check_console_errors(scan_id, page, ux_data):
    data = ux_data.get(page["url"], {})
    errors = data.get("console_errors", [])
    if errors:
        _add(scan_id, "console_errors", "high",
             f"Console errors detected ({len(errors)} violations): {page['url']}",
             page_id=page["id"])


def _check_broken_images(scan_id, page, soup):
    count = 0
    for img in soup.find_all("img"):
        src = img.get("src", "")
        if not src:
            count += 1
            continue
        src_lower = src.strip().lower()
        if src_lower in ("", "about:blank"):
            count += 1
        elif "/404" in src_lower or "/error" in src_lower:
            count += 1
        elif src_lower.endswith("/null") or src_lower.endswith("/undefined"):
            count += 1
        elif src_lower == "data:" or src_lower.startswith("data:image/svg+xml,"):
            alt = img.get("alt", "")
            width = img.get("width", "")
            if not alt and not width:
                count += 1
    if count > 0:
        _add(scan_id, "broken_images", "warning",
             f"Broken or empty images ({count} violations): {page['url']}",
             page_id=page["id"])


def _check_missing_error_messages(scan_id, page, soup):
    forms = soup.find_all("form")
    if not forms:
        return
    count = 0
    for form in forms:
        form_html = str(form).lower()
        has_aria_live = "aria-live" in form_html
        has_error_class = (
            "error" in form_html
            or "invalid" in form_html
            or "has-error" in form_html
            or "form-error" in form_html
        )
        has_validation = (
            "required" in form_html
            or "pattern=" in form_html
            or "aria-invalid" in form_html
        )
        has_error_container = (
            form.find(class_=lambda c: c and "error" in c.lower())
            or form.find(class_=lambda c: c and "invalid" in c.lower())
            or form.find(class_=lambda c: c and "validation" in c.lower())
        )
        if not (has_aria_live or has_error_class or has_validation or has_error_container):
            count += 1
    if count > 0:
        _add(scan_id, "missing_error_messages", "warning",
             f"Forms without error messages ({count} violations): {page['url']}",
             page_id=page["id"])


def _check_missing_success_messages(scan_id, page, soup):
    forms = soup.find_all("form")
    if not forms:
        return
    count = 0
    for form in forms:
        form_html = str(form).lower()
        has_success_class = (
            "success" in form_html
            or "thank" in form_html
            or "confirmation" in form_html
            or "complete" in form_html
        )
        has_aria_live = "aria-live" in form_html
        sibling = form.find_next_sibling()
        sibling_html = str(sibling).lower() if sibling else ""
        has_sibling_success = (
            "success" in sibling_html
            or "thank" in sibling_html
            or "confirmation" in sibling_html
        )
        if not (has_success_class or has_aria_live or has_sibling_success):
            count += 1
    if count > 0:
        _add(scan_id, "missing_success_messages", "info",
             f"Forms without success indicators ({count} violations): {page['url']}",
             page_id=page["id"])
