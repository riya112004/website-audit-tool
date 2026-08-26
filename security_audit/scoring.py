"""
Security Audit Scoring — 100-point weighted scale.

Scoring weights:
  HTTPS / SSL              20
  Security Headers         25
  Cookies / Session        15
  Sensitive Data Exposure  20
  Forms / Authentication   10
  Third-party Resources     5
  Infrastructure            5
                          ---
  Total                   100

Deductions per finding severity:
  critical  → -15 to -25 (contextual)
  high      → -8 to -12
  medium    → -3 to -6
  low       → -1 to -2
  info      → 0 (observational)
  good      → +0 (already at max)
"""

CATEGORY_WEIGHTS = {
    "https_ssl":              20,
    "security_headers":       25,
    "cookies_session":        15,
    "sensitive_data":         20,
    "forms_auth":             10,
    "third_party":             5,
    "infrastructure":          5,
}

# Map check names to categories
CHECK_TO_CATEGORY = {
    "https_usage": "https_ssl",
    "csp_unsafe_inline": "security_headers",
    "csp_unsafe_eval": "security_headers",
    "cookie_secure": "cookies_session",
    "cookie_httponly": "cookies_session",
    "cookie_samesite": "cookies_session",
    "cookie_security": "cookies_session",
    "sensitive_data": "sensitive_data",
    "internal_urls_exposed": "sensitive_data",
    "login_form_present": "forms_auth",
    "login_form_http": "forms_auth",
    "password_field_type": "forms_auth",
    "csrf_missing": "forms_auth",
    "form_no_action": "forms_auth",
    "form_security": "forms_auth",
    "external_scripts": "third_party",
    "suspicious_scripts": "third_party",
    "sri_missing": "third_party",
    "sri_partial": "third_party",
    "server_disclosure": "infrastructure",
    "powered_by_disclosure": "infrastructure",
    "error_pages": "infrastructure",
    "robots_txt_check": "infrastructure",
}

SEVERITY_DEDUCTIONS = {
    "critical": 20,
    "high": 10,
    "medium": 4,
    "low": 1,
    "info": 0,
    "good": 0,
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


def score_security_audit(result: dict) -> dict:
    """Score security audit results.

    Returns: {
        "security_score": int (0-100),
        "grade": str,
        "total_observations": int,
        "by_severity": { critical, high, medium, low, info, good },
        "category_scores": { cat: score },
        "findings": [...],
    }
    """
    findings = result.get("findings", [])
    page_count = result.get("page_count", 0)

    # Group findings by category
    category_findings = {cat: [] for cat in CATEGORY_WEIGHTS}
    for f in findings:
        check = f.get("check", "")
        cat = CHECK_TO_CATEGORY.get(check, "infrastructure")
        if cat in category_findings:
            category_findings[cat].append(f)

    # Score each category
    category_scores = {}
    for cat, weight in CATEGORY_WEIGHTS.items():
        cat_findings = category_findings[cat]

        if not cat_findings:
            category_scores[cat] = weight
            continue

        # Start at full weight, deduct based on severity
        score = weight
        for f in cat_findings:
            sev = f.get("severity", "info")
            if sev in ("good", "info"):
                continue
            deduction = SEVERITY_DEDUCTIONS.get(sev, 0)
            # Scale deduction by affected_pages / total_pages to avoid double-counting
            affected = f.get("affected_pages", 1)
            if page_count > 0:
                affected_ratio = min(1.0, affected / page_count)
            else:
                affected_ratio = 1.0
            scaled_deduction = deduction * affected_ratio
            score -= scaled_deduction

        category_scores[cat] = max(0, round(score))

    # Overall score
    total_score = sum(category_scores.values())
    total_score = max(0, min(100, total_score))

    # Severity counts
    by_severity = {"critical": 0, "high": 0, "medium": 0, "low": 0, "info": 0, "good": 0}
    for f in findings:
        sev = f.get("severity", "info")
        if sev in by_severity:
            by_severity[sev] += 1

    return {
        "security_score": total_score,
        "grade": _grade(total_score),
        "total_observations": len(findings),
        "by_severity": by_severity,
        "category_scores": category_scores,
        "findings": findings,
    }
