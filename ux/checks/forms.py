from app import db
from ux.engine import _add, _is_crawlable


def run(context):
    scan_id = context["scan_id"]
    pages = context["pages"]
    page_htmls = context["page_htmls"]

    _check_inputs_without_labels(scan_id, pages, page_htmls)
    _check_missing_placeholders(scan_id, pages, page_htmls)
    _check_incorrect_input_types(scan_id, pages, page_htmls)
    _check_required_fields_no_indicator(scan_id, pages, page_htmls)
    _check_no_submit_action(scan_id, pages, page_htmls)
    _check_submit_no_text(scan_id, pages, page_htmls)
    _check_very_long_forms(scan_id, pages, page_htmls)


def _check_inputs_without_labels(scan_id, pages, page_htmls):
    for p in pages:
        soup = page_htmls.get(p["url"])
        if not soup:
            continue
        inputs = soup.find_all(["input", "select", "textarea"])
        for inp in inputs:
            if inp.get("type") in ("hidden", "submit", "button", "reset"):
                continue
            inp_id = inp.get("id", "")
            has_label = bool(inp_id and soup.find("label", {"for": inp_id}))
            has_aria = bool(inp.get("aria-label") or inp.get("aria-labelledby"))
            has_placeholder = bool(inp.get("placeholder"))
            if not has_label and not has_aria:
                _add(scan_id, "inputs_without_labels", "warning",
                     f"Form input missing label: {p['url']}",
                     page_id=p["id"])
                break


def _check_missing_placeholders(scan_id, pages, page_htmls):
    for p in pages:
        soup = page_htmls.get(p["url"])
        if not soup:
            continue
        inputs = soup.find_all(["input", "textarea"])
        missing = 0
        for inp in inputs:
            if inp.get("type") in ("hidden", "submit", "button", "reset", "checkbox", "radio"):
                continue
            if not inp.get("placeholder") and not inp.get("aria-label"):
                missing += 1
        if missing > 3:
            _add(scan_id, "missing_placeholders", "info",
                 f"{missing} inputs without placeholders: {p['url']}",
                 page_id=p["id"])


def _check_incorrect_input_types(scan_id, pages, page_htmls):
    for p in pages:
        soup = page_htmls.get(p["url"])
        if not soup:
            continue
        for inp in soup.find_all("input"):
            name = (inp.get("name", "") + inp.get("id", "")).lower()
            input_type = (inp.get("type") or "text").lower()
            if ("email" in name or "e-mail" in name) and input_type != "email":
                _add(scan_id, "incorrect_input_types", "warning",
                     f"Email field using type='{input_type}' instead of 'email': {p['url']}",
                     page_id=p["id"])
            elif ("phone" in name or "tel" in name) and input_type != "tel":
                _add(scan_id, "incorrect_input_types", "warning",
                     f"Phone field using type='{input_type}' instead of 'tel': {p['url']}",
                     page_id=p["id"])


def _check_required_fields_no_indicator(scan_id, pages, page_htmls):
    for p in pages:
        soup = page_htmls.get(p["url"])
        if not soup:
            continue
        forms = soup.find_all("form")
        for form in forms:
            required_inputs = form.find_all(attrs={"required": True})
            for inp in required_inputs:
                inp_id = inp.get("id", "")
                label = soup.find("label", {"for": inp_id}) if inp_id else None
                label_text = label.get_text() if label else ""
                if "*" not in label_text and "required" not in label_text.lower():
                    _add(scan_id, "required_fields_no_indicator", "warning",
                         f"Required field has no visible indicator: {p['url']}",
                         page_id=p["id"])
                    break


def _check_no_submit_action(scan_id, pages, page_htmls):
    for p in pages:
        soup = page_htmls.get(p["url"])
        if not soup:
            continue
        forms = soup.find_all("form")
        for form in forms:
            submit = form.find("button", {"type": "submit"})
            if not submit:
                submit = form.find("input", {"type": "submit"})
            if not submit:
                _add(scan_id, "no_submit_action", "warning",
                     f"Form has no submit button: {p['url']}",
                     page_id=p["id"])


def _check_submit_no_text(scan_id, pages, page_htmls):
    for p in pages:
        soup = page_htmls.get(p["url"])
        if not soup:
            continue
        submits = soup.find_all("button", {"type": "submit"})
        for btn in submits:
            text = btn.get_text(strip=True)
            aria = btn.get("aria-label", "")
            if not text and not aria:
                _add(scan_id, "submit_no_text", "warning",
                     f"Submit button has no text: {p['url']}",
                     page_id=p["id"])


def _check_very_long_forms(scan_id, pages, page_htmls):
    for p in pages:
        soup = page_htmls.get(p["url"])
        if not soup:
            continue
        forms = soup.find_all("form")
        for form in forms:
            inputs = form.find_all(["input", "select", "textarea"])
            inputs = [i for i in inputs if i.get("type") not in ("hidden", "submit", "button")]
            if len(inputs) > 10:
                _add(scan_id, "very_long_forms", "info",
                     f"Form has {len(inputs)} fields — consider simplifying: {p['url']}",
                     page_id=p["id"])
