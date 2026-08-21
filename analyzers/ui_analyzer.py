"""HTML-based measurable UI analysis.

Takes page data (from crawl) + parsed BeautifulSoup HTML and produces
a list of UI finding dicts.  The caller is responsible for persisting
the findings to the database.
"""

import re
import statistics
from collections import Counter
from urllib.parse import urlparse

from bs4 import BeautifulSoup, Tag

# ─── Constants ──────────────────────────────────────────────

CTA_KEYWORDS = [
    "buy", "apply", "book", "contact", "register", "get started", "learn more",
    "download", "enroll", "sign up", "subscribe", "purchase", "order", "try",
    "demo", "free trial", "join", "start now", "explore", "discover", "shop",
    "hire us", "get quote", "request", "schedule", "start", "begin", "claim",
]

GENERIC_CTA_TEXT = {"click here", "read more", "here", "more", "link", "learn more", "see more"}

HEADING_TAGS = {"h1", "h2", "h3", "h4", "h5", "h6"}

_SIZE_RE = re.compile(r"([\d.]+)\s*(px|pt|rem|em)")
_FONT_RE = re.compile(r"font-family\s*:\s*([^;]+)", re.IGNORECASE)
_COLOR_RE = re.compile(r"(?:^|[\s;,])color\s*:\s*([^;]+)", re.IGNORECASE)


def _safe_int(val, default=0):
    try:
        return int(val)
    except (TypeError, ValueError):
        return default


def _make_finding(
    check_name: str,
    severity: str,
    message: str,
    page_url: str,
    page_id: int,
    evidence: str,
    recommendation: str,
) -> dict:
    return {
        "check_name": check_name,
        "severity": severity,
        "message": message,
        "page_url": page_url,
        "page_id": page_id,
        "evidence": evidence,
        "recommendation": recommendation,
    }


def _parse_inline_styles(soup: BeautifulSoup) -> list[str]:
    """Return all inline style attribute values found in the document."""
    return [tag["style"] for tag in soup.find_all(attrs={"style": True}) if tag.get("style")]


def _extract_font_sizes(styles: list[str]) -> list[float]:
    """Extract numeric px font-size values from inline styles."""
    sizes: list[float] = []
    for style in styles:
        for m in _SIZE_RE.finditer(style):
            val = float(m.group(1))
            unit = m.group(2).lower()
            if unit == "px":
                sizes.append(val)
            elif unit == "pt":
                sizes.append(val * 1.333)
            elif unit == "rem":
                sizes.append(val * 16)
            elif unit == "em":
                sizes.append(val * 16)
    return sizes


def _extract_font_families(styles: list[str]) -> list[str]:
    """Extract font-family values from inline styles."""
    families: list[str] = []
    for style in styles:
        for m in _FONT_RE.finditer(style):
            raw = m.group(1).strip().strip("'\"").strip()
            families.append(raw.lower())
    return families


def _extract_colors(styles: list[str]) -> list[str]:
    """Extract color values from inline styles."""
    colors: list[str] = []
    for style in styles:
        for m in _COLOR_RE.finditer(style):
            raw = m.group(1).strip().lower()
            colors.append(raw)
    return colors


def _text_words(text: str) -> int:
    return len(text.split())


def _get_soup(url: str, page_htmls: dict) -> BeautifulSoup | None:
    return page_htmls.get(url)


# ─── Per-Page Checks ────────────────────────────────────────


