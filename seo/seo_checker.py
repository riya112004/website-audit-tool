import os
import re
from urllib.parse import urlparse

import httpx
from bs4 import BeautifulSoup

from app import db
from seo.recommendations import RECOMMENDATIONS

CATEGORY = "seo"


_HTML_CACHE: dict[str, BeautifulSoup] = {}


def _load_html(raw_html_path: str | None) -> BeautifulSoup | None:
    if not raw_html_path or not os.path.exists(raw_html_path):
        return None
    if raw_html_path in _HTML_CACHE:
        return _HTML_CACHE[raw_html_path]
    with open(raw_html_path, "r", encoding="utf-8") as f:
        soup = BeautifulSoup(f.read(), "html.parser")
    _HTML_CACHE[raw_html_path] = soup
    return soup


def clear_html_cache():
    _HTML_CACHE.clear()


def _add(scan_id, check_name, severity, message, page_id=None, recommendation=None):
    rec = recommendation or RECOMMENDATIONS.get(check_name, "")
    db.insert_finding(
        scan_id=scan_id,
        category=CATEGORY,
        check_name=check_name,
        severity=severity,
        message=message,
        page_id=page_id,
        recommendation=rec,
    )


def _is_crawlable(p: dict) -> bool:
    status = p.get("status_code")
    html_path = p.get("raw_html_path")
    if not status or status < 200 or status >= 300:
        return False
    if not html_path or not os.path.exists(html_path):
        return False
    return True


# ─── Severity Levels ──────────────────────────────────────
# error    = must fix, directly hurts SEO
# warning  = should fix, may impact SEO
# info     = recommendation, best practice


# ─── Crawl Access Layer ───────────────────────────────────

def check_crawl_access(scan_id: int, pages: list[dict]):
    for p in pages:
        status = p.get("status_code")
        if not status:
            _add(scan_id, "crawl_failed", "error",
                 f"Crawler could not reach page: {p['url']}",
                 page_id=p["id"])
        elif status == 403:
            _add(scan_id, "crawl_access_blocked", "warning",
                 f"Access blocked (HTTP 403): {p['url']}. SEO checks skipped — verify manually.",
                 page_id=p["id"])
        elif status == 401:
            _add(scan_id, "crawl_access_blocked", "warning",
                 f"Authentication required (HTTP 401): {p['url']}. SEO checks skipped.",
                 page_id=p["id"])
        elif status == 404:
            _add(scan_id, "page_not_found", "error",
                 f"Page does not exist (HTTP 404): {p['url']}",
                 page_id=p["id"])
        elif status >= 500:
            _add(scan_id, "server_error", "error",
                 f"Server error (HTTP {status}): {p['url']}",
                 page_id=p["id"])


# ─── Title Checks ─────────────────────────────────────────

def check_titles(scan_id: int, pages: list[dict]):
    """Check titles: length, keyword relevance, CTR quality signals."""
    seen_titles: dict[str, list[str]] = {}

    # CTR quality signals
    POWER_WORDS = {"best", "top", "free", "guide", "how", "why", "what",
                   "review", "vs", "tips", "ultimate", "complete", "easy",
                   "fast", "proven", "official", "authentic"}
    BRAND_PATTERNS = {"|", "-", "—", "–", "•", "::"}

    for p in pages:
        if not _is_crawlable(p):
            continue
        soup = _load_html(p.get("raw_html_path"))
        if not soup:
            continue

        title_tag = soup.title
        title_text = title_tag.get_text(strip=True) if title_tag else ""

        if not title_text:
            _add(scan_id, "missing_title", "error",
                 f"No <title> tag: {p['url']}",
                 page_id=p["id"])
        else:
            length = len(title_text)
            title_lower = title_text.lower()

            # Length checks
            if length < 20:
                _add(scan_id, "short_title", "warning",
                     f"Title too short ({length} chars): \"{title_text}\" — {p['url']}",
                     page_id=p["id"])
            elif length > 60:
                _add(scan_id, "long_title", "warning",
                     f"Title may truncate in SERPs ({length} chars): \"{title_text[:60]}...\" — {p['url']}",
                     page_id=p["id"])

            # Keyword relevance: title should contain words from page content + URL
            # Extract top content words (from heading/body)
            url_words = [w for w in p["url"].split("/") if w and len(w) > 2]

            # Also get content words from page
            content_words = set()
            if soup:
                # Get words from headings and first few paragraphs
                for h in soup.find_all(["h1", "h2", "h3"]):
                    content_words.update(h.get_text().lower().split())
                body_text = (soup.body or soup).get_text(" ", strip=True)[:2000]
                for w in body_text.lower().split():
                    if len(w) > 3 and w.isalpha() and w not in _STOP_WORDS:
                        content_words.add(w)

            title_words = set(title_lower.split())
            # Check relevance against both URL and content
            url_relevance = sum(1 for w in url_words if w.lower() in title_lower)
            content_relevance = len(title_words & content_words)
            total_relevance = url_relevance + content_relevance

            if length > 20 and total_relevance == 0:
                _add(scan_id, "title_no_keyword_relevance", "warning",
                     f"Title shares no keywords with page content or URL: \"{title_text[:50]}\" — {p['url']}",
                     page_id=p["id"])

            # CTR quality: no power words = boring title
            has_power_word = any(w in title_lower for w in POWER_WORDS)
            has_number = any(c.isdigit() for c in title_text)
            has_brand_separator = any(s in title_text for s in BRAND_PATTERNS)
            ctr_signals = sum([has_power_word, has_number, has_brand_separator])

            if length > 30 and ctr_signals == 0:
                _add(scan_id, "weak_title_ctr", "info",
                     f"Title lacks CTR signals (no power words/numbers/brand): \"{title_text[:50]}\" — {p['url']}",
                     page_id=p["id"])

            # Keyword stuffing: same word repeated 3+ times
            word_freq = {}
            for w in title_lower.split():
                if len(w) > 2:
                    word_freq[w] = word_freq.get(w, 0) + 1
            stuffed = [w for w, c in word_freq.items() if c >= 3]
            if stuffed:
                _add(scan_id, "title_keyword_stuffing", "warning",
                     f"Title keyword stuffing ({', '.join(stuffed)} repeated 3+×): \"{title_text[:50]}\" — {p['url']}",
                     page_id=p["id"])

            if title_text not in seen_titles:
                seen_titles[title_text] = []
            seen_titles[title_text].append(p["url"])

    for title_text, urls in seen_titles.items():
        if len(urls) > 1:
            pages_str = ", ".join(urls[:5])
            _add(scan_id, "duplicate_title", "warning",
                 f"Same title on {len(urls)} pages: \"{title_text}\" — {pages_str}")


# ─── Meta Description Checks ──────────────────────────────

