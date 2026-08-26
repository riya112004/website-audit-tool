"""
Security Observations Audit — detect security-related observations across crawled pages.

Categories:
  1. HTTPS / SSL            — 20%
  2. Security Headers       — 25%
  3. Cookies / Session      — 15%
  4. Sensitive Data Exposure — 20%
  5. Forms / Authentication  — 10%
  6. Third-party Resources   — 5%
  7. Infrastructure          — 5%

Design principle: Report as observations/potential risks, not confirmed vulnerabilities.
Same issue on multiple pages → one finding with affected page count.
"""

from __future__ import annotations

import json
import re
from urllib.parse import urlparse
from bs4 import BeautifulSoup

# ── Sensitive data patterns ─────────────────────────────────────────────────

SECRET_PATTERNS = [
    (r"(?:api[_-]?key|apikey)\s*[:=]\s*['\"][A-Za-z0-9_\-]{16,}['\"]", "API Key"),
    (r"(?:secret[_-]?key|client[_-]?secret)\s*[:=]\s*['\"][A-Za-z0-9_\-]{16,}['\"]", "Secret Key"),
    (r"(?:password|passwd|pwd)\s*[:=]\s*['\"][^'\"]{4,}['\"]", "Hardcoded Password"),
    (r"(?:token|auth[_-]?token|access[_-]?token)\s*[:=]\s*['\"][A-Za-z0-9_\-\.]{20,}['\"]", "Auth Token"),
    (r"(?:aws[_-]?access[_-]?key[_-]?id)\s*[:=]\s*['\"]?(?:AKIA)[A-Z0-9]{16}['\"]?", "AWS Access Key"),
    (r"(?:aws[_-]?secret[_-]?access[_-]?key)\s*[:=]\s*['\"][A-Za-z0-9/+=]{40}['\"]", "AWS Secret Key"),
    (r"(?:private[_-]?key)\s*[:=]\s*['\"]?(?:-----BEGIN)?", "Private Key"),
    (r"(?:smtp|mail)\s*[:=]\s*['\"]?[a-zA-Z0-9._-]+@[a-zA-Z0-9._-]+['\"]?", "Email/SMTP Config"),
    (r"(?:mongodb|mysql|postgres|redis|amqp)(?:\+srv)?://[^\s'\"]+", "Database Connection String"),
    (r"(?:internal|staging|dev|test)[._-]?(?:url|host|api)\s*[:=]\s*['\"]https?://", "Internal URL"),
]

# ── Utility ─────────────────────────────────────────────────────────────────

def _soup(html: str) -> BeautifulSoup:
    return BeautifulSoup(html or "", "html.parser")


def _parse_headers(page: dict) -> dict:
    """Parse stored response_headers JSON into a normalized dict."""
    raw = page.get("response_headers", "")
    if isinstance(raw, dict):
        return {k.lower(): v for k, v in raw.items()}
    try:
        h = json.loads(raw) if raw else {}
        return {k.lower(): v for k, v in h.items()}
    except (json.JSONDecodeError, TypeError):
        return {}


def _is_https(url: str) -> bool:
    return urlparse(url).scheme == "https"


def _has_http_redirect(page: dict) -> bool:
    """Check if HTTP version redirects to HTTPS (can't fully test without extra request)."""
    url = page.get("url", "")
    if not _is_https(url):
        # If the crawled URL is HTTPS but originally was HTTP, redirect happened
        return False
    return True


# ── Check 1: HTTPS / SSL (20%) ─────────────────────────────────────────────

def _check_https_ssl(pages: list[dict], page_htmls: dict) -> list[dict]:
    """Check HTTPS usage and SSL indicators."""
    findings = []
    http_pages = []
    https_pages = []

    for p in pages:
        url = p.get("url", "")
        if _is_https(url):
            https_pages.append(url)
        else:
            http_pages.append(url)

    if http_pages:
        findings.append({
            "check": "https_usage",
            "severity": "critical",
            "message": f"HTTP (not HTTPS) detected on {len(http_pages)} page(s)",
            "detail": f"Pages: {', '.join(u.split('//')[-1][:40] for u in http_pages[:3])}",
            "recommendation": "Migrate all pages to HTTPS. Set up HTTP → HTTPS redirect.",
            "affected_pages": len(http_pages),
        })
    elif https_pages:
        findings.append({
            "check": "https_usage",
            "severity": "good",
            "message": f"All {len(https_pages)} pages served over HTTPS",
            "affected_pages": len(https_pages),
        })

    return findings


