"""Standalone script to run a scan — invoked as subprocess for direct CLI usage."""
import asyncio
import sys
import os
import time

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

    total_start = time.time()

    # Step 1: Crawl
    step_start = time.time()
    print(f"\n{'#'*60}")
    print(f"  STEP 1/5: CRAWLING")
    print(f"{'#'*60}")
    asyncio.run(crawl_site(scan_id))
    step_elapsed = time.time() - step_start
    print(f"  >> Step 1 done in {step_elapsed:.1f}s\n")

    # Step 2: SEO checks (populates findings in DB)
    step_start = time.time()
    print(f"{'#'*60}")
    print(f"  STEP 2/5: SEO CHECKS")
    print(f"{'#'*60}")
    run_seo_checks(scan_id)
    step_elapsed = time.time() - step_start
    print(f"  >> Step 2 done in {step_elapsed:.1f}s\n")

    # Step 3: All analyzers + ALL scores in one pipeline
    step_start = time.time()
    print(f"{'#'*60}")
    print(f"  STEP 3/5: UI/UX/SEO ANALYZERS + SCORING")
    print(f"{'#'*60}")
    results = run_analyzers(scan_id)
    step_elapsed = time.time() - step_start
    print(f"  >> Step 3 done in {step_elapsed:.1f}s\n")

    # Step 4: Accessibility checks (axe-core)
    step_start = time.time()
    print(f"{'#'*60}")
    print(f"  STEP 4/5: ACCESSIBILITY (axe-core)")
    print(f"{'#'*60}")
    try:
        from accessibility_checks import run_axe_on_pages, save_accessibility_to_db
        pages = db.get_pages(scan_id)
        print(f"[A11y] Running axe-core on {min(5, len(pages))} pages...")
        a11y_result = asyncio.run(run_axe_on_pages(pages, max_pages=5))
        save_accessibility_to_db(scan_id, a11y_result)
        print(f"[A11y] Score: {a11y_result['score']}/100 — {len(a11y_result['issues'])} issue types")
    except Exception as e:
        print(f"[A11y] Accessibility check failed: {e}")
    step_elapsed = time.time() - step_start
    print(f"  >> Step 4 done in {step_elapsed:.1f}s\n")

    # Step 5: Technology stack detection
    step_start = time.time()
    print(f"{'#'*60}")
    print(f"  STEP 5/5: TECH STACK DETECTION")
    print(f"{'#'*60}")
    try:
        from techstack import detect_tech, save_tech_to_db
        pages = db.get_pages(scan_id)
        tech_result = detect_tech(pages)
        save_tech_to_db(scan_id, tech_result)
        total_tech = sum(len(v) for v in tech_result.values())
        print(f"[TechStack] Detected {total_tech} technologies")
    except Exception as e:
        print(f"[TechStack] Detection failed: {e}")
    step_elapsed = time.time() - step_start
    print(f"  >> Step 5 done in {step_elapsed:.1f}s\n")

    # Final summary
    total_elapsed = time.time() - total_start
    scan = db.get_scan(scan_id)
    print(f"\n{'#'*60}")
    print(f"  SCAN COMPLETE — Scan #{scan_id}")
    print(f"{'#'*60}")
    print(f"  Status: {scan['status']}")
    print(f"  Pages crawled: {scan['pages_crawled']}")
    print(f"  ---")
    print(f"  UI Score:       {results['ui']['score']}/100 ({results['ui']['grade']})")
    print(f"  UX Score:       {results['ux']['score']}/100 ({results['ux']['grade']})")
    print(f"  SEO Score:      {results['seo']['score']}/100 ({results['seo']['grade']})")
    print(f"  Overall Score:  {results['overall']['overall_score']}/100 ({results['overall']['grade']})")
    print(f"  ---")
    print(f"  Total time: {int(total_elapsed // 60)}m {int(total_elapsed % 60)}s")
    print(f"{'#'*60}\n")

if __name__ == "__main__":
    main()