def check_meta_descriptions(scan_id: int, pages: list[dict]):
    """Check meta descriptions: length, keyword relevance, CTR quality."""
    seen: dict[str, list[str]] = {}

    CTA_WORDS = {"buy", "shop", "learn", "discover", "find", "get", "try",
                 "sign up", "register", "contact", "call", "visit", "explore",
                 "compare", "read", "download", "start", "join"}

    for p in pages:
        if not _is_crawlable(p):
            continue
        soup = _load_html(p.get("raw_html_path"))
        if not soup:
            continue

        meta = soup.find("meta", {"name": "description"})
        content = meta.get("content", "").strip() if meta else ""

        if not content:
            _add(scan_id, "missing_meta_description", "warning",
                 f"No meta description: {p['url']}",
                 page_id=p["id"])
        else:
            length = len(content)

            # Length checks
            if length < 70:
                _add(scan_id, "short_meta_description", "warning",
                     f"Meta description too short ({length} chars): {p['url']}",
                     page_id=p["id"])
            elif length > 160:
                _add(scan_id, "long_meta_description", "warning",
                     f"Meta description may truncate ({length} chars): {p['url']}",
                     page_id=p["id"])

            # Keyword relevance: description should relate to page content + URL
            content_lower = content.lower()
            url_words = [w for w in p["url"].split("/") if w and len(w) > 2]
            url_in_desc = sum(1 for w in url_words if w.lower() in content_lower)

            # Also check against page heading content
            heading_words = set()
            if soup:
                for h in soup.find_all(["h1", "h2"]):
                    heading_words.update(h.get_text().lower().split())
            desc_words = set(content_lower.split())
            heading_relevance = len(desc_words & heading_words)

            total_relevance = url_in_desc + heading_relevance
            if total_relevance == 0 and length > 50:
                _add(scan_id, "desc_no_keyword_relevance", "info",
                     f"Meta description shares no keywords with page headings or URL: {p['url']}",
                     page_id=p["id"])

            # CTR quality: should have CTA or engaging language
            has_cta = any(w in content_lower for w in CTA_WORDS)
            has_numbers = any(c.isdigit() for c in content)
            has_period = content.endswith(".")
            ctr_score = sum([has_cta, has_numbers, has_period])

            if length > 80 and ctr_score == 0:
                _add(scan_id, "weak_desc_ctr", "info",
                     f"Meta description lacks CTR signals (no CTA/numbers/punctuation): {p['url']}",
                     page_id=p["id"])

            # Keyword stuffing in description
            words = content_lower.split()
            word_freq = {}
            for w in words:
                if len(w) > 3:
                    word_freq[w] = word_freq.get(w, 0) + 1
            stuffed = [w for w, c in word_freq.items() if c >= 4]
            if stuffed:
                _add(scan_id, "desc_keyword_stuffing", "warning",
                     f"Meta description keyword stuffing ({', '.join(stuffed[:3])} repeated 4+×): {p['url']}",
                     page_id=p["id"])

            if content not in seen:
                seen[content] = []
            seen[content].append(p["url"])

    for desc, urls in seen.items():
        if len(urls) > 1:
            pages_str = ", ".join(urls[:5])
            _add(scan_id, "duplicate_meta_description", "warning",
                 f"Same meta description on {len(urls)} pages — {pages_str}")


# ─── Heading Checks ───────────────────────────────────────

def check_headings(scan_id: int, pages: list[dict]):
    """Check heading hierarchy, repeated headings, and empty headings."""
    for p in pages:
        if not _is_crawlable(p):
            continue
        soup = _load_html(p.get("raw_html_path"))
        if not soup:
            continue

        h1s = soup.find_all("h1")
        if len(h1s) == 0:
            _add(scan_id, "missing_h1", "warning",
                 f"No <h1> tag: {p['url']}",
                 page_id=p["id"])
        elif len(h1s) > 1:
            _add(scan_id, "multiple_h1s", "warning",
                 f"Multiple <h1> tags ({len(h1s)}): {p['url']}",
                 page_id=p["id"])

        headings = soup.find_all(["h1", "h2", "h3", "h4", "h5", "h6"])

        # Hierarchy skip check
        violations = []
        prev_level = 0
        for h in headings:
            level = int(h.name[1])
            if prev_level > 0 and level > prev_level + 1:
                violations.append({"from": prev_level, "to": level})
            prev_level = level

        if violations:
            skip_details = ", ".join("h%d->h%d" % (v["from"], v["to"]) for v in violations)
            _add(scan_id, "heading_order_broken", "warning",
                 f"Heading level skips ({len(violations)}: {skip_details}): {p['url']}",
                 page_id=p["id"])

        # Repeated headings — same text used multiple times
        heading_texts = {}
        for h in headings:
            text = h.get_text(strip=True).lower()
            if text and len(text) > 2:
                heading_texts.setdefault(text, []).append(h.name)

        for text, tags in heading_texts.items():
            if len(tags) >= 3:
                _add(scan_id, "repeated_headings", "warning",
                     f"Heading repeated {len(tags)}× (\"{text[:50]}\"): {p['url']}",
                     page_id=p["id"])
                break  # One finding per page

        # Empty headings
        empty_count = 0
        for h in headings:
            text = h.get_text(strip=True)
            has_img = bool(h.find("img", alt=True))
            has_aria = bool(h.get("aria-label"))
            if not text and not has_img and not has_aria:
                empty_count += 1

        if empty_count > 0:
            _add(scan_id, "empty_headings", "warning",
                 f"Empty headings ({empty_count}): {p['url']}",
                 page_id=p["id"])


# ─── Image Checks ─────────────────────────────────────────

def check_images(scan_id: int, pages: list[dict]):
    """Check images: missing ALT, generic/poor ALT text, decorative ALT issues."""
    GENERIC_ALT = {
        "image", "photo", "picture", "img", "icon", "logo", "banner",
        "graphic", "illustration", "screenshot", "untitled", "dsc_",
        "img_", "photo_", "image_", "pic", "pic_", "dsc", "img001",
        "download", "upload", "tmp", "temp",
    }
    FILENAME_ALT = re.compile(r"^(img|image|photo|pic|dsc|screenshot|banner|icon|logo)[_\-\s]?\d*\.\w+$", re.I)

    for p in pages:
        if not _is_crawlable(p):
            continue
        soup = _load_html(p.get("raw_html_path"))
        if not soup:
            continue

        imgs = soup.find_all("img")
        if not imgs:
            continue

        missing_alt = 0
        generic_alt = 0
        poor_alt_samples = []

        for img in imgs:
            alt = img.get("alt")
            src = (img.get("src") or "").strip()

            # Check if decorative (alt="" is valid for decorative images)
            if alt is not None and alt.strip() == "":
                continue  # Valid decorative image

            if alt is None or not alt.strip():
                missing_alt += 1
                continue

            alt_lower = alt.strip().lower()
            alt_text = alt.strip()

            # Check for generic ALT text
            if alt_lower in GENERIC_ALT:
                generic_alt += 1
                poor_alt_samples.append(f'"{alt_text[:30]}" (generic)')
                continue

            # Check for filename-based ALT (e.g., "IMG_1234.jpg")
            if FILENAME_ALT.match(alt_lower):
                generic_alt += 1
                poor_alt_samples.append(f'"{alt_text[:30]}" (filename)')
                continue

            # Check for very short ALT that's not meaningful
            if len(alt_text) < 3 and alt_text not in {"OK", "NO", "Up", "New", "Hot"}:
                generic_alt += 1
                poor_alt_samples.append(f'"{alt_text}" (too short)')
                continue

            # Check for repetitive ALT (same word repeated)
            words = alt_lower.split()
            if len(words) >= 2 and len(set(words)) == 1:
                generic_alt += 1
                poor_alt_samples.append(f'"{alt_text[:30]}" (repetitive)')
                continue

        if missing_alt > 0:
            _add(scan_id, "images_missing_alt", "warning",
                 f"{missing_alt}/{len(imgs)} images missing alt text: {p['url']}",
                 page_id=p["id"])

        if generic_alt > 0:
            samples = "; ".join(poor_alt_samples[:3])
            _add(scan_id, "generic_alt_text", "warning",
                 f"{generic_alt} images with generic/poor alt text: {samples} -- {p['url']}",
                 page_id=p["id"])


# ─── Canonical Check ──────────────────────────────────────

