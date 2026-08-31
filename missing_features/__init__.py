"""
Missing Features Audit — detect website type, then check expected functional features.

8 categories:
  1. Navigation & Discovery    — 15%
  2. Conversion / CTA          — 20%
  3. Forms & User Input        — 15%
  4. Search & Filtering        — 10%
  5. Trust & Support           — 10%
  6. User Account Features     — 10%
  7. Error & Feedback States   — 10%
  8. Accessibility/Utility     — 10%

Key principle: Features are only checked when APPLICABLE to the detected website type.
"""

from bs4 import BeautifulSoup
import re


# ── Website Type Detection ──────────────────────────────────────────────

from urllib.parse import urlparse

WEBSITE_TYPES = {
    "ecommerce": {
        "signals": ["buy", "cart", "checkout", "shop", "product", "price", "add to cart",
                     "order", "purchase", "wishlist", "store"],
        "url_patterns": ["/shop", "/product", "/cart", "/checkout", "/store", "/buy"],
        "description": "E-commerce / Online Store",
    },
    "saas": {
        "signals": ["pricing", "features", "demo", "free trial", "sign up", "subscribe",
                     "dashboard", "integrations", "api", "plan"],
        "url_patterns": ["/pricing", "/features", "/demo", "/signup", "/login", "/register"],
        "description": "SaaS / Software Product",
    },
    "blog": {
        "signals": ["blog", "post", "article", "author", "category", "tag", "read more",
                     "published", "comments", "share"],
        "url_patterns": ["/blog", "/post", "/article", "/author", "/category"],
        "description": "Blog / Content Publishing",
    },
    "corporate": {
        "signals": ["about us", "contact", "team", "services", "solutions", "clients",
                     "partner", "career", "investor", "annual report"],
        "url_patterns": ["/about", "/contact", "/services", "/team", "/careers", "/solutions"],
        "description": "Corporate / Business Website",
    },
    "portfolio": {
        "signals": ["portfolio", "projects", "work", "case study", "gallery", "showcase",
                     "hire me", "freelance", "resume", "cv"],
        "url_patterns": ["/portfolio", "/projects", "/work", "/about"],
        "description": "Portfolio / Personal Website",
    },
    "education": {
        "signals": ["course", "student", "enroll", "university", "school", "learn",
                     "curriculum", "faculty", "admission", "exam", "lecture"],
        "url_patterns": ["/course", "/student", "/enroll", "/admission", "/faculty"],
        "description": "Education / Learning Platform",
    },
    "media": {
        "signals": ["news", "video", "podcast", "episode", "watch", "listen",
                     "stream", "live", "media", "press"],
        "url_patterns": ["/news", "/video", "/podcast", "/watch", "/live"],
        "description": "Media / News / Entertainment",
    },
    "nonprofit": {
        "signals": ["donate", "volunteer", "mission", "impact", "community",
                     "foundation", "charity", "cause", "campaign"],
        "url_patterns": ["/donate", "/volunteer", "/mission", "/impact"],
        "description": "Non-profit / NGO",
    },
}


def detect_website_type(pages: list[dict], page_htmls: dict[int, str]) -> dict:
    """Detect website type from crawled pages content, URLs, and structure.

    Returns: {
        "type": str,
        "confidence": float (0-1),
        "description": str,
        "signals_found": [str],
    }
    """
    all_text = ""
    all_urls = ""

    for page in pages:
        url = page.get("url", "").lower()
        all_urls += " " + url
        html = page_htmls.get(page["id"], "")
        soup = BeautifulSoup(html, "html.parser")
        text = soup.get_text(separator=" ", strip=True).lower()
        all_text += " " + text

    scores = {}
    for wtype, config in WEBSITE_TYPES.items():
        score = 0
        signals_found = []
        for signal in config["signals"]:
            if signal in all_text:
                score += 1
                signals_found.append(signal)
        for pattern in config["url_patterns"]:
            if pattern in all_urls:
                score += 2
                signals_found.append(f"url:{pattern}")
        scores[wtype] = {"score": score, "signals": signals_found}

    best_type = max(scores, key=lambda k: scores[k]["score"])
    best_score = scores[best_type]["score"]
    total_possible = len(WEBSITE_TYPES[best_type]["signals"]) + len(WEBSITE_TYPES[best_type]["url_patterns"]) * 2

    confidence = min(1.0, best_score / max(total_possible * 0.3, 1))

    # Fallback to corporate if confidence too low
    if confidence < 0.2:
        best_type = "corporate"
        confidence = 0.3
        signals_found = ["fallback"]

    return {
        "type": best_type,
        "confidence": round(confidence, 2),
        "description": WEBSITE_TYPES[best_type]["description"],
        "signals_found": scores[best_type]["signals"][:10],
    }


