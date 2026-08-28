"""Weighted scoring engine for UI, UX and SEO audit findings.

UI Scoring (100 points), UX Scoring (100 points), SEO Scoring (100 points)
are combined into an overall score: overall = ui * 0.3 + ux * 0.3 + seo * 0.4.
"""

# ─── UI Scoring Weights (total = 100) ──────────────────────
# 5 categories per industry-standard UI audit:
#   visual_hierarchy    20%  — headings, H1, section separation, above-fold
#   layout_spacing      20%  — margins, padding, alignment, overflow, responsive
#   typography_color    15%  — fonts, sizes, color contrast, readability
#   components          20%  — buttons, cards, images, visual clutter
#   usability           25%  — CTAs, interactions, forms, keyboard, tap targets

UI_WEIGHTS = {
    "visual_hierarchy": 20,
    "layout_spacing": 20,
    "typography_color": 15,
    "components": 20,
    "usability": 25,
}

# ─── UX Scoring Weights (total = 100) ──────────────────────

UX_WEIGHTS = {
    "navigation": 20,
    "content_clarity": 15,
    "cta_user_flow": 15,
    "interaction_quality": 15,
    "forms": 10,
    "mobile_ux": 10,
    "accessibility": 15,
}

# ─── UI Check → Category ───────────────────────────────────
# Maps every check_name emitted by ui_analyzer.py to its category.
# Unmapped checks fall back to "components" in _score_categories().

UI_CHECK_TO_CATEGORY = {
    # ── VISUAL HIERARCHY (20%) ─────────────────────────────
    # H1 / heading structure
    "no_h1_found": "visual_hierarchy",
    "heading_count_imbalance": "visual_hierarchy",
    # Overall hierarchy scoring (multiple severity variants)
    "weak_visual_hierarchy": "visual_hierarchy",

    # ── LAYOUT & SPACING (20%) ─────────────────────────────
    "crowded_layout": "layout_spacing",
    "excessive_whitespace": "layout_spacing",

    # ── TYPOGRAPHY & COLOR (15%) ───────────────────────────
    # Typography
    "small_text_detected": "typography_color",
    "excessive_font_variations": "typography_color",
    "inconsistent_font_sizes": "typography_color",
    # Color
    "color_inconsistency": "typography_color",
    "too_many_colors": "typography_color",

    # ── COMPONENTS & CONSISTENCY (20%) ─────────────────────
    "inconsistent_button_styles": "components",
    "mixed_ui_patterns": "components",
    "broken_images": "components",
    "no_alt_text_images": "components",
    "images_without_dimensions": "components",
    "visual_clutter": "components",
    "no_favicon": "components",

    # ── USABILITY & INTERACTION (25%) ──────────────────────
    "too_many_ctas": "usability",
    "weak_cta_text": "usability",
    "no_primary_cta": "usability",
    "missing_meta_viewport": "usability",
}

# ─── UX Check → Category ───────────────────────────────────

UX_CHECK_TO_CATEGORY = {
    "confusing_navigation": "navigation",
    "deep_nesting": "navigation",
    "no_search_functionality": "navigation",
    "breadcrumb_missing": "navigation",
    "unclear_information_architecture": "navigation",
    "poor_content_readability": "content_clarity",
    "information_overload": "content_clarity",
    "wall_of_text": "content_clarity",
    "content_not_scannable": "content_clarity",
    "no_clear_value_proposition": "content_clarity",
    "weak_cta_hierarchy": "cta_user_flow",
    "competing_ctas": "cta_user_flow",
    "no_primary_cta": "cta_user_flow",
    "dead_end_pages": "cta_user_flow",
    "confusing_user_flow": "cta_user_flow",
    "missing_hover_states": "interaction_quality",
    "no_loading_feedback": "interaction_quality",
    "broken_interactions": "interaction_quality",
    "missing_keyboard_navigation": "interaction_quality",
    "no_error_recovery": "interaction_quality",
    "forms_without_labels": "forms",
    "excessive_form_fields": "forms",
    "no_form_validation": "forms",
    "confusing_form_layout": "forms",
    "missing_required_indicators": "forms",
    "poor_mobile_responsive": "mobile_ux",
    "touch_targets_too_small": "mobile_ux",
    "horizontal_scroll_mobile": "mobile_ux",
    "mobile_menu_poor": "mobile_ux",
    "pinch_to_zoom_disabled": "mobile_ux",
    "missing_aria_labels": "accessibility",
    "poor_color_contrast": "accessibility",
    "missing_alt_text": "accessibility",
    "keyboard_trap": "accessibility",
    "missing_focus_indicators": "accessibility",
    "missing_skip_navigation": "accessibility",
}

