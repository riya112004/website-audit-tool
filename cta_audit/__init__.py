"""
CTA / Conversion Audit — detect, analyse and score Call-to-Action elements.

8 categories:
  1. CTA Presence       — 15%
  2. CTA Clarity        — 15%
  3. Visibility          — 15%
  4. Placement           — 15%
  5. Usability           — 15%
  6. Conversion Path     — 15%
  7. Consistency         — 5%
  8. CTA Density         — 5%
"""

from __future__ import annotations

import re
from urllib.parse import urljoin, urlparse
from bs4 import BeautifulSoup, Tag

# ── CTA keyword lists ──────────────────────────────────────────────────────

PRIMARY_CTA_KEYWORDS = [
    "buy", "purchase", "book", "order", "checkout", "add to cart", "get started",
    "sign up", "signup", "register", "subscribe", "contact", "call", "apply",
    "demo", "trial", "free trial", "download", "install", "hire", "quote",
    "get quote", "request quote", "join", "enroll", "donate", "contribute",
    "submit", "send", "request", "schedule", "reserve", "claim", "redeem",
    "start", "begin", "open", "upgrade", "renew", "pay", "checkout now",
]

SECONDARY_CTA_KEYWORDS = [
    "learn more", "view more", "see more", "read more", "explore", "discover",
    "details", "more details", "view details", "find out", "find out more",
    "how it works", "see how", "watch demo", "watch video", "tour", "take a tour",
    "compare", "pricing", "features", "see plans", "view plans",
]

GENERIC_CTA_TEXTS = [
    "click here", "click", "here", "more", "link", "submit", "ok", "yes",
    "continue", "next", "back", "close", "done", "save", "cancel",
]

# Hero section selectors
HERO_SELECTORS = [
    ".hero", "#hero", ".banner", "#banner", ".jumbotron", ".header-cta",
    "[class*='hero']", "[class*='banner']",
    "section:first-of-type", "header:first-of-type",
]

# ── Utility helpers ─────────────────────────────────────────────────────────

def _soup(html: str) -> BeautifulSoup:
    return BeautifulSoup(html or "", "html.parser")


def _text(el: Tag) -> str:
    return (el.get_text(strip=True) or "").lower()


def _href(el: Tag) -> str:
    return (el.get("href") or "").strip()


def _is_cta_element(el: Tag) -> bool:
    """Only count prominent action elements, not generic nav/footer links."""
    if el.name == "button":
        return True
    if el.name == "input" and (el.get("type", "").lower() in {"submit", "button"}):
        return True
    if el.name != "a":
        return False

    text = _text(el)
    if not text:
        return False

    # Exclude structural navigation/footer links first.
    if _is_structural_link(el):
        return False

    classes = " ".join(el.get("class", []))
    role = (el.get("role") or "").lower()
    if role == "button" or re.search(r"\b(btn|button|cta|primary|hero|outline)\b", classes, re.I):
        return True

    text_norm = re.sub(r"[^a-z0-9\s-]", " ", text.lower())
    if len(text_norm.split()) > 6:
        return False

    for kw in PRIMARY_CTA_KEYWORDS + SECONDARY_CTA_KEYWORDS:
        if kw in text_norm:
            return True

    return False


def _is_structural_link(el: Tag) -> bool:
    """Exclude ordinary navigation/header/footer links from conversion analysis."""
    if el.name != "a":
        return False

    parent = el.parent
    while parent and getattr(parent, "name", None) not in ("body", "html"):
        name = (getattr(parent, "name", "") or "").lower()
        classes = " ".join(parent.get("class", []) if isinstance(parent, Tag) else [])
        pid = (parent.get("id") or "").lower()
        combined = f"{name} {classes} {pid}".lower()
        if name in {"nav", "footer", "header", "aside", "ul", "ol", "menu"} or re.search(r"nav|navbar|navigation|menu|footer|sidebar|header", combined):
            return True
        parent = parent.parent

    return False


