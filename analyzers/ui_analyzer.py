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
from analyzers.scoring import UI_WEIGHTS

# ─── Constants ──────────────────────────────────────────────

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


def _check_visual_hierarchy(page: dict, soup: BeautifulSoup, rendered: dict = None) -> tuple[list[dict], dict]:
    """Weighted visual hierarchy scoring using Playwright rendered styles.
    
    Hierarchy = heading_scale + font_weight + spacing + section_separation + CTA_prominence + content_grouping
    Contrast is NOT hierarchy — handled separately in color_consistency.
    
    Returns (findings, {"visual_hierarchy_score": int, "vh_breakdown": dict})
    """
    url = page["url"]
    pid = page["id"]
    findings: list[dict] = []
    score = 100
    breakdown = {}

    if not rendered:
        # No rendered data — use basic HTML checks only
        headings = soup.find_all(list(HEADING_TAGS))
        counts = Counter(h.name for h in headings)
        h1_count = counts.get("h1", 0)
        if h1_count == 0:
            findings.append(_make_finding("no_h1_found", "critical",
                f"No H1 Found: {url}", url, pid,
                "Page has no <h1> element",
                "Add a single, descriptive <h1> that clearly identifies the page topic"))
            score -= 20
        elif h1_count > 3:
            findings.append(_make_finding("heading_count_imbalance", "high",
                f"Heading Count Imbalance ({h1_count} H1 tags): {url}", url, pid,
                f"Page contains {h1_count} <h1> elements",
                "Use a single <h1> for the main page heading"))
            score -= 15
        breakdown["heading_progression"] = score
        return findings, {"visual_hierarchy_score": max(0, score), "vh_breakdown": breakdown}

    r_headings = rendered.get("headings", [])
    r_body = rendered.get("bodyTexts", [])
    r_ctas = rendered.get("ctas", [])
    r_sections = rendered.get("sections", [])
    vh = rendered.get("viewportHeight", 720)

    # ── 1. Heading Size Progression (20%) ──────────────────
    heading_progression = 20
    if r_headings:
        sizes_by_level = {}
        for h in r_headings:
            lvl = int(h["tag"][1]) if h["tag"].startswith("h") and h["tag"][1:].isdigit() else 99
            sizes_by_level.setdefault(lvl, []).append(h["fontSize"])
        
        avg_by_level = {k: sum(v)/len(v) for k, v in sizes_by_level.items()}
        sorted_levels = sorted(avg_by_level.keys())
        
        violations = 0
        for i in range(len(sorted_levels) - 1):
            cur = sorted_levels[i]
            nxt = sorted_levels[i + 1]
            if avg_by_level[cur] < avg_by_level[nxt]:
                violations += 1
                penalty = 8 if cur == 1 else 4 if cur == 2 else 2
                heading_progression -= penalty
        
        if violations == 0 and len(sorted_levels) >= 2:
            heading_progression = min(20, heading_progression + 2)
    else:
        heading_progression = 10
    score -= (20 - heading_progression)
    breakdown["heading_progression"] = heading_progression

    # ── 2. Heading ↔ Content Relationship (15%) ───────────
    # Composite heuristic: size ratio + font weight + spacing + visual prominence
    hc_relationship = 15
    if r_headings and r_body:
        # Size ratio
        avg_heading_size = sum(h["fontSize"] for h in r_headings) / len(r_headings)
        body_sizes = [b["fontSize"] for b in r_body if b["fontSize"] > 0]
        avg_body_size = sum(body_sizes) / len(body_sizes) if body_sizes else 16
        size_ratio = avg_heading_size / avg_body_size if avg_body_size > 0 else 1

        # Font weight difference
        avg_heading_weight = sum(h["fontWeight"] for h in r_headings) / len(r_headings)
        body_weights = [b["fontWeight"] for b in r_body if b["fontWeight"] > 0]
        avg_body_weight = sum(body_weights) / len(body_weights) if body_weights else 400
        weight_diff = avg_heading_weight - avg_body_weight

        # Spacing: headings should have more margin/padding than body
        heading_margins = [h.get("marginTop", 0) + h.get("marginBottom", 0) for h in r_headings if h.get("marginTop", 0) is not None]
        body_margins = [b.get("marginTop", 0) + b.get("marginBottom", 0) for b in r_body if b.get("marginTop", 0) is not None]
        avg_heading_margin = sum(heading_margins) / len(heading_margins) if heading_margins else 0
        avg_body_margin = sum(body_margins) / len(body_margins) if body_margins else 0
        margin_ratio = avg_heading_margin / avg_body_margin if avg_body_margin > 0 else 1

        # Composite scoring: each factor contributes
        composite = 0
        # Size ratio contribution (0-40 points)
        if size_ratio >= 1.5:
            composite += 40
        elif size_ratio >= 1.2:
            composite += 25
        elif size_ratio >= 1.0:
            composite += 10
        # else 0

        # Font weight contribution (0-30 points)
        if weight_diff >= 200:
            composite += 30
        elif weight_diff >= 100:
            composite += 20
        elif weight_diff > 0:
            composite += 10

        # Spacing contribution (0-30 points)
        if margin_ratio >= 1.5:
            composite += 30
        elif margin_ratio >= 1.0:
            composite += 15
        # else 0

        # Convert composite (0-100) to penalty (0-15)
        if composite < 30:
            hc_relationship -= 10  # poor: headings blend with body
        elif composite < 60:
            hc_relationship -= 5   # mediocre: could be clearer
        # 60+ = good hierarchy, no penalty
    else:
        hc_relationship = 7
    score -= (15 - hc_relationship)
    breakdown["heading_content_relationship"] = hc_relationship

    # ── 3. Font Weight Hierarchy (10%) ────────────────────
    # Headings should be bolder than body text
    font_weight_hierarchy = 10
    if r_headings and r_body:
        avg_heading_weight = sum(h["fontWeight"] for h in r_headings) / len(r_headings)
        body_weights = [b["fontWeight"] for b in r_body if b["fontWeight"] > 0]
        avg_body_weight = sum(body_weights) / len(body_weights) if body_weights else 400
        
        weight_diff = avg_heading_weight - avg_body_weight
        if weight_diff < 0:
            font_weight_hierarchy -= 6  # headings lighter than body = bad
        elif weight_diff < 100:
            font_weight_hierarchy -= 3  # barely bolder
        # 100+ difference = good hierarchy
    else:
        font_weight_hierarchy = 5
    score -= (10 - font_weight_hierarchy)
    breakdown["font_weight_hierarchy"] = font_weight_hierarchy

    # ── 4. Section Spacing (15%) ──────────────────────────
    section_spacing = 15
    if r_sections:
        paddings = [s["paddingTop"] + s["paddingBottom"] for s in r_sections if s["height"] > 50]
        
        if paddings:
            avg_pad = sum(paddings) / len(paddings)
            pad_var = (sum((p - avg_pad)**2 for p in paddings) / len(paddings)) ** 0.5
            
            if avg_pad < 8:
                section_spacing -= 5
            elif avg_pad > 120:
                section_spacing -= 3
            
            if pad_var > 30:
                section_spacing -= 3
            
            if len(r_sections) >= 3:
                heights = [s["height"] for s in r_sections if s["height"] > 50]
                pads = [s["paddingTop"] + s["paddingBottom"] for s in r_sections if s["height"] > 50]
                if len(heights) >= 3:
                    corr = _rank_correlation(heights, pads)
                    if corr > 0.3:
                        section_spacing = min(15, section_spacing + 2)
    else:
        section_spacing = 8
    score -= (15 - section_spacing)
    breakdown["section_spacing"] = section_spacing

    # ── 5. Above-the-Fold Hierarchy (15%) ─────────────────
    above_fold = 15
    if r_headings:
        h1_elements = [h for h in r_headings if h["tag"] == "h1" and h["visible"]]
        if h1_elements:
            h1_top = min(h["top"] for h in h1_elements)
            if h1_top > vh:
                above_fold -= 8
            elif h1_top > vh * 0.6:
                above_fold -= 3
        else:
            above_fold -= 5
        
        visible_headings = [h for h in r_headings if h["visible"]]
        if len(visible_headings) >= 3:
            tops = sorted(h["top"] for h in visible_headings[:5])
            gaps = [tops[i+1] - tops[i] for i in range(len(tops)-1)]
            if gaps:
                avg_gap = sum(gaps) / len(gaps)
                if avg_gap < 5:
                    above_fold -= 3
    else:
        above_fold = 7
    score -= (15 - above_fold)
    breakdown["above_fold_hierarchy"] = above_fold

    # ── 6. CTA Prominence (10%) ──────────────────────────
    cta_prominence = 10
    if r_ctas:
        primary_cta = max(r_ctas, key=lambda c: c["fontSize"] * c["fontWeight"])
        avg_body_size = sum(b["fontSize"] for b in r_body) / len(r_body) if r_body else 16
        
        cta_size_ratio = primary_cta["fontSize"] / avg_body_size if avg_body_size > 0 else 1
        if cta_size_ratio < 0.8:
            cta_prominence -= 5
        elif cta_size_ratio < 1.0:
            cta_prominence -= 2
        
        if primary_cta["fontWeight"] < 600:
            cta_prominence -= 2
        
        if primary_cta["top"] > vh:
            cta_prominence -= 3
    else:
        cta_prominence = 5
    score -= (10 - cta_prominence)
    breakdown["cta_prominence"] = cta_prominence

    # ── 7. Section Separation / Content Grouping (15%) ────
    # Sections should have distinct visual boundaries
    section_separation = 15
    if r_sections and len(r_sections) >= 2:
        bg_colors = [s["backgroundColor"] for s in r_sections if s["backgroundColor"] not in ("rgba(0, 0, 0, 0)", "transparent", "")]
        has_bg_variation = len(set(bg_colors)) >= 2
        
        paddings_top = [s["paddingTop"] for s in r_sections if s["height"] > 50]
        paddings_bot = [s["paddingBottom"] for s in r_sections if s["height"] > 50]
        has_spacing_variation = (len(set(1 for p in paddings_top if p > 20)) >= 2 or
                                len(set(1 for p in paddings_bot if p > 20)) >= 2)
        
        if has_bg_variation:
            section_separation = min(15, section_separation + 2)
        if has_spacing_variation:
            section_separation = min(15, section_separation + 1)
        
        if not has_bg_variation and not has_spacing_variation:
            section_separation -= 5
    else:
        section_separation = 8
    score -= (15 - section_separation)
    breakdown["section_separation"] = section_separation

    score = max(0, min(100, score))

    # Generate findings based on scoring breakdown
    if heading_progression < 10:
        findings.append(_make_finding("weak_visual_hierarchy", "high",
            f"Weak Heading Progression ({heading_progression}/20): {url}", url, pid,
            "Heading font sizes don't follow proper descending order",
            "Ensure H1 is largest, followed by H2, H3, etc. with clear size differences"))
    
    if hc_relationship < 8:
        findings.append(_make_finding("weak_visual_hierarchy", "low",
            f"Heading/Body Relationship Unclear ({hc_relationship}/15): {url}", url, pid,
            "Headings don't stand out from body text in size, weight, or spacing",
            "Increase heading size, weight, or spacing relative to body text for clearer visual hierarchy"))
    
    if font_weight_hierarchy < 5:
        findings.append(_make_finding("weak_visual_hierarchy", "medium",
            f"Weak Font Weight Hierarchy ({font_weight_hierarchy}/10): {url}", url, pid,
            "Headings are not bolder than body text",
            "Use font-weight 600+ for headings to distinguish them from body text"))
    
    if above_fold < 8:
        findings.append(_make_finding("weak_visual_hierarchy", "medium",
            f"Poor Above-the-Fold Layout ({above_fold}/15): {url}", url, pid,
            "Key headings or CTAs are below the viewport fold",
            "Place primary heading and CTA within the visible viewport area"))
    
    if cta_prominence < 5:
        findings.append(_make_finding("weak_visual_hierarchy", "medium",
            f"CTA Not Prominent Enough ({cta_prominence}/10): {url}", url, pid,
            "Primary call-to-action is too small or below the fold",
            "Make CTA larger, bolder, and place it above the fold"))

    return findings, {"visual_hierarchy_score": score, "vh_breakdown": breakdown}


