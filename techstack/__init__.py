"""Technology Stack Detection — identifies frontend frameworks, CMS, analytics, CDN from HTML/headers/scripts."""
import re
import json
import os
from urllib.parse import urlparse
from app import db


# ─── Detection Rules ────────────────────────────────────────
# Each rule: (category, name, patterns_to_match, location)
# location: "html" = in HTML source, "headers" = in response headers, "scripts" = in script URLs

TECH_RULES = {
    # ── Frontend Frameworks ──────────────────────────────────
    "frontend": [
        ("React", [
            r"react[.\-/]", r"__NEXT_DATA__", r"_next/static",
            r"data-reactroot", r"data-reactid",
            r"react\.production\.min\.js", r"react-dom",
        ], "html"),
        ("Next.js", [
            r"__NEXT_DATA__", r"_next/static", r"_next/image",
            r"next/head", r"next/script",
        ], "html"),
        ("Vue.js", [
            r"vue[.\-/]", r"data-v-", r"Vue\.",
            r"vue\.min\.js", r"vue\.runtime",
        ], "html"),
        ("Nuxt.js", [
            r"__NUXT__", r"_nuxt/", r"nuxt\.js",
            r"nuxt\.config", r"window\.__NUXT__",
        ], "html"),
        ("Angular", [
            r"ng-version", r"angular[.\-/]", r"ng-app",
            r"angular\.min\.js", r"@angular",
            r"ng-controller", r"ng-cloak",
        ], "html"),
        ("Svelte", [
            r"svelte[.\-/]", r"svelte-[a-z0-9]+",
            r"__sveltekit",
        ], "html"),
        ("jQuery", [
            r"jquery[.\-/]", r"jquery\.min\.js",
            r"jQuery\.", r"\$\(",  # careful — only match with jquery context
        ], "html"),
        ("Bootstrap", [
            r"bootstrap[.\-/]", r"bootstrap\.min\.(css|js)",
            r"bootstrap.bundle", r"btn-primary",
            r"col-md-", r"col-lg-",
        ], "html"),
        ("Tailwind CSS", [
            r"tailwindcss", r"tailwind[.\-/]",
            r"(?:^|\s)(flex|grid|text-|bg-|p-|m-|w-|h-|rounded|shadow)(?:\s|$)",
        ], "html"),
        ("Alpine.js", [
            r"alpine[.\-/]", r"x-data", r"x-bind", r"x-on",
            r"x-show", r"x-for", r"alpinejs",
        ], "html"),
        ("Ember.js", [
            r"ember[.\-/]", r"Ember\.", r"ember-application",
        ], "html"),
    ],

    # ── CMS ──────────────────────────────────────────────────
    "cms": [
        ("WordPress", [
            r"wp-content", r"wp-includes", r"wordpress",
            r"wp-json", r"/wp-admin", r"wp-embed\.min\.js",
        ], "html"),
        ("Shopify", [
            r"shopify[.\-/]", r"cdn\.shopify\.com",
            r"Shopify\.theme", r"shopify-payment-button",
        ], "html"),
        ("Drupal", [
            r"drupal[.\-/]", r"sites/default/files",
            r"drupal\.js", r"Drupal\.",
        ], "html"),
        ("Joomla", [
            r"joomla[.\-/]", r"/media/jui/",
            r"Joomla!", r"joomla\.js",
        ], "html"),
        ("Webflow", [
            r"webflow[.\-/]", r"webflow\.css",
            r"wf-canvas", r"wf-page",
        ], "html"),
        ("Wix", [
            r"wix[.\-/]", r"wixstatic\.com",
            r"wix\.com", r"WixBlocks",
        ], "html"),
        ("Squarespace", [
            r"squarespace[.\-/]", r"sqsp-[a-z]",
            r"squarespace\.com",
        ], "html"),
        ("Ghost", [
            r"ghost[.\-/]", r"ghost\.min\.js",
            r"ghost-footer", r"content/themes/ghost",
        ], "html"),
        ("HubSpot", [
            r"hubspot[.\-/]", r"hs-scripts",
            r"hs-analytics", r"HubSpot",
        ], "html"),
    ],

    # ── Backend / Server (from headers) ──────────────────────
    "backend": [
        ("PHP", [], "headers", {"X-Powered-By": "PHP"}),
        ("ASP.NET", [], "headers", {"X-Powered-By": "ASP.NET", "X-AspNet-Version": None}),
        ("Laravel", [], "headers", {"Set-Cookie": "laravel_session"}),
        ("Express.js", [], "headers", {"X-Powered-By": "Express"}),
        ("Django", [], "headers", {"X-Frame-Options": "DENY"}),  # weak signal, only if confirmed
        ("Ruby on Rails", [], "headers", {"X-Powered-By": "Phusion Passenger", "X-Request-Id": None}),
    ],

    # ── Analytics / Marketing ────────────────────────────────
    "analytics": [
        ("Google Analytics", [
            r"google-analytics\.com", r"googletagmanager\.com/gtag",
            r"ga\('send'", r"gtag\(",
            r"google-analytics\.com/analytics\.js",
        ], "html"),
        ("Google Tag Manager", [
            r"googletagmanager\.com/gtm\.js", r"GTM-[A-Z0-9]+",
            r"gtm\.js", r"dataLayer",
        ], "html"),
        ("Meta Pixel", [
            r"connect\.facebook\.net", r"fbq\(",
            r"facebook\.com/tr", r"fbevents\.js",
        ], "html"),
        ("Hotjar", [
            r"hotjar\.com", r"hj\(",
            r"hotjar\.js", r"_hjSettings",
        ], "html"),
        ("Microsoft Clarity", [
            r"clarity\.ms", r"clarity\.js",
            r"clarity\.ms/tag/",
        ], "html"),
        ("Mixpanel", [
            r"mixpanel\.com", r"mixpanel\.init",
            r"mixpanel\.track",
        ], "html"),
        ("Segment", [
            r"segment\.com/analytics", r"analytics\.load",
            r"cdn\.segment\.com",
        ], "html"),
        ("Heap Analytics", [
            r"heap-[a-z0-9]+\.js", r"heap\.com",
        ], "html"),
        ("Amplitude", [
            r"amplitude\.com", r"amplitude\.getInstance",
        ], "html"),
        ("FullStory", [
            r"fullstory\.com", r"fs\(",
            r"fullstory\.js",
        ], "html"),
    ],

    # ── CDN / Hosting ────────────────────────────────────────
    "cdn": [
        ("Cloudflare", [
            r"cloudflare\.com", r"cf-ray",
            r"__cfduid", r"cf-browser-verification",
        ], "both"),
        ("Vercel", [
            r"vercel[.\-/]", r"vercel\.app",
            r"_vercel/", r"vc-url",
        ], "both"),
        ("Netlify", [
            r"netlify\.com", r"netlify\.app",
            r"netlify-cdn", r"__netlify",
        ], "both"),
        ("AWS CloudFront", [
            r"cloudfront\.net", r"cloudfront",
            r"x-amz-cf-id",
        ], "both"),
        ("AWS S3", [
            r"s3\.amazonaws\.com", r"amazonaws\.com",
        ], "html"),
        ("Google Cloud", [
            r"googleapis\.com", r"googlecloud",
            r"gstatic\.com",
        ], "html"),
        ("Fastly", [
            r"fastly\.net", r"x-served-by.*fastly",
        ], "both"),
        ("Akamai", [
            r"akamai\.net", r"akamaihd\.net",
            r"akamai-im",
        ], "both"),
    ],

    # ── JavaScript Libraries ─────────────────────────────────
    "libraries": [
        ("Lodash", [r"lodash[.\-/]", r"lodash\.min\.js"], "html"),
        ("Moment.js", [r"moment[.\-/]", r"moment\.min\.js"], "html"),
        ("Day.js", [r"dayjs[.\-/]", r"dayjs\.min\.js"], "html"),
        ("Axios", [r"axios[.\-/]", r"axios\.min\.js"], "html"),
        ("Three.js", [r"three\.js", r"three\.min\.js", r"threejs"], "html"),
        ("D3.js", [r"d3\.js", r"d3\.min\.js", r"d3js"], "html"),
        ("Chart.js", [r"chart\.js", r"Chart\("], "html"),
        ("GSAP", [r"gsap[.\-/]", r"greensock", r"TweenMax"], "html"),
        ("Anime.js", [r"anime\.js", r"anime\.min\.js"], "html"),
        ("Socket.io", [r"socket\.io", r"socketio"], "html"),
        ("Stripe", [r"stripe\.com", r"Stripe\("], "html"),
        ("Recaptcha", [r"recaptcha", r"grecaptcha"], "html"),
    ],
}