def check_canonical(scan_id: int, pages: list[dict]):
    """Check canonical tags: present, self-referencing, valid URL, same origin."""
    from urllib.parse import urlparse

    for p in pages:
        if not _is_crawlable(p):
            continue
        soup = _load_html(p.get("raw_html_path"))
        if not soup:
            continue

        canonical = soup.find("link", {"rel": "canonical"})
        page_url = p["url"]
        parsed_page = urlparse(page_url)

        if not canonical or not canonical.get("href"):
            _add(scan_id, "missing_canonical", "info",
                 f"No canonical tag: {page_url}",
                 page_id=p["id"])
            continue

        href = canonical["href"].strip()

        # Empty canonical
        if not href:
            _add(scan_id, "empty_canonical", "warning",
                 f"Empty canonical href: {page_url}",
                 page_id=p["id"])
            continue

        # Relative canonical (should be absolute)
        if href.startswith("/") or (not href.startswith("http") and not href.startswith("//")):
            href = f"{parsed_page.scheme}://{parsed_page.netloc}{href}"

        try:
            parsed_canon = urlparse(href)
        except Exception:
            _add(scan_id, "invalid_canonical", "warning",
                 f"Invalid canonical URL: {href} on {page_url}",
                 page_id=p["id"])
            continue

        # Canonical points to different domain
        if parsed_canon.netloc and parsed_canon.netloc != parsed_page.netloc:
            _add(scan_id, "canonical_wrong_domain", "warning",
                 f"Canonical points to different domain: {href} (page: {page_url})",
                 page_id=p["id"])
            continue

        # Canonical URL doesn't match page URL (non-self-referencing)
        canon_path = parsed_canon.path.rstrip("/") or "/"
        page_path = parsed_page.path.rstrip("/") or "/"
        canon_query = parsed_canon.query
        page_query = parsed_page.query

        is_self_ref = (canon_path == page_path and canon_query == page_query)

        if not is_self_ref:
            _add(scan_id, "canonical_not_self_referencing", "warning",
                 f"Canonical not self-referencing: canonical={href}, page={page_url}",
                 page_id=p["id"])
            continue

        # Canonical points to a redirected/normalized version (check if different after normalization)
        canon_normalized = href.rstrip("/").lower()
        page_normalized = page_url.rstrip("/").lower()
        if canon_normalized != page_normalized:
            _add(scan_id, "canonical_url_mismatch", "info",
                 f"Canonical URL normalized differently: canonical={href}, page={page_url}",
                 page_id=p["id"])


# ─── Structured Data Check ────────────────────────────────

def check_structured_data(scan_id: int, pages: list[dict]):
    """Check structured data: presence, validity, completeness, page-type suitability."""
    import json as _json

    REQUIRED_FIELDS = {
        "Organization": {"name", "url", "logo"},
        "WebSite": {"name", "url"},
        "Product": {"name", "description", "image", "offers"},
        "Article": {"headline", "datePublished", "author"},
        "BlogPosting": {"headline", "datePublished", "author"},
        "JobPosting": {"title", "description", "datePosted", "hiringOrganization"},
        "FAQPage": {"mainEntity"},
        "Event": {"name", "startDate", "location"},
        "Course": {"name", "description", "provider"},
        "LocalBusiness": {"name", "address", "telephone"},
        "BreadcrumbList": {"itemListElement"},
        "ContactPage": {"name"},
    }

    for p in pages:
        if not _is_crawlable(p):
            continue
        soup = _load_html(p.get("raw_html_path"))
        if not soup:
            continue

        ld_json_scripts = soup.find_all("script", {"type": "application/ld+json"})

        if not ld_json_scripts:
            page_type = _detect_page_type(p, soup)
            if page_type:
                schema_types = PAGE_SCHEMA_MAP.get(page_type, [])
                _add(scan_id, "no_structured_data", "info",
                     f"No {', '.join(schema_types)} schema for {page_type} page: {p['url']}",
                     page_id=p["id"])
            continue

        # Parse and validate each schema block
        for script in ld_json_scripts:
            try:
                data = _json.loads(script.string or "{}")
            except (_json.JSONDecodeError, TypeError):
                _add(scan_id, "invalid_schema", "warning",
                     f"Invalid JSON-LD schema (parse error): {p['url']}",
                     page_id=p["id"])
                continue

            # Handle @graph arrays
            items = data if isinstance(data, list) else [data]
            if isinstance(data, dict) and "@graph" in data:
                items = data["@graph"]

            for item in items:
                if not isinstance(item, dict):
                    continue

                schema_type = item.get("@type", "")
                if not schema_type:
                    _add(scan_id, "schema_no_type", "warning",
                         f"Schema missing @type: {p['url']}",
                         page_id=p["id"])
                    continue

                # Check if schema type matches page type
                page_type = _detect_page_type(p, soup)
                if page_type:
                    expected_types = PAGE_SCHEMA_MAP.get(page_type, [])

                    # Organization/Corporation are valid for ANY page type — don't flag
                    GENERAL_TYPES = {"Organization", "Corporation", "WebPage", "Thing", "CollectionPage"}
                    if schema_type in GENERAL_TYPES:
                        pass  # always valid
                    else:
                        type_matches = schema_type in expected_types or any(
                            t in schema_type for t in expected_types
                        )
                        if not type_matches and expected_types:
                            _add(scan_id, "schema_wrong_type", "info",
                                 f"Schema @type={schema_type} not ideal for {page_type} page (expected {', '.join(expected_types)}): {p['url']}",
                                 page_id=p["id"])

                # Check required fields completeness
                required = REQUIRED_FIELDS.get(schema_type, set())
                if required:
                    present = {k for k in required if item.get(k)}
                    missing_fields = required - present
                    if missing_fields:
                        _add(scan_id, "schema_incomplete", "warning",
                             f"Schema {schema_type} missing fields: {', '.join(sorted(missing_fields))}: {p['url']}",
                             page_id=p["id"])

                # Check for empty/null values
                empty_count = sum(1 for k, v in item.items()
                                  if v in (None, "", [], {}) and k not in ("@context", "@type", "@id"))
                if empty_count >= 3:
                    _add(scan_id, "schema_empty_values", "warning",
                         f"Schema {schema_type} has {empty_count} empty fields: {p['url']}",
                         page_id=p["id"])


# ─── Page Type Detection for Schema ───────────────────────

# Maps page type → recommended schema.org types
PAGE_SCHEMA_MAP = {
    "homepage": ["Organization", "WebSite"],
    "about": ["Organization", "AboutPage"],
    "services": ["Service"],
    "careers": ["JobPosting", "Organization"],
    "products": ["Product", "ItemList"],
    "blog": ["Article", "BlogPosting"],
    "research": ["ScholarlyArticle", "Article"],
    "education": ["Course", "EducationalOrganization"],
    "faq": ["FAQPage"],
    "contact": ["ContactPage"],
    "events": ["Event"],
    "courses": ["Course"],
    "local_business": ["LocalBusiness"],
}

# URL/title patterns → page type
_PAGE_TYPE_PATTERNS = {
    "homepage": {
        "url_paths": {""},
        "title_keywords": set(),
    },
    "about": {
        "url_keywords": {"about", "our-story", "team", "leadership", "company", "who-we-are", "whoweare", "mission", "vision", "values"},
        "title_keywords": {"about us", "our story", "our team", "company", "who we are", "mission", "vision", "leadership"},
    },
    "services": {
        "url_keywords": {"services", "solutions", "products", "features", "offerings", "what-we-do"},
        "title_keywords": {"services", "solutions", "products", "features", "offerings", "what we do"},
    },
    "careers": {
        "url_keywords": {"careers", "jobs", "hiring", "recruitment", "join-us", "work-with-us", "openings"},
        "title_keywords": {"careers", "jobs", "hiring", "recruitment", "join us", "work with us", "openings", "vacancies"},
    },
    "products": {
        "url_keywords": {"shop", "store", "product", "buy", "pricing", "plans", "catalog"},
        "title_keywords": {"shop", "store", "product", "buy", "pricing", "plans", "catalog"},
    },
    "blog": {
        "url_keywords": {"blog", "articles", "news", "posts", "journal", "insights", "resources"},
        "title_keywords": {"blog", "article", "news", "post", "journal", "insights"},
    },
    "faq": {
        "url_keywords": {"faq", "faqs", "frequently-asked", "help-center", "help-center"},
        "title_keywords": {"faq", "frequently asked", "help center", "common questions"},
    },
    "contact": {
        "url_keywords": {"contact", "enquiry", "inquiry", "reach-us", "get-in-touch"},
        "title_keywords": {"contact us", "get in touch", "reach us", "enquiry"},
    },
    "events": {
        "url_keywords": {"events", "event", "conference", "webinar", "workshop", "seminar"},
        "title_keywords": {"events", "conference", "webinar", "workshop", "seminar"},
    },
    "courses": {
        "url_keywords": {"courses", "course", "programs", "program", "degrees", "certifications", "academics"},
        "title_keywords": {"courses", "programs", "degrees", "certifications", "academics", "curriculum"},
    },
    "research": {
        "url_keywords": {"research", "papers", "publications", "journal", "study", "studies", "findings", "analysis"},
        "title_keywords": {"research", "paper", "publication", "journal", "study", "findings", "analysis", "academic"},
    },
    "education": {
        "url_keywords": {"education", "school", "college", "department", "faculty", "centre", "center", "institute", "academy"},
        "title_keywords": {"education", "school", "college", "department", "faculty", "centre", "center", "institute", "academy"},
    },
    "local_business": {
        "url_keywords": {"locations", "branches", "offices", "find-us", "stores"},
        "title_keywords": {"locations", "branches", "offices", "find us", "store locator"},
    },
}