def _check_visual_hierarchy(page: dict, soup: BeautifulSoup) -> list[dict]:
    url = page["url"]
    pid = page["id"]
    findings: list[dict] = []

    headings = soup.find_all(list(HEADING_TAGS))
    counts = Counter()
    for h in headings:
        counts[h.name] += 1

    h1_count = counts.get("h1", 0)

    if h1_count == 0:
        findings.append(_make_finding(
            "no_h1_found",
            "critical",
            f"No H1 Found: {url}",
            url, pid,
            "Page has no <h1> element",
            "Add a single, descriptive <h1> that clearly identifies the page topic",
        ))

    if h1_count > 3:
        findings.append(_make_finding(
            "heading_count_imbalance",
            "high",
            f"Heading Count Imbalance ({h1_count} H1 tags): {url}",
            url, pid,
            f"Page contains {h1_count} <h1> elements — a page should have exactly one",
            "Use a single <h1> for the main page heading; demote secondary headings to <h2> or below",
        ))

    # Weak hierarchy: heading levels wildly unbalanced
    # E.g. 0 h1 but lots of h2/h3, or huge gap between levels
    h2_count = counts.get("h2", 0)
    h3_count = counts.get("h3", 0)
    total_headings = sum(counts.values())
    if total_headings >= 10:
        if h1_count == 0 and (h2_count + h3_count) > 10:
            findings.append(_make_finding(
                "weak_visual_hierarchy",
                "high",
                f"Weak Visual Hierarchy: {url}",
                url, pid,
                f"No H1 but {h2_count} H2 and {h3_count} H3 detected",
                "Restructure headings so the page has one clear H1 with nested H2-H6 beneath it",
            ))

    # Inconsistent heading hierarchy: levels skip (h1 -> h3 without h2)
    prev_level = 0
    for h in headings:
        level = int(h.name[1])
        if prev_level > 0 and level > prev_level + 1:
            findings.append(_make_finding(
                "inconsistent_heading_hierarchy",
                "medium",
            f"Inconsistent Heading Hierarchy (H{prev_level} to H{level}): {url}",
            url, pid,
            f"Heading levels skip from <h{prev_level}> to <h{level}>",
                "Ensure heading levels descend one at a time without skipping levels",
            ))
            break  # one finding per page is enough
        prev_level = level

    return findings


def _check_typography(page: dict, soup: BeautifulSoup) -> list[dict]:
    url = page["url"]
    pid = page["id"]
    findings: list[dict] = []

    styles = _parse_inline_styles(soup)
    if not styles:
        return findings

    font_sizes = _extract_font_sizes(styles)
    small_count = sum(1 for s in font_sizes if s < 12 and s > 0)
    if small_count > 5:
        findings.append(_make_finding(
            "small_text_detected",
            "medium",
            f"Small Text Detected ({small_count} elements < 12px): {url}",
            url, pid,
            f"{small_count} inline-styled elements use font-size below 12px",
            "Increase body text to at least 14px and secondary text to at least 12px for readability",
        ))

    font_families = _extract_font_families(styles)
    unique_families = set(font_families)
    if len(unique_families) > 5:
        findings.append(_make_finding(
            "excessive_font_variations",
            "medium",
            f"Excessive Font Variations ({len(unique_families)} different families): {url}",
            url, pid,
            f"Found {len(unique_families)} unique font-family values in inline styles",
            "Limit font families to 2-3 maximum: one for headings, one for body, and optionally one accent font",
        ))

    unique_sizes = set(s for s in font_sizes if s > 0)
    if len(unique_sizes) > 8:
        findings.append(_make_finding(
            "inconsistent_font_sizes",
            "low",
            f"Inconsistent Font Sizes ({len(unique_sizes)} different sizes): {url}",
            url, pid,
            f"Found {len(unique_sizes)} unique font-size values across inline-styled elements",
            "Use a consistent type scale (e.g., 12/14/16/20/24/32px) for visual harmony",
        ))

    return findings


def _check_color_consistency(page: dict, soup: BeautifulSoup) -> list[dict]:
    url = page["url"]
    pid = page["id"]
    findings: list[dict] = []

    styles = _parse_inline_styles(soup)
    if not styles:
        return findings

    colors = _extract_colors(styles)
    unique_colors = set(colors)

    if len(unique_colors) > 15:
        findings.append(_make_finding(
            "too_many_colors",
            "high",
            f"Too Many Colors ({len(unique_colors)} unique): {url}",
            url, pid,
            f"Found {len(unique_colors)} distinct color values in inline styles",
            "Establish a brand color palette of 3-5 core colors and apply consistently across the site",
        ))
    elif len(unique_colors) > 10:
        findings.append(_make_finding(
            "color_inconsistency",
            "medium",
            f"Color Inconsistency ({len(unique_colors)} unique colors): {url}",
            url, pid,
            f"Found {len(unique_colors)} distinct color values — consider consolidating",
            "Audit the color palette and reduce to a focused set of brand-consistent colors",
        ))

    return findings


