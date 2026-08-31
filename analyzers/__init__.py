"""Analyzer orchestrator — runs UI, UX, Accessibility, and Vision analyzers.

Pipeline:
  RAW DETECTION → VALIDATE → DEDUPLICATE → ENRICH → SCORE

Each finding gets:
  - confidence: 0.0–1.0 (how sure we are this is a real issue)
  - affected_pages: count of pages with this issue
  - total_violations: total instances across all pages
  - penalty: score penalty (severity × confidence × violations with diminishing returns)

N/A categories (not checked) are excluded from weighted score calculation.
0 = not detected/failure. N/A ≠ 0.
"""
import json
import os

from app import db
from analyzers.ui_analyzer import analyze_ui
from analyzers.ux_analyzer import analyze_ux
from analyzers.accessibility_analyzer import analyze_accessibility
from analyzers.vision_analyzer import analyze_visual
from analyzers.scoring import (
    compute_ui_score, compute_ux_score, compute_seo_score, compute_overall_score,
    validate_findings, aggregate_findings,
    UI_WEIGHTS, UX_WEIGHTS, SEO_WEIGHTS, SEO_CHECK_PENALTIES, UI_CHECK_PENALTIES,
)


def _load_ux_data(scan_id: int) -> dict:
    """Load UX data JSON from crawl."""
    base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    ux_file = os.path.join(base, "data", "html", f"scan{scan_id}", "ux_data.json")
    if not os.path.exists(ux_file):
        return {}
    try:
        with open(ux_file, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return {}


def _load_html(raw_html_path: str):
    """Load and parse HTML file."""
    if not raw_html_path or not os.path.exists(raw_html_path):
        return None
    from bs4 import BeautifulSoup
    with open(raw_html_path, "r", encoding="utf-8") as f:
        return BeautifulSoup(f.read(), "html.parser")


def _save_findings(scan_id: int, category: str, findings: list[dict]) -> None:
    """Persist findings to DB, mapping only the fields insert_finding accepts."""
    for f in findings:
        db.insert_finding(
            scan_id=scan_id,
            category=category,
            check_name=f["check_name"],
            severity=f["severity"],
            message=f["message"],
            page_id=f.get("page_id"),
            recommendation=f.get("recommendation", ""),
        )


def _clear_old_findings(scan_id: int) -> None:
    """Delete old findings for this scan so stale results don't persist."""
    conn = db.get_conn()
    conn.execute("DELETE FROM findings WHERE scan_id = ?", (scan_id,))
    conn.commit()
    conn.close()


def _process_findings(raw_findings: list[dict], total_pages: int,
                      check_penalties: dict = None) -> list[dict]:
    """Full pipeline: validate → aggregate → enrich findings.
    
    Returns enriched findings with confidence, affected_pages, total_violations, penalty.
    check_penalties: optional dict mapping check_name → custom penalty (e.g. SEO_CHECK_PENALTIES).
    """
    # Step 1: Remove info-level, duplicates, false positives
    validated = validate_findings(raw_findings)

    # Step 2: Aggregate same-issue findings across pages
    aggregated = aggregate_findings(validated, total_pages, check_penalties=check_penalties)

    return aggregated


def run_analyzers(scan_id: int, fast_mode: bool = False) -> dict:
    """Run analyzers with a lighter fast-path when requested.

    Pipeline: Detection → Validate → Deduplicate → Enrich → Score

    Returns:
        {
            "ui": {"score": int, "grade": str, "findings": [...], "category_scores": {...}},
            "ux": {"score": int, "grade": str, "findings": [...], "category_scores": {...}},
            "seo": {"score": int, "grade": str, "category_scores": {...}},
            "overall": {"score": int, "grade": str}
        }
    """
    print(f"\n{'='*60}")
    print(f"  ANALYZERS — Scan #{scan_id}")
    print(f"{'='*60}")

    pages = db.get_pages(scan_id)
    if not pages:
        print(f"[Analyzers] No pages found — skipping")
        return {"ui": {"score": 0, "grade": "N/A", "findings": []},
                "ux": {"score": 0, "grade": "N/A", "findings": []},
                "seo": {"score": 0, "grade": "N/A"},
                "overall": {"score": 0, "grade": "N/A"}}

    total_pages = len(pages)
    print(f"[Analyzers] Processing {total_pages} pages...")

    # ── Step 1: Load context data ─────────────────────────
    ux_data = _load_ux_data(scan_id)
    page_htmls = {}
    for p in pages:
        soup = _load_html(p.get("raw_html_path"))
        if soup:
            page_htmls[p["url"]] = soup

    scan = db.get_scan(scan_id)
    origin = ""
    if scan:
        conn = db.get_conn()
        site = conn.execute(
            "SELECT * FROM sites WHERE id = ?", (scan["site_id"],)
        ).fetchone()
        conn.close()
        if site:
            origin = site["origin"]

    edges = db.get_edges(scan_id)
    all_elements = {}
    for p in pages:
        all_elements[p["url"]] = db.get_elements(p["id"])

    # ── Step 4: RAW DETECTION — run all analyzers ────────
    print(f"[Analyzers] Running UI analyzer...")
    ui_findings_raw, ui_vh_data = analyze_ui(scan_id, pages, page_htmls, ux_data, fast_mode=fast_mode)
    print(f"[Analyzers] UI: {len(ui_findings_raw)} raw findings detected")

    print(f"[Analyzers] Running UX analyzer...")
    ux_findings_raw = analyze_ux(scan_id, pages, page_htmls, edges, all_elements, ux_data, origin, fast_mode=fast_mode)
    print(f"[Analyzers] UX: {len(ux_findings_raw)} raw findings detected")

    print(f"[Analyzers] Running accessibility analyzer...")
    a11y_findings_raw = analyze_accessibility(scan_id, pages, page_htmls, all_elements, fast_mode=fast_mode)
    print(f"[Analyzers] A11y: {len(a11y_findings_raw)} raw findings detected")

    print(f"[Analyzers] Running visual analyzer...")
    vision_findings_raw = analyze_visual(scan_id, pages, ux_data)
    print(f"[Analyzers] Vision: {len(vision_findings_raw)} raw findings detected")

    # ── Step 5: VALIDATE + DEDUPLICATE + ENRICH ──────────
    print(f"[Analyzers] Validating & enriching findings...")
    # UI: validate → aggregate (one finding per check_name)
    ui_findings = _process_findings(ui_findings_raw, total_pages)

    # UX + A11y: combine, validate, aggregate
    all_ux_raw = ux_findings_raw + a11y_findings_raw
    ux_findings = _process_findings(all_ux_raw, total_pages)

    # SEO: keep ALL raw findings (including info/recommendations) for report
    # But only score non-info findings
    seo_findings_raw = db.get_findings(scan_id, "seo")
    seo_findings_scored = _process_findings(seo_findings_raw, total_pages,
                                            check_penalties=SEO_CHECK_PENALTIES)  # for scoring only

    # Vision: keep raw (LLM findings are already validated by the model)
    vision_findings = vision_findings_raw

    print(f"[Analyzers] Enriched: UI={len(ui_findings)}, UX={len(ux_findings)}, SEO={len(seo_findings_raw)}, Vision={len(vision_findings)}")

    # ── Step 6: Save enriched findings ────────────────────
    print(f"[Analyzers] Saving findings to database...")
    _save_findings(scan_id, "ui", ui_findings)
    _save_findings(scan_id, "ux", ux_findings)
    _save_findings(scan_id, "a11y", [])  # Already merged into ux
    _save_findings(scan_id, "vision", vision_findings)
    # SEO: already saved in Step 2, only score here

    # ── Step 7: SCORE — with N/A support ──────────────────
    print(f"[Analyzers] Computing scores...")
    ui_checked = ui_vh_data.get("checked_categories") or set(UI_WEIGHTS.keys())
    ui_result = compute_ui_score(ui_findings, vh_score=ui_vh_data["visual_hierarchy_score"],
                                 checked_categories=ui_checked)
    ux_result = compute_ux_score(ux_findings, checked_categories=set(UX_WEIGHTS.keys()))
    seo_result = compute_seo_score(seo_findings_scored, checked_categories=set(SEO_WEIGHTS.keys()))

    overall_result = compute_overall_score(
        ui_result["ui_score"], ux_result["ux_score"], seo_result["seo_score"]
    )

    # ── Step 8: Save ALL scores atomically ───────────────
    print(f"[Analyzers] Saving scores to database...")
    db.update_scan(
        scan_id,
        ui_score=ui_result["ui_score"],
        ux_score=ux_result["ux_score"],
        seo_score=seo_result["seo_score"],
        overall_score=overall_result["overall_score"],
    )

    print(f"\n  --- SCORES ---")
    print(f"  UI:  {ui_result['ui_score']}/100 ({ui_result['grade']})")
    print(f"  UX:  {ux_result['ux_score']}/100 ({ux_result['grade']})")
    print(f"  SEO: {seo_result['seo_score']}/100 ({seo_result['grade']})")
    print(f"  Overall: {overall_result['overall_score']}/100 ({overall_result['grade']})")
    print(f"{'='*60}\n")

    return {
        "ui": {
            "score": ui_result["ui_score"],
            "grade": ui_result["grade"],
            "findings": ui_findings,
            "category_scores": ui_result["category_scores"],
            "by_severity": ui_result["by_severity"],
        },
        "ux": {
            "score": ux_result["ux_score"],
            "grade": ux_result["grade"],
            "findings": ux_findings,
            "category_scores": ux_result["category_scores"],
            "by_severity": ux_result["by_severity"],
        },
        "seo": {
            "score": seo_result["seo_score"],
            "grade": seo_result["grade"],
            "findings": seo_findings_raw,  # ALL findings including info/recommendations
            "category_scores": seo_result["category_scores"],
            "by_severity": seo_result["by_severity"],
        },
        "overall": overall_result,
    }
