"""Standalone script to run a FAST scan — crawl only + 1-page mobile check."""
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
        print("Usage: _run_scan_fast.py <scan_id>")
        sys.exit(1)

    scan_id = int(sys.argv[1])
    db.init_db()

    total_start = time.time()
    scan = db.get_scan(scan_id)
    if not scan:
        print(f"Scan #{scan_id} not found")
        sys.exit(1)

    print(f"\n{'#'*60}")
    print(f"  FAST SCAN #{scan_id}")
    print(f"{'#'*60}\n")

    # ─── STEP 1: CRAWL (5 pages max, lower concurrency for speed)
    step_start = time.time()
    print(f"{'#'*60}")
    print(f"  STEP 1/5: CRAWL (5 pages max, 4 workers)")
    print(f"{'#'*60}")
    asyncio.run(crawl_site(scan_id))
    step_elapsed = time.time() - step_start
    print(f"  >> Step 1 done in {step_elapsed:.1f}s\n")

    pages = db.get_pages(scan_id)
    if not pages:
        print("[Fast scan] No pages were crawled; audit stages skipped")
        return

    # ─── STEP 2: SEO CHECKS (first 3 pages in fast mode)
    step_start = time.time()
    print(f"{'#'*60}")
    print(f"  STEP 2/5: SEO CHECKS (FAST)")
    print(f"{'#'*60}")
    run_seo_checks(scan_id, fast_mode=True)
    step_elapsed = time.time() - step_start
    print(f"  >> Step 2 done in {step_elapsed:.1f}s\n")

    # ─── STEP 3: UI/UX/SEO ANALYZERS + SCORING
    step_start = time.time()
    print(f"{'#'*60}")
    print(f"  STEP 3/5: UI/UX/SEO ANALYZERS + SCORING")
    print(f"{'#'*60}")
    results = run_analyzers(scan_id, fast_mode=True)
    step_elapsed = time.time() - step_start
    print(f"  >> Step 3 done in {step_elapsed:.1f}s\n")

    # ─── STEP 4: MOBILE (1 page, single fast breakpoint)
    step_start = time.time()
    print(f"{'#'*60}")
    print(f"  STEP 4/5: MOBILE (1 page, 390px only)")
    print(f"{'#'*60}")
    mobile_score = 0
    try:
        from mobile_responsiveness import run_mobile_checks
        from mobile_responsiveness.scoring import score_mobile_results
        pages = db.get_pages(scan_id)
        pages_to_check = [p for p in pages if p.get("status_code") and 200 <= p["status_code"] < 400][:1]
        if pages_to_check:
            print(f"[Mobile] Testing {len(pages_to_check)} page...")
            raw_mobile = asyncio.run(run_mobile_checks(pages_to_check, max_pages=1, fast_mode=True))
            mobile_result = score_mobile_results(raw_mobile)
            db.save_mobile_findings(scan_id, mobile_result)
            mobile_score = mobile_result["mobile_score"]
            print(f"[Mobile] Score: {mobile_score}/100 ({mobile_result['grade']})")
        else:
            print(f"[Mobile] No valid pages to check")
    except Exception as e:
        print(f"[Mobile] Check failed: {e}")
    step_elapsed = time.time() - step_start
    print(f"  >> Step 4 done in {step_elapsed:.1f}s\n")

    # ─── STEP 5: LIGHTWEIGHT CHECKS (Tech + Features + CTA + Security in parallel)
    step_start = time.time()
    print(f"{'#'*60}")
    print(f"  STEP 5/5: TECH/FEATURES/CTA/SECURITY (PARALLEL)")
    print(f"{'#'*60}")

    pages = db.get_pages(scan_id)
    light_pages = pages[:1]
    page_htmls = {}
    for p in light_pages:
        html_path = p.get("raw_html_path")
        if html_path and os.path.exists(html_path):
            with open(html_path, "r", encoding="utf-8") as f:
                page_htmls[p["id"]] = f.read()

    def _run_techstack():
        from techstack import detect_tech, save_tech_to_db
        tech_result = detect_tech(pages)
        save_tech_to_db(scan_id, tech_result)
        total_tech = sum(len(v) for v in tech_result.values())
        print(f"[TechStack] Detected {total_tech} technologies")

    def _run_features():
        from missing_features import run_missing_features_checks
        from missing_features.scoring import score_features
        mf_result = run_missing_features_checks(light_pages, page_htmls)
        mf_scored = score_features(mf_result)
        db.save_missing_features_findings(scan_id, mf_scored)
        print(f"[Features] Score: {mf_scored['missing_features_score']}/100")
        return mf_scored["missing_features_score"]

    def _run_cta():
        from cta_audit import run_cta_audit
        from cta_audit.scoring import score_cta_audit
        cta_result = run_cta_audit(light_pages, page_htmls)
        cta_scored = score_cta_audit(cta_result)
        db.save_cta_findings(scan_id, cta_scored)
        print(f"[CTA] Score: {cta_scored['cta_score']}/100")
        return cta_scored["cta_score"]

    def _run_security():
        from security_audit import run_security_audit
        from security_audit.scoring import score_security_audit
        sec_result = run_security_audit(light_pages, page_htmls)
        sec_scored = score_security_audit(sec_result)
        db.save_security_findings(scan_id, sec_scored)
        print(f"[Security] Score: {sec_scored['security_score']}/100")
        return sec_scored["security_score"]

    import concurrent.futures
    missing_features_score = 0
    cta_score = 0
    security_score = 0

    with concurrent.futures.ThreadPoolExecutor(max_workers=3) as executor:
        futures = {
            executor.submit(_run_techstack): "techstack",
            executor.submit(_run_features): "features",
            executor.submit(_run_cta): "cta",
            executor.submit(_run_security): "security",
        }
        for future in concurrent.futures.as_completed(futures):
            name = futures[future]
            try:
                result = future.result()
                if name == "features":
                    missing_features_score = result
                elif name == "cta":
                    cta_score = result
                elif name == "security":
                    security_score = result
            except Exception as e:
                print(f"[{name.upper()}] Failed: {e}")

    step_elapsed = time.time() - step_start
    print(f"  >> Step 5 done in {step_elapsed:.1f}s\n")

    # ─── FINAL SCORE
    from analyzers.scoring import compute_overall_score
    overall_score = compute_overall_score(
        results["ui"]["score"],
        results["ux"]["score"],
        results["seo"]["score"],
        mobile_score=mobile_score,
        missing_features_score=missing_features_score,
        cta_score=cta_score,
        security_score=security_score,
    )
    db.update_scan(
        scan_id,
        status="completed",
        finished_at=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        overall_score=overall_score["overall_score"],
        ui_score=results["ui"]["score"],
        ux_score=results["ux"]["score"],
        seo_score=results["seo"]["score"],
        mobile_score=mobile_score,
        missing_features_score=missing_features_score,
        cta_score=cta_score,
        security_score=security_score
    )

    total_elapsed = time.time() - total_start
    scan = db.get_scan(scan_id)
    print(f"{'#'*60}")
    print(f"  SCAN COMPLETE")
    print(f"{'#'*60}")
    print(f"  Status: {scan['status']}")
    print(f"  Pages crawled: {scan['pages_crawled']}")
    print(f"  ---")
    print(f"  UI Score:         {results['ui']['score']}/100")
    print(f"  UX Score:         {results['ux']['score']}/100")
    print(f"  SEO Score:        {results['seo']['score']}/100")
    print(f"  Mobile Score:    {mobile_score}/100")
    print(f"  Features Score:  {missing_features_score}/100")
    print(f"  CTA Score:       {cta_score}/100")
    print(f"  Security Score:  {security_score}/100")
    print(f"  Overall Score:   {overall_score['overall_score']}/100 ({overall_score['grade']})")
    print(f"  ---")
    print(f"  Total time: {int(total_elapsed // 60)}m {int(total_elapsed % 60)}s")
    print(f"{'#'*60}\n")

if __name__ == "__main__":
    main()
