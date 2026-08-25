"""
Mobile Responsiveness Scoring — per-page scoring + aggregate.

Category weights:
  1. Viewport & Overflow     — 20%
  2. Responsive Layout       — 20%
  3. Typography & Content    — 15%
  4. Images & Media          — 10%
  5. Navigation              — 15%
  6. Touch & Interaction     — 10%
  7. Fixed/Sticky Elements   —  5%
  8. Mobile Visual Quality   —  5%

Severity penalties (per-check):
  Critical = 100% of check weight
  High     = 70%
  Medium   = 40%
  Low      = 15%
"""

from . import BREAKPOINTS

CATEGORY_WEIGHTS = {
    "viewport_overflow":     20,
    "responsive_layout":     20,
    "typography":            15,
    "images_media":          10,
    "navigation":            15,
    "touch_interaction":     10,
    "fixed_elements":         5,
    "visual_quality":         5,
}

SEVERITY_PENALTY_PCT = {
    "critical": 1.0,
    "high":     0.7,
    "medium":   0.4,
    "low":      0.15,
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


def _count_affected_pages(pages_data: dict, check_fn) -> tuple[int, int]:
    """Return (affected_pages, total_pages) for a given check function."""
    affected = 0
    total = 0
    for url, bp_data in pages_data.items():
        if "page_id" not in bp_data:
            continue
        total += 1
        if check_fn(bp_data):
            affected += 1
    return affected, total


def _score_page(page_data: dict) -> dict:
    """Score a single page across all breakpoints.

    Returns: {
        "score": int (0-100),
        "category_scores": { cat: int },
        "findings": [ { check_name, severity, message, recommendation } ],
        "by_severity": { critical: n, high: n, medium: n, low: n },
        "pages_tested": int (breakpoints),
    }
    """
    # Collect breakpoint results (skip errors)
    bp_results = []
    for bp in BREAKPOINTS:
        if bp in page_data and "error" not in page_data[bp]:
            bp_results.append((bp, page_data[bp]))

    if not bp_results:
        return {"score": 0, "category_scores": {}, "findings": [], "by_severity": {}, "pages_tested": 0}

    category_penalties = {cat: 0.0 for cat in CATEGORY_WEIGHTS}
    findings = []
    by_severity = {"critical": 0, "high": 0, "medium": 0, "low": 0}

    for bp, data in bp_results:
        vw = data.get("viewport_overflow", {})
        ly = data.get("responsive_layout", {})
        ty = data.get("typography", {})
        im = data.get("images_media", {})
        nv = data.get("navigation", {})
        tc = data.get("touch_interaction", {})
        fx = data.get("fixed_elements", [])
        vq = data.get("visual_quality", {})

        bp_label = f"{bp}px"

        # ── 1. Viewport & Overflow (20%) ──
        if vw.get("has_hscroll"):
            category_penalties["viewport_overflow"] += 8.0
            by_severity["critical"] += 1
            findings.append({
                "check_name": "horizontal_overflow",
                "severity": "critical",
                "message": f"Horizontal scroll detected at {bp_label} ({vw.get('overflow_px', 0)}px overflow)",
                "recommendation": "Remove fixed-width elements and use relative units (%, vw, max-width).",
                "page_url": None, "breakpoint": bp,
            })
        if vw.get("body_hscroll"):
            category_penalties["viewport_overflow"] += 5.0
            by_severity["high"] += 1
            findings.append({
                "check_name": "body_horizontal_overflow",
                "severity": "high",
                "message": f"Body-level horizontal scroll at {bp_label}",
                "recommendation": "Set body { overflow-x: hidden } and fix root cause.",
                "page_url": None, "breakpoint": bp,
            })
        if vw.get("fixed_width_elements", 0) > 0:
            count = vw["fixed_width_elements"]
            category_penalties["viewport_overflow"] += min(count * 2.0, 6.0)
            sev = "high" if count >= 3 else "medium"
            by_severity[sev] += 1
            findings.append({
                "check_name": "fixed_width_elements",
                "severity": sev,
                "message": f"{count} element(s) wider than viewport at {bp_label}",
                "recommendation": "Use max-width: 100% or responsive units on overflowing elements.",
                "page_url": None, "breakpoint": bp,
            })
        if vw.get("overflow_elements", 0) > 0:
            count = vw["overflow_elements"]
            category_penalties["viewport_overflow"] += min(count * 1.5, 5.0)
            sev = "high" if count >= 5 else "medium"
            by_severity[sev] += 1
            findings.append({
                "check_name": "content_overflow",
                "severity": sev,
                "message": f"{count} element(s) extending beyond viewport at {bp_label}",
                "recommendation": "Check positioning and width of overflowing elements.",
                "page_url": None, "breakpoint": bp,
            })
        if not vw.get("has_meta_viewport"):
            category_penalties["viewport_overflow"] += 10.0
            by_severity["critical"] += 1
            findings.append({
                "check_name": "missing_meta_viewport",
                "severity": "critical",
                "message": "Missing meta viewport tag",
                "recommendation": "Add <meta name=\"viewport\" content=\"width=device-width, initial-scale=1\"> to <head>.",
                "page_url": None, "breakpoint": bp,
            })

        # ── 2. Responsive Layout (20%) ──
        if ly.get("broken_containers", 0) > 0:
            count = ly["broken_containers"]
            category_penalties["responsive_layout"] += min(count * 4.0, 10.0)
            sev = "high" if count >= 2 else "medium"
            by_severity[sev] += 1
            findings.append({
                "check_name": "broken_containers",
                "severity": sev,
                "message": f"{count} container(s) wider than viewport at {bp_label}",
                "recommendation": "Use CSS Grid/Flexbox with responsive breakpoints.",
                "page_url": None, "breakpoint": bp,
            })

        # ── 3. Typography & Content (15%) ──
        if ty.get("text_clipping", 0) > 0:
            count = ty["text_clipping"]
            category_penalties["typography"] += min(count * 2.0, 6.0)
            sev = "medium" if count < 5 else "high"
            by_severity[sev] += 1
            findings.append({
                "check_name": "text_clipping",
                "severity": sev,
                "message": f"{count} text element(s) clipped at {bp_label}",
                "recommendation": "Add word-wrap: break-word or adjust container width.",
                "page_url": None, "breakpoint": bp,
            })
        if ty.get("small_font_elements", 0) > 0:
            count = ty["small_font_elements"]
            category_penalties["typography"] += min(count * 1.5, 5.0)
            sev = "medium" if count < 10 else "high"
            by_severity[sev] += 1
            findings.append({
                "check_name": "small_font_size",
                "severity": sev,
                "message": f"{count} element(s) with font-size < 12px at {bp_label}",
                "recommendation": "Use at least 14px body text and 16px for readability on mobile.",
                "page_url": None, "breakpoint": bp,
            })
        if ty.get("line_height_issues", 0) > 0:
            count = ty["line_height_issues"]
            category_penalties["typography"] += min(count * 1.0, 4.0)
            sev = "low" if count < 5 else "medium"
            by_severity[sev] += 1
            findings.append({
                "check_name": "line_height_issues",
                "severity": sev,
                "message": f"{count} element(s) with poor line-height ratio at {bp_label}",
                "recommendation": "Use line-height between 1.4–1.8 for body text.",
                "page_url": None, "breakpoint": bp,
            })
        if ty.get("hidden_content", 0) > 0:
            count = ty["hidden_content"]
            category_penalties["typography"] += min(count * 2.0, 5.0)
            sev = "medium"
            by_severity[sev] += 1
            findings.append({
                "check_name": "hidden_content",
                "severity": sev,
                "message": f"{count} element(s) with text clipped by overflow:hidden at {bp_label}",
                "recommendation": "Ensure important content is not hidden on small screens.",
                "page_url": None, "breakpoint": bp,
            })

        # ── 4. Images & Media (10%) ──
        if im.get("no_max_width", 0) > 0:
            count = im["no_max_width"]
            category_penalties["images_media"] += min(count * 2.0, 6.0)
            sev = "medium" if count < 5 else "high"
            by_severity[sev] += 1
            findings.append({
                "check_name": "images_no_max_width",
                "severity": sev,
                "message": f"{count} image(s) without max-width:100% at {bp_label}",
                "recommendation": "Add img { max-width: 100%; height: auto } to your CSS.",
                "page_url": None, "breakpoint": bp,
            })
        if im.get("oversized", 0) > 0:
            count = im["oversized"]
            category_penalties["images_media"] += min(count * 2.5, 5.0)
            sev = "medium"
            by_severity[sev] += 1
            findings.append({
                "check_name": "oversized_images",
                "severity": sev,
                "message": f"{count} image(s) wider than 150% viewport at {bp_label}",
                "recommendation": "Use responsive images with srcset or set max-width.",
                "page_url": None, "breakpoint": bp,
            })
        if im.get("non_resp_media", 0) > 0:
            count = im["non_resp_media"]
            category_penalties["images_media"] += min(count * 3.0, 6.0)
            sev = "high"
            by_severity[sev] += 1
            findings.append({
                "check_name": "non_responsive_media",
                "severity": sev,
                "message": f"{count} iframe/video not responsive at {bp_label}",
                "recommendation": "Wrap in a container with aspect-ratio and max-width:100%.",
                "page_url": None, "breakpoint": bp,
            })
        if im.get("broken_aspect", 0) > 0:
            count = im["broken_aspect"]
            category_penalties["images_media"] += min(count * 1.5, 4.0)
            sev = "low"
            by_severity[sev] += 1
            findings.append({
                "check_name": "broken_aspect_ratio",
                "severity": sev,
                "message": f"{count} image(s) with distorted aspect ratio at {bp_label}",
                "recommendation": "Use object-fit: cover/contain or intrinsic dimensions.",
                "page_url": None, "breakpoint": bp,
            })

        # ── 5. Navigation (15%) ──
        if not nv.get("has_nav"):
            if bp <= 414:
                category_penalties["navigation"] += 4.0
                by_severity["low"] += 1
                findings.append({
                    "check_name": "no_navigation_element",
                    "severity": "low",
                    "message": f"No nav element found at {bp_label}",
                    "recommendation": "Use semantic <nav> element for mobile navigation.",
                    "page_url": None, "breakpoint": bp,
                })
        if bp <= 414 and not nv.get("has_hamburger") and nv.get("nav_item_count", 0) > 5:
            category_penalties["navigation"] += 8.0
            by_severity["high"] += 1
            findings.append({
                "check_name": "no_mobile_menu",
                "severity": "high",
                "message": f"{nv['nav_item_count']} nav items with no hamburger menu at {bp_label}",
                "recommendation": "Add a hamburger/toggle menu for mobile viewports.",
                "page_url": None, "breakpoint": bp,
            })
        if nv.get("overlapping_items", 0) > 0:
            count = nv["overlapping_items"]
            category_penalties["navigation"] += min(count * 3.0, 8.0)
            sev = "high" if count >= 3 else "medium"
            by_severity[sev] += 1
            findings.append({
                "check_name": "nav_overlapping_items",
                "severity": sev,
                "message": f"{count} overlapping nav item(s) at {bp_label}",
                "recommendation": "Stack nav items vertically or use a dropdown on mobile.",
                "page_url": None, "breakpoint": bp,
            })
        if nv.get("sticky_covers_content", 0) > 0:
            category_penalties["navigation"] += 5.0
            by_severity["medium"] += 1
            findings.append({
                "check_name": "sticky_header_covers",
                "severity": "medium",
                "message": f"Sticky header/nav too tall ({nv['sticky_covers_content']}px) at {bp_label}",
                "recommendation": "Reduce sticky header height on mobile or add scroll-padding.",
                "page_url": None, "breakpoint": bp,
            })

        # ── 6. Touch & Interaction (10%) ──
        if tc.get("too_small_targets", 0) > 0:
            count = tc["too_small_targets"]
            total = tc.get("total_clickables", 1)
            pct = count / max(total, 1)
            category_penalties["touch_interaction"] += min(pct * 12.0, 8.0)
            sev = "high" if pct > 0.3 else "medium"
            by_severity[sev] += 1
            findings.append({
                "check_name": "small_touch_targets",
                "severity": sev,
                "message": f"{count}/{total} clickable elements < 44×44px at {bp_label}",
                "recommendation": "Increase touch target size to at least 44×44px (WCAG 2.5.5).",
                "page_url": None, "breakpoint": bp,
            })
        if tc.get("overlapping_clickables", 0) > 0:
            count = tc["overlapping_clickables"]
            category_penalties["touch_interaction"] += min(count * 2.0, 5.0)
            sev = "medium"
            by_severity[sev] += 1
            findings.append({
                "check_name": "overlapping_clickables",
                "severity": sev,
                "message": f"{count} overlapping clickable element(s) at {bp_label}",
                "recommendation": "Add spacing between interactive elements.",
                "page_url": None, "breakpoint": bp,
            })
        if tc.get("overflow_inputs", 0) > 0:
            count = tc["overflow_inputs"]
            category_penalties["touch_interaction"] += min(count * 3.0, 6.0)
            sev = "high"
            by_severity[sev] += 1
            findings.append({
                "check_name": "form_input_overflow",
                "severity": sev,
                "message": f"{count} form input(s) overflow viewport at {bp_label}",
                "recommendation": "Add input { max-width: 100%; box-sizing: border-box }.",
                "page_url": None, "breakpoint": bp,
            })

        # ── 7. Fixed/Sticky Elements (5%) ──
        if fx:
            covering = [e for e in fx if e["top"] < 10 and e["height"] > 60 and e["type"] != "navigation"]
            if covering:
                category_penalties["fixed_elements"] += min(len(covering) * 2.0, 4.0)
                for e in covering:
                    by_severity["low"] += 1
                    findings.append({
                        "check_name": "fixed_element_covers",
                        "severity": "low",
                        "message": f"{e['type']} ({e['width']}×{e['height']}px) may cover content at {bp_label}",
                        "recommendation": "Ensure fixed elements can be dismissed or don't block content.",
                        "page_url": None, "breakpoint": bp,
                    })

        # ── 8. Visual Quality (5%) ──
        if vq.get("excessive_gap", 0) > 0:
            count = vq["excessive_gap"]
            category_penalties["visual_quality"] += min(count * 1.5, 4.0)
            sev = "low" if count < 3 else "medium"
            by_severity[sev] += 1
            findings.append({
                "check_name": "excessive_whitespace",
                "severity": sev,
                "message": f"{count} section(s) with excessive margin/padding at {bp_label}",
                "recommendation": "Reduce spacing on mobile viewports via responsive CSS.",
                "page_url": None, "breakpoint": bp,
            })

    # ── Compute category scores ──
    category_scores = {}
    total_penalty = 0.0
    for cat, weight in CATEGORY_WEIGHTS.items():
        pen = min(category_penalties[cat], weight)
        cat_score = max(0, round(weight - pen))
        category_scores[cat] = cat_score
        total_penalty += pen

    page_score = max(0, min(100, 100 - round(total_penalty)))

    return {
        "score": page_score,
        "category_scores": category_scores,
        "findings": findings,
        "by_severity": by_severity,
        "pages_tested": len(bp_results),
    }


def score_mobile_results(raw_results: dict) -> dict:
    """Score all pages and produce aggregate results.

    Returns: {
        "mobile_score": int,
        "grade": str,
        "category_scores": { cat: int },
        "pages_scored": int,
        "total_findings": int,
        "by_severity": { critical: n, high: n, medium: n, low: n },
        "per_page": { url: { score, category_scores, ... } },
        "all_findings": [ ... ],
    }
    """
    per_page = {}
    all_findings = []
    agg_severity = {"critical": 0, "high": 0, "medium": 0, "low": 0}
    agg_category = {cat: 0 for cat in CATEGORY_WEIGHTS}
    scores = []

    for url, page_data in raw_results.items():
        if "page_id" not in page_data:
            continue
        result = _score_page(page_data)
        per_page[url] = result
        scores.append(result["score"])

        for f in result["findings"]:
            f["page_url"] = url
            all_findings.append(f)

        for sev, count in result["by_severity"].items():
            agg_severity[sev] += count

        for cat, sc in result["category_scores"].items():
            agg_category[cat] += sc

    pages_scored = len(scores)
    if pages_scored == 0:
        return {
            "mobile_score": 0,
            "grade": "Poor",
            "category_scores": agg_category,
            "pages_scored": 0,
            "total_findings": 0,
            "by_severity": agg_severity,
            "per_page": per_page,
            "all_findings": all_findings,
        }

    mobile_score = round(sum(scores) / pages_scored)

    # Average category scores across pages
    for cat in agg_category:
        agg_category[cat] = round(agg_category[cat] / pages_scored)

    return {
        "mobile_score": mobile_score,
        "grade": _grade(mobile_score),
        "category_scores": agg_category,
        "pages_scored": pages_scored,
        "total_findings": len(all_findings),
        "by_severity": agg_severity,
        "per_page": per_page,
        "all_findings": all_findings,
    }