def _check_spacing_layout(page: dict, soup: BeautifulSoup) -> list[dict]:
    url = page["url"]
    pid = page["id"]
    findings: list[dict] = []

    body = soup.body or soup
    text = body.get_text(separator=" ", strip=True)
    word_count = _text_words(text)

    section_tags = body.find_all(["section", "article", "main", "aside", "div"])
    # Rough section count: unique parents that contain substantial text
    section_count = 0
    seen_parents: set[int] = set()
    for sec in section_tags:
        pid_attr = id(sec.parent) if sec.parent else 0
        if pid_attr not in seen_parents:
            seen_parents.add(pid_attr)
            section_count += 1

    if word_count > 5000 and section_count < 5:
        findings.append(_make_finding(
            "crowded_layout",
            "high",
            f"Crowded Layout ({word_count} words in {section_count} sections): {url}",
            url, pid,
            f"Page has {word_count} words spread across only {section_count} structural sections",
            "Break content into distinct sections with clear headings, whitespace, and visual separation",
        ))

    if word_count < 100 and section_count > 10:
        findings.append(_make_finding(
            "excessive_whitespace",
            "low",
            f"Excessive Whitespace ({word_count} words across {section_count} sections): {url}",
            url, pid,
            f"Page has only {word_count} words spread across {section_count} structural sections",
            "Consolidate sparse sections or add meaningful content to each section",
        ))

    return findings


def _check_cta_design(page: dict, soup: BeautifulSoup) -> list[dict]:
    url = page["url"]
    pid = page["id"]
    findings: list[dict] = []

    # Detect CTAs: buttons and prominent links
    buttons = soup.find_all("button")
    cta_links = []
    for a in soup.find_all("a"):
        text = a.get_text(strip=True).lower()
        href = a.get("href", "")
        is_cta = (
            any(kw in text for kw in CTA_KEYWORDS)
            or a.get("class") and any(
                "btn" in c.lower() or "cta" in c.lower() or "button" in c.lower()
                for c in a.get("class", [])
            )
        )
        if is_cta:
            cta_links.append(a)

    cta_count = len(buttons) + len(cta_links)

    if cta_count > 15:
        findings.append(_make_finding(
            "too_many_ctas",
            "medium",
            f"Too Many CTAs ({cta_count} detected): {url}",
            url, pid,
            f"{cta_count} call-to-action elements found (buttons + CTA links)",
            "Reduce to 3-5 primary CTAs and hierarchy them by importance",
        ))

    # Weak CTA text: CTAs using generic or non-action-oriented text
    weak_ctas: list[str] = []
    for btn in buttons:
        btn_text = btn.get_text(strip=True).lower()
        if btn_text in GENERIC_CTA_TEXT or not btn_text:
            weak_ctas.append(btn_text or "(empty)")
    for link in cta_links:
        link_text = link.get_text(strip=True).lower()
        if link_text in GENERIC_CTA_TEXT or not link_text:
            weak_ctas.append(link_text or "(empty)")

    if weak_ctas:
        samples = ", ".join(f'"{t}"' for t in weak_ctas[:5])
        findings.append(_make_finding(
            "weak_cta_text",
            "low",
            f"Weak CTA Text ({len(weak_ctas)} generic CTAs): {url}",
            url, pid,
            f"Generic or empty CTA text found: {samples}",
            "Use action-oriented, specific CTA text (e.g., 'Start Free Trial' instead of 'Click Here')",
        ))

    # No primary CTA: all CTAs are the same element type with no standout
    if cta_count >= 5:
        all_buttons = all(isinstance(c, type(buttons[0])) for c in buttons) if buttons else True
        all_links = all(isinstance(c, type(cta_links[0])) for c in cta_links) if cta_links else True
        # Check if any CTA has primary/hero/distinctive CSS classes
        has_primary = False
        for btn in buttons:
            classes = " ".join(btn.get("class", [])).lower()
            if any(p in classes for p in ("primary", "hero", "main", "large", "big", "featured")):
                has_primary = True
                break
        for link in cta_links:
            classes = " ".join(link.get("class", [])).lower()
            if any(p in classes for p in ("primary", "hero", "main", "large", "big", "featured")):
                has_primary = True
                break

        if not has_primary and cta_count >= 7:
            findings.append(_make_finding(
                "no_primary_cta",
                "low",
                f"No Clear Primary CTA ({cta_count} similar CTAs): {url}",
                url, pid,
                "All CTAs appear equal in prominence — no clear primary call-to-action",
                "Designate one primary CTA with a contrasting style and place it prominently above the fold",
            ))

    return findings