def _classify_cta(el: Tag) -> str:
    """Classify CTA as primary, secondary, or generic."""
    text = _text(el)
    cls = " ".join(el.get("class", []))

    # Check generic first
    for g in GENERIC_CTA_TEXTS:
        if text == g or text.strip() == g:
            return "generic"

    # Check primary by text
    for kw in PRIMARY_CTA_KEYWORDS:
        if kw in text:
            return "primary"

    # Check primary by styling (btn-primary, cta-primary, etc.)
    if re.search(r"btn-primary|cta-primary|primary|hero.*btn", cls, re.I):
        return "primary"

    # Check secondary
    for kw in SECONDARY_CTA_KEYWORDS:
        if kw in text:
            return "secondary"

    # Default: if it's a button/link with action-like styling
    if re.search(r"btn|cta|button", cls, re.I):
        return "primary"  # styled buttons are usually primary

    return "secondary"


def _find_section(el: Tag) -> str:
    """Determine which section of the page an element belongs to."""
    # Walk up parents to find section context
    parent = el.parent
    while parent and parent.name != "body" and parent.name != "html":
        cls = " ".join(parent.get("class", []) if isinstance(parent, Tag) else [])
        pid = parent.get("id", "")
        tag = parent.name

        combined = f"{cls} {pid} {tag}".lower()

        if re.search(r"hero|banner|jumbotron|header-cta", combined):
            return "hero"
        if re.search(r"\bnav\b|navbar|menu|navigation", combined):
            return "navbar"
        if re.search(r"\bfooter\b|site-footer|page-footer", combined):
            return "footer"
        if re.search(r"\bform\b|search-form|contact-form", combined):
            return "form"
        if re.search(r"\bcard\b|product-card|pricing-card|feature-card", combined):
            return "card"
        if re.search(r"\bmodal\b|popup|dialog", combined):
            return "modal"
        if re.search(r"\bsidebar\b|aside", combined):
            return "sidebar"
        if re.search(r"callout|highlight|promo", combined):
            return "callout"
        parent = parent.parent

    # Check if inside first 30% of page (above-fold heuristic)
    # We can't compute exact position without rendering, but we check depth
    depth = 0
    p = el.parent
    while p and p.name not in ("body", "html", None):
        depth += 1
        p = p.parent
    if depth <= 3:
        return "above-fold"

    return "body"


def _is_visible(el: Tag) -> bool:
    """Check CSS-level visibility (crude but useful)."""
    style = (el.get("style") or "").lower()
    if "display:none" in style.replace(" ", "") or "display: none" in style:
        return False
    if "visibility:hidden" in style.replace(" ", "") or "visibility: hidden" in style:
        return False
    if "opacity:0" in style.replace(" ", "") or "opacity: 0" in style:
        return False
    return True


def _is_above_fold(el: Tag, soup: BeautifulSoup) -> bool:
    """Heuristic: inside hero, header, or first main section."""
    section = _find_section(el)
    if section in ("hero", "navbar", "above-fold"):
        return True
    # Check if parent is first <section> or <header>
    parent = el.parent
    while parent and parent.name not in ("body", "html", None):
        if parent.name == "header":
            return True
        if parent.name == "section":
            # Check if it's the first section
            prev = parent.find_previous_sibling("section")
            if prev is None:
                return True
            break
        parent = parent.parent
    return False


def _get_cta_style(el: Tag) -> dict:
    """Extract inline style properties relevant to CTA."""
    style = el.get("style", "")
    result = {}
    for prop in ["width", "height", "min-width", "min-height", "padding", "font-size", "background", "background-color", "color", "border", "border-radius", "display", "visibility", "opacity"]:
        m = re.search(rf"{prop}\s*:\s*([^;]+)", style, re.I)
        if m:
            result[prop] = m.group(1).strip()
    return result


# ── Per-page CTA detection ──────────────────────────────────────────────────