# ─── SEO Scoring Weights (total = 100) ─────────────────────
# 6 categories per industry-standard SEO audit structure:
#   technical  25%  — crawling, indexing, infrastructure
#   onpage     30%  — titles, descriptions, headings, images, OG/social
#   content    15%  — content quality, relevance, depth
#   schema     10%  — structured data / JSON-LD
#   performance 15% — Core Web Vitals (LCP, CLS, TTFB)
#   mobile      5%  — mobile viewport, mobile-friendliness

SEO_WEIGHTS = {
    "technical": 25,
    "onpage": 30,
    "content": 15,
    "schema": 10,
    "performance": 15,
    "mobile": 5,
}

# ─── SEO Check → Category ──────────────────────────────────
# Maps every check_name emitted by seo_checker.py to its category.
# Unmapped checks fall back to "onpage" in _score_categories().

SEO_CHECK_TO_CATEGORY = {
    # ── TECHNICAL (25%) ────────────────────────────────────
    # HTTPS
    "missing_ssl": "technical",
    # canonical
    "missing_canonical": "technical",
    "empty_canonical": "technical",
    "invalid_canonical": "technical",
    "canonical_wrong_domain": "technical",
    "canonical_not_self_referencing": "technical",
    "canonical_url_mismatch": "technical",
    "canonical_noindex_conflict": "technical",
    # robots / sitemap
    "missing_robots_txt": "technical",
    "blocked_robots_txt": "technical",
    "error_robots_txt": "technical",
    "missing_sitemap": "technical",
    "blocked_sitemap": "technical",
    "error_sitemap": "technical",
    "no_sitemap_in_robots": "technical",
    "declared_sitemap_not_found": "technical",
    "declared_sitemap_error": "technical",
    "declared_sitemap_unreachable": "technical",
    "large_sitemap_index": "technical",
    # indexability / noindex / nofollow
    "meta_noindex": "technical",
    "meta_nofollow": "technical",
    "meta_nosnippet": "technical",
    "meta_max_snippet_zero": "technical",
    "x_robots_noindex": "technical",
    "internal_nofollow_links": "technical",
    # redirects / crawl
    "redirect_chain": "technical",
    "crawl_failed": "technical",
    "crawl_access_blocked": "technical",
    "page_not_found": "technical",
    "server_error": "technical",
    "crawl_error": "technical",
    # links
    "broken_link": "technical",
    "orphan_pages": "technical",
    "deep_link_depth": "technical",
    "excessive_link_depth": "technical",
    "thin_internal_links": "technical",

    # ── ON-PAGE (30%) ──────────────────────────────────────
    # title
    "missing_title": "onpage",
    "duplicate_title": "onpage",
    "long_title": "onpage",
    "short_title": "onpage",
    "title_no_keyword_relevance": "onpage",
    "weak_title_ctr": "onpage",
    "title_keyword_stuffing": "onpage",
    # meta description
    "missing_meta_description": "onpage",
    "duplicate_meta_description": "onpage",
    "long_meta_description": "onpage",
    "short_meta_description": "onpage",
    "desc_no_keyword_relevance": "onpage",
    "weak_desc_ctr": "onpage",
    "desc_keyword_stuffing": "onpage",
    # headings
    "missing_h1": "onpage",
    "multiple_h1s": "onpage",
    "heading_order_broken": "onpage",
    "repeated_headings": "onpage",
    "empty_headings": "onpage",
    "missing_h2": "onpage",
    # images
    "images_missing_alt": "onpage",
    "generic_alt_text": "onpage",
    "large_images": "onpage",
    # links
    "non_descriptive_link_text": "onpage",
    # open graph / social
    "missing_open_graph": "onpage",
    "incomplete_open_graph": "onpage",
    "weak_og_title": "onpage",
    "weak_og_description": "onpage",
    "invalid_og_image": "onpage",
    "og_title_not_customized": "onpage",
    "og_description_not_customized": "onpage",
    "missing_og_type": "onpage",
    "missing_twitter_card": "onpage",
    "invalid_twitter_card_type": "onpage",
    "missing_twitter_title": "onpage",
    "missing_twitter_description": "onpage",
    "missing_twitter_image": "onpage",
    "missing_twitter_site": "onpage",

    # ── CONTENT (15%) ──────────────────────────────────────
    "duplicate_content": "content",
    "low_title_content_relevance": "content",
    "thin_content_page": "content",
    "short_content_page": "content",
    "scattered_topic": "content",

    # ── SCHEMA (10%) ───────────────────────────────────────
    "no_structured_data": "schema",
    "invalid_schema": "schema",
    "schema_no_type": "schema",
    "schema_wrong_type": "schema",
    "schema_incomplete": "schema",
    "schema_empty_values": "schema",

    # ── PERFORMANCE (15%) ──────────────────────────────────
    "poor_lcp": "performance",
    "slow_lcp": "performance",
    "high_avg_lcp": "performance",
    "poor_cls": "performance",
    "moderate_cls": "performance",
    "high_avg_cls": "performance",
    "slow_page_speed": "performance",

    # ── MOBILE (5%) ────────────────────────────────────────
    "missing_viewport": "mobile",
    "mobile_unfriendly": "mobile",
}