# Pages where schema is NOT relevant
_SCHEMA_NOT_RELEVANT = {
    "privacy", "policy", "terms", "conditions", "legal", "disclaimer",
    "sitemap", "cookie", "consent", "gdpr", "refund", "cancellation",
    "login", "signin", "signup", "register", "forgot-password", "reset-password",
    "404", "error", "not-found",
}


def _detect_page_type(page: dict, soup) -> str | None:
    """Detect page type from URL, title, and content. Returns page type or None if schema not relevant."""
    url = page.get("url", "").lower()
    title = page.get("title", "").lower()

    from urllib.parse import urlparse
    parsed = urlparse(url)
    path = parsed.path.strip("/")

    # Check if page is in "not relevant" category
    for pattern in _SCHEMA_NOT_RELEVANT:
        if pattern in path or pattern in title:
            return None

    # Homepage check
    if path in ("", "index.html", "index.php"):
        return "homepage"

    # Match against patterns
    for page_type, patterns in _PAGE_TYPE_PATTERNS.items():
        url_keywords = patterns.get("url_keywords", set())
        title_keywords = patterns.get("title_keywords", set())

        # URL keyword match
        for kw in url_keywords:
            if kw in path:
                return page_type

        # Title keyword match
        for kw in title_keywords:
            if kw in title:
                return page_type

    # Content-based detection as fallback
    if soup:
        text = soup.get_text()[:2000].lower()

        # Check for job posting content indicators
        if any(w in text for w in ("job title", "job description", "apply for this position", "employment type", "salary range")):
            return "careers"

        # Check for product content indicators
        if any(w in text for w in ("add to cart", "buy now", "price", "in stock", "out of stock", "add to bag")):
            return "products"

        # Check for FAQ content indicators
        faq_count = text.count("?")
        if faq_count >= 5 and any(w in text for w in ("frequently asked", "common questions")):
            return "faq"

    return None  # Generic page — schema not specifically needed


# ─── Viewport Check ───────────────────────────────────────

def check_viewport(scan_id: int, pages: list[dict]):
    for p in pages:
        if not _is_crawlable(p):
            continue
        soup = _load_html(p.get("raw_html_path"))
        if not soup:
            continue

        viewport = soup.find("meta", {"name": "viewport"})
        if not viewport:
            _add(scan_id, "missing_viewport", "warning",
                 f"No viewport meta tag: {p['url']}",
                 page_id=p["id"])


# ─── Link Text Check ──────────────────────────────────────

def check_link_text(scan_id: int, pages: list[dict]):
    vague = {"click here", "read more", "here", "learn more", "link"}
    for p in pages:
        if not _is_crawlable(p):
            continue
        soup = _load_html(p.get("raw_html_path"))
        if not soup:
            continue

        vague_links = []
        for a in soup.find_all("a"):
            text = a.get_text(strip=True).lower()
            if text in vague:
                vague_links.append(a.get_text(strip=True))

        if vague_links:
            _add(scan_id, "non_descriptive_link_text", "info",
                 f"Non-descriptive link text ({len(vague_links)} links): {p['url']}",
                 page_id=p["id"])


# ─── HTTPS Check ──────────────────────────────────────────

def check_https(scan_id: int, pages: list[dict]):
    for p in pages:
        if not p["url"].startswith("https://"):
            _add(scan_id, "missing_ssl", "warning",
                 f"Not HTTPS: {p['url']}",
                 page_id=p["id"])


# ─── Broken Links ─────────────────────────────────────────

def check_broken_links(scan_id: int, pages: list[dict]):
    for p in pages:
        status = p.get("status_code")
        if not status:
            continue
        if status == 404:
            _add(scan_id, "broken_link", "error",
                 f"Broken link (404): {p['url']}",
                 page_id=p["id"])
        elif status >= 500:
            _add(scan_id, "broken_link", "error",
                 f"Server error ({status}): {p['url']}",
                 page_id=p["id"])


# ─── Robots & Sitemap ─────────────────────────────────────

def check_robots_and_sitemap(scan_id: int, origin: str):
    """Check robots.txt + sitemap.xml. Also parse robots.txt for declared sitemap locations."""
    # ── robots.txt ──────────────────────────────────────────
    robots_content = ""
    try:
        resp = httpx.get(f"{origin}/robots.txt", follow_redirects=True, timeout=10)
        if resp.status_code == 404:
            _add(scan_id, "missing_robots_txt", "warning",
                 f"robots.txt not found (404): {origin}")
        elif resp.status_code == 403:
            _add(scan_id, "blocked_robots_txt", "info",
                 f"robots.txt exists but blocked (403): {origin} -- verify manually")
        elif resp.status_code >= 500:
            _add(scan_id, "error_robots_txt", "warning",
                 f"robots.txt server error ({resp.status_code}): {origin}")
        else:
            robots_content = resp.text
    except Exception:
        _add(scan_id, "missing_robots_txt", "info",
             f"Could not fetch robots.txt from {origin}")

    # Parse Sitemap directives from robots.txt
    declared_sitemaps = []
    if robots_content:
        for line in robots_content.splitlines():
            line = line.strip()
            if line.lower().startswith("sitemap:"):
                sitemap_url = line.split(":", 1)[1].strip()
                if sitemap_url:
                    declared_sitemaps.append(sitemap_url)

    # ── sitemap.xml ──────────────────────────────────────────
    try:
        resp = httpx.get(f"{origin}/sitemap.xml", follow_redirects=True, timeout=10)
        if resp.status_code == 404:
            _add(scan_id, "missing_sitemap", "warning",
                 f"sitemap.xml not found (404): {origin}")
        elif resp.status_code == 403:
            _add(scan_id, "blocked_sitemap", "info",
                 f"sitemap.xml exists but blocked (403): {origin} -- verify manually")
        elif resp.status_code >= 500:
            _add(scan_id, "error_sitemap", "warning",
                 f"sitemap.xml server error ({resp.status_code}): {origin}")
    except Exception:
        _add(scan_id, "missing_sitemap", "info",
             f"Could not fetch sitemap.xml from {origin}")

    # ── Check declared sitemaps from robots.txt ─────────────
    if declared_sitemaps:
        # Verify each declared sitemap is reachable
        for sm_url in declared_sitemaps[:5]:  # cap at 5
            try:
                sm_resp = httpx.get(sm_url, follow_redirects=True, timeout=10)
                if sm_resp.status_code == 404:
                    _add(scan_id, "declared_sitemap_not_found", "warning",
                         f"Sitemap declared in robots.txt but returns 404: {sm_url}")
                elif sm_resp.status_code >= 500:
                    _add(scan_id, "declared_sitemap_error", "warning",
                         f"Sitemap declared in robots.txt server error ({sm_resp.status_code}): {sm_url}")
            except Exception:
                _add(scan_id, "declared_sitemap_unreachable", "warning",
                     f"Sitemap declared in robots.txt but unreachable: {sm_url}")

        # Check if sitemap.xml matches what's declared
        if f"{origin}/sitemap.xml" not in declared_sitemaps:
            # Default sitemap.xml not declared in robots.txt
            pass  # Not an error, just informational

        # Check for sitemap index (contains other sitemaps)
        for sm_url in declared_sitemaps[:3]:
            try:
                sm_resp = httpx.get(sm_url, follow_redirects=True, timeout=10)
                if sm_resp.status_code == 200:
                    sm_text = sm_resp.text[:5000]
                    if "<sitemapindex" in sm_text:
                        # It's a sitemap index — check sub-sitemaps
                        from bs4 import BeautifulSoup as _BS
                        sm_soup = _BS(sm_text, "xml")
                        sub_sitemaps = sm_soup.find_all("sitemap")
                        if len(sub_sitemaps) > 20:
                            _add(scan_id, "large_sitemap_index", "info",
                                 f"Sitemap index has {len(sub_sitemaps)} sub-sitemaps: {sm_url}")
            except Exception:
                pass
    else:
        # No sitemaps declared in robots.txt
        if robots_content and robots_content.strip():
            # robots.txt exists but has no Sitemap directive
            _add(scan_id, "no_sitemap_in_robots", "info",
                 f"robots.txt exists but no Sitemap directive declared: {origin}")


