"""
Missing Features Scoring — applicability-based weighted scoring.

Score = Σ(applicable feature points earned) / Σ(applicable feature points) × 100

Feature Status:
  implemented    = 100% of feature weight
  partial        = 50%
  missing        = 0%
  not_applicable = excluded from scoring

Severity (used for finding display, not scoring):
  Critical = 4 points
  High     = 3 points
  Medium   = 2 points
  Low      = 1 point
"""

from . import FEATURE_CATEGORIES

SEVERITY_POINTS = {
    "critical": 4,
    "high": 3,
    "medium": 2,
    "low": 1,
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


def score_features(result: dict) -> dict:
    """Score missing features audit results.

    Returns: {
        "missing_features_score": int (0-100),
        "grade": str,
        "website_type": str,
        "total_features_checked": int,
        "applicable_features": int,
        "implemented": int,
        "partial": int,
        "missing": int,
        "not_applicable": int,
        "by_severity": { critical: n, high: n, medium: n, low: n },
        "category_scores": { cat_id: { score, weight, features } },
        "findings": [ ... ],
    }
    """
    category_results = result.get("category_results", {})
    findings = result.get("findings", [])
    site_type = result.get("website_type", {})

    total_weighted_points = 0.0
    earned_weighted_points = 0.0
    total_features = 0
    applicable = 0
    implemented = 0
    partial = 0
    missing = 0
    not_applicable = 0
    category_scores = {}

    by_severity = {"critical": 0, "high": 0, "medium": 0, "low": 0}

    for cat_id, cat_data in category_results.items():
        weight = cat_data["weight"]
        features = cat_data["features"]

        cat_applicable = 0
        cat_earned = 0.0

        for feat in features:
            total_features += 1
            status = feat["status"]

            if status == "not_applicable":
                not_applicable += 1
                continue

            applicable += 1
            cat_applicable += 1

            if status == "implemented":
                cat_earned += 1.0
                implemented += 1
            elif status == "partial":
                cat_earned += 0.5
                partial += 1
            elif status == "missing":
                cat_earned += 0.0
                missing += 1

                sev = feat.get("severity", "medium")
                if sev in by_severity:
                    by_severity[sev] += 1

        # Category score: proportion of earned vs applicable × weight
        if cat_applicable > 0:
            cat_score = round((cat_earned / cat_applicable) * weight)
        else:
            cat_score = weight  # all features not applicable = full marks

        category_scores[cat_id] = {
            "score": cat_score,
            "weight": weight,
            "implemented": sum(1 for f in features if f["status"] == "implemented"),
            "partial": sum(1 for f in features if f["status"] == "partial"),
            "missing": sum(1 for f in features if f["status"] == "missing"),
            "not_applicable": sum(1 for f in features if f["status"] == "not_applicable"),
        }

        total_weighted_points += weight
        earned_weighted_points += cat_score

    if total_weighted_points > 0:
        score = round((earned_weighted_points / total_weighted_points) * 100)
    else:
        score = 0

    score = max(0, min(100, score))

    return {
        "missing_features_score": score,
        "grade": _grade(score),
        "website_type": site_type.get("description", "Unknown"),
        "website_type_confidence": site_type.get("confidence", 0),
        "total_features_checked": total_features,
        "applicable_features": applicable,
        "implemented": implemented,
        "partial": partial,
        "missing": missing,
        "not_applicable": not_applicable,
        "by_severity": by_severity,
        "category_scores": category_scores,
        "findings": findings,
    }
