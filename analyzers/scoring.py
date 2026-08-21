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
    "inconsistent_heading_hierarchy": "visual_hierarchy",
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
    "missing_meta_description": "meta_tags",
    "duplicate_meta_description": "meta_tags",
    "long_meta_description": "meta_tags",
    "short_meta_description": "meta_tags",
    "missing_canonical": "meta_tags",
    "duplicate_canonical": "meta_tags",
    "missing_h1": "headings",
    "multiple_h1": "headings",
    "heading_order_broken": "headings",
    "missing_h2": "headings",
    "thin_content": "content",
    "duplicate_content": "content",
    "keyword_stuffing": "content",
    "non_descriptive_link_text": "content",
    "images_missing_alt": "images",
    "images_duplicate_alt": "images",
    "large_images": "images",
    "broken_links": "links",
    "external_nofollow_links": "links",
    "orphan_pages": "links",
    "no_structured_data": "technical",
    "missing_robots_txt": "technical",
    "missing_sitemap": "technical",
    "slow_page_speed": "technical",
    "mobile_unfriendly": "technical",
    "missing_ssl": "technical",
    "crawl_error": "technical",
    "server_error": "technical",
}

# ─── Severity Penalties ────────────────────────────────────

SEVERITY_PENALTY = {
    "critical": 15,
    "high": 10,
    "medium": 6,
    "low": 3,
    "info": 1,
}

SEVERITY_KEYS = ("critical", "high", "medium", "low", "info")


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
    check_to_category: dict[str, str],
    weights: dict[str, int],
) -> tuple[dict[str, int], dict[str, dict[str, int]]]:
    """Score findings against a weighted category map.

    Returns (category_scores, category_severity_counts).
    """
    cat_counts: dict[str, dict[str, int]] = {cat: {s: 0 for s in SEVERITY_KEYS} for cat in weights}

    for f in findings:
        check_name = f.get("check_name", "")
        cat = check_to_category.get(check_name)
        if not cat:
            continue
        severity = f.get("severity", "info")
        if severity in cat_counts[cat]:
            cat_counts[cat][severity] += 1

    category_scores: dict[str, int] = {}
    for cat, counts in cat_counts.items():
        score = 100
        for severity, count in counts.items():
            score -= SEVERITY_PENALTY.get(severity, 0) * count
        category_scores[cat] = max(0, min(100, score))

    return category_scores, cat_counts


def _weighted_total(category_scores: dict[str, int], weights: dict[str, int]) -> int:
    total_weight = sum(weights.values())
    if total_weight == 0:
        return 100
    weighted = sum(category_scores[cat] * w for cat, w in weights.items())
    return max(0, min(100, round(weighted / total_weight)))


def _count_by_severity(findings: list[dict]) -> dict[str, int]:
    counts = {s: 0 for s in SEVERITY_KEYS}
    for f in findings:
        sev = f.get("severity", "info")
        if sev in counts:
            counts[sev] += 1
    return counts


def compute_ui_score(ui_findings: list[dict]) -> dict:
    """Score UI findings against the UI category weights.

    Returns dict with keys:
        ui_score, category_scores, total_issues, by_severity, grade
    """
    category_scores, _ = _score_categories(ui_findings, UI_CHECK_TO_CATEGORY, UI_WEIGHTS)
    ui_score = _weighted_total(category_scores, UI_WEIGHTS)
    by_severity = _count_by_severity(ui_findings)

    return {
        "ui_score": ui_score,
        "category_scores": category_scores,
        "total_issues": len(ui_findings),
        "by_severity": by_severity,
        "grade": _grade(ui_score),
    }


def compute_ux_score(ux_findings: list[dict]) -> dict:
    """Score UX findings against the UX category weights.

    Returns dict with keys:
        ux_score, category_scores, total_issues, by_severity, grade
    """
    category_scores, _ = _score_categories(ux_findings, UX_CHECK_TO_CATEGORY, UX_WEIGHTS)
    ux_score = _weighted_total(category_scores, UX_WEIGHTS)
    by_severity = _count_by_severity(ux_findings)

    return {
        "ux_score": ux_score,
        "category_scores": category_scores,
        "total_issues": len(ux_findings),
        "by_severity": by_severity,
        "grade": _grade(ux_score),
    }


def compute_seo_score(seo_findings: list[dict]) -> dict:
    """Score SEO findings against the SEO category weights.

    Returns dict with keys:
        seo_score, category_scores, total_issues, by_severity, grade
    """
    category_scores, _ = _score_categories(seo_findings, SEO_CHECK_TO_CATEGORY, SEO_WEIGHTS)
    seo_score = _weighted_total(category_scores, SEO_WEIGHTS)
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