# ─── Duplicate Content Detection ──────────────────────────

def check_duplicate_content(scan_id: int, pages: list[dict]):
    """Detect similar/repeated content across pages using text fingerprinting.
    
    Strategy: Extract main text from each page, compute word frequency signature,
    compare pairs using Jaccard similarity. High similarity = duplicate content.
    """
    from bs4 import Comment

    STOP_WORDS = {"the", "a", "an", "is", "are", "was", "were", "be", "been",
                  "being", "have", "has", "had", "do", "does", "did", "will",
                  "would", "could", "should", "may", "might", "can", "shall",
                  "to", "of", "in", "for", "on", "with", "at", "by", "from",
                  "as", "into", "through", "during", "before", "after", "and",
                  "but", "or", "nor", "not", "so", "yet", "both", "either",
                  "neither", "each", "every", "all", "any", "few", "more",
                  "most", "other", "some", "such", "no", "only", "own",
                  "same", "than", "too", "very", "just", "that", "this",
                  "these", "those", "it", "its", "i", "me", "my", "we",
                  "our", "you", "your", "he", "him", "his", "she", "her",
                  "they", "them", "their", "what", "which", "who", "whom"}

    def _extract_text(soup) -> str:
        """Extract main text content, removing nav/header/footer/scripts."""
        for tag in soup.find_all(["nav", "header", "footer", "aside", "script",
                                   "style", "noscript", "iframe"]):
            tag.decompose()
        for comment in soup.find_all(string=lambda t: isinstance(t, Comment)):
            comment.extract()
        body = soup.body or soup
        return body.get_text(separator=" ", strip=True)

    def _text_fingerprint(text: str) -> set:
        """Create word frequency set (excluding stop words) for similarity comparison."""
        words = text.lower().split()
        meaningful = [w for w in words if len(w) > 2 and w not in STOP_WORDS]
        # Return top 100 most frequent words as fingerprint
        freq = {}
        for w in meaningful:
            freq[w] = freq.get(w, 0) + 1
        return set(sorted(freq, key=freq.get, reverse=True)[:100])

    def _jaccard(a: set, b: set) -> float:
        if not a or not b:
            return 0.0
        return len(a & b) / len(a | b)

    # Extract fingerprints for all pages
    page_data = []
    for p in pages:
        if not _is_crawlable(p):
            continue
        soup = _load_html(p.get("raw_html_path"))
        if not soup:
            continue
        text = _extract_text(soup)
        word_count = len(text.split())
        if word_count < 50:
            continue  # Skip thin pages
        fp = _text_fingerprint(text)
        page_data.append({"url": p["url"], "page_id": p["id"], "fingerprint": fp, "words": word_count})

    # Compare pairs
    reported = set()
    for i in range(len(page_data)):
        for j in range(i + 1, len(page_data)):
            a, b = page_data[i], page_data[j]
            sim = _jaccard(a["fingerprint"], b["fingerprint"])
            if sim >= 0.7:
                pair_key = tuple(sorted([a["url"], b["url"]]))
                if pair_key in reported:
                    continue
                reported.add(pair_key)
                pct = int(sim * 100)
                _add(scan_id, "duplicate_content", "warning",
                     f"Duplicate content ({pct}% similar, {a['words']}+{b['words']} words): {a['url']} <-> {b['url']}",
                     page_id=a["page_id"])


# ─── Internal Linking Analysis ────────────────────────────

def check_internal_linking(scan_id: int, pages: list[dict], edges: list[dict]):
    """Analyze internal linking: link depth, contextual links, orphan pages."""
    from app.crawler import normalize_url

    # Build link graph
    incoming = {}  # url -> set of source urls
    outgoing = {}  # url -> set of target urls
    all_urls = set()

    for e in edges:
        src = normalize_url(e.get("from_url", ""))
        tgt = normalize_url(e.get("to_url", ""))
        if src and tgt:
            incoming.setdefault(tgt, set()).add(src)
            outgoing.setdefault(src, set()).add(tgt)
            all_urls.add(src)
            all_urls.add(tgt)

    # Map pages by normalized URL
    page_map = {}
    for p in pages:
        norm = normalize_url(p["url"])
        page_map[norm] = p

    # ── Link Depth Analysis ──────────────────────────────
    # BFS from homepage to compute depth
    start = normalize_url(pages[0]["url"]) if pages else None
    if start:
        depth = {start: 0}
        queue = [start]
        while queue:
            current = queue.pop(0)
            for neighbor in outgoing.get(current, []):
                if neighbor not in depth and neighbor in all_urls:
                    depth[neighbor] = depth[current] + 1
                    queue.append(neighbor)

        # Flag deep pages (depth > 4)
        deep_pages = [(url, d) for url, d in depth.items() if d > 4]
        for url, d in deep_pages[:5]:
            page_id = page_map.get(url, {}).get("id")
            _add(scan_id, "deep_link_depth", "info",
                 f"Deep page (depth={d}): {url}",
                 page_id=page_id)

        # Average depth
        if depth:
            avg_depth = sum(depth.values()) / len(depth)
            if avg_depth > 3:
                _add(scan_id, "excessive_link_depth", "warning",
                     f"Average link depth {avg_depth:.1f} (>3) -- pages are hard to reach from homepage")

    # ── Orphan Pages ──────────────────────────────────────
    # Pages with no incoming internal links
    page_norms = set(normalize_url(p["url"]) for p in pages)
    orphans = []
    for p in pages:
        norm = normalize_url(p["url"])
        incoming_count = len(incoming.get(norm, set()))
        if incoming_count == 0 and norm != start:
            orphans.append(p)

    if orphans:
        samples = ", ".join(p["url"][:50] for p in orphans[:3])
        _add(scan_id, "orphan_pages", "warning",
             f"{len(orphans)} orphan pages (no internal links): {samples}",
             page_id=orphans[0]["id"])

    # ── Contextual Link Quality ──────────────────────────
    # Pages with too few outgoing links (thin linking)
    for p in pages:
        if not _is_crawlable(p):
            continue
        norm = normalize_url(p["url"])
        out_count = len(outgoing.get(norm, set()))
        # Homepage should have many links, other pages should have some
        is_home = norm == start
        if not is_home and out_count < 3:
            _add(scan_id, "thin_internal_links", "info",
                 f"Page has only {out_count} internal links: {p['url']}",
                 page_id=p["id"])


# ─── Core Web Vitals ──────────────────────────────────────

