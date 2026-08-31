"""Standalone script to run a scan — invoked as subprocess for direct CLI usage."""
import asyncio
import sys
import os
import time
import concurrent.futures

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
    scan = db.get_scan(scan_id)
    scan_mode = (scan.get("scan_mode") if scan else "fast").lower() if scan else "fast"
    if scan_mode not in {"fast", "deep"}:
        scan_mode = "fast"

    # ─────────────────────────────────────────────────────────────────────
    # STEP 1: CRAWL (sequential, must complete first)
    # ─────────────────────────────────────────────────────────────────────
    step_start = time.time()
    print(f"\n{'#'*60}")
    print(f"  STEP 1/8: CRAWLING")
    print(f"{'#'*60}")
    asyncio.run(crawl_site(scan_id))
    step_elapsed = time.time() - step_start
    print(f"  >> Step 1 done in {step_elapsed:.1f}s\n")

    # ─────────────────────────────────────────────────────────────────────
    # STEP 2: SEO CHECKS
    # ─────────────────────────────────────────────────────────────────────
    step_start = time.time()
    print(f"{'#'*60}")
    print(f"  STEP 2/8: SEO CHECKS")
    print(f"{'#'*60}")
    run_seo_checks(scan_id, fast_mode=(scan_mode == "fast"))
    step_elapsed = time.time() - step_start
    print(f"  >> Step 2 done in {step_elapsed:.1f}s\n")

    # STEPS 3-5: independent analysis tasks run concurrently after SEO.
    step_start = time.time()
    print(f"{'#'*60}")
    print(f"  STEPS 3-5: ANALYZERS + ACCESSIBILITY + MOBILE (PARALLEL)")
    print(f"{'#'*60}")

    def _run_accessibility():
        try:
            from accessibility_checks import run_axe_on_pages, save_accessibility_to_db
            pages = db.get_pages(scan_id)
            pages_to_check = pages[:3]
            print(f"[A11y] Running axe-core on {len(pages_to_check)} pages...")
            a11y_result = asyncio.run(run_axe_on_pages(pages_to_check, max_pages=3))
            save_accessibility_to_db(scan_id, a11y_result)
            print(f"[A11y] Score: {a11y_result['score']}/100 — {len(a11y_result['issues'])} issue types")
        except Exception as e:
            print(f"[A11y] Accessibility check failed: {e}")

    def _run_mobile():
        try:
            from mobile_responsiveness import run_mobile_checks
            from mobile_responsiveness.scoring import score_mobile_results
            pages = db.get_pages(scan_id)
            pages_to_check = [p for p in pages if p.get("status_code") and 200 <= p["status_code"] < 400][:3]
            print(f"[Mobile] Testing {len(pages_to_check)} pages...")
            raw_mobile = asyncio.run(run_mobile_checks(pages_to_check, max_pages=3, fast_mode=False))
            mobile_result = score_mobile_results(raw_mobile)
            db.save_mobile_findings(scan_id, mobile_result)
            print(f"[Mobile] Score: {mobile_result['mobile_score']}/100 ({mobile_result['grade']})")
            return mobile_result["mobile_score"]
        except Exception as e:
            print(f"[Mobile] Mobile check failed: {e}")
            return 0

    mobile_score = 0
    with concurrent.futures.ThreadPoolExecutor(max_workers=3) as executor:
        futures = {
            executor.submit(run_analyzers, scan_id): "analyzers",
            executor.submit(_run_accessibility): "accessibility",
            executor.submit(_run_mobile): "mobile",
        }
        for future in concurrent.futures.as_completed(futures):
            name = futures[future]
            try:
                result = future.result()
                if name == "analyzers":
                    results = result
                elif name == "mobile":
                    mobile_score = result
            except Exception as e:
                print(f"[{name.upper()}] Failed: {e}")
    step_elapsed = time.time() - step_start
    print(f"  >> Steps 3-5 done in {step_elapsed:.1f}s\n")

    # ─────────────────────────────────────────────────────────────────────
    # STEPS 6-9: PARALLEL TASKS (tech stack, features, CTA, security)
    # ─────────────────────────────────────────────────────────────────────
    step_start = time.time()
    print(f"{'#'*60}")
    print(f"  STEPS 6-9: TECH STACK + FEATURES + CTA + SECURITY (PARALLEL)")
    print(f"{'#'*60}")

    pages = db.get_pages(scan_id)
    page_htmls = {}
    for p in pages:
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
        mf_result = run_missing_features_checks(pages, page_htmls)
        mf_scored = score_features(mf_result)
        db.save_missing_features_findings(scan_id, mf_scored)
        print(f"[Features] Website type: {mf_scored['website_type']}")
        print(f"[Features] Score: {mf_scored['missing_features_score']}/100 ({mf_scored['grade']})")
        return mf_scored["missing_features_score"]

    def _run_cta():
        from cta_audit import run_cta_audit
        from cta_audit.scoring import score_cta_audit
        cta_result = run_cta_audit(pages, page_htmls)
        cta_scored = score_cta_audit(cta_result)
        db.save_cta_findings(scan_id, cta_scored)
        print(f"[CTA] Score: {cta_scored['cta_score']}/100 ({cta_scored['grade']})")
        return cta_scored["cta_score"]

    def _run_security():
        from security_audit import run_security_audit
        from security_audit.scoring import score_security_audit
        sec_result = run_security_audit(pages, page_htmls)
        sec_scored = score_security_audit(sec_result)
        db.save_security_findings(scan_id, sec_scored)
        print(f"[Security] Score: {sec_scored['security_score']}/100 ({sec_scored['grade']})")
        return sec_scored["security_score"]

    missing_features_score = 0
    cta_score = 0
    security_score = 0

    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as executor:
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
                print(f"[Parallel] {name} failed: {e}")

    step_elapsed = time.time() - step_start
    print(f"  >> Steps 6-9 done in {step_elapsed:.1f}s\n")

    # ─────────────────────────────────────────────────────────────────────
    # STEP 8: RECOMPUTE OVERALL SCORE
    # ─────────────────────────────────────────────────────────────────────
    from analyzers.scoring import compute_overall_score
    overall = compute_overall_score(
        results["ui"]["score"],
        results["ux"]["score"],
        results["seo"]["score"],
        mobile_score=mobile_score,
        missing_features_score=missing_features_score,
        cta_score=cta_score,
        security_score=security_score,
    )
    db.update_scan(scan_id, overall_score=overall["overall_score"], mobile_score=mobile_score, missing_features_score=missing_features_score, cta_score=cta_score, security_score=security_score)

    # ─────────────────────────────────────────────────────────────────────
    # FINAL SUMMARY
    # ─────────────────────────────────────────────────────────────────────
    total_elapsed = time.time() - total_start
    scan = db.get_scan(scan_id)
    print(f"\n{'#'*60}")
    print(f"  SCAN COMPLETE — Scan #{scan_id}")
    print(f"{'#'*60}")
    print(f"  Status: {scan['status']}")
    print(f"  Pages crawled: {scan['pages_crawled']}")
    print(f"  ---")
    print(f"  UI Score:        {results['ui']['score']}/100 ({results['ui']['grade']})")
    print(f"  UX Score:        {results['ux']['score']}/100 ({results['ux']['grade']})")
    print(f"  SEO Score:       {results['seo']['score']}/100 ({results['seo']['grade']})")
    print(f"  Mobile Score:    {mobile_score}/100")
    print(f"  Features Score:  {missing_features_score}/100")
    print(f"  CTA Score:       {cta_score}/100")
    print(f"  Security Score:  {security_score}/100")
    print(f"  Overall Score:   {overall['overall_score']}/100 ({overall['grade']})")
    print(f"  ---")
    print(f"  Total time: {int(total_elapsed // 60)}m {int(total_elapsed % 60)}s")
    print(f"{'#'*60}\n")

if __name__ == "__main__":
    main()