# ─── Duplicate Issue Groups ────────────────────────────────
# Same underlying issue detected by multiple analyzers.
# Canonical = scored. Duplicates = visible in report but NOT penalized.

DUPLICATE_GROUPS = {
    "images_missing_alt": {"no_alt_text_images", "missing_alt_text", "image_missing_alt"},
}

# Build flat set of all duplicate (non-canonical) check names
_DUPLICATE_CHECKS: set = set()
for canonical, dupes in DUPLICATE_GROUPS.items():
    _DUPLICATE_CHECKS.update(dupes - {canonical})

# ─── Check names excluded from scoring (informational only) ──
# These findings appear in the report but don't penalize scores.
# Recommendation-level: things to consider, not errors.

SEO_SCORING_IGNORE = {
    # canonical — informational only (not every page needs self-ref canonical)
    "missing_canonical",
    "empty_canonical",
    "canonical_url_mismatch",

    # weak CTR — not a reliable SEO rule
    "weak_title_ctr",
    "weak_desc_ctr",

    # schema — missing schema is not an error for every page
    "no_structured_data",

    # OG customization — same as <title> is fine, customization is optional
    "og_title_not_customized",
    "og_description_not_customized",

    # twitter/social — social metadata, not SEO-critical
    "missing_twitter_site",
    "missing_twitter_title",
    "missing_twitter_description",
    "missing_twitter_image",
    "missing_og_type",

    # content — experimental metrics
    "scattered_topic",
    "short_content_page",

    # technical — informational
    "meta_nosnippet",
    "meta_max_snippet_zero",
    "large_sitemap_index",
    "no_sitemap_in_robots",
    "blocked_robots_txt",
    "blocked_sitemap",
    "error_robots_txt",
    "error_sitemap",
    "deep_link_depth",
    "thin_internal_links",
}

# ─── Per-Check Custom Penalties (overrides severity-based) ──
# key = check_name, value = penalty points (0 = no penalty)
# Severity reference: critical=10, high=5, medium=3, low=1

