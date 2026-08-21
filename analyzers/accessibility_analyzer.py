import re
from bs4 import BeautifulSoup


def analyze_accessibility(scan_id: int, pages: list[dict], page_htmls: dict,
                          all_elements: dict) -> list[dict]:
    """Run accessibility checks. Returns list of finding dicts."""
    findings = []

    if not pages:
        return findings

    for p in pages:
        if p.get("status_code") and p["status_code"] >= 400:
            continue
        soup = page_htmls.get(p["url"])
        if not soup:
            continue

        _check_missing_landmarks(findings, scan_id, p, soup)
        _check_div_soup(findings, scan_id, p, soup)
        _check_missing_lang_attribute(findings, scan_id, p, soup)

        _check_heading_hierarchy_skip(findings, scan_id, p, soup)
        _check_multiple_h1(findings, scan_id, p, soup)
        _check_empty_headings(findings, scan_id, p, soup)

        _check_input_without_label(findings, scan_id, p, soup)
        _check_form_without_fieldset(findings, scan_id, p, soup)
        _check_missing_form_error_role(findings, scan_id, p, soup)

        _check_image_missing_alt(findings, scan_id, p, soup)
        _check_image_empty_alt_with_link(findings, scan_id, p, soup)

        _check_potential_low_contrast(findings, scan_id, p, soup)

        _check_aria_hidden_focusable(findings, scan_id, p, soup)
        _check_missing_role_attributes(findings, scan_id, p, soup)

        _check_table_without_headers(findings, scan_id, p, soup)
        _check_layout_table(findings, scan_id, p, soup)

    return findings


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _finding(scan_id: int, check_name: str, severity: str, message: str,
             page_url: str, page_id: int, evidence: str, recommendation: str) -> dict:
    return {
        "check_name": check_name,
        "severity": severity,
        "message": message,
        "page_url": page_url,
        "page_id": page_id,
        "evidence": evidence,
        "recommendation": recommendation,
    }


def _add_finding(findings: list, scan_id: int, check_name: str, severity: str,
                 message: str, page_url: str, page_id: int,
                 evidence: str, recommendation: str):
    findings.append(_finding(scan_id, check_name, severity, message,
                             page_url, page_id, evidence, recommendation))


_SEMANTIC_TAGS = {"article", "section", "aside", "nav", "main", "header", "footer"}


def _parse_color(color_str: str):
    """Attempt to parse a CSS color string into (r, g, b) or None."""
    color_str = color_str.strip().lower()

    named_colors = {
        "black": (0, 0, 0), "white": (255, 255, 255), "red": (255, 0, 0),
        "green": (0, 128, 0), "blue": (0, 0, 255), "yellow": (255, 255, 0),
        "gray": (128, 128, 128), "grey": (128, 128, 128), "silver": (192, 192, 192),
        "orange": (255, 165, 0), "purple": (128, 0, 128), "navy": (0, 0, 128),
        "teal": (0, 128, 128), "maroon": (128, 0, 0), "olive": (128, 128, 0),
        "aqua": (0, 255, 255), "fuchsia": (255, 0, 255), "lime": (0, 255, 0),
        "transparent": None,
    }
    if color_str in named_colors:
        return named_colors[color_str]

    hex_match = re.match(r"^#([0-9a-f]{3,8})$", color_str)
    if hex_match:
        h = hex_match.group(1)
        if len(h) == 3:
            return (int(h[0]*2, 16), int(h[1]*2, 16), int(h[2]*2, 16))
        if len(h) >= 6:
            return (int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16))

    rgb_match = re.match(r"^rgba?\(\s*(\d+)\s*,\s*(\d+)\s*,\s*(\d+)", color_str)
    if rgb_match:
        return (int(rgb_match.group(1)), int(rgb_match.group(2)), int(rgb_match.group(3)))

    return None


def _relative_luminance(r: int, g: int, b: int) -> float:
    """Calculate relative luminance per WCAG 2.0."""
    def linearize(c):
        c_srgb = c / 255.0
        return c_srgb / 12.92 if c_srgb <= 0.04045 else ((c_srgb + 0.055) / 1.055) ** 2.4
    return 0.2126 * linearize(r) + 0.7152 * linearize(g) + 0.0722 * linearize(b)


