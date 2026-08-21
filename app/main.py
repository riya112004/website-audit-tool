import asyncio
import os
import subprocess
import sys
import traceback
from urllib.parse import urlparse
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from app import db

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(BASE_DIR, "data")


@asynccontextmanager
async def lifespan(app: FastAPI):
    db.init_db()
    yield


app = FastAPI(title="Site Audit Crawler", lifespan=lifespan)
templates = Jinja2Templates(directory=os.path.join(BASE_DIR, "templates"))

app.mount("/static", StaticFiles(directory=os.path.join(BASE_DIR, "static")), name="static")


# ─── Dashboard ──────────────────────────────────────────────

@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    scans = db.get_scans()
    return templates.TemplateResponse(request, "index.html", {"scans": scans})


# ─── Scan ───────────────────────────────────────────────────

@app.post("/scan")
async def start_scan(request: Request):
    form = await request.form()
    start_url = form.get("url", "").strip()
    max_pages = int(form.get("max_pages", 50))
    max_depth = int(form.get("max_depth", 3))

    if not start_url:
        raise HTTPException(400, "URL is required")

    if not start_url.startswith(("http://", "https://")):
        start_url = "https://" + start_url

    parsed = urlparse(start_url)
    origin = f"{parsed.scheme}://{parsed.netloc}"
    site = db.get_or_create_site(origin)
    scan = db.create_scan(site["id"], start_url, max_pages, max_depth)

    # Fire-and-forget subprocess — separate process for Playwright
    python = sys.executable
    script = os.path.join(BASE_DIR, "_run_scan.py")
    subprocess.Popen(
        [python, "-u", script, str(scan["id"])],
        cwd=BASE_DIR,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        stdin=subprocess.DEVNULL,
    )

    return RedirectResponse(url=f"/scans/{scan['id']}", status_code=303)


