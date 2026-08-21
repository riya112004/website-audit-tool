import re
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

        _check_extremely_long_paragraphs(scan_id, p, soup)
        _check_very_small_text(scan_id, p, soup)
        _check_excessive_uppercase(scan_id, p, soup)
        _check_missing_headings(scan_id, p, soup)
        _check_empty_sections(scan_id, p, soup)
        _check_placeholder_text(scan_id, p, soup)


def _check_extremely_long_paragraphs(scan_id, page, soup):
    count = 0
    for p_tag in soup.find_all("p"):
        text = p_tag.get_text(strip=True)
        if len(text) > 500:
            count += 1
    if count > 0:
        _add(scan_id, "extremely_long_paragraphs", "critical",
             f"Extremely long paragraphs ({count} violations): {page['url']}",
             page_id=page["id"])


def _check_very_small_text(scan_id, page, soup):
    count = 0
    for tag in soup.find_all(True):
        style = tag.get("style", "")
        if not style:
            continue
        matches = re.findall(r"font-size\s*:\s*([\d.]+)(px|pt|em|rem)", style)
        for value, unit in matches:
            try:
                val = float(value)
            except ValueError:
                continue
            if unit == "px" and val < 10:
                count += 1
            elif unit == "pt" and val < 7.5:
                count += 1
            elif unit == "em" and val < 0.625:
                count += 1
            elif unit == "rem" and val < 0.625:
                count += 1
    if count > 0:
        _add(scan_id, "very_small_text", "high",
             f"Very small text ({count} violations): {page['url']}",
             page_id=page["id"])


def _check_excessive_uppercase(scan_id, page, soup):
    count = 0
    for text_node in soup.find_all(string=True):
        text = text_node.strip()
        if len(text) <= 20:
            continue
        alpha_chars = [c for c in text if c.isalpha()]
        if not alpha_chars:
            continue
        uppercase_ratio = sum(1 for c in alpha_chars if c.isupper()) / len(alpha_chars)
        if uppercase_ratio > 0.8:
            count += 1
    if count > 0:
        _add(scan_id, "excessive_uppercase", "warning",
             f"Excessive uppercase text ({count} violations): {page['url']}",
             page_id=page["id"])


def _check_missing_headings(scan_id, page, soup):
    headings = soup.find_all(re.compile(r"^h[1-6]$"))
    if not headings:
        _add(scan_id, "missing_headings", "warning",
             f"Missing headings - no h1-h6 tags found: {page['url']}",
             page_id=page["id"])


def _check_empty_sections(scan_id, page, soup):
    count = 0
    for section in soup.find_all(["section", "article"]):
        text = section.get_text(strip=True)
        if not text:
            count += 1
    for div in soup.find_all("div", class_="content"):
        text = div.get_text(strip=True)
        if not text:
            count += 1
    if count > 0:
        _add(scan_id, "empty_sections", "warning",
             f"Empty content sections ({count} violations): {page['url']}",
             page_id=page["id"])


def _check_placeholder_text(scan_id, page, soup):
    page_text = soup.get_text(strip=True).lower()
    placeholders = ["lorem ipsum", "coming soon", "under construction", "todo"]
    found = [p for p in placeholders if p in page_text]
    if found:
        _add(scan_id, "placeholder_text", "high",
             f"Placeholder text detected ({len(found)} violations): {page['url']}",
             page_id=page["id"])