def _contrast_ratio(rgb1, rgb2) -> float:
    """Calculate WCAG contrast ratio between two RGB tuples."""
    l1 = _relative_luminance(*rgb1)
    l2 = _relative_luminance(*rgb2)
    lighter = max(l1, l2)
    darker = min(l1, l2)
    return (lighter + 0.05) / (darker + 0.05)


# ---------------------------------------------------------------------------
# 1. Semantic HTML
# ---------------------------------------------------------------------------

def _check_missing_landmarks(findings, scan_id, page, soup):
    has_main = bool(soup.find("main") or soup.find(attrs={"role": "main"}))
    has_nav = bool(soup.find("nav") or soup.find(attrs={"role": "navigation"}))
    has_header = bool(soup.find("header") or soup.find(attrs={"role": "banner"}))
    has_footer = bool(soup.find("footer") or soup.find(attrs={"role": "contentinfo"}))

    missing = []
    if not has_main:
        missing.append("main")
    if not has_nav:
        missing.append("nav")
    if not has_header:
        missing.append("header")
    if not has_footer:
        missing.append("footer")

    if len(missing) >= 3:
        _add_finding(findings, scan_id, "missing_landmarks", "high",
                     f"Missing Landmarks ({', '.join(missing)}): {page['url']}",
                     page["url"], page["id"],
                     f"Page missing semantic landmarks: {', '.join(missing)}",
                     "Add semantic HTML5 landmark elements (<main>, <nav>, <header>, <footer>) to define page structure")
    elif missing:
        _add_finding(findings, scan_id, "missing_landmarks", "info",
                     f"Missing Landmarks ({', '.join(missing)}): {page['url']}",
                     page["url"], page["id"],
                     f"Page missing semantic landmarks: {', '.join(missing)}",
                     "Add missing landmark elements to improve screen reader navigation")


def _check_div_soup(findings, scan_id, page, soup):
    all_divs = soup.find_all("div")
    semantic_count = 0
    for tag in soup.find_all(True):
        if tag.name in _SEMANTIC_TAGS:
            semantic_count += 1

    if len(all_divs) > 50 and semantic_count < 3:
        _add_finding(findings, scan_id, "div_soup", "high",
                     f"Div Soup ({len(all_divs)} divs, {semantic_count} semantic elements): {page['url']}",
                     page["url"], page["id"],
                     f"{len(all_divs)} <div> elements vs only {semantic_count} semantic HTML elements",
                     "Replace <div> elements with appropriate semantic tags (article, section, aside, nav, main, header, footer)")


def _check_missing_lang_attribute(findings, scan_id, page, soup):
    html_tag = soup.find("html")
    if not html_tag:
        return

    if not html_tag.get("lang"):
        _add_finding(findings, scan_id, "missing_lang_attribute", "high",
                     f"Missing Lang Attribute: {page['url']}",
                     page["url"], page["id"],
                     "<html> tag has no lang attribute",
                     "Add lang attribute to <html> tag (e.g., lang=\"en\") to help screen readers use correct pronunciation")


# ---------------------------------------------------------------------------
# 2. Heading Structure
# ---------------------------------------------------------------------------

def _check_heading_hierarchy_skip(findings, scan_id, page, soup):
    headings = soup.find_all(re.compile(r"^h[1-6]$"))
    if len(headings) < 2:
        return

    prev_level = 0
    skip_found = False
    skip_from = 0
    skip_to = 0

    for h in headings:
        level = int(h.name[1])
        if prev_level > 0 and level > prev_level + 1:
            skip_found = True
            skip_from = prev_level
            skip_to = level
            break
        prev_level = level

    if skip_found:
        _add_finding(findings, scan_id, "heading_hierarchy_skip", "high",
                     f"Heading Hierarchy Skip (h{skip_from} -> h{skip_to}): {page['url']}",
                     page["url"], page["id"],
                     f"Heading levels skip from h{skip_from} to h{skip_to}",
                     "Use sequential heading levels without skipping (h1 -> h2 -> h3, not h1 -> h3)")


