"""
crawler.py
----------
Fallback BFS crawler. Only used when sitemap.py returns too few URLs
(missing, blocked, or incomplete sitemap). Crawls internal links up to
MAX_PAGES, collecting every internal URL it finds.
"""

import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse
from collections import deque

HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; ProgramURLBot/1.0)"
}

TIMEOUT = 10


def normalize(url):
    """Strip fragments/query params so we don't revisit the same page twice."""
    parsed = urlparse(url)
    return f"{parsed.scheme}://{parsed.netloc}{parsed.path}".rstrip("/")


def crawl(start_url, max_pages=500):
    """
    BFS crawl of a site, staying within the same domain.
    Returns a deduplicated list of every internal URL discovered
    (from <a href> tags AND nav/footer menus, since programs are often
    buried in mega-menus rather than in-page links).
    """
    domain = urlparse(start_url).netloc

    visited = set()
    discovered = set()
    queue = deque([start_url])

    while queue and len(visited) < max_pages:
        url = queue.popleft()
        norm = normalize(url)

        if norm in visited:
            continue
        visited.add(norm)

        try:
            resp = requests.get(url, headers=HEADERS, timeout=TIMEOUT)
            content_type = resp.headers.get("Content-Type", "")
            if "text/html" not in content_type:
                continue
            soup = BeautifulSoup(resp.text, "html.parser")
        except requests.RequestException:
            continue

        # Grab every link on the page - includes nav bars, footers, mega-menus
        for a in soup.find_all("a", href=True):
            link = urljoin(url, a["href"])
            parsed = urlparse(link)

            if parsed.netloc != domain:
                continue  # stay on the same site

            clean_link = normalize(link)
            discovered.add(clean_link)

            if clean_link not in visited:
                queue.append(clean_link)

    return sorted(discovered)