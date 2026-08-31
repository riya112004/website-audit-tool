import re
import os
from urllib.parse import urlparse
from bs4 import BeautifulSoup


# ─── Page Intent Classification ─────────────────────────

# Pages that DON'T need conversion CTAs
INFO_PAGE_PATTERNS = {
    "privacy", "policy", "terms", "conditions", "legal", "disclaimer",
    "sitemap", "cookie", "consent", "gdpr", "refund", "cancellation",
    "faq", "help", "support", "documentation", "docs", "glossary",
    "accessibility", "color-definition", "whoweare", "who-we-are",
    "license", "attributions", "changelog", "release-notes",
    "about-us", "about", "our-story", "team", "leadership",
    "news", "press", "media", "blog", "articles",
    "testimonials", "reviews", "case-studies",
}

# Pages that DO need conversion CTAs
CONVERSION_PAGE_PATTERNS = {
    "contact", "enquiry", "inquiry", "get-quote", "pricing", "plans",
    "services", "solutions", "products", "features",
    "careers", "jobs", "hiring", "apply", "recruitment",
    "signup", "sign-up", "register", "demo", "trial", "free-trial",
    "book", "schedule", "appointment", "consultation",
    "download", "resources", "whitepaper", "ebook",
    "partners", "partner", "affiliate", "reseller",
}


def _classify_page_intent(url: str, title: str = "") -> str:
    """Classify page as 'info', 'conversion', or 'neutral'.
    
    - 'info': informational pages that don't need CTAs (privacy, terms, sitemap)
    - 'conversion': pages that should have CTAs (contact, services, pricing)
    - 'neutral': pages where CTA requirement is ambiguous (homepage, custom pages)
    """
    parsed = urlparse(url)
    path = parsed.path.lower().rstrip("/")
    title_lower = (title or "").lower()
    
    # Check path segments
    segments = [s for s in path.split("/") if s]
    all_text = " ".join(segments) + " " + title_lower
    
    # Check info patterns
    for pattern in INFO_PAGE_PATTERNS:
        if pattern in all_text:
            return "info"
    
    # Check conversion patterns
    for pattern in CONVERSION_PAGE_PATTERNS:
        if pattern in all_text:
            return "conversion"
    
    # Homepage is neutral (different CTA expectations)
    if path in ("", "/"):
        return "neutral"
    
    return "neutral"


def analyze_ux(scan_id: int, pages: list[dict], page_htmls: dict, edges: list[dict],
               all_elements: dict, ux_data: dict, origin: str, fast_mode: bool = False) -> list[dict]:
    """Run UX checks, with a narrower set in fast mode."""
    findings = []

    if not pages:
        return findings

    homepage = None
    for p in pages:
        if p.get("depth", 999) == 0:
            homepage = p
            break

    _check_confusing_navigation(findings, scan_id, pages, page_htmls)
    _check_deep_nesting(findings, scan_id, pages)
    if not fast_mode:
        _check_breadcrumb_missing(findings, scan_id, pages, page_htmls)
    _check_no_search_functionality(findings, scan_id, pages, page_htmls)
    if not fast_mode:
        _check_unclear_information_architecture(findings, scan_id, pages, page_htmls)

    for p in pages:
        if p.get("status_code") and p["status_code"] >= 400:
            continue
        soup = page_htmls.get(p["url"])
        if not soup:
            continue

        _check_poor_content_readability(findings, scan_id, p, soup)
        _check_information_overload(findings, scan_id, p, soup)
        _check_wall_of_text(findings, scan_id, p, soup)
        _check_content_not_scannable(findings, scan_id, p, soup)
        _check_no_clear_value_proposition(findings, scan_id, p, soup, homepage)

        _check_weak_cta_hierarchy(findings, scan_id, p, soup)
        if not fast_mode:
            _check_competing_ctas(findings, scan_id, p, soup)
            _check_dead_end_pages(findings, scan_id, p, soup)
            _check_confusing_user_flow(findings, scan_id, p, soup)

        _check_missing_hover_states(findings, scan_id, p, soup)
        if not fast_mode:
            _check_no_loading_feedback(findings, scan_id, p, soup)
        _check_missing_keyboard_navigation(findings, scan_id, p, soup)
        if not fast_mode:
            _check_no_error_recovery(findings, scan_id, p, soup)

        _check_forms_without_labels(findings, scan_id, p, soup)
        _check_excessive_form_fields(findings, scan_id, p, soup)
        _check_no_form_validation(findings, scan_id, p, soup)
        if not fast_mode:
            _check_confusing_form_layout(findings, scan_id, p, soup)
            _check_missing_required_indicators(findings, scan_id, p, soup)

        page_ux = ux_data.get(p["url"], {})
        _check_poor_mobile_responsive(findings, scan_id, p, soup)
        _check_touch_targets_too_small(findings, scan_id, p, page_ux)
        _check_horizontal_scroll_mobile(findings, scan_id, p, page_ux)
        _check_mobile_menu_poor(findings, scan_id, p, soup)
        _check_pinch_to_zoom_disabled(findings, scan_id, p, soup)

        _check_missing_aria_labels(findings, scan_id, p, all_elements)
        _check_missing_alt_text(findings, scan_id, p, soup)
        _check_missing_focus_indicators(findings, scan_id, p, soup)
        _check_missing_skip_navigation(findings, scan_id, p, soup)

    if not fast_mode:
        # DOM-diff broken interactions — runs Playwright once for all pages
        print(f"[UX] Running broken interactions check (DOM-diff)...")
        _check_broken_interactions(findings, scan_id, pages, page_htmls)
        print(f"[UX] Broken interactions check complete")

    return findings


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _finding(scan_id: int, check_name: str, severity: str, message: str,
             page_url: str, page_id: int, evidence: str, recommendation: str) -> dict:
    return {
        "check_name": check_name,
        "severity": severity,
        "message": message,
        "page_url": page_url,
        "page_id": page_id,
        "evidence": evidence,
        "recommendation": recommendation,
    }


def _get_text_words(soup: BeautifulSoup) -> list[str]:
    """Return all visible words from the page."""
    for tag in soup.find_all(["script", "style", "noscript"]):
        tag.decompose()
    text = soup.get_text(separator=" ", strip=True)
    return [w for w in re.split(r"\s+", text) if w]


def _count_sentences(soup: BeautifulSoup) -> list[str]:
    """Return list of sentence lengths (word counts) from visible text."""
    for tag in soup.find_all(["script", "style", "noscript"]):
        tag.decompose()
    text = soup.get_text(separator=" ", strip=True)
    sentences = re.split(r"[.!?]+", text)
    return [len(w.split()) for s in sentences if (w := s.strip())]