SEO_CHECK_PENALTIES = {
    # ── TECHNICAL ──────────────────────────────────────────
    # Critical — directly blocks indexing / crawling
    "missing_ssl": 10,
    "canonical_noindex_conflict": 10,
    "meta_noindex": 10,
    "crawl_failed": 10,
    "crawl_access_blocked": 10,
    "page_not_found": 8,
    "server_error": 8,
    "crawl_error": 8,
    # High
    "canonical_wrong_domain": 5,
    "canonical_not_self_referencing": 5,
    "meta_nofollow": 5,
    "internal_nofollow_links": 5,
    "broken_link": 5,
    "redirect_chain": 5,
    "missing_robots_txt": 5,
    "missing_sitemap": 5,
    # Medium
    "x_robots_noindex": 3,
    "orphan_pages": 3,
    "excessive_link_depth": 3,
    "declared_sitemap_not_found": 3,
    "declared_sitemap_error": 3,
    "declared_sitemap_unreachable": 3,
    # Low
    "deep_link_depth": 1,
    "thin_internal_links": 1,

    # ── ON-PAGE ────────────────────────────────────────────
    # Critical — directly impacts ranking
    "missing_title": 10,
    "missing_meta_description": 8,
    "missing_h1": 10,
    # High
    "duplicate_title": 5,
    "duplicate_meta_description": 5,
    "title_keyword_stuffing": 5,
    "desc_keyword_stuffing": 5,
    "images_missing_alt": 5,
    "missing_open_graph": 3,
    # Medium
    "multiple_h1s": 3,
    "heading_order_broken": 3,
    "repeated_headings": 3,
    "long_title": 3,
    "short_title": 3,
    "long_meta_description": 3,
    "short_meta_description": 3,
    "generic_alt_text": 3,
    "large_images": 3,
    "non_descriptive_link_text": 3,
    "incomplete_open_graph": 3,
    "invalid_og_image": 3,
    "missing_twitter_card": 3,
    "invalid_twitter_card_type": 3,
    "missing_h2": 3,
    # Low
    "empty_headings": 1,
    "title_no_keyword_relevance": 1,
    "desc_no_keyword_relevance": 1,
    "weak_og_title": 1,
    "weak_og_description": 1,

    # ── CONTENT ────────────────────────────────────────────
    # High
    "duplicate_content": 5,
    "low_title_content_relevance": 5,
    "thin_content_page": 5,

    # ── SCHEMA ─────────────────────────────────────────────
    # Medium — nice to have, not critical
    "invalid_schema": 3,
    "schema_no_type": 3,
    "schema_incomplete": 3,
    "schema_empty_values": 3,
    # Low
    "schema_wrong_type": 1,

    # ── PERFORMANCE ────────────────────────────────────────
    # High
    "poor_lcp": 5,
    "poor_cls": 5,
    "slow_page_speed": 5,
    # Medium
    "slow_lcp": 3,
    "high_avg_lcp": 3,
    "moderate_cls": 3,
    "high_avg_cls": 3,

    # ── MOBILE ─────────────────────────────────────────────
    # Critical
    "missing_viewport": 5,
    # High
    "mobile_unfriendly": 5,
}

# ─── Severity Penalties ────────────────────────────────────

SEVERITY_PENALTY = {
    "critical": 25,
    "error": 20,
    "high": 15,
    "warning": 8,
    "medium": 8,
    "low": 4,
    "info": 0,  # info = not an issue, no penalty
}

SEVERITY_KEYS = ("critical", "high", "warning", "medium", "low", "info")

SEVERITY_RANK = {"critical": 4, "high": 3, "warning": 2, "medium": 2, "low": 1, "info": 0}

# ─── Scoring Ignore Sets (informational only, no penalty) ──

UI_SCORING_IGNORE = {
    "no_favicon",  # Nice to have, not a UI issue
}

UX_SCORING_IGNORE = {
    "no_loading_feedback",  # Not tested from static HTML
}

# ─── UI Per-Check Penalties (overrides severity-based) ─────
# Severity reference: critical=10, high=6, medium=3, low=1

UI_CHECK_PENALTIES = {
    # ── VISUAL HIERARCHY ───────────────────────────────────
    # Critical — H1 is essential
    "no_h1_found": 10,
    # High
    "heading_count_imbalance": 6,
    "weak_visual_hierarchy": 6,

    # ── LAYOUT & SPACING ──────────────────────────────────
    # Medium
    "crowded_layout": 3,
    # Low
    "excessive_whitespace": 1,

    # ── TYPOGRAPHY & COLOR ────────────────────────────────
    # Medium
    "small_text_detected": 3,
    "excessive_font_variations": 3,
    "color_inconsistency": 3,
    "too_many_colors": 3,
    # Low
    "inconsistent_font_sizes": 1,

    # ── COMPONENTS & CONSISTENCY ──────────────────────────
    # High
    "broken_images": 6,
    # Medium
    "inconsistent_button_styles": 3,
    "mixed_ui_patterns": 3,
    "no_alt_text_images": 3,
    "visual_clutter": 3,
    # Low
    "images_without_dimensions": 1,

    # ── USABILITY & INTERACTION ───────────────────────────
    # High
    "no_primary_cta": 6,
    "missing_meta_viewport": 6,
    # Medium
    "too_many_ctas": 3,
    "weak_cta_text": 3,
}