@app.get("/scans/{scan_id}", response_class=HTMLResponse)
async def scan_detail(request: Request, scan_id: int):
    scan = db.get_scan(scan_id)
    if not scan:
        raise HTTPException(404, "Scan not found")

    pages = db.get_pages(scan_id)
    edges = db.get_edges(scan_id)
    diff = db.diff_against_previous_scan(scan_id)

    page_details = {}
    for p in pages:
        page_details[p["id"]] = {
            "elements": db.get_elements(p["id"]),
            "interactions": db.get_interactions(p["id"]),
        }

    seo_findings = db.get_findings(scan_id, "seo")
    seo_summary = db.get_findings_summary(scan_id).get("seo", {})

    COUNTED_CHECKS = {"heading_order_broken", "non_descriptive_link_text"}

    seo_grouped = {}
    for f in seo_findings:
        name = f["check_name"]
        if name not in seo_grouped:
            seo_grouped[name] = {"severity": f["severity"], "recommendation": f["recommendation"], "issues": []}
        seo_grouped[name]["issues"].append(f)

    for name, group in seo_grouped.items():
        if name in COUNTED_CHECKS:
            total = 0
            for issue in group["issues"]:
                msg = issue["message"]
                paren = msg.find("(")
                space_after_paren = msg.find(" ", paren + 1) if paren >= 0 else -1
                if paren >= 0 and space_after_paren > paren:
                    try:
                        total += int(msg[paren + 1:space_after_paren])
                    except ValueError:
                        total += 1
                else:
                    total += 1
            group["total_violations"] = total
        else:
            group["total_violations"] = 0

    # UX findings
    ux_findings = db.get_findings(scan_id, "ux")
    ux_summary = db.get_findings_summary(scan_id).get("ux", {})

    # New analyzer findings
    ui_findings = db.get_findings(scan_id, "ui")
    ui_summary = db.get_findings_summary(scan_id).get("ui", {})
    a11y_findings = db.get_findings(scan_id, "a11y")
    a11y_summary = db.get_findings_summary(scan_id).get("a11y", {})
    vision_findings = db.get_findings(scan_id, "vision")

    UX_COUNTED_CHECKS = {
        "broken_internal_links", "empty_href_links", "hash_only_links", "js_void_links",
        "excessive_nav_items", "duplicate_nav_links", "unclear_anchor_text", "orphan_pages",
        "unlabeled_buttons", "tiny_click_targets", "missing_accessible_names",
        "inputs_without_labels", "missing_placeholders", "incorrect_input_types",
        "very_long_forms", "extremely_long_paragraphs", "missing_headings",
        "console_errors", "broken_images", "inconsistent_navigation",
        "inconsistent_cta_naming", "inconsistent_footer",
        "poor_heading_hierarchy_a11y", "missing_accessible_names_a11y",
        "images_no_dimensions", "mobile_horizontal_overflow", "mobile_small_text",
        "mobile_tiny_touch_targets", "mobile_fixed_element_blocking",
    }

    ux_grouped = {}
    for f in ux_findings:
        name = f["check_name"]
        if name not in ux_grouped:
            ux_grouped[name] = {"severity": f["severity"], "recommendation": f["recommendation"], "issues": []}
        ux_grouped[name]["issues"].append(f)

    for name, group in ux_grouped.items():
        if name in UX_COUNTED_CHECKS:
            total = 0
            for issue in group["issues"]:
                msg = issue["message"]
                paren = msg.find("(")
                space_after_paren = msg.find(" ", paren + 1) if paren >= 0 else -1
                if paren >= 0 and space_after_paren > paren:
                    try:
                        total += int(msg[paren + 1:space_after_paren])
                    except ValueError:
                        total += 1
                else:
                    total += 1
            group["total_violations"] = total
        else:
            group["total_violations"] = 0

    # Group UI findings
    ui_grouped = {}
    for f in ui_findings:
        name = f["check_name"]
        if name not in ui_grouped:
            ui_grouped[name] = {"severity": f["severity"], "recommendation": f["recommendation"], "issues": []}
        ui_grouped[name]["issues"].append(f)

    # Group A11y findings
    a11y_grouped = {}
    for f in a11y_findings:
        name = f["check_name"]
        if name not in a11y_grouped:
            a11y_grouped[name] = {"severity": f["severity"], "recommendation": f["recommendation"], "issues": []}
        a11y_grouped[name]["issues"].append(f)

    from analyzers.scoring import compute_ui_score, compute_ux_score, compute_seo_score, compute_overall_score
    ui_score_data = compute_ui_score(ui_findings)
    all_ux = ux_findings + a11y_findings
    ux_score_data = compute_ux_score(all_ux)
    seo_score_data = compute_seo_score(seo_findings)
    overall_score_data = compute_overall_score(
        ui_score_data["ui_score"], ux_score_data["ux_score"], seo_score_data["seo_score"]
    )

    return templates.TemplateResponse(request, "scan_detail.html", {
        "scan": scan,
        "pages": pages,
        "edges": edges,
        "diff": diff,
        "page_details": page_details,
        "seo_findings": seo_findings,
        "seo_summary": seo_summary,
        "seo_grouped": seo_grouped,
        "ux_findings": ux_findings,
        "ux_summary": ux_summary,
        "ux_grouped": ux_grouped,
        "ux_score_data": ux_score_data,
        "seo_score_data": seo_score_data,
        "ui_findings": ui_findings,
        "ui_summary": ui_summary,
        "ui_grouped": ui_grouped,
        "ui_score_data": ui_score_data,
        "a11y_findings": a11y_findings,
        "a11y_summary": a11y_summary,
        "a11y_grouped": a11y_grouped,
        "vision_findings": vision_findings,
        "overall_score_data": overall_score_data,
    })


# ─── API (for AJAX polling) ────────────────────────────────

@app.get("/api/scan/{scan_id}")
async def api_scan_status(scan_id: int):
    scan = db.get_scan(scan_id)
    if not scan:
        raise HTTPException(404, "Scan not found")
    return JSONResponse(dict(scan))


@app.get("/api/scan/{scan_id}/pages")
async def api_scan_pages(scan_id: int):
    return JSONResponse([dict(p) for p in db.get_pages(scan_id)])


@app.get("/api/scan/{scan_id}/progress")
async def api_scan_progress(scan_id: int):
    scan = db.get_scan(scan_id)
    if not scan:
        raise HTTPException(404, "Scan not found")
    pages = db.get_pages(scan_id)
    findings = db.get_findings(scan_id, "seo")
    seo_summary = db.get_findings_summary(scan_id).get("seo", {})
    page_list = []
    for p in pages:
        elems = db.get_elements(p["id"])
        page_list.append({
            "url": p["url"],
            "title": p["title"],
            "status_code": p["status_code"],
            "elements_count": len(elems),
        })
    return JSONResponse({
        "status": scan["status"],
        "pages_crawled": scan["pages_crawled"] or 0,
        "elements_found": scan["elements_found"] or 0,
        "pages": page_list,
        "findings_count": len(findings),
        "seo_summary": seo_summary,
    })