def _get_cta_elements(soup: BeautifulSoup) -> list:
    """Return elements that are actual action CTAs — not navigation, not informational links.
    
    Classification:
    - navigation: links inside <nav>, <header>, footer, sidebar, <li><ul> dropdowns → EXCLUDED
    - informational: "read more", "learn more", "view details" → EXCLUDED  
    - secondary CTA: less prominent actions → included but marked
    - primary CTA: main hero/featured actions → included
    - conversion CTA: sign up, buy, contact, demo → included
    """
    NAV_EXCLUDE_PATTERNS = {"nav", "navbar", "menu", "sidebar", "footer-nav", "topbar", "top-bar"}
    INFO_TEXT_PATTERNS = {
        "read more", "learn more", "view more", "see more", "find out more",
        "discover more", "explore more", "click here", "here", "more",
        "view details", "see details", "learn about", "find out",
        "continue reading", "keep reading", "go back", "back to",
        "show more", "show all", "load more", "view all", "see all",
        "browse", "explore", "view", "see", "read", "watch",
        "next", "previous", "prev", "back", "forward",
        "home", "about us", "contact us", "sitemap",
    }
    FOOTER_KEYWORDS = {
        "privacy", "policy", "terms", "conditions", "legal", "disclaimer",
        "copyright", "©", "all rights reserved",
        "facebook", "twitter", "instagram", "linkedin", "youtube",
        "github", "social",
    }

    def _is_in_nav_context(tag):
        """Check if tag is inside nav/header/footer/dropdown/list-menu context."""
        parent = tag.parent
        for _ in range(10):
            if parent is None:
                break
            tag_name = parent.name if hasattr(parent, 'name') else ""
            classes = " ".join(parent.get("class", [])).lower() if hasattr(parent, 'get') else ""

            # Direct nav/header/footer tags
            if tag_name in ("nav", "header", "footer"):
                return True

            # Class-based nav detection
            for pattern in NAV_EXCLUDE_PATTERNS:
                if pattern in classes:
                    return True

            # Dropdown / mega-menu / submenu classes
            if re.search(r"dropdown|mega-menu|submenu|collapsible|accordion|off-canvas|mobile-menu", classes):
                return True

            # <li> inside <ul> = list-based navigation (dropdown items, menu items, social links)
            if tag_name == "li":
                grandparent = parent.parent
                if grandparent is not None:
                    gp_name = grandparent.name if hasattr(grandparent, 'name') else ""
                    if gp_name == "ul":
                        # Great-grandparent = likely a nav menu container
                        ggp = grandparent.parent
                        if ggp is not None:
                            ggp_name = ggp.name if hasattr(ggp, 'name') else ""
                            ggp_cls = " ".join(ggp.get("class", [])).lower() if hasattr(ggp, 'get') else ""
                            if ggp_name in ("nav", "header", "div"):
                                # If the div has menu/nav/dropdown class, or is inside nav context
                                if (re.search(r"menu|nav|dropdown|header|sidebar", ggp_cls) or
                                    ggp_name in ("nav", "header")):
                                    return True
                                # Even plain <div> > <ul> > <li> > <a> is likely navigation
                                # unless it's inside <main> or <article>
                                if not self_in_main(parent):
                                    return True

            # <button> inside <li> = toggle button for dropdown
            if tag_name == "li" and parent.parent is not None:
                gp_name = parent.parent.name if hasattr(parent.parent, 'name') else ""
                if gp_name == "ul" and tag.name == "button":
                    return True

            parent = parent.parent
        return False

    def self_in_main(tag):
        """Check if any ancestor up to 10 levels is <main> or <article>."""
        p = tag.parent
        for _ in range(10):
            if p is None:
                return False
            name = p.name if hasattr(p, 'name') else ""
            if name in ("main", "article", "section"):
                return True
            p = p.parent
        return False

    def _is_informational(tag):
        """Check if tag text is informational rather than action-oriented."""
        text = _cta_text(tag).lower().strip()
        if not text or len(text) < 2:
            return True
        for pattern in INFO_TEXT_PATTERNS:
            if text == pattern or text.startswith(pattern):
                return True
        if len(text.split()) == 1 and text in ("home", "about", "blog", "news", "faq", "help", "menu"):
            return True
        return False

    def _is_footer_link(tag):
        """Check if tag is a footer social/info link."""
        text = _cta_text(tag).lower().strip()
        href = tag.get("href", "").lower()
        for kw in FOOTER_KEYWORDS:
            if kw in text or kw in href:
                return True
        return False

    ctas = []
    seen = set()
    for tag in soup.find_all(["a", "button", "input"]):
        if _is_in_nav_context(tag):
            continue
        tag_type = (tag.get("type") or "").lower()
        if tag.name == "input" and tag_type not in ("submit", "button", "image"):
            continue
        if _is_informational(tag):
            continue
        if _is_footer_link(tag):
            continue
        text = _cta_text(tag)
        if text and id(tag) not in seen:
            seen.add(id(tag))
            ctas.append(tag)

    for tag in soup.find_all(attrs={"role": "button"}):
        if tag.name not in ("a", "button", "input"):
            if not _is_in_nav_context(tag) and id(tag) not in seen:
                ctas.append(tag)

    return ctas


def _cta_text(tag) -> str:
    text = tag.get_text(strip=True)
    if text:
        return text
    if tag.get("aria-label"):
        return tag["aria-label"]
    if tag.get("value"):
        return tag["value"]
    if tag.get("title"):
        return tag["title"]
    for img in tag.find_all("img"):
        alt = img.get("alt", "").strip()
        if alt:
            return alt
    return ""


def _has_submenu_grouping(nav_tag) -> bool:
    """Check if a nav has submenu / dropdown grouping."""
    if nav_tag.find("ul", recursive=True):
        nested = nav_tag.find("ul").find("ul")
        if nested:
            return True
    if nav_tag.find(attrs={"aria-haspopup": True}):
        return True
    if nav_tag.find("details"):
        return True
    classes_str = " ".join(nav_tag.get("class", []))
    if re.search(r"dropdown|submenu|mega", classes_str, re.I):
        return True
    for child in nav_tag.find_all(True, recursive=True):
        child_classes = " ".join(child.get("class", []))
        if re.search(r"dropdown|submenu|mega|collapsible", child_classes, re.I):
            return True
    return False


# ---------------------------------------------------------------------------
# 1. Navigation (cross-page)
# ---------------------------------------------------------------------------

def _check_confusing_navigation(findings, scan_id, pages, page_htmls):
    checked_urls = set()
    for p in pages:
        if p["url"] in checked_urls:
            continue
        soup = page_htmls.get(p["url"])
        if not soup:
            continue
        navs = soup.find_all("nav")
        for nav in navs:
            links = nav.find_all("a")
            if len(links) > 20:
                if not _has_submenu_grouping(nav):
                    _add_finding(findings, scan_id, "confusing_navigation", "high",
                                 f"Confusing Navigation ({len(links)} items, no clear grouping): {p['url']}",
                                 p["url"], p["id"],
                                 f"Navigation contains {len(links)} items without submenus, dropdowns, or grouping",
                                 "Group navigation items into logical sections with submenus or use a mega-menu for large site maps")
                    break
        checked_urls.add(p["url"])


def _check_deep_nesting(findings, scan_id, pages):
    for p in pages:
        depth = p.get("depth", 0)
        if depth > 4:
            _add_finding(findings, scan_id, "deep_nesting", "high",
                         f"Deep Nesting (depth {depth}): {p['url']}",
                         p["url"], p["id"],
                         f"Page is {depth} levels deep from homepage",
                         "Flatten site hierarchy so important pages are within 3 clicks of homepage")


