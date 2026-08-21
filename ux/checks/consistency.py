import re
from collections import Counter
from bs4 import BeautifulSoup
from ux.engine import _add
from app import db


def run(context):
    scan_id = context["scan_id"]
    pages = context["pages"]
    page_htmls = context["page_htmls"]
    edges = context["edges"]
    all_elements = context.get("all_elements", {})

    valid_pages = [
        p
        for p in pages
        if (not p["status_code"] or p["status_code"] < 400)
        and page_htmls.get(p["url"])
    ]

    if len(valid_pages) < 2:
        return

    _check_inconsistent_navigation(scan_id, valid_pages, page_htmls)
    _check_inconsistent_cta_naming(scan_id, valid_pages, all_elements)
    _check_inconsistent_footer(scan_id, valid_pages, page_htmls)
    _check_different_form_styles(scan_id, valid_pages, page_htmls)


def _extract_nav_links(soup):
    nav = soup.find("nav")
    if not nav:
        nav = soup.find(class_=lambda c: c and "nav" in c.lower())
    if not nav:
        nav = soup.find("ul", class_=lambda c: c and "menu" in c.lower())
    if not nav:
        return []
    links = []
    for a in nav.find_all("a", href=True):
        text = a.get_text(strip=True).lower()
        if text:
            links.append(text)
    return sorted(links)


def _check_inconsistent_navigation(scan_id, pages, page_htmls):
    nav_signatures = {}
    for p in pages:
        soup = page_htmls[p["url"]]
        links = _extract_nav_links(soup)
        if links:
            nav_signatures[p["url"]] = links

    if len(nav_signatures) < 2:
        return

    link_counts = Counter(len(v) for v in nav_signatures.values())
    most_common_count = link_counts.most_common(1)[0][0]

    for url, links in nav_signatures.items():
        if len(links) != most_common_count:
            page = next(p for p in pages if p["url"] == url)
            _add(scan_id, "inconsistent_navigation", "warning",
                 f"Inconsistent navigation ({len(links)} links vs {most_common_count} typical): {url}",
                 page_id=page["id"])


def _check_inconsistent_cta_naming(scan_id, pages, all_elements):
    cta_patterns = {
        "contact": ["contact us", "get in touch", "reach out", "contact", "email us", "talk to us"],
        "buy": ["buy now", "purchase", "add to cart", "buy", "order now", "shop now"],
        "signup": ["sign up", "register", "create account", "join", "get started free", "start free"],
        "learn": ["learn more", "read more", "find out more", "discover", "see more", "view more"],
        "download": ["download", "get the app", "install", "get it now"],
        "subscribe": ["subscribe", "join newsletter", "sign up for updates", "get updates"],
        "request": ["request", "request a demo", "request quote", "get a quote", "request info", "request pricing"],
        "call": ["call us", "call now", "give us a call", "phone us"],
    }

    page_ctas = {}
    for p in pages:
        elements = all_elements.get(p["url"], [])
        ctas = []
        for el in elements:
            if el.get("role") in ("button", "link"):
                name = (el.get("accessible_name") or "").lower().strip()
                if name:
                    ctas.append(name)
        if ctas:
            page_ctas[p["url"]] = ctas

    if len(page_ctas) < 2:
        return

    category_usage = {}
    for url, ctas in page_ctas.items():
        page_categories = set()
        for cta in ctas:
            for category, variants in cta_patterns.items():
                if any(variant in cta for variant in variants):
                    page_categories.add(category)
        category_usage[url] = page_categories

    all_categories = set()
    for cats in category_usage.values():
        all_categories.update(cats)

    for category in all_categories:
        category_names = {}
        for url, ctas in page_ctas.items():
            for cta in ctas:
                for pattern_category, variants in cta_patterns.items():
                    if pattern_category == category and any(v in cta for v in variants):
                        if url not in category_names:
                            category_names[url] = set()
                        category_names[url].add(cta)

        if len(category_names) < 2:
            continue

        all_texts = set()
        for texts in category_names.values():
            all_texts.update(texts)

        if len(all_texts) > 1:
            sample = ", ".join(sorted(all_texts)[:3])
            page = next(p for p in pages if p["url"] == next(iter(category_names)))
            _add(scan_id, "inconsistent_cta_naming", "warning",
                 f"Inconsistent CTA naming for '{category}' ({len(all_texts)} variants): {sample}",
                 page_id=page["id"])


def _extract_footer_links(soup):
    footer = soup.find("footer")
    if not footer:
        footer = soup.find(class_=lambda c: c and "footer" in c.lower())
    if not footer:
        return []
    links = []
    for a in footer.find_all("a", href=True):
        text = a.get_text(strip=True).lower()
        if text:
            links.append(text)
    return sorted(links)


def _check_inconsistent_footer(scan_id, pages, page_htmls):
    footer_data = {}
    for p in pages:
        soup = page_htmls[p["url"]]
        links = _extract_footer_links(soup)
        footer_data[p["url"]] = links

    with_footer = {url: links for url, links in footer_data.items() if links}
    without_footer = [url for url, links in footer_data.items() if not links]

    if not with_footer:
        return

    link_counts = Counter(len(v) for v in with_footer.values())
    most_common_count = link_counts.most_common(1)[0][0]

    for url, links in with_footer.items():
        if abs(len(links) - most_common_count) > 3:
            page = next(p for p in pages if p["url"] == url)
            _add(scan_id, "inconsistent_footer", "info",
                 f"Inconsistent footer ({len(links)} links vs {most_common_count} typical): {url}",
                 page_id=page["id"])


def _extract_form_signature(soup):
    forms = soup.find_all("form")
    signatures = []
    for form in forms:
        inputs = []
        for inp in form.find_all(["input", "textarea", "select"]):
            input_type = inp.get("type", "text")
            name = inp.get("name", "")
            inputs.append(f"{input_type}:{name}")
        buttons = []
        for btn in form.find_all("button"):
            buttons.append(btn.get_text(strip=True).lower())
        sig = f"inputs={sorted(inputs)}|buttons={sorted(buttons)}"
        signatures.append(sig)
    return sorted(signatures)


def _check_different_form_styles(scan_id, pages, page_htmls):
    form_sigs = {}
    for p in pages:
        soup = page_htmls[p["url"]]
        sigs = _extract_form_signature(soup)
        if sigs:
            form_sigs[p["url"]] = sigs

    if len(form_sigs) < 2:
        return

    sig_sets = {}
    for url, sigs in form_sigs.items():
        sig_key = frozenset(sigs)
        if sig_key not in sig_sets:
            sig_sets[sig_key] = []
        sig_sets[sig_key].append(url)

    if len(sig_sets) > 1:
        largest_group_urls = max(sig_sets.values(), key=len)
        outlier_urls = [
            url for urls in sig_sets.values() for url in urls
            if url not in largest_group_urls
        ]
        for outlier_url in outlier_urls[:3]:
            page = next(p for p in pages if p["url"] == outlier_url)
            _add(scan_id, "different_form_styles", "info",
                 f"Different form structure vs other pages: {outlier_url}",
                 page_id=page["id"])