def detect_tech(pages: list[dict], edges: list[dict] = None) -> dict:
    """Detect technologies from crawled pages.
    
    Analyzes HTML source and response headers from all crawled pages.
    Returns categorized technology stack.
    """
    result = {
        "frontend": [],
        "cms": [],
        "backend": [],
        "analytics": [],
        "cdn": [],
        "libraries": [],
    }

    # Collect all HTML content and headers
    all_html = ""
    all_headers = {}
    cookies_str = ""

    for p in pages:
        # Read HTML
        html_path = p.get("raw_html_path")
        if html_path and os.path.exists(html_path):
            try:
                with open(html_path, "r", encoding="utf-8", errors="ignore") as f:
                    content = f.read()
                    all_html += content + "\n"
            except Exception:
                pass

        # Read headers
        headers_raw = p.get("response_headers", "{}")
        try:
            headers = json.loads(headers_raw) if isinstance(headers_raw, str) else headers_raw
            for k, v in headers.items():
                all_headers[k.lower()] = v
                if k.lower() == "set-cookie":
                    cookies_str += v + " "
        except Exception:
            pass

    # Run detection
    for category, rules in TECH_RULES.items():
        detected = set()
        for rule in rules:
            tech_name = rule[0]
            patterns = rule[1]
            method = rule[2]
            header_checks = rule[3] if len(rule) > 3 else None

            if tech_name in detected:
                continue

            found = False

            if method in ("html", "both"):
                for pattern in patterns:
                    if re.search(pattern, all_html, re.IGNORECASE):
                        found = True
                        break

            if not found and method in ("headers", "both"):
                for pattern in patterns:
                    if re.search(pattern, json.dumps(all_headers), re.IGNORECASE):
                        found = True
                        break

            # Backend-specific header matching
            if category == "backend" and not found and header_checks:
                for hdr_name, hdr_value in header_checks.items():
                    actual = all_headers.get(hdr_name.lower(), "")
                    if actual:
                        if hdr_value is None or hdr_value.lower() in actual.lower():
                            found = True
                            break

            if found:
                detected.add(tech_name)
                result[category].append(tech_name)

    # Deduplicate and sort
    for cat in result:
        result[cat] = sorted(set(result[cat]))

    return result