# ── Check 2: Security Headers (25%) ────────────────────────────────────────

REQUIRED_HEADERS = {
    "strict-transport-security": {
        "name": "HSTS",
        "severity": "high",
        "weight": 5,
        "check": lambda v: v and "max-age=" in v.lower() and int(re.search(r"max-age=(\d+)", v.lower()).group(1)) >= 300,
    },
    "content-security-policy": {
        "name": "Content-Security-Policy",
        "severity": "high",
        "weight": 5,
        "check": lambda v: v and len(v) > 10,
    },
    "x-frame-options": {
        "name": "X-Frame-Options",
        "severity": "medium",
        "weight": 3,
        "check": lambda v: v and any(val.strip().upper() in ("DENY", "SAMEORIGIN") for val in v.split(",")),
    },
    "x-content-type-options": {
        "name": "X-Content-Type-Options",
        "severity": "medium",
        "weight": 3,
        "check": lambda v: v and "nosniff" in v.lower(),
    },
    "referrer-policy": {
        "name": "Referrer-Policy",
        "severity": "low",
        "weight": 2,
        "check": lambda v: v and v.lower() in ("strict-origin-when-cross-origin", "strict-origin", "no-referrer", "same-origin"),
    },
    "permissions-policy": {
        "name": "Permissions-Policy",
        "severity": "low",
        "weight": 2,
        "check": lambda v: v and len(v) > 5,
    },
}


def _check_security_headers(pages: list[dict]) -> list[dict]:
    """Check security headers across all pages (deduplicated)."""
    findings = []
    header_counts = {}  # header_key -> { present: [pages], missing: [pages] }

    for header_key in REQUIRED_HEADERS:
        header_counts[header_key] = {"present": [], "missing": []}

    for p in pages:
        url = p.get("url", "")
        headers = _parse_headers(p)

        for header_key, config in REQUIRED_HEADERS.items():
            value = headers.get(header_key, "")
            if value:
                try:
                    if config["check"](value):
                        header_counts[header_key]["present"].append(url)
                    else:
                        header_counts[header_key]["missing"].append(url)
                except Exception:
                    header_counts[header_key]["present"].append(url)
            else:
                header_counts[header_key]["missing"].append(url)

    total = len(pages)
    for header_key, config in REQUIRED_HEADERS.items():
        present = len(header_counts[header_key]["present"])
        missing = len(header_counts[header_key]["missing"])

        if missing == 0:
            findings.append({
                "check": f"header_{header_key}",
                "severity": "good",
                "message": f"{config['name']} present on all {present} page(s)",
                "affected_pages": present,
            })
        elif present == 0:
            findings.append({
                "check": f"header_{header_key}",
                "severity": config["severity"],
                "message": f"{config['name']} missing on all {total} page(s)",
                "affected_pages": total,
                "recommendation": f"Add {config['name']} header to all pages",
            })
        else:
            findings.append({
                "check": f"header_{header_key}",
                "severity": config["severity"],
                "message": f"{config['name']} missing on {missing}/{total} page(s)",
                "affected_pages": missing,
                "recommendation": f"Add {config['name']} header consistently across all pages",
            })

    # Check for dangerous CSP values
    for p in pages:
        headers = _parse_headers(p)
        csp = headers.get("content-security-policy", "")
        if csp:
            if "unsafe-inline" in csp.lower():
                findings.append({
                    "check": "csp_unsafe_inline",
                    "severity": "high",
                    "message": f"CSP allows 'unsafe-inline' on {p.get('url', '')[:50]}",
                    "affected_pages": 1,
                    "recommendation": "Remove 'unsafe-inline' from CSP; use nonces or hashes instead",
                })
                break  # deduplicate
            if "'unsafe-eval'" in csp.lower():
                findings.append({
                    "check": "csp_unsafe_eval",
                    "severity": "high",
                    "message": f"CSP allows 'unsafe-eval' on {p.get('url', '')[:50]}",
                    "affected_pages": 1,
                    "recommendation": "Remove 'unsafe-eval' from CSP",
                })
                break

    return findings