def _check_breadcrumb_missing(findings, scan_id, pages, page_htmls):
    non_home = [p for p in pages if p.get("depth", 0) > 0
                and (not p.get("status_code") or p["status_code"] < 400)]
    found_breadcrumb = False
    for p in non_home:
        if found_breadcrumb:
            break
        soup = page_htmls.get(p["url"])
        if not soup:
            continue
        if soup.find(attrs={"aria-label": "breadcrumb"}):
            found_breadcrumb = True
            break
        if soup.find("nav", class_=re.compile(r"breadcrumb", re.I)):
            found_breadcrumb = True
            break
        if soup.find(class_=re.compile(r"breadcrumb", re.I)):
            found_breadcrumb = True
            break
        if soup.find("ol", class_=re.compile(r"breadcrumb", re.I)):
            found_breadcrumb = True
            break

    if not found_breadcrumb and len(non_home) > 0:
        _add_finding(findings, scan_id, "breadcrumb_missing", "info",
                     f"Breadcrumb Missing on {len(non_home)} non-homepage pages",
                     non_home[0]["url"], non_home[0]["id"],
                     f"{len(non_home)} pages without breadcrumb navigation",
                     "Add breadcrumb navigation to help users understand their location within the site")


def _check_no_search_functionality(findings, scan_id, pages, page_htmls):
    has_search = False
    for p in pages:
        if has_search:
            break
        soup = page_htmls.get(p["url"])
        if not soup:
            continue
        if soup.find("input", {"type": "search"}):
            has_search = True
            break
        search_input = soup.find("input", attrs={"role": "search"})
        if search_input:
            has_search = True
            break
        search_form = soup.find("form", attrs={"role": "search"})
        if search_form:
            has_search = True
            break
        search_section = soup.find(attrs={"aria-label": re.compile(r"search", re.I)})
        if search_section:
            has_search = True
            break
        for inp in soup.find_all("input"):
            placeholder = (inp.get("placeholder") or "").lower()
            name = (inp.get("name") or "").lower()
            inp_id = (inp.get("id") or "").lower()
            if "search" in placeholder or "search" in name or "search" in inp_id:
                has_search = True
                break

    if not has_search and len(pages) > 5:
        _add_finding(findings, scan_id, "no_search_functionality", "medium",
                     "No Search Functionality found on any page",
                     pages[0]["url"], pages[0]["id"],
                     f"No search input or search form detected across {len(pages)} pages",
                     "Add a search function to help users find content, especially for sites with >10 pages")


def _check_unclear_information_architecture(findings, scan_id, pages, page_htmls):
    nav_link_counts = {}
    for p in pages:
        soup = page_htmls.get(p["url"])
        if not soup:
            continue
        navs = soup.find_all("nav")
        max_links = 0
        for nav in navs:
            links = nav.find_all("a")
            if len(links) > max_links:
                max_links = len(links)
        if max_links > 0:
            nav_link_counts[p["url"]] = max_links

    if len(nav_link_counts) < 3:
        return

    counts = list(nav_link_counts.values())
    avg = sum(counts) / len(counts)
    if avg == 0:
        return

    high_variance_urls = []
    for url, count in nav_link_counts.items():
        if abs(count - avg) > avg * 0.5:
            high_variance_urls.append(url)

    if len(high_variance_urls) > len(nav_link_counts) * 0.3:
        sample = high_variance_urls[0]
        sample_page = next((p for p in pages if p["url"] == sample), None)
        if sample_page:
            _add_finding(findings, scan_id, "unclear_information_architecture", "medium",
                         f"Unclear Information Architecture ({len(high_variance_urls)} pages with inconsistent nav)",
                         sample, sample_page["id"],
                         f"Nav link counts vary significantly: min={min(counts)}, max={max(counts)}, avg={avg:.1f}",
                         "Standardize navigation structure across pages for consistent user experience")


# ---------------------------------------------------------------------------
# 2. Content Clarity (per page)
# ---------------------------------------------------------------------------

def _check_poor_content_readability(findings, scan_id, page, soup):
    words = _get_text_words(soup)
    if not words:
        return
    avg_word_len = sum(len(w) for w in words) / len(words)

    sentence_lens = _count_sentences(soup)
    long_sentences = [s for s in sentence_lens if s > 30]

    if avg_word_len > 8 and len(sentence_lens) > 5:
        _add_finding(findings, scan_id, "poor_content_readability", "medium",
                     f"Poor Content Readability (avg word length: {avg_word_len:.1f} chars): {page['url']}",
                     page["url"], page["id"],
                     f"Average word length {avg_word_len:.1f} chars, {len(long_sentences)} sentences with >30 words",
                     "Use shorter, simpler words and break long sentences into shorter ones for better readability")
    elif len(long_sentences) > len(sentence_lens) * 0.3 and len(sentence_lens) > 5:
        _add_finding(findings, scan_id, "poor_content_readability", "medium",
                     f"Poor Content Readability ({len(long_sentences)}/{len(sentence_lens)} sentences >30 words): {page['url']}",
                     page["url"], page["id"],
                     f"{len(long_sentences)} out of {len(sentence_lens)} sentences exceed 30 words",
                     "Break long sentences into shorter ones; aim for 15-20 words per sentence")


def _check_information_overload(findings, scan_id, page, soup):
    words = _get_text_words(soup)
    word_count = len(words)
    sections = soup.find_all(["section", "article", "div"])
    heading_tags = soup.find_all(re.compile(r"^h[1-6]$"))
    section_count = max(len(sections), len(heading_tags))

    if word_count > 7000 and section_count > 15:
        _add_finding(findings, scan_id, "information_overload", "high",
                     f"Information Overload ({word_count} words, {section_count} sections): {page['url']}",
                     page["url"], page["id"],
                     f"{word_count} words across {section_count} sections detected",
                     "Reduce redundant sections and prioritize primary user goals")


def _check_wall_of_text(findings, scan_id, page, soup):
    words = _get_text_words(soup)
    word_count = len(words)
    heading_tags = soup.find_all(re.compile(r"^h[1-6]$"))
    sections = soup.find_all(["section", "article"])
    section_count = max(len(heading_tags), len(sections))

    if word_count > 3000 and section_count < 3:
        _add_finding(findings, scan_id, "wall_of_text", "high",
                     f"Wall of Text ({word_count} words, only {section_count} headings/sections): {page['url']}",
                     page["url"], page["id"],
                     f"{word_count} words with only {section_count} content breaks",
                     "Add headings, subheadings, bullet points, and visual breaks to improve content scannability")


def _check_content_not_scannable(findings, scan_id, page, soup):
    words = _get_text_words(soup)
    word_count = len(words)
    heading_tags = soup.find_all(re.compile(r"^h[1-6]$"))
    h2_plus = [h for h in heading_tags if h.name != "h1"]

    if word_count > 1000 and len(h2_plus) < 3:
        _add_finding(findings, scan_id, "content_not_scannable", "medium",
                     f"Content Not Scannable ({word_count} words, {len(h2_plus)} headings): {page['url']}",
                     page["url"], page["id"],
                     f"{word_count} words with only {len(h2_plus)} h2+ headings for visual breaks",
                     "Add descriptive headings and subheadings to create a clear content hierarchy")