def _detect_ctas_on_page(soup: BeautifulSoup, page_url: str = "") -> list[dict]:
    """Detect all CTA elements on a single page.

    Returns list of:
    {
        "element": Tag,
        "text": str,
        "type": "primary" | "secondary" | "generic",
        "section": str,
        "href": str,
        "is_visible": bool,
        "is_button": bool,
        "has_aria": bool,
        "style": dict,
    }
    """
    ctas = []

    # Find all candidate elements
    candidates = []
    for btn in soup.find_all("button"):
        candidates.append(btn)
    for a in soup.find_all("a", href=True):
        if _is_cta_element(a) and not _is_structural_link(a):
            candidates.append(a)

    # Also find <input type="submit"> and <input type="button">
    for inp in soup.find_all("input", attrs={"type": re.compile(r"submit|button", re.I)}):
        candidates.append(inp)

    seen_texts = set()
    for el in candidates:
        text = _text(el) if el.name != "input" else (el.get("value", "").strip().lower())
        if not text and el.name == "a":
            # Check for img with alt text
            img = el.find("img")
            if img:
                text = (img.get("alt") or "").lower()
        if not text:
            continue

        # Calendar controls are navigation, not conversion opportunities.
        if text in {"jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"}:
            continue

        # Deduplicate same text on same page
        key = text[:50]
        if key in seen_texts:
            continue
        seen_texts.add(key)

        href = ""
        if el.name == "a":
            href = _href(el)
        elif el.name == "input":
            # Submit inputs inside forms
            form = el.find_parent("form")
            if form:
                href = form.get("action", "")

        ctas.append({
            "element": el,
            "text": text,
            "type": _classify_cta(el),
            "section": _find_section(el),
            "href": href,
            "is_visible": _is_visible(el),
            "is_button": el.name in ("button", "input"),
            "has_aria": bool(el.get("aria-label") or el.get("aria-labelledby")),
            "style": _get_cta_style(el),
            "above_fold": _is_above_fold(el, soup),
        })

    return ctas


# ── Analysis functions ──────────────────────────────────────────────────────

def _analyse_presence(page_ctas: list[dict]) -> dict:
    """Check 1: CTA Presence (15%)"""
    findings = []

    total = len(page_ctas)
    primaries = [c for c in page_ctas if c["type"] == "primary"]
    secondaries = [c for c in page_ctas if c["type"] == "secondary"]

    if total == 0:
        findings.append({
            "check": "cta_presence",
            "severity": "critical",
            "message": "No CTA elements detected on page",
            "recommendation": "Add at least one clear call-to-action (e.g., Get Started, Contact Us)",
        })
    elif len(primaries) == 0:
        findings.append({
            "check": "cta_presence",
            "severity": "warning",
            "message": f"Found {total} CTAs but no primary CTA",
            "recommendation": "Add a primary CTA with clear action text (e.g., Sign Up, Buy Now)",
        })
    elif len(primaries) > 5:
        findings.append({
            "check": "cta_presence",
            "severity": "warning",
            "message": f"Found {len(primaries)} primary CTAs — may cause decision fatigue",
            "recommendation": "Limit to 1-2 primary CTAs per page for clarity",
        })
    else:
        findings.append({
            "check": "cta_presence",
            "severity": "good",
            "message": f"Found {len(primaries)} primary, {len(secondaries)} secondary CTAs",
            "recommendation": "",
        })

    return {"total": total, "primary": len(primaries), "secondary": len(secondaries), "findings": findings}