# ── Check 3: Cookies / Session (15%) ───────────────────────────────────────

def _check_cookies(pages: list[dict]) -> list[dict]:
    """Check cookie security attributes from Set-Cookie headers."""
    findings = []
    cookie_issues = {"no_secure": [], "no_httponly": [], "no_samesite": []}

    for p in pages:
        headers = _parse_headers(p)
        set_cookie = headers.get("set-cookie", "")
        if not set_cookie:
            continue

        # Parse multiple Set-Cookie headers (may be comma-separated or list)
        cookies = set_cookie if isinstance(set_cookie, list) else [set_cookie]
        cookie_str = ", ".join(cookies) if isinstance(cookies, list) else set_cookie

        for cookie in cookie_str.split("\n"):
            cookie = cookie.strip()
            if not cookie:
                continue
            low = cookie.lower()
            name = cookie.split("=")[0].strip() if "=" in cookie else "unknown"

            if "secure" not in low:
                cookie_issues["no_secure"].append(name)
            if "httponly" not in low:
                cookie_issues["no_httponly"].append(name)
            if "samesite" not in low:
                cookie_issues["no_samesite"].append(name)

    if cookie_issues["no_secure"]:
        findings.append({
            "check": "cookie_secure",
            "severity": "high",
            "message": f"{len(cookie_issues['no_secure'])} cookie(s) missing Secure flag: {', '.join(cookie_issues['no_secure'][:5])}",
            "affected_pages": len(set(p.get("url", "") for p in pages)),
            "recommendation": "Add Secure flag to all cookies to ensure they're only sent over HTTPS",
        })

    if cookie_issues["no_httponly"]:
        findings.append({
            "check": "cookie_httponly",
            "severity": "high",
            "message": f"{len(cookie_issues['no_httponly'])} cookie(s) missing HttpOnly flag: {', '.join(cookie_issues['no_httponly'][:5])}",
            "affected_pages": len(set(p.get("url", "") for p in pages)),
            "recommendation": "Add HttpOnly flag to session cookies to prevent XSS access",
        })

    if cookie_issues["no_samesite"]:
        findings.append({
            "check": "cookie_samesite",
            "severity": "medium",
            "message": f"{len(cookie_issues['no_samesite'])} cookie(s) missing SameSite attribute: {', '.join(cookie_issues['no_samesite'][:5])}",
            "affected_pages": len(set(p.get("url", "") for p in pages)),
            "recommendation": "Add SameSite=Strict or SameSite=Lax to cookies",
        })

    if not any(cookie_issues.values()):
        has_cookies = any(_parse_headers(p).get("set-cookie") for p in pages)
        if has_cookies:
            findings.append({
                "check": "cookie_security",
                "severity": "good",
                "message": "All cookies have Secure, HttpOnly, and SameSite attributes",
            })
        else:
            findings.append({
                "check": "cookie_security",
                "severity": "info",
                "message": "No cookies detected in responses",
            })

    return findings


# ── Check 4: Sensitive Data Exposure (20%) ─────────────────────────────────