def _check_multiple_h1(findings, scan_id, page, soup):
    h1_tags = soup.find_all("h1")
    if len(h1_tags) > 1:
        _add_finding(findings, scan_id, "multiple_h1", "high",
                     f"Multiple H1 Tags ({len(h1_tags)} h1 elements): {page['url']}",
                     page["url"], page["id"],
                     f"Page contains {len(h1_tags)} <h1> elements",
                     "Use exactly one <h1> per page for the main page heading")


def _check_empty_headings(findings, scan_id, page, soup):
    headings = soup.find_all(re.compile(r"^h[1-6]$"))
    empty_count = 0
    for h in headings:
        text = h.get_text(strip=True)
        has_img_alt = False
        for img in h.find_all("img"):
            if img.get("alt", "").strip():
                has_img_alt = True
                break
        has_aria_label = bool(h.get("aria-label"))
        if not text and not has_img_alt and not has_aria_label:
            empty_count += 1

    if empty_count > 0:
        _add_finding(findings, scan_id, "empty_headings", "high",
                     f"Empty Headings ({empty_count} empty heading elements): {page['url']}",
                     page["url"], page["id"],
                     f"{empty_count} heading elements contain no text content",
                     "Ensure all headings contain meaningful text or have aria-label for screen readers")


# ---------------------------------------------------------------------------
# 3. Forms Accessibility
# ---------------------------------------------------------------------------

def _check_input_without_label(findings, scan_id, page, soup):
    forms = soup.find_all("form")
    unlabeled_total = 0

    for form in forms:
        inputs = form.find_all(["input", "select", "textarea"])
        for inp in inputs:
            inp_type = (inp.get("type") or "").lower()
            if inp_type in ("hidden", "submit", "button", "reset", "image"):
                continue

            inp_id = inp.get("id", "")
            has_for_label = bool(inp_id and soup.find("label", {"for": inp_id}))
            has_aria_label = bool(inp.get("aria-label"))
            has_aria_labelledby = bool(inp.get("aria-labelledby"))
            has_title = bool(inp.get("title"))
            wrapped_in_label = bool(inp.find_parent("label"))

            if not has_for_label and not has_aria_label and not has_aria_labelledby and not has_title and not wrapped_in_label:
                unlabeled_total += 1

    if unlabeled_total > 0:
        _add_finding(findings, scan_id, "input_without_label", "high",
                     f"Input Without Label ({unlabeled_total} unlabeled inputs): {page['url']}",
                     page["url"], page["id"],
                     f"{unlabeled_total} form input(s) have no associated label via for/id, aria-label, aria-labelledby, or wrapping <label>",
                     "Associate each input with a visible <label> element using for/id attribute matching")


def _check_form_without_fieldset(findings, scan_id, page, soup):
    forms = soup.find_all("form")
    for form in forms:
        radios = form.find_all("input", {"type": "radio"})
        checkboxes = form.find_all("input", {"type": "checkbox"})
        choice_count = len(radios) + len(checkboxes)

        if choice_count > 3:
            has_fieldset = bool(form.find("fieldset"))
            has_role_group = bool(form.find(attrs={"role": "group"}))
            if not has_fieldset and not has_role_group:
                _add_finding(findings, scan_id, "form_without_fieldset", "medium",
                             f"Form Without Fieldset ({choice_count} radio/checkbox inputs): {page['url']}",
                             page["url"], page["id"],
                             f"{choice_count} radio/checkbox inputs without <fieldset> or role=group grouping",
                             "Group related radio buttons and checkboxes within <fieldset> with a <legend>")


def _check_missing_form_error_role(findings, scan_id, page, soup):
    forms = soup.find_all("form")
    for form in forms:
        inputs = form.find_all(["input", "select", "textarea"])
        missing_count = 0
        for inp in inputs:
            inp_type = (inp.get("type") or "").lower()
            if inp_type in ("hidden", "submit", "button", "reset", "image"):
                continue
            has_aria_describedby = bool(inp.get("aria-describedby"))
            has_aria_invalid = bool(inp.get("aria-invalid"))
            has_role = bool(inp.get("role"))
            has_custom_validity = bool(inp.get("oninvalid"))

            if not has_aria_describedby and not has_aria_invalid and not has_custom_validity:
                missing_count += 1

        if missing_count > 3:
            _add_finding(findings, scan_id, "missing_form_error_role", "medium",
                         f"Missing Form Error Role ({missing_count} inputs lack error handling): {page['url']}",
                         page["url"], page["id"],
                         f"{missing_count} form inputs lack aria-describedby for error messages",
                         "Add aria-describedby pointing to error message elements and aria-invalid for invalid states")


