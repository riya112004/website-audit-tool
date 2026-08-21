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
from analyzers.scoring import compute_seo_score, compute_overall_score

def main():
    if len(sys.argv) < 2:
        print("Usage: _run_scan.py <scan_id>")
        sys.exit(1)

    scan_id = int(sys.argv[1])
    db.init_db()

    asyncio.run(crawl_site(scan_id))
    run_seo_checks(scan_id)

    # Run UI/UX analyzers
    results = run_analyzers(scan_id)

    # Compute SEO score
    seo_findings = db.get_findings(scan_id, "seo")
    seo_result = compute_seo_score(seo_findings)

    # Compute overall with SEO included
    overall = compute_overall_score(
        results["ui"]["score"], results["ux"]["score"], seo_result["seo_score"]
    )

    # Save seo_score and overall
    db.update_scan(scan_id, seo_score=seo_result["seo_score"],
                   overall_score=overall["overall_score"])

    scan = db.get_scan(scan_id)
    print(f"Scan {scan_id}: {scan['status']} — {scan['pages_crawled']} pages, "
          f"UI: {results['ui']['score']}/100, UX: {results['ux']['score']}/100, "
          f"SEO: {seo_result['seo_score']}/100, "
          f"Overall: {overall['overall_score']}/100")

if __name__ == "__main__":
    main()
