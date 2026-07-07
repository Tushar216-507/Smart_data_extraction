"""
sitemap.py
----------
Fetches and parses sitemap.xml files (including sitemap indexes and .gz sitemaps).
Goal: pull as many URLs as possible with zero crawling, since most universities
already list every program page in their sitemap.
"""

import gzip
import io
import requests
from urllib.parse import urljoin
from xml.etree import ElementTree as ET

HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; ProgramURLBot/1.0)"
}

TIMEOUT = 15

# Common locations to check if /sitemap.xml doesn't exist
COMMON_SITEMAP_PATHS = [
    "/sitemap.xml",
    "/sitemap_index.xml",
    "/sitemap-index.xml",
    "/sitemap/sitemap.xml",
]


def fetch_raw(url):
    """Download a URL's raw bytes, handling gzip if needed. Returns None on failure."""
    try:
        resp = requests.get(url, headers=HEADERS, timeout=TIMEOUT)
        if resp.status_code != 200:
            return None

        content = resp.content

        # Handle gzipped sitemaps (.xml.gz) - either by extension or magic bytes
        if url.endswith(".gz") or content[:2] == b"\x1f\x8b":
            try:
                content = gzip.decompress(content)
            except OSError:
                pass  # not actually gzipped, use as-is

        return content
    except requests.RequestException:
        return None


def parse_sitemap_xml(xml_bytes):
    """
    Parses sitemap XML content.
    Returns a tuple: (list_of_page_urls, list_of_child_sitemap_urls)
    A sitemap is either a <urlset> (contains pages) or a <sitemapindex> (contains other sitemaps).
    """
    page_urls = []
    child_sitemaps = []

    try:
        root = ET.fromstring(xml_bytes)
    except ET.ParseError:
        return page_urls, child_sitemaps

    # Namespace-agnostic tag matching (sitemaps use xmlns which varies)
    tag = root.tag.lower()

    for elem in root:
        elem_tag = elem.tag.lower()

        if elem_tag.endswith("sitemap"):
            # This is a <sitemap> entry inside a <sitemapindex>
            loc = elem.find("{*}loc")
            if loc is not None and loc.text:
                child_sitemaps.append(loc.text.strip())

        elif elem_tag.endswith("url"):
            # This is a <url> entry inside a <urlset>
            loc = elem.find("{*}loc")
            if loc is not None and loc.text:
                page_urls.append(loc.text.strip())

    return page_urls, child_sitemaps


def get_all_sitemap_urls(base_url, max_sitemaps=200):
    """
    Discovers and recursively parses all sitemaps for a domain.
    Returns a deduplicated list of every page URL found across all sitemaps.
    """
    all_page_urls = set()
    visited_sitemaps = set()
    queue = []

    # Step 1: try robots.txt for a Sitemap: directive (often points to the real one)
    robots_url = urljoin(base_url, "/robots.txt")
    robots_content = fetch_raw(robots_url)
    if robots_content:
        try:
            text = robots_content.decode("utf-8", errors="ignore")
            for line in text.splitlines():
                if line.lower().startswith("sitemap:"):
                    sitemap_url = line.split(":", 1)[1].strip()
                    queue.append(sitemap_url)
        except Exception:
            pass

    # Step 2: also try common sitemap paths directly (some sites don't list them in robots.txt)
    for path in COMMON_SITEMAP_PATHS:
        queue.append(urljoin(base_url, path))

    # Step 3: BFS through sitemap index tree
    while queue and len(visited_sitemaps) < max_sitemaps:
        sitemap_url = queue.pop(0)

        if sitemap_url in visited_sitemaps:
            continue
        visited_sitemaps.add(sitemap_url)

        raw = fetch_raw(sitemap_url)
        if raw is None:
            continue

        pages, children = parse_sitemap_xml(raw)
        all_page_urls.update(pages)

        for child in children:
            if child not in visited_sitemaps:
                queue.append(child)

    return sorted(all_page_urls)