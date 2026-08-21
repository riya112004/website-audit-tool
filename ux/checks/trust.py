from app import db
from ux.engine import _add


def run(context):
    scan_id = context["scan_id"]
    pages = context["pages"]
    page_htmls = context["page_htmls"]
    ux_data = context.get("ux_data", {})

    _check_missing_contact_info(scan_id, pages, page_htmls)
    _check_no_cta_detected(scan_id, pages, page_htmls)
    _check_no_contact_form(scan_id, pages, page_htmls)
    _check_missing_privacy_links(scan_id, pages, page_htmls)
    _check_missing_social_proof(scan_id, pages, page_htmls)


def _check_missing_contact_info(scan_id, pages, page_htmls):
    contact_keywords = ["contact", "phone", "email", "tel:", "mailto:", "address"]
    for p in pages:
        soup = page_htmls.get(p["url"])
        if not soup:
            continue
        body_text = soup.get_text(strip=True).lower()
        has_contact = any(kw in body_text for kw in contact_keywords)
        if not has_contact:
            _add(scan_id, "missing_contact_info", "info",
                 f"No contact information found: {p['url']}",
                 page_id=p["id"])


def _check_no_cta_detected(scan_id, pages, page_htmls):
    cta_keywords = ["buy", "sign up", "register", "subscribe", "get started",
                    "contact us", "request", "download", "try", "start", "order"]
    for p in pages:
        soup = page_htmls.get(p["url"])
        if not soup:
            continue
        buttons = soup.find_all("button") + soup.find_all("a", class_=lambda c: c and "btn" in c)
        has_cta = False
        for btn in buttons:
            text = btn.get_text(strip=True).lower()
            if any(kw in text for kw in cta_keywords):
                has_cta = True
                break
        if not has_cta:
            _add(scan_id, "no_cta_detected", "info",
                 f"No clear call-to-action found: {p['url']}",
                 page_id=p["id"])


def _check_no_contact_form(scan_id, pages, page_htmls):
    for p in pages:
        url = p["url"].lower()
        soup = page_htmls.get(p["url"])
        if not soup:
            continue
        is_contact_page = any(kw in url for kw in ["contact", "support", "help"])
        if is_contact_page:
            forms = soup.find_all("form")
            has_contact_form = False
            for form in forms:
                text = form.get_text(strip=True).lower()
                inputs = [i.get("name", "").lower() for i in form.find_all(["input", "textarea"])]
                if any(kw in text or kw in " ".join(inputs) for kw in ["message", "subject", "inquiry", "comment"]):
                    has_contact_form = True
                    break
            if not has_contact_form:
                _add(scan_id, "no_contact_form", "warning",
                     f"Contact page has no contact form: {p['url']}",
                     page_id=p["id"])


def _check_missing_privacy_links(scan_id, pages, page_htmls):
    privacy_keywords = ["privacy", "terms", "cookie", "legal"]
    for p in pages:
        soup = page_htmls.get(p["url"])
        if not soup:
            continue
        footer = soup.find("footer")
        if not footer:
            continue
        footer_text = footer.get_text(strip=True).lower()
        footer_links = [a.get_text(strip=True).lower() for a in footer.find_all("a")]
        all_text = footer_text + " " + " ".join(footer_links)
        has_privacy = any(kw in all_text for kw in privacy_keywords)
        if not has_privacy:
            _add(scan_id, "missing_privacy_links", "info",
                 f"No privacy/terms links in footer: {p['url']}",
                 page_id=p["id"])


def _check_missing_social_proof(scan_id, pages, page_htmls):
    proof_keywords = ["testimonial", "review", "rating", "star", "trust",
                      "certified", "verified", "award", "customer", "client"]
    for p in pages:
        soup = page_htmls.get(p["url"])
        if not soup:
            continue
        body_text = soup.get_text(strip=True).lower()
        has_proof = any(kw in body_text for kw in proof_keywords)
        if not has_proof:
            _add(scan_id, "missing_social_proof", "info",
                 f"No social proof elements found: {p['url']}",
                 page_id=p["id"])
