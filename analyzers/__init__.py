"""Analyzer orchestrator — runs UI, UX, Accessibility, and Vision analyzers."""
import json
import os

from app import db
from analyzers.ui_analyzer import analyze_ui
from analyzers.ux_analyzer import analyze_ux
from analyzers.accessibility_analyzer import analyze_accessibility
from analyzers.vision_analyzer import analyze_visual
from analyzers.scoring import compute_ui_score, compute_ux_score, compute_overall_score


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


def run_analyzers(scan_id: int) -> dict:
    """Run all analyzers and return structured results.

    Returns:
        {
            "ui": {"score": 65, "grade": "Average", "findings": [...]},
            "ux": {"score": 60, "grade": "Needs Improvement", "findings": [...]},
            "overall": {"score": 62, "grade": "Needs Improvement"}
        }
    """
    pages = db.get_pages(scan_id)
    if not pages:
        return {"ui": {"score": 0, "grade": "N/A", "findings": []},
                "ux": {"score": 0, "grade": "N/A", "findings": []},
                "overall": {"score": 0, "grade": "N/A"}}

    # Load context data
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

    # Run analyzers
    ui_findings = analyze_ui(scan_id, pages, page_htmls, ux_data)
    ux_findings = analyze_ux(scan_id, pages, page_htmls, edges, all_elements, ux_data, origin)
    a11y_findings = analyze_accessibility(scan_id, pages, page_htmls, all_elements)
    vision_findings = analyze_visual(scan_id, pages, ux_data)

    # Save all findings to DB
    _save_findings(scan_id, "ui", ui_findings)
    _save_findings(scan_id, "ux", ux_findings)
    _save_findings(scan_id, "a11y", a11y_findings)
    _save_findings(scan_id, "vision", vision_findings)

    # Compute scores (accessibility findings count towards UX accessibility category)
    ui_result = compute_ui_score(ui_findings)
    all_ux_findings = ux_findings + a11y_findings
    ux_result = compute_ux_score(all_ux_findings)
    overall_result = compute_overall_score(ui_result["ui_score"], ux_result["ux_score"])

    # Save scores to scan record
    db.update_scan(
        scan_id,
        ui_score=ui_result["ui_score"],
        ux_score=ux_result["ux_score"],
        overall_score=overall_result["overall_score"],
    )

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
            "findings": all_ux_findings,
            "category_scores": ux_result["category_scores"],
            "by_severity": ux_result["by_severity"],
        },
        "vision": {
            "findings": vision_findings,
        },
        "overall": overall_result,
    }