def save_tech_to_db(scan_id: int, tech_result: dict) -> None:
    """Save technology stack as JSON in the scans table (uses a custom approach).
    
    Stores in a new tech_stack column or as findings with category='tech_stack'.
    """
    # Store as findings for simplicity — one finding per detected technology
    for category, technologies in tech_result.items():
        if not technologies:
            continue
        tech_list = ", ".join(technologies)
        db.insert_finding(
            scan_id=scan_id,
            page_id=None,
            category="tech_stack",
            check_name=f"detected_{category}",
            severity="info",
            message=f"{category.replace('_', ' ').title()}: {tech_list}",
            recommendation="",
        )

    # Also store as JSON for easy retrieval
    # We'll store in a dedicated scan result
    conn = db.get_conn()
    try:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS tech_stack (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                scan_id INTEGER NOT NULL UNIQUE REFERENCES scans(id),
                data TEXT NOT NULL,
                created_at TEXT NOT NULL
            )
        """)
        conn.execute(
            "INSERT OR REPLACE INTO tech_stack (scan_id, data, created_at) VALUES (?, ?, ?)",
            (scan_id, json.dumps(tech_result), __import__("datetime").datetime.now(__import__("datetime").timezone.utc).isoformat()),
        )
        conn.commit()
    except Exception:
        pass
    finally:
        conn.close()


def get_tech_from_db(scan_id: int) -> dict:
    """Retrieve technology stack from DB."""
    conn = db.get_conn()
    try:
        row = conn.execute("SELECT data FROM tech_stack WHERE scan_id = ?", (scan_id,)).fetchone()
        if row:
            return json.loads(row["data"])
    except Exception:
        pass
    finally:
        conn.close()
    return {}