def _check_no_clear_value_proposition(findings, scan_id, page, soup, homepage):
    if not homepage:
        return
    if page["url"] != homepage["url"]:
        return

    first_section_words = []
    body = soup.find("body")
    if not body:
        return

    direct_children = body.find_all(["section", "div", "header", "main"], recursive=False)
    if not direct_children:
        direct_children = body.find_all(["section", "div", "header", "main"])

    seen_headings = 0
    for child in direct_children[:5]:
        text = child.get_text(separator=" ", strip=True)
        words = [w for w in re.split(r"\s+", text) if w]
        first_section_words.extend(words)
        if len(first_section_words) >= 50:
            break

    if len(first_section_words) < 50:
        _add_finding(findings, scan_id, "no_clear_value_proposition", "high",
                     f"No Clear Value Proposition (only {len(first_section_words)} words above fold): {page['url']}",
                     page["url"], page["id"],
                     f"Homepage has only {len(first_section_words)} words in the above-fold area",
                     "Communicate the primary value proposition prominently within the first screen of the homepage")


# ---------------------------------------------------------------------------
# 3. CTA / User Flow (per page)
# ---------------------------------------------------------------------------

def _check_weak_cta_hierarchy(findings, scan_id, page, soup):
    intent = _classify_page_intent(page["url"], page.get("title", ""))
    if intent == "info":
        return  # informational pages don't need CTA hierarchy
    
    ctas = _get_cta_elements(soup)
    if len(ctas) < 3:
        return

    tag_classes = set()
    for cta in ctas:
        tag_name = cta.name
        classes = " ".join(cta.get("class", []))
        tag_classes.add(f"{tag_name}|{classes}")

    if len(tag_classes) == 1:
        _add_finding(findings, scan_id, "weak_cta_hierarchy", "medium",
                     f"Weak CTA Hierarchy ({len(ctas)} CTAs all same style): {page['url']}",
                     page["url"], page["id"],
                     f"All {len(ctas)} CTAs share identical tag/class combination — no visual priority",
                     "Differentiate primary and secondary CTAs using distinct visual styles, sizes, or colors")


def _check_competing_ctas(findings, scan_id, page, soup):
    intent = _classify_page_intent(page["url"], page.get("title", ""))
    if intent == "info":
        return  # informational pages don't need CTA focus
    
    ctas = _get_cta_elements(soup)
    if len(ctas) < 3:
        return  # fewer than 3 action CTAs = no competition issue
    
    # CTA intent categories
    INTENT_PATTERNS = {
        "contact": {"contact", "email", "call", "phone", "get in touch", "reach us", "chat"},
        "sign_up": {"sign up", "signup", "register", "join", "create account", "subscribe"},
        "buy": {"buy", "purchase", "order", "add to cart", "checkout", "buy now"},
        "demo": {"demo", "try", "free trial", "get started", "start free", "request demo"},
        "learn": {"learn more", "read more", "discover", "explore", "find out", "see more", "view more"},
        "download": {"download", "get", "obtain", "save"},
        "navigate": {"view all", "see all", "browse", "view details", "see details", "learn about"},
    }
    
    def _classify_cta_intent(text):
        text_lower = text.lower().strip()
        for intent_name, keywords in INTENT_PATTERNS.items():
            for kw in keywords:
                if kw in text_lower:
                    return intent_name
        return "other"
    
    # Classify each CTA
    cta_data = []
    for cta in ctas:
        text = _cta_text(cta).strip()
        if not text or len(text) < 2:
            continue
        cta_intent = _classify_cta_intent(text)
        classes = " ".join(cta.get("class", [])).lower()
        is_primary_style = any(p in classes for p in ("primary", "hero", "main", "btn-primary", "featured", "large", "big"))
        cta_data.append({
            "text": text,
            "intent": cta_intent,
            "is_primary_style": is_primary_style,
            "element": cta,
        })
    
    if not cta_data:
        return
    
    # Group by intent
    by_intent = {}
    for cta in cta_data:
        by_intent.setdefault(cta["intent"], []).append(cta)
    
    # Check for genuine duplicates: same intent, 3+ CTAs
    competing_intents = []
    for intent_name, group in by_intent.items():
        if intent_name == "other":
            continue
        if len(group) >= 3:
            competing_intents.append((intent_name, group))
    
    # Check visual hierarchy: are primary CTAs distinguishable?
    primary_count = sum(1 for c in cta_data if c["is_primary_style"])
    has_clear_hierarchy = primary_count > 0 and primary_count <= 3
    
    # Only flag if there are genuine competing intents
    if competing_intents:
        for intent_name, group in competing_intents:
            samples = ", ".join('"{}"'.format(c["text"][:30]) for c in group[:4])
            severity = "medium" if len(group) >= 5 else "low"
            _add_finding(findings, scan_id, "competing_ctas", severity,
                         f"Competing {intent_name} CTAs ({len(group)} similar): {page['url']}",
                         page["url"], page["id"],
                         f"{len(group)} CTAs with same intent ({intent_name}): {samples}",
                         f"Consolidate into 1-2 {intent_name} CTAs to reduce user decision fatigue")
    
    # Flag if too many CTAs with no visual hierarchy
    if len(cta_data) > 12 and not has_clear_hierarchy:
        _add_finding(findings, scan_id, "competing_ctas", "medium",
                     f"No CTA Hierarchy ({len(cta_data)} CTAs, {primary_count} primary-styled): {page['url']}",
                     page["url"], page["id"],
                     f"Page has {len(cta_data)} CTAs but only {primary_count} with primary styling — no clear focal point",
                     "Designate 1-2 primary CTAs with contrasting style; de-emphasize secondary CTAs")


def _check_dead_end_pages(findings, scan_id, page, soup):
    internal_links = []
    for a in soup.find_all("a", href=True):
        href = a["href"].strip()
        if href.startswith("#") or href.startswith("javascript:") or href.startswith("mailto:") or href.startswith("tel:"):
            continue
        if href.startswith("/"):
            internal_links.append(href)
        elif href.startswith("http"):
            internal_links.append(href)

    if len(internal_links) == 0 and page.get("depth", 0) > 0:
        _add_finding(findings, scan_id, "dead_end_pages", "critical",
                     f"Dead End Page (no outgoing internal links): {page['url']}",
                     page["url"], page["id"],
                     "Page has no internal links — users cannot navigate away",
                     "Add relevant internal links, related content suggestions, or clear next-step CTAs")