def _analyse_clarity(page_ctas: list[dict]) -> dict:
    """Check 2: CTA Text Clarity (15%)"""
    findings = []

    generic = [c for c in page_ctas if c["type"] == "generic"]
    too_long = [c for c in page_ctas if len(c["text"]) > 40]

    for c in generic:
        findings.append({
            "check": "cta_clarity",
            "severity": "warning",
            "message": f'Generic CTA text: "{c["text"][:50]}" in {c["section"]}',
            "recommendation": "Replace with action-oriented text (e.g., Get Started, Book a Demo)",
        })

    for c in too_long:
        findings.append({
            "check": "cta_clarity",
            "severity": "warning",
            "message": f'CTA text too long ({len(c["text"])} chars): "{c["text"][:50]}..."',
            "recommendation": "Keep CTA text under 5 words / 30 characters",
        })

    clear = [c for c in page_ctas if c["type"] in ("primary", "secondary") and c["type"] != "generic" and len(c["text"]) <= 40]
    if not generic and clear:
        findings.append({
            "check": "cta_clarity",
            "severity": "good",
            "message": f"All {len(clear)} CTAs have clear, action-oriented text",
            "recommendation": "",
        })

    return {"generic_count": len(generic), "too_long_count": len(too_long), "findings": findings}


def _analyse_visibility(page_ctas: list[dict]) -> dict:
    """Check 3: CTA Visibility (15%)"""
    findings = []

    hidden = [c for c in page_ctas if not c["is_visible"]]
    no_aria = [c for c in page_ctas if c["is_button"] and not c["has_aria"]]

    for c in hidden:
        findings.append({
            "check": "cta_visibility",
            "severity": "high",
            "message": f'CTA is hidden via CSS: "{c["text"][:40]}" ({c["section"]})',
            "recommendation": "Remove display:none/visibility:hidden from CTA elements",
        })

    # Check for very small CTAs (heuristic: font-size < 10px from inline style)
    for c in page_ctas:
        fs = c["style"].get("font-size", "")
        if fs:
            try:
                px = float(re.search(r"(\d+)", fs).group(1))
                if px < 10:
                    findings.append({
                        "check": "cta_visibility",
                        "severity": "high",
                        "message": f'CTA text very small ({px}px): "{c["text"][:40]}"',
                        "recommendation": "Increase font-size to at least 14px for readability",
                    })
            except (AttributeError, ValueError):
                pass

    visible_primary = [c for c in page_ctas if c["type"] == "primary" and c["is_visible"]]
    above_fold_primary = [c for c in visible_primary if c.get("above_fold")]

    if not visible_primary:
        findings.append({
            "check": "cta_visibility",
            "severity": "high",
            "message": "No visible primary CTA on page",
            "recommendation": "Ensure primary CTA is visible and not hidden",
        })
    elif not above_fold_primary:
        findings.append({
            "check": "cta_visibility",
            "severity": "warning",
            "message": "No primary CTA above the fold",
            "recommendation": "Place a primary CTA in the hero or header section",
        })

    return {"hidden": len(hidden), "findings": findings}


def _analyse_placement(page_ctas: list[dict]) -> dict:
    """Check 4: CTA Placement (15%)"""
    findings = []

    sections_with_ctas = set(c["section"] for c in page_ctas)
    has_hero = "hero" in sections_with_ctas or "above-fold" in sections_with_ctas
    has_footer = "footer" in sections_with_ctas
    has_nav = "navbar" in sections_with_ctas

    primary_sections = set(c["section"] for c in page_ctas if c["type"] == "primary")

    if not has_hero and not has_nav:
        findings.append({
            "check": "cta_placement",
            "severity": "warning",
            "message": "No CTA in hero/header area — users may not see conversion prompt early",
            "recommendation": "Add a primary CTA in the hero section or navigation bar",
        })

    if not has_footer:
        findings.append({
            "check": "cta_placement",
            "severity": "info",
            "message": "No CTA in footer — footer is a common secondary conversion point",
            "recommendation": "Consider adding a CTA (Contact, Sign Up) in the footer",
        })

    if primary_sections:
        findings.append({
            "check": "cta_placement",
            "severity": "good",
            "message": f"Primary CTA found in: {', '.join(sorted(primary_sections))}",
            "recommendation": "",
        })

    return {"sections": list(sections_with_ctas), "findings": findings}