def check_core_web_vitals(scan_id: int, pages: list[dict], ux_data: dict):
    """Analyze LCP, CLS from collected PerformanceObserver data.
    
    Thresholds (Google Core Web Vitals):
    - LCP (Largest Contentful Paint): Good <=2500ms, Poor >4000ms
    - CLS (Cumulative Layout Shift): Good <=0.1, Poor >0.25
    - INP (Interaction to Next Paint): Not measurable from static crawl, skip
    """
    lcp_values = []
    cls_values = []
    lcp_details = []
    cls_details = []

    for p in pages:
        url = p.get("url", "")
        page_cwv = ux_data.get(url, {}).get("core_web_vitals", {})
        if not page_cwv:
            continue

        lcp = page_cwv.get("lcp", 0)
        cls = page_cwv.get("cls", 0)

        if lcp > 0:
            lcp_values.append(lcp)
            if lcp > 2500:
                entries = page_cwv.get("lcp_entries", [])
                element = entries[-1].get("element", "unknown") if entries else "unknown"
                lcp_details.append({"url": url, "lcp": lcp, "element": element, "page_id": p["id"]})

        if cls > 0:
            cls_values.append(cls)
            if cls > 0.1:
                entries = page_cwv.get("cls_entries", [])
                cls_details.append({"url": url, "cls": cls, "shifts": len(entries), "page_id": p["id"]})

    # ── LCP Analysis ──────────────────────────────────────
    if lcp_values:
        avg_lcp = sum(lcp_values) / len(lcp_values)
        poor_lcp = [d for d in lcp_details if d["lcp"] > 4000]
        needs_improvement = [d for d in lcp_details if 2500 < d["lcp"] <= 4000]

        if poor_lcp:
            samples = "; ".join(f"{d['lcp']}ms ({d['element']})" for d in poor_lcp[:3])
            _add(scan_id, "poor_lcp", "warning",
                 f"Poor LCP on {len(poor_lcp)}/{len(lcp_values)} pages (>4000ms): {samples}")

        if needs_improvement:
            samples = "; ".join(f"{d['url'][:50]}={d['lcp']}ms" for d in needs_improvement[:3])
            _add(scan_id, "slow_lcp", "info",
                 f"LCP needs improvement on {len(needs_improvement)} pages (2500-4000ms): {samples}")

        if avg_lcp > 3000:
            _add(scan_id, "high_avg_lcp", "warning",
                 f"Average LCP {avg_lcp:.0f}ms across {len(lcp_values)} pages (>3000ms)")

    # ── CLS Analysis ──────────────────────────────────────
    if cls_values:
        avg_cls = sum(cls_values) / len(cls_values)
        poor_cls = [d for d in cls_details if d["cls"] > 0.25]
        needs_improvement_cls = [d for d in cls_details if 0.1 < d["cls"] <= 0.25]

        if poor_cls:
            samples = "; ".join(f"CLS={d['cls']:.3f} ({d['shifts']} shifts)" for d in poor_cls[:3])
            _add(scan_id, "poor_cls", "warning",
                 f"Poor CLS on {len(poor_cls)}/{len(cls_values)} pages (>0.25): {samples}")

        if needs_improvement_cls:
            samples = "; ".join(f"{d['url'][:50]}={d['cls']:.3f}" for d in needs_improvement_cls[:3])
            _add(scan_id, "moderate_cls", "info",
                 f"CLS needs improvement on {len(needs_improvement_cls)} pages (0.1-0.25): {samples}")

        if avg_cls > 0.15:
            _add(scan_id, "high_avg_cls", "warning",
                 f"Average CLS {avg_cls:.3f} across {len(cls_values)} pages (>0.15)")

def run_seo_checks(scan_id: int, fast_mode: bool = False):
    print(f"\n{'='*60}")
    print(f"  SEO CHECKS — Scan #{scan_id} (fast_mode={fast_mode})")
    print(f"{'='*60}")

    db.delete_findings(scan_id, CATEGORY)

    pages = db.get_pages(scan_id)
    if not pages:
        print(f"[SEO] No pages found — skipping")
        return

    # In fast mode, keep a quick but useful sample
    if fast_mode:
        pages = pages[:3]
        print(f"[SEO] Fast mode: limiting to {len(pages)} pages")

    scan = db.get_scan(scan_id)
    origin = ""
    if scan:
        site = db.get_conn().execute("SELECT * FROM sites WHERE id = ?", (scan["site_id"],)).fetchone()
        if site:
            origin = site["origin"]

    edges = db.get_edges(scan_id)

    print(f"[SEO] Checking {len(pages)} pages...")

    if fast_mode:
        print(f"[SEO] Fast mode: running core checks only...")
        # Essential SEO checks for a quick but useful report
        check_crawl_access(scan_id, pages)
        check_titles(scan_id, pages)
        check_meta_descriptions(scan_id, pages)
        check_headings(scan_id, pages)
        check_canonical(scan_id, pages)
        check_viewport(scan_id, pages)
        check_broken_links(scan_id, pages)
        check_https(scan_id, pages)
        check_indexability(scan_id, pages)
    else:
        print(f"[SEO] Running crawl access checks...")
        check_crawl_access(scan_id, pages)

        print(f"[SEO] Running title checks...")
        check_titles(scan_id, pages)

        print(f"[SEO] Running meta description checks...")
        check_meta_descriptions(scan_id, pages)

        print(f"[SEO] Running heading checks...")
        check_headings(scan_id, pages)

        print(f"[SEO] Running image checks...")
        check_images(scan_id, pages)

        print(f"[SEO] Running canonical checks...")
        check_canonical(scan_id, pages)

        print(f"[SEO] Running structured data checks...")
        check_structured_data(scan_id, pages)

        print(f"[SEO] Running viewport checks...")
        check_viewport(scan_id, pages)

        print(f"[SEO] Running link text checks...")
        check_link_text(scan_id, pages)

        print(f"[SEO] Running broken link checks...")
        check_broken_links(scan_id, pages)

        if not fast_mode:
            print(f"[SEO] Running duplicate content detection...")
            check_duplicate_content(scan_id, pages)

        print(f"[SEO] Running internal linking analysis...")
        check_internal_linking(scan_id, pages, edges)

        # Core Web Vitals (needs ux_data)
        import json as _json
        import os as _os
        print(f"[SEO] Running Core Web Vitals analysis...")
        ux_dir = _os.path.join(_os.path.dirname(_os.path.dirname(_os.path.abspath(__file__))), "data", "html", f"scan{scan_id}")
        ux_file = _os.path.join(ux_dir, "ux_data.json")
        ux_data = {}
        if _os.path.exists(ux_file):
            try:
                with open(ux_file, "r", encoding="utf-8") as f:
                    ux_data = _json.load(f)
            except Exception:
                pass
        check_core_web_vitals(scan_id, pages, ux_data)

        print(f"[SEO] Running HTTPS checks...")
        check_https(scan_id, pages)

        if origin:
            print(f"[SEO] Running robots.txt & sitemap checks...")
            check_robots_and_sitemap(scan_id, origin)

        print(f"[SEO] Running content SEO analysis...")
        if not fast_mode:
            check_content_seo(scan_id, pages)
        check_indexability(scan_id, pages)
        if not fast_mode:
            check_open_graph(scan_id, pages)

    findings = db.get_findings(scan_id, CATEGORY)
    print(f"[SEO] Complete — {len(findings)} total findings")
    print(f"{'='*60}\n")

    clear_html_cache()
    return findings


# ─── Content SEO — Topic, Intent, Keywords, Entities ────

