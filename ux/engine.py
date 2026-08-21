import json
import os
from urllib.parse import urlparse

from bs4 import BeautifulSoup

from app import db

CATEGORY = "ux"


def _add(scan_id, check_name, severity, message, page_id=None, recommendation=None):
    from ux.recommendations import RECOMMENDATIONS
    rec = recommendation or RECOMMENDATIONS.get(check_name, "")
    db.insert_finding(
        scan_id=scan_id,
        category=CATEGORY,
        check_name=check_name,
        severity=severity,
        message=message,
        page_id=page_id,
        recommendation=rec,
    )


def _load_html(raw_html_path: str | None) -> BeautifulSoup | None:
    if not raw_html_path or not os.path.exists(raw_html_path):
        return None
    with open(raw_html_path, "r", encoding="utf-8") as f:
        return BeautifulSoup(f.read(), "html.parser")


def _is_crawlable(p: dict) -> bool:
    status = p.get("status_code")
    html_path = p.get("raw_html_path")
    if not status or status < 200 or status >= 300:
        return False
    if not html_path or not os.path.exists(html_path):
        return False
    return True


def _load_ux_data(scan_id: int) -> dict:
    base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    data_dir = os.path.join(base, "data", "html", f"scan{scan_id}")
    ux_file = os.path.join(data_dir, "ux_data.json")
    if not os.path.exists(ux_file):
        return {}
    try:
        with open(ux_file, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return {}


def run_ux_checks(scan_id: int):
    db.delete_findings(scan_id, CATEGORY)

    pages = db.get_pages(scan_id)
    if not pages:
        return

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
        site = conn.execute("SELECT * FROM sites WHERE id = ?", (scan["site_id"],)).fetchone()
        conn.close()
        if site:
            origin = site["origin"]

    edges = db.get_edges(scan_id)

    all_elements = {}
    for p in pages:
        all_elements[p["url"]] = db.get_elements(p["id"])

    context = {
        "scan_id": scan_id,
        "pages": pages,
        "page_htmls": page_htmls,
        "ux_data": ux_data,
        "origin": origin,
        "edges": edges,
        "all_elements": all_elements,
    }

    from ux.checks import navigation
    from ux.checks import interaction
    from ux.checks import forms
    from ux.checks import mobile
    from ux.checks import accessibility as accessibility_ux
    from ux.checks import visual
    from ux.checks import readability
    from ux.checks import performance as performance_ux
    from ux.checks import errors as errors_ux
    from ux.checks import consistency
    from ux.checks import trust

    navigation.run(context)
    interaction.run(context)
    forms.run(context)
    mobile.run(context)
    accessibility_ux.run(context)
    visual.run(context)
    readability.run(context)
    performance_ux.run(context)
    errors_ux.run(context)
    consistency.run(context)
    trust.run(context)

    return db.get_findings(scan_id, CATEGORY)