def _check_confusing_user_flow(findings, scan_id, page, soup):
    ctas = _get_cta_elements(soup)
    back_ctas = []
    next_ctas = []
    destinations = {}

    for cta in ctas:
        text = _cta_text(cta).strip().lower()
        href = cta.get("href", "")
        if not href:
            continue
        if any(w in text for w in ("back", "previous", "prev", "return")):
            back_ctas.append((cta, href, text))
        if any(w in text for w in ("next", "forward", "continue", "proceed")):
            next_ctas.append((cta, href, text))
        destinations.setdefault(href, []).append(text)

    for href, texts in destinations.items():
        if len(texts) >= 2:
            has_back = any(any(w in t for w in ("back", "prev", "return")) for t in texts)
            has_next = any(any(w in t for w in ("next", "forward", "continue")) for t in texts)
            if has_back and has_next:
                _add_finding(findings, scan_id, "confusing_user_flow", "high",
                             f"Confusing User Flow (back and next CTAs point to same destination): {page['url']}",
                             page["url"], page["id"],
                             f"Multiple CTAs with conflicting navigation intent point to: {href}",
                             "Ensure forward and backward navigation actions point to logically distinct destinations")
                return

    if back_ctas and next_ctas:
        back_hrefs = set(h for _, h, _ in back_ctas)
        next_hrefs = set(h for _, h, _ in next_ctas)
        if back_hrefs & next_hrefs:
            _add_finding(findings, scan_id, "confusing_user_flow", "high",
                         f"Confusing User Flow (overlapping back/next destinations): {page['url']}",
                         page["url"], page["id"],
                         f"Back and next CTAs share destinations: {back_hrefs & next_hrefs}",
                         "Create clear directional navigation where back and forward actions are unambiguous")


# ---------------------------------------------------------------------------
# 4. Interaction Quality (per page)
# ---------------------------------------------------------------------------

HOVER_PATTERNS = re.compile(
    r"hover|:hover|mouse-hover|on-hover|mouseover|pointer-over",
    re.I,
)
FOCUS_PATTERNS = re.compile(
    r":focus-visible|:focus-within|:focus\b|focus-visible|focus-within",
    re.I,
)
FOCUS_OUTLINE_PATTERNS = re.compile(
    r"outline\s*:\s*(none|0|transparent|hidden)",
    re.I,
)
LOADING_PATTERNS = re.compile(
    r"loading|spinner|loader|progress|ajax-loading|is-loading|isLoading|skeleton",
    re.I,
)


def _check_missing_hover_states(findings, scan_id, page, soup):
    """Check for missing :hover CSS on interactive elements.
    
    Hover is a mouse interaction feedback — NOT an accessibility requirement.
    Severity: low (nice-to-have, not a UX failure).
    """
    buttons = soup.find_all("button")
    links = soup.find_all("a")
    interactive = buttons + links

    if len(interactive) < 5:
        return

    css_text = ""
    for tag in soup.find_all("style"):
        css_text += tag.get_text() + " "
    for tag in interactive:
        css_text += tag.get("style", "") + " "

    has_hover = bool(HOVER_PATTERNS.search(css_text))

    # Check class names for hover utilities (Tailwind, Bootstrap)
    if not has_hover:
        for tag in interactive:
            classes = " ".join(tag.get("class", [])).lower()
            if "hover" in classes:
                has_hover = True
                break

    if not has_hover:
        _add_finding(findings, scan_id, "missing_hover_states", "low",
                     f"Missing :hover Styles ({len(interactive)} elements): {page['url']}",
                     page["url"], page["id"],
                     "No :hover CSS found — interactive elements lack visual feedback on mouse hover",
                     "Add :hover styles (color change, underline, background) to provide mouse interaction feedback")


def _check_no_loading_feedback(findings, scan_id, page, soup):
    """Check for loading feedback on forms.
    
    Static HTML can't verify if async interactions actually show loading states.
    If forms exist but no loading indicators found in CSS → "Not Tested", not an issue.
    Only flag if we can confirm the issue (e.g., form has AJAX attribute but no spinner).
    """
    forms = soup.find_all("form")
    if not forms:
        return

    # Check if any form uses async submission (AJAX)
    async_forms = []
    for form in forms:
        action = form.get("action", "")
        method = form.get("method", "get").lower()
        attrs = " ".join(f"{k}={v}" for k, v in form.attrs.items()).lower()
        has_ajax = any(kw in attrs for kw in ("ajax", "fetch", "xhr", "data-remote", "data-ajax"))
        has_file = form.find("input", {"type": "file"})
        has_textarea = form.find("textarea")
        # Forms with file upload or long text are likely to benefit from loading feedback
        if has_ajax or has_file or has_textarea:
            async_forms.append(form)

    if not async_forms:
        return  # No async forms = loading feedback not relevant

    # Check CSS for loading indicators
    has_loading = False
    for tag in soup.find_all(["style"]):
        text = tag.get_text()
        if LOADING_PATTERNS.search(text):
            has_loading = True
            break

    if not has_loading:
        for tag in soup.find_all(True):
            classes = " ".join(tag.get("class", []))
            if LOADING_PATTERNS.search(classes):
                has_loading = True
                break

    if not has_loading:
        _add_finding(findings, scan_id, "no_loading_feedback", "info",
                     f"No Loading Feedback Detected ({len(async_forms)} async forms): {page['url']}",
                     page["url"], page["id"],
                     f"{len(async_forms)} form(s) with async behavior found but no loading indicator in CSS — not verified",
                     "Consider adding loading spinners for form submissions (not verified from static HTML)")


def _check_broken_interactions(findings, scan_id, pages, page_htmls):
    """Detect truly broken interactions by clicking elements and checking DOM/state changes.
    
    Strategy: 
    1. Find suspicious elements (javascript:void(0), empty onclick, divs/spans with click handlers)
    2. Snapshot DOM before click
    3. Click element
    4. Compare DOM after click
    5. DOM changed = working, DOM unchanged = broken
    """
    try:
        import asyncio
        from playwright.async_api import async_playwright
    except ImportError:
        return

    async def _run_dom_diff_check():
        async with async_playwright() as p:
            browser = await p.chromium.launch(
                headless=True,
                args=["--disable-blink-features=AutomationControlled"],
            )
            context = await browser.new_context(
                viewport={"width": 1280, "height": 720},
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            )

            pages_checked = 0
            MAX_PAGES = 5
            for pg in pages:
                if pages_checked >= MAX_PAGES:
                    break
                if pg.get("status_code") and pg["status_code"] >= 400:
                    continue
                soup = page_htmls.get(pg["url"])
                if not soup:
                    continue

                suspicious = _find_suspicious_interactive_elements(soup)
                if not suspicious:
                    continue

                print(f"[UX] Checking interactions on: {pg['url'][:50]} ({len(suspicious)} suspicious elements)")
                try:
                    page = await context.new_page()
                    await page.goto(pg["url"], timeout=12000, wait_until="domcontentloaded")
                    await page.wait_for_timeout(600)

                    broken_count = 0

                    for selector, tag_desc in suspicious[:5]:
                        try:
                            el = page.locator(selector).first
                            if not await el.is_visible(timeout=300):
                                continue

                            html_before = await page.evaluate("() => document.body.innerHTML.length")

                            await el.click(timeout=1500)
                            await page.wait_for_timeout(400)

                            html_after = await page.evaluate("() => document.body.innerHTML.length")

                            if html_before == html_after:
                                broken_count += 1

                        except Exception:
                            broken_count += 1

                    if broken_count > 0:
                        _add_finding(findings, scan_id, "broken_interactions", "critical",
                                     f"Broken Interactions ({broken_count} non-functional): {pg['url']}",
                                     pg["url"], pg["id"],
                                     f"{broken_count} clickable elements had no DOM/state change after click",
                                     "Ensure click handlers trigger visible state changes")

                    await page.close()
                    pages_checked += 1

                except Exception:
                    pass

            await context.close()
            await browser.close()

    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor() as pool:
                pool.submit(lambda: asyncio.run(_run_dom_diff_check()))
        else:
            loop.run_until_complete(_run_dom_diff_check())
    except Exception:
        pass


