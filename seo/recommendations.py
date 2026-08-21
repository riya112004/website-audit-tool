RECOMMENDATIONS = {
    "missing_title": (
        "Add exactly one <title> per page describing the page's main topic — "
        "search engines use it as a strong relevance signal. Keep it 30-60 characters."
    ),
    "short_title": (
        "Title is under 30 characters. Expand it to 30-60 characters with "
        "relevant keywords to improve click-through from search results."
    ),
    "long_title": (
        "Title exceeds 60 characters and will be truncated in search results. "
        "Shorten it to under 60 characters while keeping the primary keyword near the start."
    ),
    "duplicate_title": (
        "Multiple pages share the same <title>. Each page needs a unique title "
        "that accurately describes its specific content to avoid keyword cannibalization."
    ),
    "missing_meta_description": (
        "Add a meta description between 70-160 characters. This is the snippet text "
        "shown in search results — a compelling description improves click-through rate."
    ),
    "short_meta_description": (
        "Meta description is under 70 characters. Expand to 70-160 characters to "
        "maximize the SERP snippet and include relevant keywords naturally."
    ),
    "long_meta_description": (
        "Meta description exceeds 160 characters and will be truncated. Shorten to "
        "under 160 characters, placing the most important information first."
    ),
    "duplicate_meta_description": (
        "Multiple pages share the same meta description. Write unique descriptions "
        "for each page that reflect its distinct content and target keywords."
    ),
    "missing_h1": (
        "Add exactly one <h1> per page describing the page's main topic — "
        "search engines use it as a strong relevance signal."
    ),
    "multiple_h1s": (
        "Only one <h1> tag should exist per page. Multiple <h1>s dilute the "
        "topic signal. Convert extras to <h2> or <h3>."
    ),
    "heading_order_broken": (
        "Heading levels must be sequential (h1 → h2 → h3). Skipping levels "
        "(e.g. h1 → h3) confuses screen readers and weakens content hierarchy."
    ),
    "images_missing_alt": (
        "Add descriptive alt attributes to all images. Alt text helps search engines "
        "understand image content and is critical for screen reader accessibility."
    ),
    "missing_canonical": (
        "Add a <link rel='canonical'> pointing to the preferred URL. This prevents "
        "duplicate content issues when the same page is accessible via multiple URLs."
    ),
    "no_structured_data": (
        "Add JSON-LD structured data to enable rich snippets in search results "
        "(star ratings, FAQs, product info). Use schema.org vocabulary."
    ),
    "missing_viewport": (
        "Add <meta name='viewport' content='width=device-width, initial-scale=1'> "
        "for mobile-friendliness. Google uses mobile-first indexing."
    ),
    "non_descriptive_link_text": (
        "Replace vague anchor text ('click here', 'read more') with descriptive text "
        "that tells users and search engines what the linked page is about."
    ),
    "missing_robots_txt": (
        "Add a robots.txt file at the site root to guide search engine crawlers. "
        "Block non-essential paths and point to your sitemap."
    ),
    "missing_sitemap_xml": (
        "Add an XML sitemap listing all important pages. Submit it to Google Search "
        "Console to ensure complete and timely indexing."
    ),
    "broken_internal_link": (
        "Fix or remove pages returning HTTP 4xx/5xx errors. Broken pages waste "
        "crawl budget, create dead ends for users, and hurt ranking."
    ),
    "not_https": (
        "Migrate all pages to HTTPS. HTTPS is a confirmed Google ranking signal "
        "and required for browser security indicators and modern web features."
    ),
    "crawl_access_blocked": (
        "The crawler received HTTP 403/401 and could not retrieve the page's HTML. "
        "SEO element checks were skipped. Verify the page manually or adjust server "
        "access rules to allow crawling."
    ),
    "crawl_failed": (
        "The crawler could not reach this page at all. Check if the URL is correct "
        "and the server is responding."
    ),
    "page_not_found": (
        "The page returned HTTP 404. Remove internal links pointing to this URL "
        "or fix the destination."
    ),
    "server_error": (
        "The page returned a 5xx server error. Investigate server logs and fix "
        "the underlying issue."
    ),
    "access_blocked_robots_txt": (
        "robots.txt exists but the crawler is blocked from accessing it (HTTP 403). "
        "Verify the file manually — the site may intentionally block non-search crawlers."
    ),
    "access_blocked_sitemap_xml": (
        "sitemap.xml exists but the crawler is blocked from accessing it (HTTP 403). "
        "Verify the file manually — the site may intentionally block non-search crawlers."
    ),
    "server_error_robots_txt": (
        "robots.txt returned a server error. Check server configuration."
    ),
    "server_error_sitemap_xml": (
        "sitemap.xml returned a server error. Check server configuration."
    ),
}