# Common stop words for keyword extraction
_STOP_WORDS = {
    "the", "a", "an", "is", "are", "was", "were", "be", "been", "being",
    "have", "has", "had", "do", "does", "did", "will", "would", "could",
    "should", "may", "might", "can", "shall", "to", "of", "in", "for",
    "on", "with", "at", "by", "from", "as", "into", "through", "during",
    "before", "after", "and", "but", "or", "nor", "not", "so", "yet",
    "both", "either", "neither", "each", "every", "all", "any", "few",
    "more", "most", "other", "some", "such", "no", "only", "own", "same",
    "than", "too", "very", "just", "that", "this", "these", "those", "it",
    "its", "i", "me", "my", "we", "our", "you", "your", "he", "him",
    "his", "she", "her", "they", "them", "their", "what", "which", "who",
    "whom", "when", "where", "why", "how", "if", "then", "else", "also",
    "about", "up", "out", "off", "over", "under", "again", "further",
    "once", "here", "there", "any", "now", "get", "got", "don", "dont",
    "just", "also", "like", "well", "back", "even", "still", "new", "way",
    "use", "http", "https", "www", "com", "org", "html", "php",
}

# Search intent signals
_INTENT_SIGNALS = {
    "informational": {
        "title_kw": {"what", "how", "why", "guide", "tutorial", "learn", "explain", "understand", "tips", "examples"},
        "url_kw": {"blog", "guide", "tutorial", "learn", "article", "news", "how-to", "tips"},
        "content_kw": {"according to", "research shows", "studies", "statistics", "data shows", "evidence", "definition"},
    },
    "navigational": {
        "title_kw": {"login", "sign in", "dashboard", "account", "portal", "official"},
        "url_kw": {"login", "signin", "dashboard", "account", "portal", "app"},
        "content_kw": set(),
    },
    "commercial": {
        "title_kw": {"best", "top", "review", "comparison", "vs", "alternative", "pricing", "plan"},
        "url_kw": {"compare", "review", "best", "top", "pricing", "plans", "vs"},
        "content_kw": {"features", "pros", "cons", "verdict", "recommendation", "affordable"},
    },
    "transactional": {
        "title_kw": {"buy", "purchase", "order", "subscribe", "download", "free trial", "get started", "sign up"},
        "url_kw": {"buy", "purchase", "order", "subscribe", "download", "cart", "checkout", "signup"},
        "content_kw": {"add to cart", "buy now", "subscribe", "order now", "free trial", "limited offer"},
    },
}

# Named entity patterns (simplified NER)
_ENTITY_PATTERNS = {
    "organization": {
        "suffixes": {"inc", "llc", "ltd", "corp", "co", "company", "group", "associates"},
        "signals": {"university", "college", "institute", "foundation", "council", "board"},
    },
    "location": {
        "suffixes": {"city", "town", "village", "county", "state", "province", "country"},
        "signals": {"street", "road", "avenue", "boulevard", "drive", "lane", "circle"},
    },
    "person": {
        "patterns": {"mr", "mrs", "ms", "dr", "prof", "sir"},
    },
    "product": {
        "signals": {"version", "edition", "pro", "premium", "basic", "standard", "enterprise"},
    },
}


def check_content_seo(scan_id: int, pages: list[dict]):
    """Analyze content SEO: topic detection, search intent, keyword coverage, entities, topical relevance."""
    from bs4 import Comment

    for p in pages:
        if not _is_crawlable(p):
            continue
        soup = _load_html(p.get("raw_html_path"))
        if not soup:
            continue

        url = p["url"]
        title = p.get("title", "") or ""

        # Extract main text
        for tag in soup.find_all(["script", "style", "nav", "footer", "header", "aside"]):
            tag.decompose()
        for comment in soup.find_all(string=lambda t: isinstance(t, Comment)):
            comment.extract()
        body = soup.body or soup
        body_text = body.get_text(separator=" ", strip=True)
        word_count = len(body_text.split())

        # ── 1. Search Intent Detection ────────────────────
        intent_scores = {"informational": 0, "navigational": 0, "commercial": 0, "transactional": 0}

        for intent, signals in _INTENT_SIGNALS.items():
            # Title signals
            title_lower = title.lower()
            for kw in signals.get("title_kw", set()):
                if kw in title_lower:
                    intent_scores[intent] += 3

            # URL signals
            url_lower = url.lower()
            for kw in signals.get("url_kw", set()):
                if kw in url_lower:
                    intent_scores[intent] += 2

            # Content signals
            content_lower = body_text[:3000].lower()
            for kw in signals.get("content_kw", set()):
                if kw in content_lower:
                    intent_scores[intent] += 1

        detected_intent = max(intent_scores, key=intent_scores.get) if max(intent_scores.values()) > 0 else None

        # ── 2. Topic Extraction ───────────────────────────
        words = body_text.lower().split()
        meaningful = [w for w in words if len(w) > 3 and w.isalpha() and w not in _STOP_WORDS]

        # Word frequency for topic detection
        freq = {}
        for w in meaningful:
            freq[w] = freq.get(w, 0) + 1
        top_topics = sorted(freq, key=freq.get, reverse=True)[:5]

        # ── 3. Title-Content Keyword Overlap ──────────────
        title_words = set(title.lower().split())
        title_content_overlap = len(title_words & set(meaningful[:200])) / max(len(title_words), 1)

        if title_content_overlap < 0.2 and title_words:
            _add(scan_id, "low_title_content_relevance", "warning",
                 f"Title-content keyword overlap only {title_content_overlap:.0%}: title='{title[:50]}', top topics={top_topics[:3]}",
                 page_id=p["id"])

        # ── 4. Entity Detection ───────────────────────────
        detected_entities = {"organization": [], "location": [], "person": [], "product": []}
        text_lower = body_text.lower()

        for entity_type, patterns in _ENTITY_PATTERNS.items():
            for suffix in patterns.get("suffixes", set()):
                import re as _re
                matches = _re.findall(rf'\b\w+\s+{suffix}\b', text_lower)
                if matches:
                    detected_entities[entity_type].extend(matches[:3])
            for signal in patterns.get("signals", set()):
                if signal in text_lower:
                    detected_entities[entity_type].append(signal)

        # ── 5. Content Depth Score ────────────────────────
        # Based on word count, heading structure, lists, paragraphs
        headings = len(soup.find_all(["h1", "h2", "h3", "h4", "h5", "h6"]))
        lists = len(soup.find_all(["ul", "ol"]))
        paragraphs = len(soup.find_all("p"))

        depth_score = 0
        if word_count >= 300: depth_score += 1
        if word_count >= 1000: depth_score += 1
        if headings >= 3: depth_score += 1
        if lists >= 1: depth_score += 1
        if paragraphs >= 5: depth_score += 1

        if word_count < 100:
            _add(scan_id, "thin_content_page", "warning",
                 f"Very thin content ({word_count} words): {url}",
                 page_id=p["id"])
        elif word_count < 300:
            _add(scan_id, "short_content_page", "info",
                 f"Short content ({word_count} words, topic coverage may be limited): {url}",
                 page_id=p["id"])

        # ── 6. Topical Relevance ─────────────────────────
        # Check if page covers a focused topic or is too broad
        if len(freq) > 0:
            # Shannon entropy of word distribution
            total = sum(freq.values())
            import math
            entropy = -sum((c / total) * math.log2(c / total) for c in freq.values() if c > 0)
            # High entropy = scattered topic, low entropy = focused
            if entropy > 8 and word_count > 500:
                _add(scan_id, "scattered_topic", "info",
                     f"Content covers many topics (entropy={entropy:.1f}, {word_count} words): {url}",
                     page_id=p["id"])


# ─── Indexability — noindex, robots, canonical conflicts ──