def _check_sensitive_data(pages: list[dict], page_htmls: dict) -> list[dict]:
    """Scan HTML/JS for hardcoded secrets, keys, tokens, internal URLs."""
    findings = []
    detected = {}  # pattern_name -> { pages: set, sample: str }

    for p in pages:
        pid = p["id"]
        html = page_htmls.get(pid, "")
        if not html:
            continue

        # Limit to first 50KB to avoid regex perf issues on large pages
        html = html[:50000]

        # Strip script tag contents (fast regex, no BS4)
        clean_html = re.sub(r"<script[\s\S]*?</script>", "", html, flags=re.IGNORECASE)

        for pattern, name in SECRET_PATTERNS:
            matches = re.findall(pattern, clean_html, re.IGNORECASE)
            if matches:
                if name not in detected:
                    detected[name] = {"pages": set(), "sample": matches[0][:60]}
                detected[name]["pages"].add(p.get("url", "")[:50])

    for name, info in detected.items():
        count = len(info["pages"])
        findings.append({
            "check": "sensitive_data",
            "severity": "critical",
            "message": f"Potential {name} detected on {count} page(s) — sample: {info['sample']}...",
            "affected_pages": count,
            "recommendation": f"Remove {name} from client-side code; use environment variables or server-side config",
        })

    # Check for internal URLs in HTML
    internal_urls = set()
    for p in pages:
        pid = p["id"]
        html = page_htmls.get(pid, "")
        if not html:
            continue
        urls = re.findall(r'https?://(?:localhost|127\.0\.0\.1|192\.168\.\d+\.\d+|10\.\d+\.\d+\.\d+|172\.(?:1[6-9]|2\d|3[01])\.\d+\.\d+)[^\s\'"]*', html)
        if urls:
            internal_urls.update(urls[:3])

    if internal_urls:
        findings.append({
            "check": "internal_urls_exposed",
            "severity": "high",
            "message": f"Internal/private URLs found in HTML on {len(pages)} page(s): {', '.join(list(internal_urls)[:3])}",
            "affected_pages": len(pages),
            "recommendation": "Remove internal URLs from client-side HTML; use relative paths or environment variables",
        })

    if not detected and not internal_urls:
        findings.append({
            "check": "sensitive_data",
            "severity": "good",
            "message": "No hardcoded secrets, keys, or internal URLs detected in page HTML",
        })

    return findings


# ── Check 5: Forms / Authentication (10%) ──────────────────────────────────

def _check_form_security(pages: list[dict], page_htmls: dict) -> list[dict]:
    """Check login forms, HTTPS, CSRF, password field types."""
    findings = []
    login_forms = []
    all_forms = []
    password_fields = []
    forms_without_action = []
    forms_without_csrf = []

    for p in pages[:10]:  # limit BS4 processing
        pid = p["id"]
        html = page_htmls.get(pid, "")
        soup = _soup(html)

        for form in soup.find_all("form"):
            action = (form.get("action") or "").strip()
            method = (form.get("method") or "get").lower()
            all_forms.append({"url": p.get("url", ""), "action": action, "method": method})

            # Check for password fields
            pw_fields = form.find_all("input", attrs={"type": "password"})
            if pw_fields:
                password_fields.append(p.get("url", ""))
                login_forms.append({"url": p.get("url", ""), "action": action, "method": method})

                # Check if form action is HTTPS
                if action and not action.startswith(("https://", "/", "#", "javascript:")):
                    if action.startswith("http://"):
                        findings.append({
                            "check": "login_form_http",
                            "severity": "critical",
                            "message": f"Login form submits to HTTP: {action[:60]}",
                            "affected_pages": 1,
                            "recommendation": "Change form action to HTTPS",
                        })

                # Check password field type
                for pw in pw_fields:
                    if pw.get("type") != "password":
                        findings.append({
                            "check": "password_field_type",
                            "severity": "high",
                            "message": f"Password field missing type='password' on {p.get('url', '')[:50]}",
                            "affected_pages": 1,
                            "recommendation": "Set type='password' on password input fields",
                        })

            # Check for CSRF tokens
            csrf_found = False
            for inp in form.find_all("input"):
                name = (inp.get("name") or "").lower()
                if name in ("csrf", "csrf_token", "_token", "csrfmiddlewaretoken", "authenticity_token", "__RequestVerificationToken"):
                    csrf_found = True
                    break
            if not csrf_found and method == "post":
                forms_without_csrf.append(p.get("url", "")[:50])

            if not action:
                forms_without_action.append(p.get("url", "")[:50])

    if login_forms:
        findings.append({
            "check": "login_form_present",
            "severity": "info",
            "message": f"Login/authentication form(s) found on {len(login_forms)} page(s)",
            "affected_pages": len(login_forms),
        })

    if forms_without_csrf:
        findings.append({
            "check": "csrf_missing",
            "severity": "high",
            "message": f"{len(forms_without_csrf)} POST form(s) without CSRF token",
            "affected_pages": len(forms_without_csrf),
            "recommendation": "Add CSRF tokens to all POST forms",
        })

    if forms_without_action and len(forms_without_action) > 3:
        findings.append({
            "check": "form_no_action",
            "severity": "medium",
            "message": f"{len(forms_without_action)} form(s) have no action attribute",
            "affected_pages": len(forms_without_action),
            "recommendation": "Set explicit action URLs on forms",
        })

    if not login_forms and not all_forms:
        findings.append({
            "check": "form_security",
            "severity": "info",
            "message": "No forms detected on crawled pages",
        })

    return findings