def _analyse_usability(page_ctas: list[dict]) -> dict:
    """Check 5: CTA Usability (15%)"""
    findings = []

    for c in page_ctas:
        # Broken link check
        if c["is_button"] and not c["is_visible"]:
            continue
        if c["href"]:
            href = c["href"]
            if href.startswith("#") or href.startswith("javascript:"):
                if href == "#" or href == "#0":
                    findings.append({
                        "check": "cta_usability",
                        "severity": "warning",
                        "message": f'CTA has empty anchor: "{c["text"][:40]}" → {href}',
                        "recommendation": "Replace placeholder href with actual destination",
                    })
            elif href.startswith("mailto:") or href.startswith("tel:"):
                pass  # valid
            elif not href.startswith(("http://", "https://", "/")):
                findings.append({
                    "check": "cta_usability",
                    "severity": "warning",
                    "message": f'CTA has unusual href: "{c["text"][:40]}" → {href[:50]}',
                    "recommendation": "Ensure href is a valid URL or path",
                })

        # Button without accessible name
        if c["is_button"] and not c["has_aria"] and not c["text"]:
            findings.append({
                "check": "cta_usability",
                "severity": "high",
                "message": f"Button has no accessible name (no text, no aria-label)",
                "recommendation": "Add aria-label or visible text to button",
            })

    return {"findings": findings}


def _analyse_conversion_path(page_ctas: list[dict], page_url: str) -> dict:
    """Check 6: Conversion Path (15%)"""
    findings = []

    primary_ctas = [c for c in page_ctas if c["type"] == "primary"]

    for c in primary_ctas:
        href = c["href"]
        if not href:
            findings.append({
                "check": "conversion_path",
                "severity": "high",
                "message": f'Primary CTA "{c["text"][:40]}" has no destination (href empty)',
                "recommendation": "Link primary CTA to a conversion page (contact, signup, etc.)",
            })
            continue

        if href.startswith("#") or href.startswith("javascript:"):
            findings.append({
                "check": "conversion_path",
                "severity": "warning",
                "message": f'Primary CTA "{c["text"][:40]}" → {href[:50]} (not a real page)',
                "recommendation": "Point CTA to an actual conversion page",
            })
            continue

        # Check if href looks like a real page
        parsed = urlparse(href)
        if parsed.scheme and parsed.netloc:
            # External link — check if it's same domain or known
            page_domain = urlparse(page_url).netloc
            if parsed.netloc != page_domain:
                findings.append({
                    "check": "conversion_path",
                    "severity": "info",
                    "message": f'Primary CTA "{c["text"][:40]}" links to external: {parsed.netloc}',
                    "recommendation": "Verify external CTA destination is trustworthy",
                })

    if primary_ctas and not any(f["severity"] in ("high", "critical") for f in findings if f["check"] == "conversion_path"):
        findings.append({
            "check": "conversion_path",
            "severity": "good",
            "message": f"All {len(primary_ctas)} primary CTAs have valid destinations",
            "recommendation": "",
        })

    return {"findings": findings}


def _analyse_consistency(all_page_ctas: list[list[dict]]) -> dict:
    """Check 7: CTA Consistency (5%) — cross-page analysis."""
    findings = []

    if len(all_page_ctas) < 2:
        return {"findings": []}

    # Collect all primary CTA texts across pages
    all_primary_texts = []
    for page_ctas in all_page_ctas:
        for c in page_ctas:
            if c["type"] == "primary":
                all_primary_texts.append(c["text"][:50])

    if not all_primary_texts:
        return {"findings": []}

    # Check for inconsistency: many different primary CTA labels
    unique_texts = set(all_primary_texts)
    if len(unique_texts) > 4:
        findings.append({
            "check": "cta_consistency",
            "severity": "warning",
            "message": f"Found {len(unique_texts)} different primary CTA labels across pages: {', '.join(list(unique_texts)[:5])}...",
            "recommendation": "Standardize primary CTA wording across the site for consistency",
        })

    # Check style consistency
    all_styles = []
    for page_ctas in all_page_ctas:
        for c in page_ctas:
            if c["type"] == "primary" and c["style"]:
                all_styles.append(c["style"])

    return {"unique_primary_labels": len(unique_texts), "findings": findings}