def _find_suspicious_interactive_elements(soup) -> list[tuple[str, str]]:
    """Find elements that are suspicious — javascript:void(0), empty onclick, clickable non-semantic elements.
    Returns list of (CSS selector, description) tuples. Deduplicated by selector.
    """
    seen = set()
    results = []

    def _add(selector, desc):
        if selector and selector not in seen:
            seen.add(selector)
            results.append((selector, desc))

    # 1. Links with javascript:void(0) or href="#"
    for a in soup.find_all("a", href=True):
        href = a["href"].strip()
        if "javascript:void(0)" in href or href == "#":
            _add(_build_css_selector(a, soup), f"<a> with {href[:30]}")

    # 2. Elements with empty/no-op onclick
    for tag in soup.find_all(True, onclick=True):
        onclick = tag.get("onclick", "").strip()
        if not onclick or re.match(r"^\s*(function\s*\(\)\s*\{\s*\}\s*|void\s*\(\s*\)|\s*)\s*$", onclick):
            _add(_build_css_selector(tag, soup), f"<{tag.name}> with empty onclick")

    # 3. Non-semantic clickable elements (div/span with role or framework click handlers)
    for tag in soup.find_all(["div", "span", "li", "td", "p"]):
        role = tag.get("role", "")
        tabindex = tag.get("tabindex", "")
        has_click_attr = any(tag.get(a) for a in ["ng-click", "v-on:click", "@click", "v-on:click.prevent"])

        if has_click_attr or (role in ("button", "link", "tab", "menuitem") and tabindex != "-1"):
            _add(_build_css_selector(tag, soup), f"<{tag.name}> role={role}")

    return results


def _build_css_selector(el, soup) -> str | None:
    """Build a unique CSS selector for an element."""
    tag = el.name
    el_id = el.get("id")
    if el_id:
        return f"#{el_id}"

    classes = el.get("class", [])
    if classes:
        cls_str = ".".join(c for c in classes if c and not c.startswith("_"))
        if cls_str:
            selector = f"{tag}.{cls_str}"
            try:
                if len(soup.select(selector)) == 1:
                    return selector
            except Exception:
                pass

    # Fallback: nth-of-type from body
    parent = el.parent
    while parent is not None:
        siblings = [c for c in parent.children if hasattr(c, 'name') and c.name == tag]
        try:
            idx = siblings.index(el) + 1
        except ValueError:
            parent = parent.parent
            continue

        if parent.name == "body" or parent.name == "html":
            return f"body > {tag}:nth-of-type({idx})"
        
        # Try parent selector
        parent_sel = _build_css_selector(parent, soup)
        if parent_sel:
            return f"{parent_sel} > {tag}:nth-of-type({idx})"
        
        parent = parent.parent

    return f"body > {tag}"


def _check_missing_keyboard_navigation(findings, scan_id, page, soup):
    """Check keyboard navigation for custom interactive elements only.
    
    Native elements (<a href>, <button>, <input>) are keyboard accessible by default.
    Only check: div/span with click handlers, role attributes, or interactive classes.
    """
    CLICK_HANDLER_ATTRS = {
        "onclick", "onkeydown", "onkeypress", "onkeyup",
        "ng-click", "v-on:click", "@click",
    }
    INTERACTIVE_CLASSES = {"btn", "button", "clickable", "link", "nav-link", "tab"}

    non_focusable = []

    # Custom elements with click handlers or interactive roles
    for tag in soup.find_all(["div", "span", "p", "li", "td", "th"]):
        has_click = any(tag.get(attr) for attr in CLICK_HANDLER_ATTRS)
        classes = " ".join(tag.get("class", [])).lower()
        has_click_class = any(kw in classes for kw in INTERACTIVE_CLASSES)
        has_role = bool(tag.get("role"))

        if not has_click and not has_click_class and not has_role:
            continue

        # Custom elements need tabindex to be keyboard focusable
        tabindex = tag.get("tabindex")
        has_tabindex = tabindex is not None and tabindex != "-1"

        if not has_tabindex:
            non_focusable.append(tag)

    if len(non_focusable) > 3:
        _add_finding(findings, scan_id, "missing_keyboard_navigation", "medium",
                     f"Missing Keyboard Navigation ({len(non_focusable)} custom elements): {page['url']}",
                     page["url"], page["id"],
                     f"{len(non_focusable)} custom interactive elements lack tabindex for keyboard access",
                     'Add tabindex="0" to custom interactive elements (div/span) to enable keyboard navigation')


def _check_no_error_recovery(findings, scan_id, page, soup):
    forms = soup.find_all("form")
    if not forms:
        return

    for form in forms:
        inputs = form.find_all(["input", "select", "textarea"])
        visible_inputs = [i for i in inputs if i.get("type") not in ("hidden", "submit", "button", "reset")]
        if len(visible_inputs) < 2:
            continue

        has_reset = bool(form.find("button", {"type": "reset"}) or form.find("input", {"type": "reset"}))
        has_cancel = False
        for btn in form.find_all(["button", "a"]):
            text = btn.get_text(strip=True).lower()
            if "cancel" in text or "reset" in text:
                has_cancel = True
                break

        if not has_reset and not has_cancel:
            _add_finding(findings, scan_id, "no_error_recovery", "low",
                         f"No Error Recovery ({len(visible_inputs)} field form without reset/cancel): {page['url']}",
                         page["url"], page["id"],
                         f"Form with {len(visible_inputs)} fields has no reset or cancel button",
                         "Add reset/cancel buttons to complex forms to allow users to recover from mistakes")


# ---------------------------------------------------------------------------
# 5. Forms (per page)
# ---------------------------------------------------------------------------

def _check_forms_without_labels(findings, scan_id, page, soup):
    forms = soup.find_all("form")
    for form in forms:
        unlabeled = 0
        inputs = form.find_all(["input", "select", "textarea"])
        for inp in inputs:
            inp_type = (inp.get("type") or "").lower()
            if inp_type in ("hidden", "submit", "button", "reset", "image"):
                continue
            inp_id = inp.get("id", "")
            has_label = bool(inp_id and soup.find("label", {"for": inp_id}))
            has_aria_label = bool(inp.get("aria-label"))
            has_aria_labelledby = bool(inp.get("aria-labelledby"))
            has_title = bool(inp.get("title"))
            wrapped_in_label = bool(inp.find_parent("label"))
            if not has_label and not has_aria_label and not has_aria_labelledby and not has_title and not wrapped_in_label:
                unlabeled += 1

        if unlabeled > 0:
            _add_finding(findings, scan_id, "forms_without_labels", "high",
                         f"Forms Without Labels ({unlabeled} unlabeled inputs): {page['url']}",
                         page["url"], page["id"],
                         f"{unlabeled} form input(s) missing associated labels",
                         "Associate every form input with a <label> element using for/id or aria-label")