def _check_imagery(page: dict, soup: BeautifulSoup) -> list[dict]:
    url = page["url"]
    pid = page["id"]
    findings: list[dict] = []

    images = soup.find_all("img")
    if not images:
        return findings

    total = len(images)
    missing_alt = [img for img in images if not img.get("alt")]
    no_dimensions = [img for img in images if not (img.get("width") or img.get("height"))]
    broken: list[str] = []
    for img in images:
        src = (img.get("src") or "").strip()
        if not src or src == "data:" or "error" in src.lower():
            broken.append(src or "(empty)")

    alt_pct = len(missing_alt) / total * 100 if total else 0
    if alt_pct > 30:
        findings.append(_make_finding(
            "no_alt_text_images",
            "high",
            f"No Alt Text on {len(missing_alt)}/{total} Images ({alt_pct:.0f}%): {url}",
            url, pid,
            f"{len(missing_alt)} of {total} images are missing alt attributes ({alt_pct:.0f}%)",
            "Add descriptive alt text to all meaningful images for accessibility and SEO",
        ))

    dim_pct = len(no_dimensions) / total * 100 if total else 0
    if dim_pct > 50:
        findings.append(_make_finding(
            "images_without_dimensions",
            "medium",
            f"Images Without Dimensions ({len(no_dimensions)}/{total}): {url}",
            url, pid,
            f"{len(no_dimensions)} of {total} images lack width/height attributes ({dim_pct:.0f}%)",
            "Add explicit width and height attributes to prevent layout shift (CLS)",
        ))

    if broken:
        findings.append(_make_finding(
            "broken_images",
            "high",
            f"Broken Images ({len(broken)} detected): {url}",
            url, pid,
            f"{len(broken)} image(s) have empty or invalid src attributes",
            "Remove broken images or fix their src URLs to point to valid resources",
        ))

    return findings


def _check_overall_polish(page: dict, soup: BeautifulSoup) -> list[dict]:
    url = page["url"]
    pid = page["id"]
    findings: list[dict] = []

    dom_size = len(soup.find_all(True))
    if dom_size > 3000:
        findings.append(_make_finding(
            "visual_clutter",
            "high",
            f"Visual Clutter ({dom_size} DOM nodes): {url}",
            url, pid,
            f"Page DOM contains {dom_size} elements (threshold: 3000)",
            "Reduce DOM complexity by removing unnecessary wrapper elements and combining redundant containers",
        ))

    favicon = soup.find("link", rel=lambda r: r and "icon" in r.lower() if isinstance(r, str) else False)
    if not favicon:
        findings.append(_make_finding(
            "no_favicon",
            "info",
            f"No Favicon Found: {url}",
            url, pid,
            "No <link rel=\"icon\"> or <link rel=\"shortcut icon\"> element found",
            "Add a favicon for brand recognition and professional appearance in browser tabs",
        ))

    viewport = soup.find("meta", attrs={"name": "viewport"})
    if not viewport:
        findings.append(_make_finding(
            "missing_meta_viewport",
            "critical",
            f"Missing Meta Viewport Tag: {url}",
            url, pid,
            "No <meta name=\"viewport\"> tag found in the document",
            "Add <meta name=\"viewport\" content=\"width=device-width, initial-scale=1\"> for proper mobile rendering",
        ))

    return findings