def check_indexability(scan_id: int, pages: list[dict]):
    """Check noindex directives, robots rules, canonical conflicts, blocked resources."""
    import re as _re

    for p in pages:
        if not _is_crawlable(p):
            continue
        soup = _load_html(p.get("raw_html_path"))
        if not soup:
            continue

        url = p["url"]

        # ── 1. Meta robots noindex ───────────────────────
        meta_robots = soup.find("meta", {"name": "robots"})
        meta_googlebot = soup.find("meta", {"name": "googlebot"})

        robots_content = ""
        if meta_robots and meta_robots.get("content"):
            robots_content = meta_robots["content"].lower()
        if meta_googlebot and meta_googlebot.get("content"):
            robots_content += " " + meta_googlebot["content"].lower()

        if "noindex" in robots_content:
            _add(scan_id, "meta_noindex", "warning",
                 f"Page has noindex directive: {url}",
                 page_id=p["id"])

        if "nofollow" in robots_content:
            _add(scan_id, "meta_nofollow", "warning",
                 f"Page has nofollow directive: {url}",
                 page_id=p["id"])

        if "nosnippet" in robots_content:
            _add(scan_id, "meta_nosnippet", "info",
                 f"Page has nosnippet directive: {url}",
                 page_id=p["id"])

        if "max-snippet" in robots_content or "max-image-preview" in robots_content:
            # Extract the value
            match = _re.search(r'max-snippet:\s*(\d+)', robots_content)
            if match and int(match.group(1)) == 0:
                _add(scan_id, "meta_max_snippet_zero", "warning",
                     f"Page restricts snippet to 0 chars: {url}",
                     page_id=p["id"])

        # ── 2. X-Robots-Tag in response headers ──────────
        headers_raw = p.get("response_headers", "{}")
        try:
            import json as _json
            headers = _json.loads(headers_raw) if isinstance(headers_raw, str) else headers_raw
        except Exception:
            headers = {}

        x_robots = headers.get("x-robots-tag", "")
        if isinstance(x_robots, str) and "noindex" in x_robots.lower():
            _add(scan_id, "x_robots_noindex", "warning",
                 f"X-Robots-Tag header contains noindex: {url}",
                 page_id=p["id"])

        # ── 3. Canonical conflicts ───────────────────────
        canonical = soup.find("link", {"rel": "canonical"})
        if canonical and canonical.get("href"):
            canon_href = canonical["href"].strip()
            if "noindex" in robots_content:
                _add(scan_id, "canonical_noindex_conflict", "warning",
                     f"Conflict: page has both canonical ({canon_href[:50]}) and noindex: {url}",
                     page_id=p["id"])

        # ── 4. Blocked resources ─────────────────────────
        # Check for CSS/JS with integrity + crossorigin (may indicate SRI blocking)
        blocked_scripts = soup.find_all("script", {"integrity": True})
        blocked_links = soup.find_all("link", {"integrity": True})

        # Check for lazy-loaded resources that might be blocked
        noscript_imgs = soup.find_all("noscript")
        noscript_count = len(noscript_imgs) if noscript_imgs else 0

        # Check for nofollow on important internal links
        nofollow_internal = 0
        for a in soup.find_all("a", rel=True):
            if "nofollow" in a.get("rel", []) and a.get("href", "").startswith("/"):
                nofollow_internal += 1

        if nofollow_internal > 0:
            _add(scan_id, "internal_nofollow_links", "warning",
                 f"{nofollow_internal} internal links with nofollow: {url}",
                 page_id=p["id"])

        # ── 5. Redirect chain detection ──────────────────
        status = p.get("status_code")
        if status and 300 <= status < 400:
            _add(scan_id, "redirect_chain", "warning",
                 f"Page returns redirect ({status}): {url}",
                 page_id=p["id"])


# ─── Open Graph / Social Metadata ───────────────────────

def check_open_graph(scan_id: int, pages: list[dict]):
    """Check OG title, description, image, Twitter/X metadata completeness."""
    REQUIRED_OG = {"og:title", "og:description", "og:image", "og:url"}
    REQUIRED_TWITTER = {"twitter:card"}

    for p in pages:
        if not _is_crawlable(p):
            continue
        soup = _load_html(p.get("raw_html_path"))
        if not soup:
            continue

        url = p["url"]
        title = p.get("title", "") or ""
        meta_desc = ""

        # Gather all meta tags
        og_tags = {}
        twitter_tags = {}
        all_meta = {}

        for meta in soup.find_all("meta"):
            name = (meta.get("name") or meta.get("property") or "").lower()
            content = meta.get("content", "")
            if not name or not content:
                continue
            all_meta[name] = content

            if name.startswith("og:"):
                og_tags[name] = content
            elif name.startswith("twitter:"):
                twitter_tags[name] = content

        # ── 1. OG Tags ──────────────────────────────────
        missing_og = REQUIRED_OG - set(og_tags.keys())

        if missing_og:
            # Only flag if page has NO OG tags at all (partial is better than none)
            if len(og_tags) == 0:
                _add(scan_id, "missing_open_graph", "info",
                     f"No Open Graph tags found: {url}",
                     page_id=p["id"])
            else:
                _add(scan_id, "incomplete_open_graph", "info",
                     f"Missing OG tags: {', '.join(sorted(missing_og))}: {url}",
                     page_id=p["id"])
        else:
            # All present — check quality
            og_title = og_tags.get("og:title", "")
            og_desc = og_tags.get("og:description", "")
            og_image = og_tags.get("og:image", "")
            og_url = og_tags.get("og:url", "")

            # OG title too short or missing value
            if len(og_title.strip()) < 5:
                _add(scan_id, "weak_og_title", "warning",
                     f"OG title too short ('{og_title[:30]}'): {url}",
                     page_id=p["id"])

            # OG description too short
            if len(og_desc.strip()) < 20:
                _add(scan_id, "weak_og_description", "warning",
                     f"OG description too short ({len(og_desc)} chars): {url}",
                     page_id=p["id"])

            # OG image missing http(s) or too short
            if not og_image.startswith("http"):
                _add(scan_id, "invalid_og_image", "warning",
                     f"OG image URL invalid ('{og_image[:50]}'): {url}",
                     page_id=p["id"])

            # OG title matches page title exactly (might be auto-generated)
            if og_title.strip() == title.strip() and title.strip():
                _add(scan_id, "og_title_not_customized", "info",
                     f"OG title matches page title exactly (consider customizing): {url}",
                     page_id=p["id"])

            # OG description matches meta description exactly
            meta_desc = all_meta.get("description", "")
            if og_desc.strip() == meta_desc.strip() and meta_desc.strip():
                _add(scan_id, "og_description_not_customized", "info",
                     f"OG description matches meta description exactly (consider customizing): {url}",
                     page_id=p["id"])

            # Missing og:type
            if "og:type" not in og_tags:
                _add(scan_id, "missing_og_type", "info",
                     f"Missing og:type tag: {url}",
                     page_id=p["id"])

        # ── 2. Twitter/X Tags ───────────────────────────
        if not twitter_tags:
            _add(scan_id, "missing_twitter_card", "info",
                 f"No Twitter/X card tags found: {url}",
                 page_id=p["id"])
        else:
            card_type = twitter_tags.get("twitter:card", "")
            if card_type not in ("summary", "summary_large_image", "player", "app"):
                _add(scan_id, "invalid_twitter_card_type", "warning",
                     f"Invalid twitter:card type ('{card_type}'): {url}",
                     page_id=p["id"])

            # twitter:title and twitter:description
            tw_title = twitter_tags.get("twitter:title", "")
            tw_desc = twitter_tags.get("twitter:description", "")
            tw_image = twitter_tags.get("twitter:image", "")

            if not tw_title:
                _add(scan_id, "missing_twitter_title", "info",
                     f"Missing twitter:title: {url}",
                     page_id=p["id"])

            if not tw_desc:
                _add(scan_id, "missing_twitter_description", "info",
                     f"Missing twitter:description: {url}",
                     page_id=p["id"])

            if not tw_image:
                _add(scan_id, "missing_twitter_image", "info",
                     f"Missing twitter:image: {url}",
                     page_id=p["id"])

            # twitter:site handle missing
            if "twitter:site" not in twitter_tags:
                _add(scan_id, "missing_twitter_site", "info",
                     f"Missing twitter:site handle: {url}",
                     page_id=p["id"])