# ---------------------------------------------------------------------------
# 4. Images
# ---------------------------------------------------------------------------

def _check_image_missing_alt(findings, scan_id, page, soup):
    images = soup.find_all("img")
    if not images:
        return

    missing = 0
    for img in images:
        if not img.has_attr("alt"):
            missing += 1

    if missing > 0:
        severity = "high" if missing > 3 else "medium"
        _add_finding(findings, scan_id, "image_missing_alt", severity,
                     f"Image Missing Alt ({missing}/{len(images)} images): {page['url']}",
                     page["url"], page["id"],
                     f"{missing} out of {len(images)} images are missing the alt attribute",
                     "Add alt attribute to all <img> elements; use alt=\"\" for decorative images")


def _check_image_empty_alt_with_link(findings, scan_id, page, soup):
    linked_images = []
    for a in soup.find_all("a"):
        for img in a.find_all("img"):
            linked_images.append(img)

    empty_linked = 0
    for img in linked_images:
        alt = img.get("alt")
        if alt is not None and alt.strip() == "":
            empty_linked += 1

    if empty_linked > 0:
        _add_finding(findings, scan_id, "image_empty_alt_with_link", "high",
                     f"Image Empty Alt With Link ({empty_linked} linked images with alt=\"\"): {page['url']}",
                     page["url"], page["id"],
                     f"{empty_linked} images inside links have alt=\"\" making the link inaccessible",
                     "Provide descriptive alt text for images inside links, or add aria-label to the link")


# ---------------------------------------------------------------------------
# 5. Color / Contrast (heuristic from inline styles)
# ---------------------------------------------------------------------------

def _check_potential_low_contrast(findings, scan_id, page, soup):
    low_contrast_count = 0
    checked = 0

    for tag in soup.find_all(True):
        style = tag.get("style", "")
        if not style:
            continue

        style_lower = style.lower().replace(" ", "")
        color_match = re.search(r"(?:^|;|{)color\s*:\s*([^;}{]+)", style)
        bg_match = re.search(r"(?:^|;|{)background(?:-color)?\s*:\s*([^;}{]+)", style)

        if not color_match or not bg_match:
            continue

        fg_str = color_match.group(1).strip()
        bg_str = bg_match.group(1).strip()

        fg_rgb = _parse_color(fg_str)
        bg_rgb = _parse_color(bg_str)

        if fg_rgb is None or bg_rgb is None:
            continue

        checked += 1
        ratio = _contrast_ratio(fg_rgb, bg_rgb)
        if ratio < 3.0:
            low_contrast_count += 1

    if low_contrast_count > 0:
        _add_finding(findings, scan_id, "potential_low_contrast", "high",
                     f"Potential Low Contrast ({low_contrast_count} low-contrast elements): {page['url']}",
                     page["url"], page["id"],
                     f"{low_contrast_count} inline-styled elements have contrast ratio below 3:1",
                     "Ensure text meets WCAG AA contrast ratio of at least 4.5:1 for normal text and 3:1 for large text")


# ---------------------------------------------------------------------------
# 6. ARIA
# ---------------------------------------------------------------------------