def _check_excessive_form_fields(findings, scan_id, page, soup):
    forms = soup.find_all("form")
    for form in forms:
        inputs = form.find_all(["input", "select", "textarea"])
        visible = [i for i in inputs if i.get("type") not in ("hidden", "submit", "button", "reset", "image")]
        if len(visible) > 8:
            _add_finding(findings, scan_id, "excessive_form_fields", "medium",
                         f"Excessive Form Fields ({len(visible)} fields in one form): {page['url']}",
                         page["url"], page["id"],
                         f"Single form contains {len(visible)} input fields",
                         "Reduce form fields to essential information only; use multi-step forms for complex flows")


def _check_no_form_validation(findings, scan_id, page, soup):
    forms = soup.find_all("form")
    for form in forms:
        inputs = form.find_all(["input", "select", "textarea"])
        visible = [i for i in inputs if i.get("type") not in ("hidden", "submit", "button", "reset", "image")]
        if len(visible) < 2:
            continue
        unvalidated = 0
        for inp in visible:
            has_required = inp.has_attr("required")
            has_pattern = inp.has_attr("pattern")
            has_aria_required = inp.get("aria-required") in ("true", "")
            has_type_validation = (inp.get("type") or "").lower() in ("email", "url", "tel", "number")
            if not has_required and not has_pattern and not has_aria_required and not has_type_validation:
                unvalidated += 1

        if unvalidated > len(visible) * 0.7:
            _add_finding(findings, scan_id, "no_form_validation", "medium",
                         f"No Form Validation ({unvalidated}/{len(visible)} fields unvalidated): {page['url']}",
                         page["url"], page["id"],
                         f"{unvalidated} out of {len(visible)} form fields lack any validation attributes",
                         "Add required, pattern, or type validation to form inputs to catch errors before submission")


def _check_confusing_form_layout(findings, scan_id, page, soup):
    forms = soup.find_all("form")
    for form in forms:
        inputs = form.find_all(["input", "select", "textarea"])
        visible = [i for i in inputs if i.get("type") not in ("hidden", "submit", "button", "reset", "image")]
        if len(visible) <= 5:
            continue

        has_fieldset = bool(form.find("fieldset"))
        has_aria_grouping = bool(form.find(attrs={"role": "group"}))
        has_sections = len(form.find_all(["section", "div"])) > 2

        if not has_fieldset and not has_aria_grouping and not has_sections:
            _add_finding(findings, scan_id, "confusing_form_layout", "medium",
                         f"Confusing Form Layout ({len(visible)} fields, no grouping): {page['url']}",
                         page["url"], page["id"],
                         f"Form has {len(visible)} fields without fieldset, role=group, or section grouping",
                         "Group related form fields using <fieldset>, role=group, or visual sections")


def _check_missing_required_indicators(findings, scan_id, page, soup):
    forms = soup.find_all("form")
    for form in forms:
        required_inputs = form.find_all(attrs={"required": True})
        required_inputs += form.find_all(attrs={"aria-required": "true"})
        if not required_inputs:
            continue

        has_visual_indicator = False
        for inp in required_inputs:
            inp_id = inp.get("id", "")
            label = soup.find("label", {"for": inp_id}) if inp_id else None
            if label:
                label_text = label.get_text(strip=True)
                if "*" in label_text or "required" in label_text.lower():
                    has_visual_indicator = True
                    break
            parent_label = inp.find_parent("label")
            if parent_label:
                label_text = parent_label.get_text(strip=True)
                if "*" in label_text or "required" in label_text.lower():
                    has_visual_indicator = True
                    break

        if not has_visual_indicator:
            _add_finding(findings, scan_id, "missing_required_indicators", "medium",
                         f"Missing Required Indicators ({len(required_inputs)} required fields, no visual indicator): {page['url']}",
                         page["url"], page["id"],
                         f"{len(required_inputs)} required form fields lack visual required indicators (* or 'required' text)",
                         "Add visual indicators like asterisks (*) or 'required' text next to mandatory form fields")


# ---------------------------------------------------------------------------
# 6. Mobile UX (from ux_data)
# ---------------------------------------------------------------------------

def _check_poor_mobile_responsive(findings, scan_id, page, soup):
    viewport_meta = soup.find("meta", attrs={"name": "viewport"})
    if not viewport_meta:
        _add_finding(findings, scan_id, "poor_mobile_responsive", "high",
                     f"Poor Mobile Responsive (no viewport meta tag): {page['url']}",
                     page["url"], page["id"],
                     "No viewport meta tag found in HTML",
                     "Add <meta name=\"viewport\" content=\"width=device-width, initial-scale=1\"> for mobile responsiveness")


def _check_touch_targets_too_small(findings, scan_id, page, page_ux):
    mobile_data = page_ux.get("mobile", {})
    small_targets = mobile_data.get("tiny_touch_targets", 0)
    if small_targets > 5:
        _add_finding(findings, scan_id, "touch_targets_too_small", "high",
                     f"Touch Targets Too Small ({small_targets} small targets): {page['url']}",
                     page["url"], page["id"],
                     f"{small_targets} touch targets smaller than recommended minimum",
                     "Ensure all touch targets are at least 44x44px for comfortable mobile interaction")


def _check_horizontal_scroll_mobile(findings, scan_id, page, page_ux):
    mobile_data = page_ux.get("mobile", {})
    if mobile_data.get("has_horizontal_overflow"):
        _add_finding(findings, scan_id, "horizontal_scroll_mobile", "high",
                     f"Horizontal Scroll on Mobile: {page['url']}",
                     page["url"], page["id"],
                     "Page causes horizontal scrolling on mobile viewport",
                     "Fix layout to prevent horizontal scrolling; use responsive units and overflow controls")


def _check_mobile_menu_poor(findings, scan_id, page, soup):
    has_hamburger = False
    for tag in soup.find_all(["button", "a", "div", "span"]):
        classes = " ".join(tag.get("class", [])).lower()
        aria = (tag.get("aria-label") or "").lower()
        text = tag.get_text(strip=True).lower()
        if any(kw in classes for kw in ("hamburger", "menu-toggle", "mobile-menu", "nav-toggle", "menu-btn")):
            has_hamburger = True
            break
        if any(kw in aria for kw in ("menu", "navigation menu", "mobile menu")):
            has_hamburger = True
            break
        if text in ("☰", "≡", "menu"):
            has_hamburger = True
            break

    if not has_hamburger:
        return

    has_mobile_menu = False
    for tag in soup.find_all(["div", "nav", "ul", "section"]):
        classes = " ".join(tag.get("class", [])).lower()
        if any(kw in classes for kw in ("mobile-menu", "mobile-nav", "nav-menu", "slide-menu", "off-canvas", "sidebar-nav")):
            has_mobile_menu = True
            break
        if tag.get("id"):
            tag_id = tag["id"].lower()
            if any(kw in tag_id for kw in ("mobile-menu", "mobile-nav", "nav-drawer")):
                has_mobile_menu = True
                break
        aria = (tag.get("aria-label") or "").lower()
        if "mobile" in aria and "menu" in aria:
            has_mobile_menu = True
            break
        if tag.get("role") == "dialog":
            has_mobile_menu = True
            break

    if not has_mobile_menu:
        _add_finding(findings, scan_id, "mobile_menu_poor", "high",
                     f"Mobile Menu Poor (hamburger found, no mobile menu container): {page['url']}",
                     page["url"], page["id"],
                     "Menu toggle button exists but no corresponding mobile menu container was found",
                     "Add a proper mobile menu container (drawer, slide-out, or dropdown) linked to the hamburger button")


