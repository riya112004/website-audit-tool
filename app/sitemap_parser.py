import httpx
from bs4 import BeautifulSoup


def fetch_sitemap(origin: str) -> list[str]:
    """Fetch sitemap.xml and extract all URLs. Returns empty list on failure."""
    urls = []

    # Try common sitemap locations
    for path in ["/sitemap.xml", "/sitemap_index.xml", "/sitemap-index.xml"]:
        try:
            resp = httpx.get(f"{origin}{path}", follow_redirects=True, timeout=10)
            if resp.status_code == 200:
                urls.extend(_parse_sitemap_xml(resp.text, origin))
                if urls:
                    return urls[:500]  # cap at 500 URLs
        except Exception:
            continue

    return urls


def _parse_sitemap_xml(xml_text: str, origin: str) -> list[str]:
    """Parse sitemap XML — handles both regular sitemaps and sitemap indexes."""
    urls = []
    soup = BeautifulSoup(xml_text, "xml")

    # Regular sitemap: <urlset> → <url> → <loc>
    for loc in soup.find_all("loc"):
        url = loc.get_text(strip=True)
        if url:
            urls.append(url)

    # Sitemap index: <sitemapindex> → <sitemap> → <loc> (nested sitemaps)
    if not urls:
        for sitemap in soup.find_all("sitemap"):
            loc = sitemap.find("loc")
            if loc:
                nested_url = loc.get_text(strip=True)
                try:
                    resp = httpx.get(nested_url, follow_redirects=True, timeout=10)
                    if resp.status_code == 200:
                        urls.extend(_parse_sitemap_xml(resp.text, origin))
                except Exception:
                    continue

    return urls
