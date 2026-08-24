"""Weighted scoring engine for UI, UX and SEO audit findings.

UI Scoring (100 points), UX Scoring (100 points), SEO Scoring (100 points)
are combined into an overall score: overall = ui * 0.3 + ux * 0.3 + seo * 0.4.
"""

# ─── UI Scoring Weights (total = 100) ──────────────────────

UI_WEIGHTS = {
    "visual_hierarchy": 20,
    "typography": 10,
    "color_consistency": 10,
    "spacing_layout": 15,
    "component_consistency": 15,
    "cta_design": 10,
    "imagery": 10,
    "overall_polish": 10,
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

UI_CHECK_TO_CATEGORY = {
    "weak_visual_hierarchy": "visual_hierarchy",
    "heading_count_imbalance": "visual_hierarchy",
    "no_h1_found": "visual_hierarchy",
    "inconsistent_font_sizes": "typography",
    "small_text_detected": "typography",
    "excessive_font_variations": "typography",
    "color_inconsistency": "color_consistency",
    "low_contrast_detected": "color_consistency",
    "too_many_colors": "color_consistency",
    "crowded_layout": "spacing_layout",
    "excessive_whitespace": "spacing_layout",
    "tight_line_spacing": "spacing_layout",
    "inconsistent_margins": "spacing_layout",
    "inconsistent_button_styles": "component_consistency",
    "inconsistent_card_styles": "component_consistency",
    "mixed_ui_patterns": "component_consistency",
    "too_many_ctas": "cta_design",
    "weak_cta_text": "cta_design",
    "cta_placement_poor": "cta_design",
    "no_alt_text_images": "imagery",
    "broken_images": "imagery",
    "images_without_dimensions": "imagery",
    "visual_clutter": "overall_polish",
    "no_favicon": "overall_polish",
    "missing_meta_viewport": "overall_polish",
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

SEO_WEIGHTS = {
    "meta_tags": 20,
    "headings": 20,
    "content": 15,
    "images": 15,
    "links": 15,
    "technical": 15,
}

# ─── SEO Check → Category ──────────────────────────────────

SEO_CHECK_TO_CATEGORY = {
    "missing_title": "meta_tags",
    "duplicate_title": "meta_tags",
    "long_title": "meta_tags",
    "short_title": "meta_tags",
    "title_no_keyword_relevance": "meta_tags",
    "weak_title_ctr": "meta_tags",
    "title_keyword_stuffing": "meta_tags",
    "missing_meta_description": "meta_tags",
    "duplicate_meta_description": "meta_tags",
    "long_meta_description": "meta_tags",
    "short_meta_description": "meta_tags",
    "desc_no_keyword_relevance": "meta_tags",
    "weak_desc_ctr": "meta_tags",
    "desc_keyword_stuffing": "meta_tags",
    "missing_canonical": "meta_tags",
    "empty_canonical": "meta_tags",
    "canonical_wrong_domain": "meta_tags",
    "canonical_not_self_referencing": "meta_tags",
    "canonical_url_mismatch": "meta_tags",
    "duplicate_canonical": "meta_tags",
    "missing_h1": "headings",
    "multiple_h1": "headings",
    "heading_order_broken": "headings",
    "missing_h2": "headings",
    "repeated_headings": "headings",
    "empty_headings": "headings",
    "thin_content": "content",
    "duplicate_content": "content",
    "keyword_stuffing": "content",
    "non_descriptive_link_text": "content",
    "low_title_content_relevance": "content",
    "thin_content_page": "content",
    "short_content_page": "content",
    "scattered_topic": "content",
    "images_missing_alt": "images",
    "generic_alt_text": "images",
    "images_duplicate_alt": "images",
    "large_images": "images",
    "broken_links": "links",
    "external_nofollow_links": "links",
    "orphan_pages": "links",
    "deep_link_depth": "links",
    "excessive_link_depth": "links",
    "thin_internal_links": "links",
    "no_structured_data": "technical",
    "invalid_schema": "technical",
    "schema_no_type": "technical",
    "schema_wrong_type": "technical",
    "schema_incomplete": "technical",
    "schema_empty_values": "technical",
    "missing_robots_txt": "technical",
    "missing_sitemap": "technical",
    "blocked_robots_txt": "technical",
    "blocked_sitemap": "technical",
    "error_robots_txt": "technical",
    "error_sitemap": "technical",
    "no_sitemap_in_robots": "technical",
    "declared_sitemap_not_found": "technical",
    "declared_sitemap_error": "technical",
    "declared_sitemap_unreachable": "technical",
    "large_sitemap_index": "technical",
    "poor_lcp": "technical",
    "slow_lcp": "technical",
    "high_avg_lcp": "technical",
    "poor_cls": "technical",
    "moderate_cls": "technical",
    "high_avg_cls": "technical",
    "slow_page_speed": "technical",
    "mobile_unfriendly": "technical",
    "missing_ssl": "technical",
    "crawl_error": "technical",
    "server_error": "technical",

    # indexability
    "meta_noindex": "technical",
    "meta_nofollow": "technical",
    "meta_nosnippet": "technical",
    "meta_max_snippet_zero": "technical",
    "x_robots_noindex": "technical",
    "canonical_noindex_conflict": "technical",
    "internal_nofollow_links": "technical",
    "redirect_chain": "technical",

    # open graph / social
    "missing_open_graph": "meta_tags",
    "incomplete_open_graph": "meta_tags",
    "weak_og_title": "meta_tags",
    "weak_og_description": "meta_tags",
    "invalid_og_image": "meta_tags",
    "og_title_not_customized": "meta_tags",
    "og_description_not_customized": "meta_tags",
    "missing_og_type": "meta_tags",
    "missing_twitter_card": "meta_tags",
    "invalid_twitter_card_type": "meta_tags",
    "missing_twitter_title": "meta_tags",
    "missing_twitter_description": "meta_tags",
    "missing_twitter_image": "meta_tags",
    "missing_twitter_site": "meta_tags",
}

# ─── Duplicate Issue Groups ────────────────────────────────
# Same underlying issue detected by multiple analyzers.
# Canonical = scored. Duplicates = visible in report but NOT penalized.

DUPLICATE_GROUPS = {
    "images_missing_alt": {"no_alt_text_images", "missing_alt_text", "image_missing_alt"},
    # Add more groups here as needed, e.g.:
    # "broken_links": {"broken_links", "dead_links"},
}

# Build flat set of all duplicate (non-canonical) check names
_DUPLICATE_CHECKS: set = set()
for canonical, dupes in DUPLICATE_GROUPS.items():
    _DUPLICATE_CHECKS.update(dupes - {canonical})

# ─── Check names excluded from scoring (informational only) ──
# These findings appear in the report but don't penalize scores.
# Recommendation-level: things to consider, not errors.

SEO_SCORING_IGNORE = {
    # canonical — informational only
    "missing_canonical",
    "empty_canonical",
    "canonical_url_mismatch",

    # weak CTR — not reliable SEO rule
    "weak_title_ctr",
    "weak_desc_ctr",

    # schema — missing schema is not an error for every page
    "no_structured_data",

    # OG customization — same as <title> is fine, customization is optional
    "og_title_not_customized",
    "og_description_not_customized",

    # twitter — social metadata, not SEO-critical
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

SEO_CHECK_PENALTIES = {
    # ── CRITICAL — must fix, directly impacts ranking ──────
    # meta_tags — critical SEO elements
    "missing_title": 18,
    "missing_meta_description": 10,
    "duplicate_title": 8,
    "duplicate_meta_description": 6,
    "title_keyword_stuffing": 5,
    "desc_keyword_stuffing": 4,

    # canonical — conflicts hurt indexing
    "canonical_not_self_referencing": 6,
    "canonical_wrong_domain": 8,
    "canonical_noindex_conflict": 12,

    # headings — H1 is critical
    "missing_h1": 15,

    # content
    "thin_content": 12,
    "duplicate_content": 8,
    "keyword_stuffing": 6,

    # indexability — directly blocks indexing
    "meta_noindex": 15,
    "meta_nofollow": 10,
    "internal_nofollow_links": 5,

    # links
    "broken_links": 10,

    # technical
    "missing_viewport": 6,

    # images — accessibility + SEO
    "images_missing_alt": 6,

    # ── WARNING — should fix, affects quality ──────────────
    # headings
    "multiple_h1": 3,
    "heading_order_broken": 2,
    "repeated_headings": 3,
    "empty_headings": 2,

    # content
    "non_descriptive_link_text": 2,

    # images
    "generic_alt_text": 3,
    "images_duplicate_alt": 3,

    # links
    "orphan_pages": 4,
    "excessive_link_depth": 5,

    # technical / schema
    "invalid_schema": 5,
    "schema_no_type": 3,
    "schema_incomplete": 3,
    "schema_empty_values": 2,
    "slow_page_speed": 8,

    # core web vitals
    "poor_lcp": 8,
    "slow_lcp": 4,
    "high_avg_lcp": 6,
    "poor_cls": 8,
    "moderate_cls": 4,
    "high_avg_cls": 6,

    # sitemap
    "declared_sitemap_not_found": 5,
    "declared_sitemap_error": 4,
    "declared_sitemap_unreachable": 3,

    # content seo
    "low_title_content_relevance": 5,
    "thin_content_page": 6,

    # open graph
    "missing_open_graph": 5,
    "incomplete_open_graph": 2,
    "missing_twitter_card": 3,

    # redirect
    "redirect_chain": 3,

    # ── RECOMMENDATION — optional improvements ─────────────
    # (These should have penalty=0 or very low, mostly in SEO_SCORING_IGNORE)
    # schema_wrong_type is informational — Corporation is valid
    "schema_wrong_type": 0,
    # missing_h2 is nice-to-have
    "missing_h2": 3,
    # long/short titles — minor optimization
    "long_title": 2,
    "short_title": 2,
    "long_meta_description": 2,
    "short_meta_description": 2,
    # keyword relevance — soft signal
    "title_no_keyword_relevance": 3,
    "desc_no_keyword_relevance": 2,
    # OG/Twitter — social optimization
    "weak_og_title": 2,
    "weak_og_description": 2,
    "invalid_og_image": 3,
    "invalid_twitter_card_type": 2,
    # images
    "large_images": 2,
    # links
    "external_nofollow_links": 1,
    # robots
    "x_robots_noindex": 8,
    # misc
    "declared_sitemap_not_found": 4,
    "declared_sitemap_error": 3,
    "declared_sitemap_unreachable": 2,
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
    "no_loading_feedback",  # Not tested from static HTML
}

UX_SCORING_IGNORE = {
    "no_loading_feedback",  # Not tested from static HTML
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


def compute_finding_penalty(finding: dict) -> float:
    """Compute score penalty for a finding based on severity, confidence, and violation count.
    
    Uses diminishing returns for high violation counts (100 issues ≠ 10× worse than 10).
    But ensures critical/high severity findings have meaningful impact.
    """
    severity = finding.get("severity", "info")
    confidence = finding.get("confidence", 0.8)
    violations = finding.get("total_violations", 1)

    base_penalty = SEVERITY_PENALTY.get(severity, 0)

    # Diminishing returns: sqrt scale for violation count
    # 1 violation = 1.0×, 5 = 1.6×, 10 = 2.0×, 50 = 3.2×, 100 = 4.0×
    import math
    violation_factor = 1.0 + math.sqrt(max(1, violations)) * 0.3

    penalty = base_penalty * confidence * violation_factor
    return round(penalty, 2)  # No cap — let critical issues have real impact


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


def aggregate_findings(findings: list[dict], total_pages: int) -> list[dict]:
    """Step 2: Aggregate same-issue findings across pages into single enriched findings.
    
    Groups by check_name. For each group:
    - affected_pages: count of unique pages
    - total_violations: sum of all instances
    - severity: highest severity across all instances
    - confidence: computed from severity + page coverage
    - penalty: computed from severity + confidence + violations
    
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
        enriched["penalty"] = compute_finding_penalty(enriched)

        aggregated.append(enriched)

    return aggregated


def _grade(score: int) -> str:
    if score >= 80:
        return "Excellent"
    if score >= 60:
        return "Good"
    if score >= 40:
        return "Average"
    if score >= 20:
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
    for f in findings:
        check_name = f.get("check_name", "")
        if scoring_ignore and check_name in scoring_ignore:
            continue
        cat = check_to_category.get(check_name)
        if not cat:
            continue

        # Use pre-computed penalty from enriched finding if available
        if "penalty" in f:
            cat_penalties[cat] += f["penalty"]
        elif check_penalties and check_name in check_penalties:
            cat_penalties[cat] += check_penalties[check_name]
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
        scoring_ignore=UI_SCORING_IGNORE)
    
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


def compute_overall_score(ui_score: int, ux_score: int, seo_score: int = 0) -> dict:
    """Combine UI, UX and SEO scores into an overall score.

    Formula: overall = ui * 0.3 + ux * 0.3 + seo * 0.4

    Returns dict with keys:
        overall_score, grade
    """
    overall_score = round(ui_score * 0.3 + ux_score * 0.3 + seo_score * 0.4)
    overall_score = max(0, min(100, overall_score))

    return {
        "overall_score": overall_score,
        "grade": _grade(overall_score),
    }