# ─── Architecture: Validation + Aggregation + Confidence ──

def compute_finding_confidence(finding: dict, total_pages: int) -> float:
    """Compute confidence (0.0–1.0) that this finding is a real issue.
    
    Factors:
    - Severity: higher severity = higher confidence
    - Page coverage: more pages affected = higher confidence (consistent pattern)
    - One-off low-severity findings get lower confidence
    - Detection method: heuristic checks get lower max confidence
    """
    severity = finding.get("severity", "info")
    sev_rank = SEVERITY_RANK.get(severity, 0)

    # Base confidence from severity
    base = 0.5 + (sev_rank * 0.125)  # info=0.5, low=0.625, medium=0.75, high=0.875, critical=1.0

    # Page coverage boost (findings on more pages = more confident)
    affected = finding.get("affected_pages", 1)
    if total_pages > 0:
        coverage = affected / total_pages
    else:
        coverage = 0
    coverage_boost = min(0.2, coverage * 0.3)

    # One-off penalty: single low-severity finding on 1 page = less confident
    one_off_penalty = 0
    if severity in ("low", "info") and affected == 1 and total_pages > 2:
        one_off_penalty = 0.15

    # Detection method cap: heuristic/DOM-diff checks are less reliable
    check_name = finding.get("check_name", "")
    HEURISTIC_CHECKS = {
        "broken_interactions", "confusing_navigation", "confusing_user_flow",
        "unclear_information_architecture", "no_clear_value_proposition",
        "wall_of_text", "content_not_scannable", "information_overload",
        "dead_end_pages", "weak_cta_hierarchy",
    }
    max_confidence = 1.0
    if check_name in HEURISTIC_CHECKS:
        max_confidence = 0.8  # Cap for heuristic checks

    confidence = base + coverage_boost - one_off_penalty
    return round(max(0.1, min(max_confidence, confidence)), 2)


def compute_finding_penalty(finding: dict, check_penalty: float = None) -> float:
    """Compute score penalty for a finding based on check-specific or severity-based penalty.
    
    Priority:
      1. check_penalty (from SEO_CHECK_PENALTIES / UI / UX check_penalties) — most accurate
      2. SEVERITY_PENALTY[severity] — fallback when no custom penalty defined
    
    Violation multiplier is very gentle — scale only:
      1 issue = 1.0×, 10 = 1.1×, 100 = 1.2×
    """
    severity = finding.get("severity", "info")
    confidence = finding.get("confidence", 0.8)
    violations = finding.get("total_violations", 1)

    # Use check-specific penalty if available, otherwise fall back to severity
    if check_penalty is not None:
        base_penalty = check_penalty
    else:
        base_penalty = SEVERITY_PENALTY.get(severity, 0)

    # Very gentle diminishing returns: log2 scale
    # 1 = 1.0×, 10 = 1.1×, 100 = 1.2×
    import math
    violation_factor = 1.0 + math.log2(max(1, violations)) * 0.03

    penalty = base_penalty * confidence * violation_factor
    return round(penalty, 2)


def validate_findings(findings: list[dict]) -> list[dict]:
    """Step 1: Filter out false positives and non-issues.
    
    Removes:
    - info severity (informational, not issues)
    - findings in scoring_ignore sets
    - duplicate findings (from DUPLICATE_GROUPS)
    """
    validated = []
    for f in findings:
        severity = f.get("severity", "info")

        # Skip info-level findings (not issues)
        if severity == "info":
            continue

        # Skip known duplicates
        check_name = f.get("check_name", "")
        if check_name in _DUPLICATE_CHECKS:
            continue

        validated.append(f)
    return validated