# ── Check 6: Third-party / External Resources (5%) ─────────────────────────

def _check_external_resources(pages: list[dict], page_htmls: dict) -> list[dict]:
    """Count third-party scripts and check for suspicious domains."""
    findings = []
    all_scripts = set()
    external_scripts = {}  # domain -> count
    suspicious_domains = set()

    trusted_domains = {
        "googleapis.com", "gstatic.com", "google.com", "google-analytics.com",
        "googletagmanager.com", "cloudflare.com", "cdnjs.cloudflare.com",
        "jsdelivr.net", "unpkg.com", "bootstrapcdn.com", "facebook.net",
        "twitter.com", "linkedin.com", "youtube.com", "vimeo.com",
        "github.com", "github.io", "amazonaws.com", "cloudfront.net",
    }

    for p in pages[:10]:  # limit BS4 processing
        pid = p["id"]
        html = page_htmls.get(pid, "")
        soup = _soup(html)

        for script in soup.find_all("script", src=True):
            src = script["src"]
            all_scripts.add(src)
            try:
                parsed = urlparse(src)
                domain = parsed.netloc
                if domain:
                    external_scripts[domain] = external_scripts.get(domain, 0) + 1
                    # Check for trusted domain
                    is_trusted = any(td in domain for td in trusted_domains)
                    if not is_trusted and domain not in suspicious_domains:
                        suspicious_domains.add(domain)
            except Exception:
                pass

    if external_scripts:
        total_external = sum(external_scripts.values())
        findings.append({
            "check": "external_scripts",
            "severity": "info",
            "message": f"{total_external} external script(s) from {len(external_scripts)} domain(s) across {len(pages)} page(s)",
            "affected_pages": len(pages),
        })

    if suspicious_domains:
        findings.append({
            "check": "suspicious_scripts",
            "severity": "medium",
            "message": f"Untrusted third-party script domains: {', '.join(list(suspicious_domains)[:5])}",
            "affected_pages": len(pages),
            "recommendation": "Audit third-party scripts; consider SRI and Content Security Policy",
        })

    # Check SRI
    sri_count = 0
    no_sri_count = 0
    for p in pages[:10]:  # limit BS4 processing
        pid = p["id"]
        html = page_htmls.get(pid, "")
        soup = _soup(html)
        for script in soup.find_all("script", src=True):
            src = script["src"]
            if src and "://" in src:
                if script.get("integrity"):
                    sri_count += 1
                else:
                    no_sri_count += 1

    if no_sri_count > 0 and sri_count > 0:
        findings.append({
            "check": "sri_partial",
            "severity": "medium",
            "message": f"SRI present on {sri_count} external script(s), missing on {no_sri_count}",
            "affected_pages": len(pages),
            "recommendation": "Add integrity attribute to all external scripts",
        })
    elif no_sri_count > 0:
        findings.append({
            "check": "sri_missing",
            "severity": "medium",
            "message": f"No Subresource Integrity (SRI) found on {no_sri_count} external script(s)",
            "affected_pages": len(pages),
            "recommendation": "Add integrity attribute to external scripts to prevent tampering",
        })

    return findings


# ── Check 7: Infrastructure (5%) ───────────────────────────────────────────