# ── Feature Check Helpers ───────────────────────────────────────────────

def _soup(html: str) -> BeautifulSoup:
    return BeautifulSoup(html, "html.parser")


def _find_all(soup, selector):
    return soup.select(selector)


def _has_text(soup, keywords):
    text = soup.get_text(separator=" ", strip=True).lower()
    return any(kw in text for kw in keywords)


def _has_element(soup, selector):
    return len(soup.select(selector)) > 0


def _has_link_with_text(soup, keywords):
    for a in soup.find_all("a", href=True):
        text = (a.get_text(strip=True) or "").lower()
        href = a["href"].lower()
        if any(kw in text or kw in href for kw in keywords):
            return True
    return False


# ── Feature Definitions (with applicability per website type) ────────────
# status: "implemented" | "partial" | "missing" | "not_applicable"
# severity when missing: critical/high/medium/low

FEATURE_CATEGORIES = {
    "navigation_discovery": {
        "weight": 15,
        "features": [
            {"id": "main_nav", "name": "Main Navigation", "severity": "critical",
             "applicable": "all"},
            {"id": "logo_homepage", "name": "Logo → Homepage Link", "severity": "medium",
             "applicable": "all"},
            {"id": "footer_nav", "name": "Footer Navigation", "severity": "medium",
             "applicable": "all"},
            {"id": "search_function", "name": "Search Functionality", "severity": "high",
             "applicable": "ecommerce,education,media,blog,saas"},
            {"id": "breadcrumbs", "name": "Breadcrumbs", "severity": "low",
             "applicable": "ecommerce,education,blog,media"},
            {"id": "mobile_nav", "name": "Mobile Navigation", "severity": "high",
             "applicable": "all"},
        ],
    },
    "conversion_cta": {
        "weight": 20,
        "features": [
            {"id": "primary_cta", "name": "Primary CTA", "severity": "critical",
             "applicable": "ecommerce,saas,corporate,nonprofit,education"},
            {"id": "contact_form", "name": "Contact/Lead Form", "severity": "high",
             "applicable": "corporate,saas,portfolio,nonprofit"},
            {"id": "signup_login", "name": "Signup/Login", "severity": "high",
             "applicable": "ecommerce,saas"},
            {"id": "pricing_page", "name": "Pricing Page", "severity": "high",
             "applicable": "saas"},
            {"id": "purchase_cta", "name": "Purchase/Booking CTA", "severity": "critical",
             "applicable": "ecommerce"},
            {"id": "demo_request", "name": "Request Demo/Enquiry", "severity": "high",
             "applicable": "saas,corporate"},
            {"id": "donate_cta", "name": "Donate CTA", "severity": "critical",
             "applicable": "nonprofit"},
        ],
    },
    "forms_input": {
        "weight": 15,
        "features": [
            {"id": "contact_form_present", "name": "Contact Form Present", "severity": "high",
             "applicable": "corporate,saas,portfolio,nonprofit"},
            {"id": "form_validation", "name": "Form Validation Indicators", "severity": "medium",
             "applicable": "ecommerce,saas,education"},
            {"id": "form_labels", "name": "Form Labels/Placeholders", "severity": "medium",
             "applicable": "all"},
            {"id": "login_form", "name": "Login Form", "severity": "high",
             "applicable": "ecommerce,saas"},
        ],
    },
    "search_filtering": {
        "weight": 10,
        "features": [
            {"id": "search_present", "name": "Search Functionality", "severity": "high",
             "applicable": "ecommerce,education,media,blog"},
            {"id": "filter_options", "name": "Filter Options", "severity": "medium",
             "applicable": "ecommerce,education"},
            {"id": "sort_options", "name": "Sort Options", "severity": "low",
             "applicable": "ecommerce"},
            {"id": "pagination", "name": "Pagination/Infinite Scroll", "severity": "medium",
             "applicable": "ecommerce,blog,media,education"},
        ],
    },
    "trust_support": {
        "weight": 10,
        "features": [
            {"id": "contact_info", "name": "Contact Information", "severity": "high",
             "applicable": "all"},
            {"id": "faq_help", "name": "FAQ / Help Section", "severity": "medium",
             "applicable": "ecommerce,saas,corporate,education"},
            {"id": "privacy_policy", "name": "Privacy Policy", "severity": "high",
             "applicable": "all"},
            {"id": "terms_of_service", "name": "Terms of Service", "severity": "medium",
             "applicable": "ecommerce,saas,corporate,education"},
            {"id": "social_links", "name": "Social Media Links", "severity": "low",
             "applicable": "all"},
            {"id": "testimonials", "name": "Testimonials/Reviews", "severity": "medium",
             "applicable": "corporate,saas,nonprofit,portfolio"},
        ],
    },
    "user_account": {
        "weight": 10,
        "features": [
            {"id": "login_signup", "name": "Login/Signup", "severity": "high",
             "applicable": "ecommerce,saas"},
            {"id": "password_reset", "name": "Password Reset", "severity": "medium",
             "applicable": "ecommerce,saas"},
            {"id": "profile_page", "name": "Profile Management", "severity": "medium",
             "applicable": "ecommerce,saas"},
            {"id": "logout", "name": "Logout Functionality", "severity": "medium",
             "applicable": "ecommerce,saas"},
        ],
    },
    "error_feedback": {
        "weight": 10,
        "features": [
            {"id": "page_404", "name": "Custom 404 Page", "severity": "medium",
             "applicable": "all"},
            {"id": "loading_states", "name": "Loading State Indicators", "severity": "low",
             "applicable": "saas,ecommerce,education"},
            {"id": "empty_states", "name": "Empty State Handling", "severity": "low",
             "applicable": "ecommerce,saas,education"},
        ],
    },
    "accessibility_utility": {
        "weight": 10,
        "features": [
            {"id": "skip_link", "name": "Skip to Content Link", "severity": "low",
             "applicable": "all"},
            {"id": "lang_attribute", "name": "Language Attribute on HTML", "severity": "medium",
             "applicable": "all"},
            {"id": "print_styles", "name": "Print-friendly Styles", "severity": "low",
             "applicable": "corporate,education,portfolio,blog"},
            {"id": "language_selector", "name": "Language Selector", "severity": "low",
             "applicable": "corporate,ecommerce,saas,education"},
        ],
    },
}


