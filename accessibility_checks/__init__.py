"""Accessibility checker using axe-core via Playwright.

Runs axe-core accessibility audit on crawled pages.
Returns structured results with score, issues, and passed checks.
"""
import asyncio
import os

from app import db


async def run_axe_on_pages(pages: list[dict], max_pages: int = 5) -> dict:
    """Run axe-core on up to max_pages pages using Playwright.
    
    Returns:
        {
            "score": int (0-100),
            "issues": [{"type": str, "severity": str, "count": int, "description": str, "recommendation": str}],
            "passed_checks": int,
            "total_checks": int,
            "pages_checked": int,
            "raw_violations": list  # raw axe violations for detailed per-page view
        }
    """
    print(f"\n[Accessibility] Starting axe-core audit...")
    try:
        from playwright.async_api import async_playwright
        from axe_playwright_python.async_playwright import Axe
    except ImportError:
        return {
            "score": 0,
            "issues": [],
            "passed_checks": 0,
            "total_checks": 0,
            "pages_checked": 0,
            "raw_violations": [],
            "error": "axe-playwright-python not installed",
        }

    # Select pages to check (homepage first, then random sample)
    crawlable = [p for p in pages if p.get("status_code") and 200 <= p["status_code"] < 400]
    if not crawlable:
        return {
            "score": 0,
            "issues": [],
            "passed_checks": 0,
            "total_checks": 0,
            "pages_checked": 0,
            "raw_violations": [],
        }

    # Prioritize homepage
    homepage = [p for p in crawlable if p.get("depth", 0) == 0]
    others = [p for p in crawlable if p.get("depth", 0) > 0]
    selected = (homepage + others)[:max_pages]

    axe = Axe()
    all_violations = []
    all_violations_raw = []
    pages_checked = 0

    async with async_playwright() as pw:
        browser = await pw.chromium.launch(
            headless=True,
            args=["--disable-blink-features=AutomationControlled"],
        )
        context = await browser.new_context(
            viewport={"width": 1280, "height": 720},
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        )

        for p in selected:
            try:
                print(f"[Accessibility] Checking: {p['url'][:60]}...")
                page = await context.new_page()
                await page.goto(p["url"], timeout=20000, wait_until="domcontentloaded")
                await page.wait_for_timeout(2000)  # let page settle

                results = await axe.run(page, options={"resultTypes": ["violations"]})
                pages_checked += 1
                violations_count = len(results.response.get("violations", []))
                print(f"[Accessibility] [{pages_checked}/{len(selected)}] {p['url'][:50]} — {violations_count} violation types found")

                for v in results.response.get("violations", []):
                    # Count nodes (affected elements) per violation
                    node_count = len(v.get("nodes", []))
                    all_violations.append({
                        "id": v.get("id", "unknown"),
                        "impact": v.get("impact", "minor"),
                        "description": v.get("description", ""),
                        "help": v.get("help", ""),
                        "helpUrl": v.get("helpUrl", ""),
                        "tags": v.get("tags", []),
                        "count": node_count,
                        "page_url": p["url"],
                        "page_id": p["id"],
                    })
                    all_violations_raw.append(v)

                await page.close()
            except Exception:
                try:
                    await page.close()
                except Exception:
                    pass
                continue

        await context.close()
        await browser.close()

    if pages_checked == 0:
        return {
            "score": 0,
            "issues": [],
            "passed_checks": 0,
            "total_checks": 0,
            "pages_checked": 0,
            "raw_violations": [],
        }

    # Aggregate violations by type
    grouped = {}
    for v in all_violations:
        vid = v["id"]
        if vid not in grouped:
            grouped[vid] = {
                "type": vid,
                "severity": v["impact"],
                "count": 0,
                "description": v["description"],
                "recommendation": v["help"],
                "helpUrl": v["helpUrl"],
                "tags": v["tags"],
                "affected_pages": set(),
            }
        grouped[vid]["count"] += v["count"]
        grouped[vid]["affected_pages"].add(v["page_url"])
        # Keep highest severity if different pages report different impacts
        severity_order = {"critical": 0, "serious": 1, "moderate": 2, "minor": 3}
        if severity_order.get(v["impact"], 3) < severity_order.get(grouped[vid]["severity"], 3):
            grouped[vid]["severity"] = v["impact"]

    issues = []
    for g in grouped.values():
        g["affected_pages"] = len(g["affected_pages"])
        issues.append(g)

    # Sort by severity
    severity_order = {"critical": 0, "serious": 1, "moderate": 2, "minor": 3}
    issues.sort(key=lambda x: severity_order.get(x["severity"], 3))

    # Calculate score: start at 100, deduct per violation
    score = 100
    for issue in issues:
        impact = issue["severity"]
        count = issue["count"]
        if impact == "critical":
            score -= min(15, count * 3)
        elif impact == "serious":
            score -= min(10, count * 2)
        elif impact == "moderate":
            score -= min(5, count * 1)
        elif impact == "minor":
            score -= min(2, count * 0.5)
    score = max(0, min(100, round(score)))

    total_checks = len(axe_unique_rules())
    passed = total_checks - len(grouped)

    print(f"[Accessibility] Score: {score}/100 — {len(grouped)} issue types, {len(all_violations)} total violations")

    return {
        "score": score,
        "issues": issues,
        "passed_checks": max(0, passed),
        "total_checks": total_checks,
        "pages_checked": pages_checked,
        "raw_violations": all_violations_raw,
    }


def axe_unique_rules() -> list[str]:
    """List of common axe-core rule IDs for counting total checks."""
    return [
        "color-contrast", "valid-lang", "html-has-lang", "image-alt",
        "label", "button-name", "link-name", "duplicate-id",
        "heading-order", "region", "landmark-banner-is-top-level",
        "landmark-contentinfo-is-top-level", "landmark-main-is-top-level",
        "landmark-no-duplicate-banner", "landmark-no-duplicate-contentinfo",
        "landmark-one-main", "page-has-heading-one", "bypass",
        "tabindex", "aria-required-attr", "aria-valid-attr",
        "aria-valid-attr-value", "aria-roles", "aria-hidden-focus",
        "form-field-multiple-labels", "html-lang-valid",
        "meta-viewport", "document-title", "frame-title",
        "input-image-alt", "object-alt", "video-caption",
        "td-has-header", "th-has-data-cells", "scope-attr-valid",
        "skip-link", "link-in-text-block", "target-size",
        "meta-refresh", "no-autoplay-audio",
    ]


def save_accessibility_to_db(scan_id: int, result: dict) -> None:
    """Save axe-core results to the findings table with category 'accessibility'."""
    for issue in result.get("issues", []):
        severity_map = {"critical": "critical", "serious": "high", "moderate": "medium", "minor": "low"}
        severity = severity_map.get(issue["severity"], "info")

        affected = issue.get("affected_pages", 0)
        count = issue.get("count", 0)

        db.insert_finding(
            scan_id=scan_id,
            page_id=None,
            category="accessibility",
            check_name=issue["type"],
            severity=severity,
            message=f"{issue['description']} ({count} instances across {affected} pages)",
            recommendation=issue.get("recommendation", ""),
        )