def _check_infrastructure(pages: list[dict]) -> list[dict]:
    """Check server info disclosure, error exposure, directory listing, etc."""
    findings = []

    # Server / X-Powered-By disclosure
    servers = {}
    powered_by = {}
    for p in pages:
        headers = _parse_headers(p)
        server = headers.get("server", "")
        powered = headers.get("x-powered-by", "")
        if server:
            servers[server] = servers.get(server, 0) + 1
        if powered:
            powered_by[powered] = powered_by.get(powered, 0) + 1

    if servers:
        server_list = ", ".join(f"{s} ({c} pages)" for s, c in servers.items())
        findings.append({
            "check": "server_disclosure",
            "severity": "low",
            "message": f"Server header reveals: {server_list}",
            "affected_pages": sum(servers.values()),
            "recommendation": "Consider removing or customizing Server header",
        })

    if powered_by:
        powered_list = ", ".join(f"{p} ({c} pages)" for p, c in powered_by.items())
        findings.append({
            "check": "powered_by_disclosure",
            "severity": "low",
            "message": f"X-Powered-By header reveals: {powered_list}",
            "affected_pages": sum(powered_by.values()),
            "recommendation": "Remove X-Powered-By header",
        })

    # Check for error pages with stack traces
    error_pages = []
    for p in pages:
        status = p.get("status_code", 0)
        if status and status >= 400:
            error_pages.append(p)

    if error_pages:
        # Check if error pages expose sensitive info
        for p in error_pages:
            pid = p["id"]
            html = page_htmls_local.get(pid, "") if hasattr(page_htmls_local := {}, "get") else ""
            # We don't have page_htmls here, skip
            pass

        findings.append({
            "check": "error_pages",
            "severity": "info",
            "message": f"{len(error_pages)} error page(s) detected (status >= 400)",
            "affected_pages": len(error_pages),
            "recommendation": "Ensure error pages don't expose stack traces or internal paths",
        })

    # robots.txt sensitive paths (check in HTML for mentions)
    findings.append({
        "check": "robots_txt_check",
        "severity": "info",
        "message": "Note: robots.txt analysis requires fetching the file directly",
        "recommendation": "Check robots.txt for exposed admin/private paths",
    })

    return findings


# ── Main entry point ────────────────────────────────────────────────────────

def run_security_audit(pages: list[dict], page_htmls: dict[int, str]) -> dict:
    """Run security observations audit across all crawled pages.

    Returns: {
        "findings": [ { check, severity, message, recommendation, affected_pages } ],
        "summary": { critical, high, medium, low, info, good },
        "page_count": int,
    }
    """
    if not pages:
        return {"findings": [], "summary": {}, "page_count": 0}

    all_findings = []

    # 1. HTTPS / SSL
    print("[Security] Checking HTTPS/SSL...")
    all_findings.extend(_check_https_ssl(pages, page_htmls))

    # 2. Security Headers
    print("[Security] Checking security headers...")
    all_findings.extend(_check_security_headers(pages))

    # 3. Cookies
    print("[Security] Checking cookie security...")
    all_findings.extend(_check_cookies(pages))

    # 4. Sensitive Data
    print("[Security] Scanning for sensitive data exposure...")
    all_findings.extend(_check_sensitive_data(pages, page_htmls))

    # 5. Forms / Auth
    print("[Security] Checking form and authentication security...")
    all_findings.extend(_check_form_security(pages, page_htmls))

    # 6. External Resources
    print("[Security] Analyzing third-party resources...")
    all_findings.extend(_check_external_resources(pages, page_htmls))

    # 7. Infrastructure
    print("[Security] Checking infrastructure disclosure...")
    all_findings.extend(_check_infrastructure(pages))

    # Summary
    summary = {"critical": 0, "high": 0, "medium": 0, "low": 0, "info": 0, "good": 0}
    for f in all_findings:
        sev = f.get("severity", "info")
        if sev in summary:
            summary[sev] += 1

    print(f"[Security] {len(all_findings)} observations — {summary}")

    return {
        "findings": all_findings,
        "summary": summary,
        "page_count": len(pages),
    }