def _check_pinch_to_zoom_disabled(findings, scan_id, page, soup):
    viewport_meta = soup.find("meta", attrs={"name": "viewport"})
    if not viewport_meta:
        return

    content = (viewport_meta.get("content") or "").lower().replace(" ", "")
    if "user-scalable=no" in content or "user-scalable=0" in content:
        _add_finding(findings, scan_id, "pinch_to_zoom_disabled", "high",
                     f"Pinch to Zoom Disabled: {page['url']}",
                     page["url"], page["id"],
                     "Viewport meta has user-scalable=no which prevents zooming",
                     "Remove user-scalable=no to allow users with visual impairments to zoom the page")

    max_scale_match = re.search(r"maximum-scale\s*=\s*([\d.]+)", content)
    if max_scale_match:
        try:
            max_scale = float(max_scale_match.group(1))
            if max_scale <= 1.0:
                _add_finding(findings, scan_id, "pinch_to_zoom_disabled", "high",
                             f"Pinch to Zoom Disabled (maximum-scale=1): {page['url']}",
                             page["url"], page["id"],
                             f"Viewport meta has maximum-scale={max_scale} which restricts zooming",
                             "Remove maximum-scale restriction or set it to at least 2.0 to allow user zooming")
        except ValueError:
            pass


# ---------------------------------------------------------------------------
# 7. Accessibility (per page)
# ---------------------------------------------------------------------------

def _check_missing_aria_labels(findings, scan_id, page, all_elements):
    elements = all_elements.get(page["url"], [])
    if not elements:
        return

    interactive_roles = {
        "button", "link", "tab", "menuitem", "option", "checkbox",
        "radio", "switch", "searchbox", "combobox", "slider",
    }
    missing_count = 0
    for el in elements:
        role = (el.get("role") or "").lower()
        if role in interactive_roles:
            name = (el.get("accessible_name") or "").strip()
            if not name:
                missing_count += 1

    if missing_count > 3:
        _add_finding(findings, scan_id, "missing_aria_labels", "high",
                     f"Missing ARIA Labels ({missing_count} interactive elements): {page['url']}",
                     page["url"], page["id"],
                     f"{missing_count} interactive elements lack accessible names",
                     "Add aria-label or visible text content to all interactive elements")


def _check_missing_alt_text(findings, scan_id, page, soup):
    images = soup.find_all("img")
    if not images:
        return

    missing_alt = 0
    for img in images:
        if not img.has_attr("alt"):
            missing_alt += 1

    if missing_alt == 0:
        return

    ratio = missing_alt / len(images)
    if ratio > 0.3 or missing_alt > 3:
        _add_finding(findings, scan_id, "missing_alt_text", "high",
                     f"Missing Alt Text ({missing_alt}/{len(images)} images, {ratio:.0%}): {page['url']}",
                     page["url"], page["id"],
                     f"{missing_alt} out of {len(images)} images lack alt attribute ({ratio:.0%})",
                     "Add descriptive alt text to all images; use alt=\"\" for purely decorative images")


def _check_missing_focus_indicators(findings, scan_id, page, soup):
    """Check for missing :focus-visible / :focus CSS on interactive elements.
    
    Focus styles are an accessibility requirement — keyboard users need to see
    which element is active.
    
    Checks:
    1. :focus-visible / :focus in CSS → present = good
    2. outline:none without replacement → HIGH (removes focus indicator)
    3. No :focus styles at all → MEDIUM (keyboard navigation broken)
    """
    buttons = soup.find_all("button")
    links = soup.find_all("a")
    interactive = buttons + links

    if len(interactive) < 5:
        return

    css_text = ""
    for tag in soup.find_all("style"):
        css_text += tag.get_text() + " "
    for tag in interactive:
        css_text += tag.get("style", "") + " "

    has_focus = bool(FOCUS_PATTERNS.search(css_text))
    has_outline_none = bool(FOCUS_OUTLINE_PATTERNS.search(css_text))

    # Check class names for focus utilities (Tailwind, Bootstrap)
    if not has_focus:
        for tag in interactive:
            classes = " ".join(tag.get("class", [])).lower()
            if "focus" in classes:
                has_focus = True
                break

    # outline:none without :focus-visible replacement = HIGH
    if has_outline_none and not has_focus:
        _add_finding(findings, scan_id, "missing_focus_indicators", "high",
                     f"Focus Indicator Removed (outline:none without :focus-visible): {page['url']}",
                     page["url"], page["id"],
                     "outline:none found without :focus-visible replacement — keyboard focus invisible",
                     "Remove outline:none or pair it with :focus-visible { outline: 2px solid ... }")

    # No :focus styles at all = MEDIUM
    elif not has_focus:
        _add_finding(findings, scan_id, "missing_focus_indicators", "medium",
                     f"No :focus-visible Styles ({len(interactive)} elements): {page['url']}",
                     page["url"], page["id"],
                     "No :focus-visible or :focus CSS found — keyboard users can't see which element is active",
                     "Add :focus-visible styles (outline, box-shadow) to all interactive elements for keyboard accessibility")


def _check_missing_skip_navigation(findings, scan_id, page, soup):
    nav = soup.find("nav")
    if not nav:
        return

    skip_found = False
    for a in soup.find_all("a", href=True):
        href = a["href"]
        if href.startswith("#"):
            target_id = href[1:]
            if target_id:
                target = soup.find(id=target_id)
                if target and target.name in ("main", "content", "main-content", "content-main"):
                    skip_found = True
                    break

    if not skip_found:
        aria_label = (soup.find("a", href="#main") or
                      soup.find("a", href="#content") or
                      soup.find("a", href="#maincontent"))
        if aria_label:
            skip_found = True

    if not skip_found:
        _add_finding(findings, scan_id, "missing_skip_navigation", "info",
                     f"Missing Skip Navigation: {page['url']}",
                     page["url"], page["id"],
                     "No skip-to-content link found on page with navigation",
                     "Add a skip navigation link as the first focusable element that jumps to the main content")


# ---------------------------------------------------------------------------
# Internal helper to append findings
# ---------------------------------------------------------------------------

def _add_finding(findings: list, scan_id: int, check_name: str, severity: str,
                 message: str, page_url: str, page_id: int,
                 evidence: str, recommendation: str):
    findings.append(_finding(scan_id, check_name, severity, message,
                             page_url, page_id, evidence, recommendation))