def aggregate_findings(findings: list[dict], total_pages: int,
                       check_penalties: dict = None) -> list[dict]:
    """Step 2: Aggregate same-issue findings across pages into single enriched findings.
    
    Groups by check_name. For each group:
    - affected_pages: count of unique pages
    - total_violations: sum of all instances
    - severity: highest severity across all instances
    - confidence: computed from severity + page coverage
    - penalty: computed using check-specific penalty (if available) or severity fallback
    
    check_penalties: optional dict mapping check_name → custom penalty (e.g. SEO_CHECK_PENALTIES).
    Returns list of enriched finding dicts (one per unique check_name).
    """
    groups: dict[str, list[dict]] = {}
    for f in findings:
        check_name = f.get("check_name", "")
        groups.setdefault(check_name, []).append(f)

    aggregated = []
    for check_name, group in groups.items():
        # Highest severity across all instances
        max_sev = max(group, key=lambda x: SEVERITY_RANK.get(x.get("severity", "info"), 0))
        severity = max_sev.get("severity", "info")

        # Aggregate counts
        affected_pages = len(set(f.get("page_id") for f in group if f.get("page_id")))
        if affected_pages == 0:
            affected_pages = len(group)  # Fallback: count findings as pages
        total_violations = len(group)

        # Get a representative message and recommendation
        sample = group[0]

        enriched = {
            "check_name": check_name,
            "severity": severity,
            "message": sample.get("message", ""),
            "recommendation": sample.get("recommendation", ""),
            "url": sample.get("url", ""),
            "page_id": sample.get("page_id"),
            "affected_pages": affected_pages,
            "total_violations": total_violations,
        }

        # Compute confidence and penalty
        enriched["confidence"] = compute_finding_confidence(enriched, total_pages)

        # Use check-specific penalty if available
        custom_penalty = check_penalties.get(check_name) if check_penalties else None
        enriched["penalty"] = compute_finding_penalty(enriched, check_penalty=custom_penalty)

        aggregated.append(enriched)

    return aggregated


def _grade(score: int) -> str:
    if score >= 85:
        return "Excellent"
    if score >= 70:
        return "Good"
    if score >= 55:
        return "Average"
    if score >= 40:
        return "Needs Improvement"
    return "Poor"


def _score_categories(
    findings: list[dict],
    check_to_category: dict[str, int],
    weights: dict[str, int],
    scoring_ignore: set = None,
    check_penalties: dict[str, int] = None,
) -> tuple[dict[str, int], dict[str, dict[str, int]]]:
    """Score findings against a weighted category map.
    
    Supports both raw findings and enriched findings (with 'penalty' field).
    If finding has 'penalty' field, use it directly. Otherwise fall back to
    per-check or severity-based penalties.
    
    scoring_ignore: check names that appear in report but don't penalize scores.
    check_penalties: per-check custom penalties (overrides severity-based penalty).
    Duplicate findings (from DUPLICATE_GROUPS) are visible but NOT penalized.
    Returns (category_scores, category_severity_counts).
    """
    cat_counts: dict[str, dict[str, int]] = {cat: {s: 0 for s in SEVERITY_KEYS} for cat in weights}

    for f in findings:
        check_name = f.get("check_name", "")
        if scoring_ignore and check_name in scoring_ignore:
            continue
        cat = check_to_category.get(check_name)
        if not cat:
            continue
        severity = f.get("severity", "info")
        if severity in cat_counts[cat]:
            cat_counts[cat][severity] += 1

    category_scores: dict[str, int] = {}
    cat_penalties: dict[str, int] = {cat: 0 for cat in weights}

    # Deduplicate: each unique check_name contributes its penalty ONCE
    seen_checks: set = set()
    for f in findings:
        check_name = f.get("check_name", "")
        if scoring_ignore and check_name in scoring_ignore:
            continue
        if check_name in seen_checks:
            continue
        cat = check_to_category.get(check_name)
        if not cat:
            continue
        seen_checks.add(check_name)

        # Priority: check_penalties > pre-computed penalty > severity fallback
        if check_penalties and check_name in check_penalties:
            cat_penalties[cat] += check_penalties[check_name]
        elif "penalty" in f:
            cat_penalties[cat] += f["penalty"]
        else:
            sev = f.get("severity", "info")
            cat_penalties[cat] += SEVERITY_PENALTY.get(sev, 0)

    for cat in weights:
        category_scores[cat] = max(0, min(100, 100 - cat_penalties[cat]))

    return category_scores, cat_counts


def _weighted_total(category_scores: dict[str, int], weights: dict[str, int],
                    checked_categories: set = None) -> int:
    """Weighted total across categories.
    
    checked_categories: set of categories that were actually evaluated.
    Categories NOT in this set are N/A and excluded from weighted total.
    If None, all categories are considered checked.
    """
    total_weight = 0
    weighted = 0
    for cat, w in weights.items():
        if checked_categories is not None and cat not in checked_categories:
            continue
        total_weight += w
        weighted += category_scores[cat] * w
    if total_weight == 0:
        return 100
    return max(0, min(100, round(weighted / total_weight)))