# ── Individual Feature Checkers ─────────────────────────────────────────

def _check_feature(feature_id: str, soup: BeautifulSoup, page_url: str,
                   all_soups: list, website_type: str) -> str:
    """Check a single feature. Returns 'implemented', 'partial', or 'missing'."""

    url_lower = page_url.lower()
    try:
        parsed_url = urlparse(page_url)
        root_url = f"{parsed_url.scheme}://{parsed_url.netloc}/"
    except Exception:
        root_url = ""

    if feature_id == "main_nav":
        if _has_element(soup, "nav") or _has_element(soup, '[role="navigation"]'):
            return "implemented"
        if _has_element(soup, ".navbar, .nav, .menu, .header-menu, #menu"):
            return "implemented"
        return "missing"

    if feature_id == "logo_homepage":
        for a in soup.find_all("a", href=True):
            img = a.find("img")
            if img:
                alt = (img.get("alt") or "").lower()
                if "logo" in alt or a["href"] in ["/", root_url]:
                    return "implemented"
        for a in soup.find_all("a", href=True):
            img = a.find("img")
            if img and a["href"].rstrip("/") in ["", "/"]:
                return "implemented"
        return "missing"

    if feature_id == "footer_nav":
        footer = soup.find("footer") or soup.select_one(".footer, #footer, [role='contentinfo']")
        if footer:
            links = footer.find_all("a")
            if len(links) >= 3:
                return "implemented"
            if len(links) >= 1:
                return "partial"
        return "missing"

    if feature_id == "search_function":
        if _has_element(soup, 'input[type="search"]'):
            return "implemented"
        if _has_element(soup, ".search, #search, [role='search']"):
            return "implemented"
        for inp in soup.find_all("input", {"type": "text"}):
            placeholder = (inp.get("placeholder") or "").lower()
            if "search" in placeholder:
                return "implemented"
        return "missing"

    if feature_id == "breadcrumbs":
        if _has_element(soup, '[aria-label="breadcrumb"], .breadcrumb, nav.breadcrumb'):
            return "implemented"
        if _has_element(soup, ".breadcrumbs, .breadcrumb-nav"):
            return "implemented"
        return "missing"

    if feature_id == "mobile_nav":
        hamburger = soup.select_one('.hamburger, .menu-toggle, .navbar-toggler, .burger, [aria-label*="menu" i], [aria-label*="Menu" i], .mobile-nav-toggle')
        if hamburger:
            return "implemented"
        nav = soup.find("nav") or soup.select_one('[role="navigation"]')
        if nav:
            return "partial"
        return "missing"

    if feature_id == "primary_cta":
        cta_keywords = ["sign up", "get started", "try free", "buy now", "shop now",
                        "contact us", "request demo", "learn more", "join", "subscribe",
                        "donate", "book now", "enroll", "apply"]
        for btn in soup.find_all(["a", "button"]):
            text = (btn.get_text(strip=True) or "").lower()
            if any(kw in text for kw in cta_keywords):
                return "implemented"
        if _has_element(soup, ".cta, .btn-primary, .button-primary, [class*='cta']"):
            return "implemented"
        return "missing"

    if feature_id == "contact_form":
        if _has_element(soup, 'form[action*="contact"], form[action*="submit"]'):
            return "implemented"
        if _has_element(soup, 'form'):
            inputs = _find_all(soup, 'form input[type="email"], form input[type="tel"], form textarea')
            if inputs:
                return "implemented"
        return "missing"

    if feature_id == "signup_login":
        if _has_link_with_text(soup, ["sign up", "signup", "register", "create account"]):
            return "implemented"
        if _has_element(soup, 'form[action*="login"], form[action*="signup"], form[action*="register"]'):
            return "implemented"
        if _has_link_with_text(soup, ["login", "log in", "sign in"]):
            return "implemented"
        return "missing"

    if feature_id == "pricing_page":
        if _has_text(soup, ["pricing", "plans", "per month", "per year", "/mo", "/yr"]):
            return "implemented"
        if _has_link_with_text(soup, ["pricing", "plans"]):
            return "implemented"
        return "missing"

    if feature_id == "purchase_cta":
        if _has_element(soup, '[class*="add-to-cart"], [class*="buy-now"], [data-action*="cart"]'):
            return "implemented"
        if _has_text(soup, ["add to cart", "buy now", "purchase", "order now"]):
            return "implemented"
        return "missing"

    if feature_id == "demo_request":
        if _has_link_with_text(soup, ["request demo", "book demo", "schedule demo", "free demo"]):
            return "implemented"
        if _has_link_with_text(soup, ["enquiry", "inquiry", "contact sales"]):
            return "implemented"
        return "missing"

    if feature_id == "donate_cta":
        if _has_link_with_text(soup, ["donate", "donation", "give now", "support us"]):
            return "implemented"
        return "missing"

    if feature_id == "contact_form_present":
        forms = _find_all(soup, "form")
        for form in forms:
            inputs = form.find_all(["input", "textarea"])
            types = [i.get("type", "text") for i in inputs]
            if "email" in types or "tel" in types or any(i.name == "textarea" for i in inputs):
                return "implemented"
        return "missing"

    if feature_id == "form_validation":
        forms = _find_all(soup, "form")
        for form in forms:
            inputs = form.find_all("input", required=True)
            if inputs:
                return "implemented"
            if form.get("novalidate") is None:
                has_validation = form.find(attrs={"pattern": True}) or form.find(attrs={"minlength": True})
                if has_validation:
                    return "implemented"
        return "missing"

    if feature_id == "form_labels":
        forms = _find_all(soup, "form")
        for form in forms:
            inputs = form.find_all(["input", "textarea", "select"])
            labeled = sum(1 for i in inputs if i.get("aria-label") or i.get("placeholder") or
                          (i.get("id") and soup.find("label", attrs={"for": i["id"]})))
            if len(inputs) > 0 and labeled / len(inputs) > 0.5:
                return "implemented"
        return "missing"

    if feature_id == "login_form":
        if _has_element(soup, 'form[action*="login"], form[action*="signin"]'):
            return "implemented"
        if _has_element(soup, 'input[type="password"]'):
            return "implemented"
        return "missing"

    if feature_id == "search_present":
        if _has_element(soup, 'input[type="search"]'):
            return "implemented"
        if _has_element(soup, '[role="search"], .search-form, #search-form, .search-bar'):
            return "implemented"
        for inp in soup.find_all("input", {"type": "text"}):
            ph = (inp.get("placeholder") or "").lower()
            if "search" in ph:
                return "implemented"
        return "missing"

    if feature_id == "filter_options":
        if _has_element(soup, '.filter, .filters, [class*="filter"], .facet, .refine'):
            return "implemented"
        if _has_text(soup, ["filter by", "refine", "narrow by"]):
            return "implemented"
        return "missing"

    if feature_id == "sort_options":
        if _has_element(soup, 'select[name*="sort"], [class*="sort"], .sort-by'):
            return "implemented"
        if _has_text(soup, ["sort by", "sort:"]):
            return "implemented"
        return "missing"

    if feature_id == "pagination":
        if _has_element(soup, '.pagination, .pager, nav[aria-label*="pagination"], [class*="pagination"]'):
            return "implemented"
        if _has_link_with_text(soup, ["next page", "previous page", "load more"]):
            return "implemented"
        return "missing"

    if feature_id == "contact_info":
        if _has_text(soup, ["@gmail.com", "@yahoo.com", "@hotmail.com", "@outlook.com"]):
            return "implemented"
        for a in soup.find_all("a", href=True):
            if a["href"].startswith("mailto:"):
                return "implemented"
        if _has_text(soup, ["phone:", "tel:", "call us", "contact us at"]):
            return "implemented"
        if _has_element(soup, 'a[href^="tel:"]'):
            return "implemented"
        return "missing"

    if feature_id == "faq_help":
        if _has_text(soup, ["frequently asked", "faq", "help center", "help centre", "support center"]):
            return "implemented"
        if _has_link_with_text(soup, ["faq", "help", "support", "knowledge base"]):
            return "implemented"
        if _has_element(soup, '.faq, #faq, .accordion, details, [class*="faq"]'):
            return "implemented"
        return "missing"

    if feature_id == "privacy_policy":
        if _has_link_with_text(soup, ["privacy policy", "privacy", "data protection"]):
            return "implemented"
        return "missing"

    if feature_id == "terms_of_service":
        if _has_link_with_text(soup, ["terms of service", "terms and conditions", "terms of use", "t&c"]):
            return "implemented"
        return "missing"

    if feature_id == "social_links":
        social_platforms = ["facebook", "twitter", "instagram", "linkedin", "youtube",
                           "github", "tiktok", "pinterest"]
        for a in soup.find_all("a", href=True):
            href = a["href"].lower()
            if any(p in href for p in social_platforms):
                return "implemented"
        return "missing"

    if feature_id == "testimonials":
        if _has_text(soup, ["testimonial", "review", "what our clients say", "what people say"]):
            return "implemented"
        if _has_element(soup, '.testimonial, .review, .testimonial-slider, [class*="testimonial"], [class*="review"]'):
            return "implemented"
        return "missing"

    if feature_id == "login_signup":
        if _has_link_with_text(soup, ["login", "log in", "sign in", "signup", "sign up", "register"]):
            return "implemented"
        if _has_element(soup, 'input[type="password"]'):
            return "implemented"
        return "missing"

    if feature_id == "password_reset":
        if _has_link_with_text(soup, ["forgot password", "reset password", "forgot your password"]):
            return "implemented"
        return "missing"

    if feature_id == "profile_page":
        if _has_link_with_text(soup, ["my account", "profile", "dashboard", "my profile"]):
            return "implemented"
        return "missing"

    if feature_id == "logout":
        if _has_link_with_text(soup, ["logout", "log out", "sign out"]):
            return "implemented"
        return "missing"

    if feature_id == "page_404":
        return "not_applicable"  # Can only check by visiting a bad URL

    if feature_id == "loading_states":
        if _has_element(soup, '.spinner, .loader, [class*="loading"], [class*="spinner"], [class*="skeleton"]'):
            return "implemented"
        return "missing"

    if feature_id == "empty_states":
        return "not_applicable"  # Can only check via interaction

    if feature_id == "skip_link":
        if _has_element(soup, 'a[href="#main"], a[href="#content"], .skip-link, .skip-to-content, [class*="skip"]'):
            return "implemented"
        return "missing"

    if feature_id == "lang_attribute":
        html_tag = soup.find("html")
        if html_tag and html_tag.get("lang"):
            return "implemented"
        return "missing"

    if feature_id == "print_styles":
        if _has_element(soup, 'link[media="print"], style[media="print"]'):
            return "implemented"
        if _has_text(soup, ["@media print"]):
            return "implemented"
        return "missing"

    if feature_id == "language_selector":
        if _has_element(soup, '[class*="lang"], [class*="locale"], [class*="language"], select[name*="lang"]'):
            return "implemented"
        if _has_link_with_text(soup, ["english", "hindi", "español", "french", "deutsch"]):
            return "partial"
        return "missing"

    return "not_applicable"