def _check_aria_hidden_focusable(findings, scan_id, page, soup):
    aria_hidden = soup.find_all(attrs={"aria-hidden": "true"})
    violations = 0

    for el in aria_hidden:
        tag = el.name.lower()
        is_natively_focusable = tag in ("a", "button", "input", "select", "textarea")
        tabindex = el.get("tabindex")
        has_tabindex_positive = False
        if tabindex is not None:
            try:
                has_tabindex_positive = int(tabindex) >= 0
            except (ValueError, TypeError):
                pass

        has_focus_handler = bool(el.get("onfocus") or el.get("onclick") or el.get("onkeydown"))

        if is_natively_focusable and not has_tabindex_positive and not has_focus_handler:
            violations += 1
        elif has_tabindex_positive:
            violations += 1
        elif has_focus_handler:
            violations += 1

    if violations > 0:
        _add_finding(findings, scan_id, "aria_hidden_focusable", "high",
                     f"Aria Hidden Focusable ({violations} elements): {page['url']}",
                     page["url"], page["id"],
                     f"{violations} elements have aria-hidden=\"true\" but remain focusable",
                     "Remove tabindex, event handlers, or native focusability from aria-hidden elements, or remove aria-hidden")


def _check_missing_role_attributes(findings, scan_id, page, soup):
    INTERACTIVE_PATTERNS = re.compile(
        r"(?:onclick|onkeydown|onkeypress|onkeyup|onmousedown|onmouseup)", re.I
    )

    missing_role_count = 0
    checked_elements = []

    for tag in soup.find_all(["div", "span", "p", "li", "td", "th", "label", "img", "svg"]):
        onclick = tag.get("onclick", "")
        classes = " ".join(tag.get("class", [])).lower()
        style = tag.get("style", "").lower()

        has_click_handler = bool(onclick and onclick.strip())
        has_click_class = any(kw in classes for kw in ("btn", "button", "clickable", "link", "nav-link", "tab"))
        has_click_cursor = "cursor:pointer" in style.replace(" ", "")

        if not has_click_handler and not has_click_class and not has_click_cursor:
            continue

        has_role = bool(tag.get("role"))
        has_tabindex = tag.has_attr("tabindex")
        has_aria_label = bool(tag.get("aria-label") or tag.get("aria-labelledby"))

        if not has_role and (has_click_handler or has_click_class):
            missing_role_count += 1

    if missing_role_count > 0:
        _add_finding(findings, scan_id, "missing_role_attributes", "high",
                     f"Missing Role Attributes ({missing_role_count} interactive elements): {page['url']}",
                     page["url"], page["id"],
                     f"{missing_role_count} custom elements used as interactive controls without role attribute",
                     "Add appropriate role attributes (role=\"button\", role=\"link\") and tabindex=\"0\" to custom interactive elements")


# ---------------------------------------------------------------------------
# 7. Tables
# ---------------------------------------------------------------------------

def _check_table_without_headers(findings, scan_id, page, soup):
    tables = soup.find_all("table")
    for table in tables:
        rows = table.find_all("tr")
        if len(rows) <= 2:
            continue

        th_count = len(table.find_all("th"))
        if th_count == 0:
            _add_finding(findings, scan_id, "table_without_headers", "medium",
                         f"Table Without Headers ({len(rows)} rows, no <th>): {page['url']}",
                         page["url"], page["id"],
                         f"Data table has {len(rows)} rows but no <th> header cells",
                         "Add <th> elements to identify column/row headers for screen reader users")


def _check_layout_table(findings, scan_id, page, soup):
    tables = soup.find_all("table")
    layout_count = 0

    for table in tables:
        role = (table.get("role") or "").lower()
        if role in ("presentation", "none"):
            layout_count += 1
            continue

        has_summary = bool(table.get("summary"))
        has_caption = bool(table.find("caption"))
        has_th = bool(table.find("th"))
        has_aria_label = bool(table.get("aria-label") or table.get("aria-labelledby"))

        rows = table.find_all("tr")
        if len(rows) > 1 and not has_summary and not has_caption and not has_th and not has_aria_label:
            classes = " ".join(table.get("class", [])).lower()
            if any(kw in classes for kw in ("layout", "grid-layout", "page-layout")):
                layout_count += 1

    if layout_count > 0:
        _add_finding(findings, scan_id, "layout_table", "info",
                     f"Layout Table ({layout_count} tables used for layout): {page['url']}",
                     page["url"], page["id"],
                     f"{layout_count} tables appear to be used for layout rather than data",
                     "Use CSS for layout instead of tables; if tables are for layout, add role=\"presentation\"")
