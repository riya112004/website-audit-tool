from urllib.parse import urlparse

from app import db
from ux.engine import _add, _is_crawlable


def run(context):
    scan_id = context["scan_id"]
    pages = context["pages"]
    edges = context["edges"]
    origin = context["origin"]

    _check_broken_internal_links(scan_id, pages, origin)
    _check_empty_href_links(scan_id, pages, page_htmls=context["page_htmls"])
    _check_hash_only_links(scan_id, pages, page_htmls=context["page_htmls"])
    _check_js_void_links(scan_id, pages, page_htmls=context["page_htmls"])
    _check_excessive_nav_items(scan_id, pages, page_htmls=context["page_htmls"])
    _check_duplicate_nav_links(scan_id, pages, page_htmls=context["page_htmls"])
    _check_unclear_anchor_text(scan_id, pages, page_htmls=context["page_htmls"])
    _check_orphan_pages(scan_id, pages, edges)


def _check_broken_internal_links(scan_id, pages, origin):
    page_urls = {p["normalized_url"] for p in pages}
    for p in pages:
        status = p.get("status_code")
        if not status or status < 200 or status >= 300:
            parsed = urlparse(p["url"])
            if origin and parsed.netloc in origin:
                _add(scan_id, "broken_internal_links", "warning",
                     f"Broken internal link (HTTP {status or 'N/A'}): {p['url']}",
                     page_id=p["id"])


def _check_empty_href_links(scan_id, pages, page_htmls):
    for p in pages:
        soup = page_htmls.get(p["url"])
        if not soup:
            continue
        for a in soup.find_all("a"):
            href = a.get("href", "")
            if href == "":
                _add(scan_id, "empty_href_links", "warning",
                     f"Link with empty href: {p['url']}",
                     page_id=p["id"])
                break


def _check_hash_only_links(scan_id, pages, page_htmls):
    for p in pages:
        soup = page_htmls.get(p["url"])
        if not soup:
            continue
        count = 0
        for a in soup.find_all("a"):
            href = a.get("href", "")
            if href.startswith("#") and len(href) > 1:
                count += 1
        if count > 10:
            _add(scan_id, "hash_only_links", "info",
                 f"{count} hash-only links found: {p['url']}",
                 page_id=p["id"])


def _check_js_void_links(scan_id, pages, page_htmls):
    for p in pages:
        soup = page_htmls.get(p["url"])
        if not soup:
            continue
        count = 0
        for a in soup.find_all("a"):
            href = a.get("href", "")
            if href.startswith("javascript:void"):
                count += 1
        if count > 0:
            _add(scan_id, "js_void_links", "warning",
                 f"{count} 'javascript:void(0)' links found: {p['url']}",
                 page_id=p["id"])


def _check_excessive_nav_items(scan_id, pages, page_htmls):
    for p in pages:
        soup = page_htmls.get(p["url"])
        if not soup:
            continue
        navs = soup.find_all("nav")
        for nav in navs:
            items = nav.find_all("a")
            if len(items) > 10:
                _add(scan_id, "excessive_nav_items", "warning",
                     f"Navigation has {len(items)} items — consider reducing: {p['url']}",
                     page_id=p["id"])


def _check_duplicate_nav_links(scan_id, pages, page_htmls):
    for p in pages:
        soup = page_htmls.get(p["url"])
        if not soup:
            continue
        navs = soup.find_all("nav")
        for nav in navs:
            hrefs = [a.get("href", "") for a in nav.find_all("a")]
            if len(hrefs) != len(set(hrefs)):
                _add(scan_id, "duplicate_nav_links", "info",
                     f"Duplicate links in navigation: {p['url']}",
                     page_id=p["id"])


def _check_unclear_anchor_text(scan_id, pages, page_htmls):
    vague = {"click here", "read more", "here", "learn more", "link", "more"}
    for p in pages:
        soup = page_htmls.get(p["url"])
        if not soup:
            continue
        vague_count = 0
        for a in soup.find_all("a"):
            text = a.get_text(strip=True).lower()
            if text in vague:
                vague_count += 1
        if vague_count > 0:
            _add(scan_id, "unclear_anchor_text", "info",
                 f"{vague_count} links with vague anchor text: {p['url']}",
                 page_id=p["id"])


def _check_orphan_pages(scan_id, pages, edges):
    linked_urls = set()
    for e in edges:
        linked_urls.add(e.get("to_url", ""))
    for p in pages:
        norm = p.get("normalized_url", "")
        if norm and norm not in linked_urls and p.get("depth", 0) > 0:
            _add(scan_id, "orphan_pages", "warning",
                 f"Orphan page — no internal links point to it: {p['url']}",
                 page_id=p["id"])