# ── Main Check Function ─────────────────────────────────────────────────

def run_missing_features_checks(pages: list[dict], page_htmls: dict[int, str]) -> dict:
    """Run missing features audit across all crawled pages.

    Returns: {
        "website_type": { type, confidence, description, signals_found },
        "findings": [ { feature_id, feature_name, category, status, severity, message, applicable } ],
        "category_results": { cat_id: { features: [...] } },
    }
    """
    if not pages:
        return {
            "website_type": {"type": "corporate", "confidence": 0, "description": "Unknown", "signals_found": []},
            "findings": [],
            "category_results": {},
        }

    # Detect website type
    site_type = detect_website_type(pages, page_htmls)
    print(f"[Features] Website type: {site_type['description']} (confidence: {site_type['confidence']})")

    # Check homepage (primary) + a few other pages
    homepage_html = None
    for p in pages:
        if p.get("depth", 0) == 0:
            homepage_html = page_htmls.get(p["id"], "")
            break
    if homepage_html is None and pages:
        homepage_html = page_htmls.get(pages[0]["id"], "")

    homepage_soup = _soup(homepage_html) if homepage_html else _soup("")
    all_soups = [_soup(page_htmls.get(p["id"], "")) for p in pages[:10]]

    findings = []
    category_results = {}

    for cat_id, cat_config in FEATURE_CATEGORIES.items():
        cat_weight = cat_config["weight"]
        cat_features = []

        for feature in cat_config["features"]:
            fid = feature["id"]
            applicable_types = [t.strip() for t in feature["applicable"].split(",")]
            is_applicable = site_type["type"] in applicable_types or "all" in applicable_types

            if not is_applicable:
                cat_features.append({
                    "id": fid,
                    "name": feature["name"],
                    "status": "not_applicable",
                    "severity": feature["severity"],
                    "message": f"{feature['name']} — Not applicable for {site_type['description']}",
                })
                continue

            # Check on homepage primarily
            status = _check_feature(fid, homepage_soup, pages[0]["url"] if pages else "", all_soups, site_type["type"])

            # If missing on homepage, also check other pages
            if status == "missing":
                for i, soup in enumerate(all_soups[1:], 1):
                    other_status = _check_feature(fid, soup, pages[i]["url"] if i < len(pages) else "", all_soups, site_type["type"])
                    if other_status == "implemented":
                        status = "partial"
                        break

            # Count pages where feature is present
            pages_with = 0
            pages_checked = len(all_soups)
            for soup in all_soups:
                s = _check_feature(fid, soup, "", all_soups, site_type["type"])
                if s == "implemented":
                    pages_with += 1

            if status == "missing":
                sev = feature["severity"]
                msg = f"{feature['name']} missing"
                if pages_checked > 1:
                    msg += f" — present on {pages_with}/{pages_checked} pages"

                findings.append({
                    "feature_id": fid,
                    "feature_name": feature["name"],
                    "category": cat_id,
                    "status": "missing",
                    "severity": sev,
                    "message": msg,
                    "applicable": True,
                })
            elif status == "partial":
                findings.append({
                    "feature_id": fid,
                    "feature_name": feature["name"],
                    "category": cat_id,
                    "status": "partial",
                    "severity": feature["severity"],
                    "message": f"{feature['name']} partially present — found on {pages_with}/{pages_checked} pages",
                    "applicable": True,
                })

            cat_features.append({
                "id": fid,
                "name": feature["name"],
                "status": status,
                "severity": feature["severity"],
                "message": f"{feature['name']}: {status}",
                "pages_with": pages_with,
                "pages_checked": pages_checked,
            })

        category_results[cat_id] = {
            "weight": cat_weight,
            "features": cat_features,
        }

    print(f"[Features] {len(findings)} findings across {len(FEATURE_CATEGORIES)} categories")

    return {
        "website_type": site_type,
        "findings": findings,
        "category_results": category_results,
    }