def _count_by_severity(findings: list[dict]) -> dict[str, int]:
    counts = {s: 0 for s in SEVERITY_KEYS}
    for f in findings:
        sev = f.get("severity", "info")
        if sev in counts:
            counts[sev] += 1
    return counts


def compute_ui_score(ui_findings: list[dict], vh_score: int = None,
                     checked_categories: set = None) -> dict:
    """Score UI findings against the UI category weights.

    If vh_score is provided, it overrides the findings-based visual_hierarchy score.
    Categories not in checked_categories are N/A and excluded from weighted total.

    Returns dict with keys:
        ui_score, category_scores, total_issues, by_severity, grade
    """
    category_scores, cat_counts = _score_categories(
        ui_findings, UI_CHECK_TO_CATEGORY, UI_WEIGHTS,
        scoring_ignore=UI_SCORING_IGNORE, check_penalties=UI_CHECK_PENALTIES)
    
    if vh_score is not None:
        category_scores["visual_hierarchy"] = max(0, min(100, vh_score))
    
    ui_score = _weighted_total(category_scores, UI_WEIGHTS, checked_categories)
    by_severity = _count_by_severity(ui_findings)

    return {
        "ui_score": ui_score,
        "category_scores": category_scores,
        "total_issues": len(ui_findings),
        "by_severity": by_severity,
        "grade": _grade(ui_score),
    }


def compute_ux_score(ux_findings: list[dict], checked_categories: set = None) -> dict:
    """Score UX findings against the UX category weights.
    
    Categories not in checked_categories are N/A and excluded from weighted total.

    Returns dict with keys:
        ux_score, category_scores, total_issues, by_severity, grade
    """
    category_scores, cat_counts = _score_categories(
        ux_findings, UX_CHECK_TO_CATEGORY, UX_WEIGHTS,
        scoring_ignore=UX_SCORING_IGNORE)
    ux_score = _weighted_total(category_scores, UX_WEIGHTS, checked_categories)
    by_severity = _count_by_severity(ux_findings)

    return {
        "ux_score": ux_score,
        "category_scores": category_scores,
        "total_issues": len(ux_findings),
        "by_severity": by_severity,
        "grade": _grade(ux_score),
    }


def compute_seo_score(seo_findings: list[dict], checked_categories: set = None) -> dict:
    """Score SEO findings against the SEO category weights.
    
    Categories with 0 findings are N/A and excluded from weighted total.

    Returns dict with keys:
        seo_score, category_scores, total_issues, by_severity, grade
    """
    category_scores, cat_counts = _score_categories(seo_findings, SEO_CHECK_TO_CATEGORY, SEO_WEIGHTS,
                                           scoring_ignore=SEO_SCORING_IGNORE, check_penalties=SEO_CHECK_PENALTIES)
    cat_finding_counts = {cat: sum(counts.values()) for cat, counts in cat_counts.items()}
    seo_score = _weighted_total(category_scores, SEO_WEIGHTS, checked_categories)
    by_severity = _count_by_severity(seo_findings)

    return {
        "seo_score": seo_score,
        "category_scores": category_scores,
        "total_issues": len(seo_findings),
        "by_severity": by_severity,
        "grade": _grade(seo_score),
    }


def compute_overall_score(ui_score: int, ux_score: int, seo_score: int = 0, mobile_score: int = 0, missing_features_score: int = 0, cta_score: int = 0, security_score: int = 0) -> dict:
    """Combine all scores into an overall score.

    Formula: overall = ui*0.12 + ux*0.12 + seo*0.18 + mobile*0.14 + missing_features*0.18 + cta*0.12 + security*0.14

    Returns dict with keys:
        overall_score, grade
    """
    overall_score = round(ui_score * 0.12 + ux_score * 0.12 + seo_score * 0.18 + mobile_score * 0.14 + missing_features_score * 0.18 + cta_score * 0.12 + security_score * 0.14)
    overall_score = max(0, min(100, overall_score))

    return {
        "overall_score": overall_score,
        "grade": _grade(overall_score),
    }