def _rank_correlation(x: list[float], y: list[float]) -> float:
    """Simple Spearman rank correlation."""
    n = min(len(x), len(y))
    if n < 3:
        return 0
    
    def _rank(arr):
        sorted_idx = sorted(range(len(arr)), key=lambda i: arr[i])
        ranks = [0.0] * len(arr)
        for rank, idx in enumerate(sorted_idx):
            ranks[idx] = rank + 1
        return ranks
    
    rx = _rank(x[:n])
    ry = _rank(y[:n])
    
    d_sq = sum((rx[i] - ry[i]) ** 2 for i in range(n))
    return 1 - (6 * d_sq) / (n * (n**2 - 1))


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
    if not colors:
        return findings

    unique_colors = set(colors)
    color_counts = {}
    for c in colors:
        color_counts[c] = color_counts.get(c, 0) + 1

    # Brand palette: colors used ≥3 times
    brand_colors = {c for c, count in color_counts.items() if count >= 3}
    # One-off colors: used only once
    one_off = {c for c, count in color_counts.items() if count == 1}
    # Occasional colors: used exactly twice
    occasional = {c for c, count in color_counts.items() if count == 2}

    # Don't flag if there's a clear dominant palette
    if len(brand_colors) >= 3 and len(one_off) <= len(brand_colors):
        return findings  # Good: clear palette with few outliers

    # Flag only if there are many one-off colors with no clear palette
    if len(one_off) > 8 and len(brand_colors) < 3:
        findings.append(_make_finding(
            "color_inconsistency",
            "medium",
            f"No Clear Brand Palette ({len(brand_colors)} repeated, {len(one_off)} one-off colors): {url}",
            url, pid,
            f"{len(one_off)} colors used once, {len(brand_colors)} colors used ≥3 times — no dominant palette",
            "Establish 3-5 brand colors and apply them consistently; reduce one-off color usage",
        ))
    elif len(unique_colors) > 15:
        findings.append(_make_finding(
            "too_many_colors",
            "medium",
            f"Too Many Colors ({len(unique_colors)} unique, {len(brand_colors)} brand): {url}",
            url, pid,
            f"Found {len(unique_colors)} distinct colors — {len(brand_colors)} are used repeatedly",
            "Consolidate to a focused palette of 3-5 core brand colors",
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

    # Page intent classification
    from analyzers.ux_analyzer import _classify_page_intent, _get_cta_elements
    intent = _classify_page_intent(url, page.get("title", ""))

    # Use classified CTAs (excludes nav, informational, footer)
    ctas = _get_cta_elements(soup)
    cta_count = len(ctas)

    # Info pages don't need CTAs
    if intent == "info":
        return findings

    # ── Too Many CTAs: page-type dependent thresholds ────
    PAGE_TYPE_CTA_LIMITS = {
        "homepage": 15,
        "services": 10,
        "products": 12,
        "careers": 8,
        "education": 10,
        "research": 6,
        "blog": 5,
        "contact": 6,
        "courses": 8,
        "local_business": 8,
        "neutral": 10,
    }
    cta_limit = PAGE_TYPE_CTA_LIMITS.get(intent, 10)

    if cta_count > cta_limit:
        findings.append(_make_finding(
            "too_many_ctas",
            "medium",
            f"Too Many CTAs for {intent} page ({cta_count} CTAs, limit ~{cta_limit}): {url}",
            url, pid,
            f"{cta_count} action-oriented CTAs found — {intent} pages typically need {cta_limit} or fewer",
            f"Reduce to {max(3, cta_limit // 2)}-{cta_limit // 2 + 2} primary CTAs and hierarchy them by importance",
        ))

    # Weak CTA text: CTAs using generic or non-action-oriented text
    GENERIC_CTA_TEXT = {
        "click here", "here", "submit", "ok", "yes", "no", "continue",
        "learn more", "read more", "more", "link",
    }
    weak_ctas: list[str] = []
    for cta in ctas:
        btn_text = cta.get_text(strip=True).lower()
        if btn_text in GENERIC_CTA_TEXT or not btn_text:
            weak_ctas.append(btn_text or "(empty)")

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

    # ── No Primary CTA: visual prominence + position + style + page goal ──
    if cta_count >= 3:
        primary_candidates = []
        for cta in ctas:
            classes = " ".join(cta.get("class", [])).lower()
            text = cta.get_text(strip=True).lower()
            tag = cta.name

            prominence_score = 0

            # Button style prominence
            if any(p in classes for p in ("btn-primary", "primary", "hero", "main", "cta")):
                prominence_score += 3
            elif any(p in classes for p in ("btn", "button")):
                prominence_score += 2
            elif tag == "button":
                prominence_score += 2
            elif tag == "a" and any(p in classes for p in ("btn", "button", "cta")):
                prominence_score += 2

            # Size prominence
            if any(p in classes for p in ("large", "big", "lg", "xl", "hero")):
                prominence_score += 2

            # Position: first CTA or in hero section
            if cta == ctas[0]:
                prominence_score += 1
            parent_classes = " ".join(cta.parent.get("class", [])).lower() if cta.parent else ""
            if any(p in parent_classes for p in ("hero", "banner", "jumbotron", "above-fold")):
                prominence_score += 2

            # Conversion text
            conversion_words = {"buy", "sign up", "register", "apply", "contact", "subscribe",
                              "demo", "trial", "download", "get started", "start", "order", "hire"}
            if any(w in text for w in conversion_words):
                prominence_score += 1

            if prominence_score >= 3:
                primary_candidates.append(prominence_score)

        has_clear_primary = len(primary_candidates) > 0

        # Flag if no CTA stands out visually
        if not has_clear_primary and cta_count >= 5:
            findings.append(_make_finding(
                "no_primary_cta",
                "low",
                f"No Visually Prominent CTA ({cta_count} equal-looking CTAs): {url}",
                url, pid,
                "All CTAs appear equal in prominence — no clear primary call-to-action",
                "Designate one primary CTA with contrasting style, larger size, or prominent position",
            ))
        # Flag if multiple CTAs compete for primary (too many high-prominence)
        elif len(primary_candidates) >= 4 and cta_count >= 8:
            findings.append(_make_finding(
                "no_primary_cta",
                "low",
                f"Competing Primary CTAs ({len(primary_candidates)} prominent out of {cta_count}): {url}",
                url, pid,
                f"{len(primary_candidates)} CTAs have primary styling — no single clear focal point",
                "Keep one primary CTA prominent; de-emphasize others with secondary styling",
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

    # Check images without dimensions, accounting for CSS/responsive handling
    no_dimensions = []
    for img in images:
        has_html_dim = img.get("width") or img.get("height")
        if has_html_dim:
            continue

        # Check CSS inline for aspect-ratio, width, height
        style = (img.get("style") or "").lower().replace(" ", "")
        has_css_dimensions = any(p in style for p in (
            "aspect-ratio", "width:", "height:",
        ))

        # Check for responsive image patterns
        classes = " ".join(img.get("class", [])).lower()
        is_responsive = any(p in classes for p in (
            "img-fluid", "img-responsive", "responsive", "cover", "contain",
            "object-fit", "w-full", "h-full", "fill",
        ))

        # Check for srcset/sizes (responsive images handle their own sizing)
        has_srcset = img.has_attr("srcset") or img.has_attr("sizes")

        if not has_css_dimensions and not is_responsive and not has_srcset:
            no_dimensions.append(img)

    dim_pct = len(no_dimensions) / total * 100 if total else 0
    if dim_pct > 50:
        findings.append(_make_finding(
            "images_without_dimensions",
            "medium",
            f"Images Without Dimensions ({len(no_dimensions)}/{total} without HTML/CSS/srcset): {url}",
            url, pid,
            f"{len(no_dimensions)} of {total} images lack width/height, CSS dimensions, and responsive attributes",
            "Add width/height attributes, CSS aspect-ratio, or srcset to prevent layout shift (CLS)",
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
    """Check for inconsistent button styles and UI patterns across pages.
    
    Compare actual computed styles (size, radius, padding, typography, colors)
    instead of just counting buttons.
    """
    findings: list[dict] = []
    if len(pages) < 2:
        return findings

    # Collect button style signatures per page
    button_styles: list[tuple[dict, dict]] = []

    for page in pages:
        soup = _get_soup(page["url"], page_htmls)
        if not soup:
            continue

        btns = soup.find_all(["button", "a"])
        style_sigs = []
        for btn in btns:
            classes = " ".join(btn.get("class", [])).lower()
            is_button = ("btn" in classes or "button" in classes or
                        btn.name == "button" or
                        btn.get("role") == "button")
            if not is_button:
                continue

            # Extract style signature
            style = (btn.get("style") or "").lower().replace(" ", "")
            font_size = ""
            border_radius = ""
            padding = ""
            bg_color = ""
            text_color = ""

            for prop in ("font-size:", "border-radius:", "padding:", "background", "color:"):
                if prop in style:
                    idx = style.index(prop)
                    val = style[idx:idx+30].split(";")[0]
                    if prop == "font-size:":
                        font_size = val
                    elif prop == "border-radius:":
                        border_radius = val
                    elif prop == "padding:":
                        padding = val
                    elif prop == "background":
                        bg_color = val
                    elif prop == "color:":
                        text_color = val

            sig = {
                "tag": btn.name,
                "classes": " ".join(sorted(set(classes.split()))),
                "font_size": font_size,
                "border_radius": border_radius,
                "padding": padding,
                "bg_color": bg_color,
                "text_color": text_color,
            }
            style_sigs.append(sig)

        if style_sigs:
            button_styles.append((page, style_sigs))

    if len(button_styles) < 2:
        return findings

    # Compare button style signatures across pages
    all_sigs = []
    for page, sigs in button_styles:
        for sig in sigs:
            all_sigs.append(sig)

    if not all_sigs:
        return findings

    # Group by class signature (most reliable indicator)
    class_groups = {}
    for sig in all_sigs:
        key = sig["classes"]
        class_groups.setdefault(key, []).append(sig)

    # Find groups that appear across multiple pages
    cross_page_groups = {}
    for class_key, sigs in class_groups.items():
        if len(sigs) >= 2 and class_key:
            cross_page_groups[class_key] = sigs

    # Check for style variations within the same class group
    inconsistent = []
    for class_key, sigs in cross_page_groups.items():
        if len(sigs) < 3:
            continue

        # Check if there are style variations
        unique_styles = set()
        for sig in sigs:
            style_key = (sig["font_size"], sig["border_radius"], sig["padding"])
            unique_styles.add(style_key)

        if len(unique_styles) > 1:
            inconsistent.append((class_key, len(sigs), len(unique_styles)))

    if inconsistent:
        samples = "; ".join(f'"{k}" ({n}×, {v} variants)' for k, n, v in inconsistent[:3])
        findings.append(_make_finding(
            "inconsistent_button_styles",
            "medium",
            f"Inconsistent Button Styles ({len(inconsistent)} class groups with variants): {pages[0]['url']}",
            pages[0]["url"], pages[0]["id"],
            f"Button class groups have style variations: {samples}",
            "Standardize button styles (size, radius, padding) for each variant across all pages",
        ))

    # Mixed UI patterns: some pages use <nav>, others don't
    nav_counts = []
    for page in pages:
        soup = _get_soup(page["url"], page_htmls)
        if soup:
            nav_counts.append((page, len(soup.find_all("nav"))))

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
    fast_mode: bool = False,
) -> tuple[list[dict], dict]:
    """Run UI checks across all pages, with reduced scope in fast mode.

    Args:
        scan_id: The scan identifier.
        pages: List of page dicts from the database.
        page_htmls: Mapping of URL → parsed BeautifulSoup.
        ux_data: UX data including rendered_styles from Playwright.

    Returns:
        (findings, {"visual_hierarchy_score": avg_score, "vh_breakdown": avg_breakdown})
    """
    findings: list[dict] = []
    vh_scores = []
    vh_breakdowns = []

    # Per-page checks
    for page in pages:
        soup = _get_soup(page["url"], page_htmls)
        if not soup:
            continue

        rendered = ux_data.get(page["url"], {}).get("rendered_styles", {})
        vh_findings, vh_result = _check_visual_hierarchy(page, soup, rendered)
        findings.extend(vh_findings)
        vh_scores.append(vh_result["visual_hierarchy_score"])
        vh_breakdowns.append(vh_result["vh_breakdown"])

        findings.extend(_check_typography(page, soup))
        findings.extend(_check_color_consistency(page, soup))
        findings.extend(_check_spacing_layout(page, soup))
        if not fast_mode:
            findings.extend(_check_cta_design(page, soup))
            findings.extend(_check_overall_polish(page, soup))
        findings.extend(_check_imagery(page, soup))

    # Cross-page checks
    if not fast_mode:
        findings.extend(_check_component_consistency(pages, page_htmls))

    # Average visual hierarchy score across all pages
    avg_vh = round(sum(vh_scores) / len(vh_scores)) if vh_scores else 50
    avg_breakdown = {}
    if vh_breakdowns:
        all_keys = set()
        for bd in vh_breakdowns:
            all_keys.update(bd.keys())
        for k in all_keys:
            vals = [bd.get(k, 0) for bd in vh_breakdowns]
            avg_breakdown[k] = round(sum(vals) / len(vals), 1)

    return findings, {
        "visual_hierarchy_score": avg_vh,
        "vh_breakdown": avg_breakdown,
        "checked_categories": UI_WEIGHTS.keys(),
    }