def _analyse_density(page_ctas: list[dict], html_length: int) -> dict:
    """Check 8: CTA Density (5%)"""
    findings = []

    total = len(page_ctas)
    if html_length < 100:
        return {"density": 0, "findings": []}

    # Rough content length in words
    content_words = html_length // 5  # rough heuristic
    density = (total / max(content_words, 1)) * 100  # CTAs per 100 words

    if total == 0:
        findings.append({
            "check": "cta_density",
            "severity": "info",
            "message": "No CTAs on page — possible missed conversion opportunity",
            "recommendation": "Consider adding at least one CTA",
        })
    elif density > 5:
        findings.append({
            "check": "cta_density",
            "severity": "warning",
            "message": f"High CTA density: {total} CTAs in ~{content_words} words ({density:.1f}%)",
            "recommendation": "Reduce CTA count to avoid overwhelming visitors",
        })
    elif density < 0.2 and total > 0:
        findings.append({
            "check": "cta_density",
            "severity": "info",
            "message": f"Low CTA density: {total} CTA in ~{content_words} words ({density:.1f}%)",
            "recommendation": "Consider adding more conversion opportunities",
        })

    return {"density": round(density, 2), "cta_count": total, "findings": findings}


# ── Main entry point ────────────────────────────────────────────────────────

def run_cta_audit(pages: list[dict], page_htmls: dict[int, str]) -> dict:
    """Run CTA / Conversion audit across all crawled pages.

    Returns: {
        "findings": [ { check, severity, message, recommendation } ],
        "page_results": [ { url, ctas_found, ... } ],
        "cross_page": { consistency, density },
    }
    """
    if not pages:
        return {"findings": [], "page_results": [], "cross_page": {}}

    all_findings = []
    page_results = []
    all_page_ctas = []

    for page in pages:
        pid = page["id"]
        url = page.get("url", "")
        html = page_htmls.get(pid, "")
        soup = _soup(html)

        ctas = _detect_ctas_on_page(soup, url)
        all_page_ctas.append(ctas)

        # Run all checks
        presence = _analyse_presence(ctas)
        clarity = _analyse_clarity(ctas)
        visibility = _analyse_visibility(ctas)
        placement = _analyse_placement(ctas)
        usability = _analyse_usability(ctas)
        conv_path = _analyse_conversion_path(ctas, url)
        density = _analyse_density(ctas, len(html))

        page_findings = []
        for result in [presence, clarity, visibility, placement, usability, conv_path, density]:
            page_findings.extend(result.get("findings", []))

        # Tag each finding with page URL
        for f in page_findings:
            f["page_url"] = url

        all_findings.extend(page_findings)

        page_results.append({
            "url": url,
            "ctas_found": len(ctas),
            "primary_count": presence["primary"],
            "secondary_count": presence["secondary"],
            "sections": placement["sections"],
            "density": density.get("density", 0),
        })

        print(f"[CTA] {url[:50]} — {len(ctas)} CTAs ({presence['primary']} primary, {presence['secondary']} secondary)")

    # Cross-page consistency
    consistency = _analyse_consistency(all_page_ctas)
    all_findings.extend(consistency.get("findings", []))

    # Overall summary
    total_primary = sum(p["primary_count"] for p in page_results)
    total_secondary = sum(p["secondary_count"] for p in page_results)
    print(f"[CTA] Total: {len(all_findings)} findings across {len(pages)} pages ({total_primary} primary, {total_secondary} secondary CTAs)")

    return {
        "findings": all_findings,
        "page_results": page_results,
        "cross_page": {
            "consistency": consistency,
            "total_pages": len(pages),
            "total_findings": len(all_findings),
        },
    }
