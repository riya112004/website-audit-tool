"""Standalone script to run a scan — invoked as subprocess for direct CLI usage."""
import asyncio
import sys
import os

if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app import db
from app.crawler import crawl_site
from seo.seo_checker import run_seo_checks
from analyzers import run_analyzers

def main():
    if len(sys.argv) < 2:
        print("Usage: _run_scan.py <scan_id>")
        sys.exit(1)

    scan_id = int(sys.argv[1])
    db.init_db()

    # Step 1: Crawl
    asyncio.run(crawl_site(scan_id))

    # Step 2: SEO checks (populates findings in DB)
    run_seo_checks(scan_id)

    # Step 3: All analyzers + ALL scores in one pipeline
    results = run_analyzers(scan_id)

    # Step 4: Accessibility checks (axe-core)
    try:
        from accessibility_checks import run_axe_on_pages, save_accessibility_to_db
        pages = db.get_pages(scan_id)
        print(f"Scan {scan_id}: Running axe-core accessibility checks on {min(5, len(pages))} pages...")
        a11y_result = asyncio.run(run_axe_on_pages(pages, max_pages=5))
        save_accessibility_to_db(scan_id, a11y_result)
        print(f"Scan {scan_id}: Accessibility score = {a11y_result['score']}/100 ({len(a11y_result['issues'])} issue types found)")
    except Exception as e:
        print(f"Scan {scan_id}: Accessibility check failed: {e}")

    # Step 5: Technology stack detection
    try:
        from techstack import detect_tech, save_tech_to_db
        pages = db.get_pages(scan_id)
        tech_result = detect_tech(pages)
        save_tech_to_db(scan_id, tech_result)
        total_tech = sum(len(v) for v in tech_result.values())
        print(f"Scan {scan_id}: Detected {total_tech} technologies")
    except Exception as e:
        print(f"Scan {scan_id}: Tech stack detection failed: {e}")

    scan = db.get_scan(scan_id)
    print(f"Scan {scan_id}: {scan['status']} — {scan['pages_crawled']} pages, "
          f"UI: {results['ui']['score']}/100, UX: {results['ux']['score']}/100, "
          f"SEO: {results['seo']['score']}/100, "
          f"Overall: {results['overall']['overall_score']}/100")

if __name__ == "__main__":
    main()