# ─── Cross-Page Checks ──────────────────────────────────────


def _check_component_consistency(pages: list[dict], page_htmls: dict) -> list[dict]:
    """Check for inconsistent button styles and UI patterns across pages."""
    findings: list[dict] = []
    if len(pages) < 2:
        return findings

    button_counts: list[tuple[dict, int]] = []
    nav_counts: list[tuple[dict, int]] = []

    for page in pages:
        soup = _get_soup(page["url"], page_htmls)
        if not soup:
            continue
        btns = soup.find_all("button")
        button_counts.append((page, len(btns)))
        navs = soup.find_all("nav")
        nav_counts.append((page, len(navs)))

    # Inconsistent button styles: high variance in button counts across pages
    if len(button_counts) >= 3:
        counts = [c for _, c in button_counts]
        mean = statistics.mean(counts) if counts else 0
        if mean > 0:
            stdev = statistics.stdev(counts) if len(counts) > 1 else 0
            cv = stdev / mean  # coefficient of variation
            if cv > 0.5:
                sample_pages = ", ".join(p["url"] for p, _ in button_counts[:3])
                findings.append(_make_finding(
                    "inconsistent_button_styles",
                    "medium",
                    f"Inconsistent Button Counts Across Pages (CV={cv:.0%})",
                    pages[0]["url"], pages[0]["id"],
                    f"Button counts vary widely across pages (mean={mean:.1f}, stdev={stdev:.1f}). Sample: {sample_pages}",
                    "Standardize button components and usage patterns across all pages for visual consistency",
                ))

    # Mixed UI patterns: some pages use <nav>, others don't
    if nav_counts:
        has_nav = sum(1 for _, c in nav_counts if c > 0)
        no_nav = sum(1 for _, c in nav_counts if c == 0)
        if has_nav > 0 and no_nav > 0 and no_nav <= len(nav_counts) // 3:
            no_nav_pages = [p["url"] for p, c in nav_counts if c == 0][:3]
            findings.append(_make_finding(
                "mixed_ui_patterns",
                "medium",
                f"Mixed UI Patterns ({no_nav_pages[0]})",
                no_nav_pages[0] if no_nav_pages else pages[0]["url"],
                next((p["id"] for p, c in nav_counts if c == 0), pages[0]["id"]),
                f"{has_nav} pages use <nav> elements, but {no_nav} pages do not",
                "Ensure consistent navigation structure across all pages using <nav> elements",
            ))

    return findings


# ─── Main Entry Point ───────────────────────────────────────


def analyze_ui(
    scan_id: int,
    pages: list[dict],
    page_htmls: dict[str, BeautifulSoup],
    ux_data: dict,
) -> list[dict]:
    """Run all UI checks across all pages.

    Args:
        scan_id: The scan identifier.
        pages: List of page dicts from the database.
        page_htmls: Mapping of URL → parsed BeautifulSoup.
        ux_data: Additional UX data (reserved for future use).

    Returns:
        List of finding dicts ready for persistence.
    """
    findings: list[dict] = []

    # Per-page checks
    for page in pages:
        soup = _get_soup(page["url"], page_htmls)
        if not soup:
            continue

        findings.extend(_check_visual_hierarchy(page, soup))
        findings.extend(_check_typography(page, soup))
        findings.extend(_check_color_consistency(page, soup))
        findings.extend(_check_spacing_layout(page, soup))
        findings.extend(_check_cta_design(page, soup))
        findings.extend(_check_imagery(page, soup))
        findings.extend(_check_overall_polish(page, soup))

    # Cross-page checks
    findings.extend(_check_component_consistency(pages, page_htmls))

    return findings
