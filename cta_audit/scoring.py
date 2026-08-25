"""
CTA Audit Scoring — 100-point weighted scale.

Scoring weights:
  CTA Presence         15
  CTA Clarity          15
  Visibility           15
  Placement            15
  Usability            15
  Conversion Path      15
  Consistency           5
  CTA Density           5
                       ---
  Total               100

Per-category scoring:
  good    → full weight
  warning → half weight
  info    → 75% weight (neutral/observational)
  high    → 25% weight
  critical → 0 weight (deducted fully)
"""

WEIGHTS = {
    "cta_presence":      15,
    "cta_clarity":       15,
    "cta_visibility":    15,
    "cta_placement":     15,
    "cta_usability":     15,
    "conversion_path":   15,
    "cta_consistency":    5,
    "cta_density":        5,
}

SEVERITY_MULTIPLIER = {
    "good":      1.0,
    "info":      0.75,
    "warning":   0.5,
    "high":      0.25,
    "critical":  0.0,
}

GRADE_MAP = [
    (80, "Excellent"),
    (60, "Good"),
    (40, "Average"),
    (20, "Needs Improvement"),
    (0,  "Poor"),
]


def _grade(score: int) -> str:
    for threshold, label in GRADE_MAP:
        if score >= threshold:
            return label
    return "Poor"


def score_cta_audit(result: dict) -> dict:
    """Score CTA audit results.

    Returns: {
        "cta_score": int (0-100),
        "grade": str,
        "total_findings": int,
        "by_severity": { critical, high, warning, info, good },
        "by_check": { check_name: { findings, score } },
        "page_results": [...],
        "findings": [...],
    }
    """
    findings = result.get("findings", [])
    page_results = result.get("page_results", [])
    cross_page = result.get("cross_page", {})

    # Group findings by check type
    by_check = {}
    for check_name in WEIGHTS:
        by_check[check_name] = {"findings": [], "severity_counts": {}}

    for f in findings:
        check = f.get("check", "")
        if check in by_check:
            by_check[check]["findings"].append(f)
            sev = f.get("severity", "info")
            by_check[check]["severity_counts"][sev] = by_check[check]["severity_counts"].get(sev, 0) + 1

    # Score each category
    category_scores = {}
    for check_name, weight in WEIGHTS.items():
        check_data = by_check[check_name]
        severity_counts = check_data["severity_counts"]
        num_findings = len(check_data["findings"])

        if num_findings == 0:
            # No findings = perfect score for this category
            category_scores[check_name] = weight
            continue

        # Start at full weight, deduct based on worst severity
        worst_severity = "good"
        severity_order = ["critical", "high", "warning", "info", "good"]
        for sev in severity_order:
            if sev in severity_counts:
                worst_severity = sev
                break

        # Calculate: base score reduced by proportion of bad findings
        total_bad = sum(1 for f in check_data["findings"] if f.get("severity") in ("critical", "high", "warning"))
        total_good = sum(1 for f in check_data["findings"] if f.get("severity") in ("good", "info"))

        if num_findings > 0:
            bad_ratio = total_bad / num_findings
            score = weight * (1 - bad_ratio * 0.8)  # up to 80% deduction for bad findings
        else:
            score = weight

        category_scores[check_name] = max(0, round(score))

    # Overall score
    total_score = sum(category_scores.values())
    total_score = max(0, min(100, total_score))

    # Severity counts
    by_severity = {"critical": 0, "high": 0, "warning": 0, "info": 0, "good": 0}
    for f in findings:
        sev = f.get("severity", "info")
        if sev in by_severity:
            by_severity[sev] += 1

    return {
        "cta_score": total_score,
        "grade": _grade(total_score),
        "total_findings": len(findings),
        "by_severity": by_severity,
        "category_scores": category_scores,
        "page_results": page_results,
        "findings": findings,
    }
