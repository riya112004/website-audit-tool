WEIGHTS = {
    "navigation": 15,
    "interaction": 15,
    "forms": 10,
    "mobile": 15,
    "accessibility": 15,
    "visual": 10,
    "readability": 10,
    "performance": 5,
    "errors": 5,
    "consistency": 5,
    "trust": 5,
}

CHECK_TO_CATEGORY = {
    "broken_internal_links": "navigation",
    "empty_href_links": "navigation",
    "hash_only_links": "navigation",
    "js_void_links": "navigation",
    "inaccessible_nav_links": "navigation",
    "excessive_nav_items": "navigation",
    "duplicate_nav_links": "navigation",
    "missing_breadcrumbs": "navigation",
    "unclear_anchor_text": "navigation",
    "orphan_pages": "navigation",
    "unlabeled_buttons": "interaction",
    "tiny_click_targets": "interaction",
    "disabled_visible_buttons": "interaction",
    "missing_accessible_names": "interaction",
    "hover_only_functionality": "interaction",
    "horizontal_scroll": "interaction",
    "hidden_cta": "interaction",
    "inputs_without_labels": "forms",
    "missing_placeholders": "forms",
    "incorrect_input_types": "forms",
    "required_fields_no_indicator": "forms",
    "no_submit_action": "forms",
    "submit_no_text": "forms",
    "very_long_forms": "forms",
    "mobile_horizontal_overflow": "mobile",
    "mobile_small_text": "mobile",
    "mobile_tiny_touch_targets": "mobile",
    "mobile_content_outside_viewport": "mobile",
    "mobile_fixed_element_blocking": "mobile",
    "missing_accessible_names_a11y": "accessibility",
    "focusable_no_outline": "accessibility",
    "poor_heading_hierarchy_a11y": "accessibility",
    "missing_skip_nav": "accessibility",
    "landmark_structure_missing": "accessibility",
    "overlapping_elements": "visual",
    "large_empty_spaces": "visual",
    "text_overflow_container": "visual",
    "images_no_dimensions": "visual",
    "inconsistent_button_sizes": "visual",
    "extremely_long_paragraphs": "readability",
    "very_small_text": "readability",
    "excessive_uppercase": "readability",
    "missing_headings": "readability",
    "empty_sections": "readability",
    "placeholder_text": "readability",
    "slow_initial_render": "performance",
    "missing_loading_indicators": "performance",
    "large_images": "performance",
    "console_errors": "errors",
    "broken_images": "errors",
    "missing_error_messages": "errors",
    "missing_success_messages": "errors",
    "inconsistent_navigation": "consistency",
    "inconsistent_cta_naming": "consistency",
    "inconsistent_footer": "consistency",
    "different_form_styles": "consistency",
    "missing_contact_info": "trust",
    "no_cta_detected": "trust",
    "no_contact_form": "trust",
    "missing_privacy_links": "trust",
    "missing_social_proof": "trust",
}

SEVERITY_PENALTY = {
    "critical": 15,
    "warning": 8,
    "info": 2,
}


def compute_ux_score(findings: list[dict]) -> dict:
    category_issues: dict[str, dict[str, int]] = {}
    for cat in WEIGHTS:
        category_issues[cat] = {"critical": 0, "warning": 0, "info": 0}

    for f in findings:
        check_name = f.get("check_name", "")
        cat = CHECK_TO_CATEGORY.get(check_name)
        if not cat:
            continue
        severity = f.get("severity", "info")
        if severity in category_issues[cat]:
            category_issues[cat][severity] += 1

    category_scores = {}
    for cat, counts in category_issues.items():
        score = 100
        for severity, count in counts.items():
            score -= SEVERITY_PENALTY.get(severity, 0) * count
        category_scores[cat] = max(0, score)

    total_weight = sum(WEIGHTS.values())
    ux_score = 0
    for cat, weight in WEIGHTS.items():
        ux_score += category_scores[cat] * weight
    ux_score = round(ux_score / total_weight) if total_weight else 100

    total_issues = len(findings)
    by_severity = {"critical": 0, "warning": 0, "info": 0}
    for f in findings:
        sev = f.get("severity", "info")
        if sev in by_severity:
            by_severity[sev] += 1

    return {
        "ux_score": ux_score,
        "category_scores": category_scores,
        "total_issues": total_issues,
        "by_severity": by_severity,
    }
