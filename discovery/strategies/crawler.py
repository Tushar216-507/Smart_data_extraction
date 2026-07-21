from collections import deque
from urllib.parse import urljoin, urlparse

from bs4 import BeautifulSoup

from discovery.context import DiscoveryContext
from discovery.models import CandidateURL
from discovery.strategies.base import DiscoveryStrategy


class CrawlerStrategy(DiscoveryStrategy):
    """
    Generic BFS crawler.

    Used as the fallback strategy when sitemap/navigation/catalog
    discovery cannot find enough pages.
    """

    def __init__(self, max_pages: int = 500):
        self.max_pages = max_pages

    def discover(
        self,
        context: DiscoveryContext,
    ) -> list[CandidateURL]:

        domain = urlparse(context.base_url).netloc

        queue = deque([context.base_url])

        candidates = []

        while queue and len(context.visited_urls) < self.max_pages:

            url = queue.popleft()

            url = self._normalize(url)

            if url in context.visited_urls:
                continue

            context.visited_urls.add(url)

            soup = self._download(
                context,
                url,
            )

            if soup is None:
                continue

            for a in soup.find_all("a", href=True):

                link = urljoin(
                    url,
                    a["href"],
                )

                link = self._normalize(link)

                parsed = urlparse(link)

                if parsed.netloc != domain:
                    continue

                if link not in context.discovered_urls:

                    context.discovered_urls.add(link)

                    candidates.append(
                        CandidateURL(
                            url=link,
                            source="crawler",
                        )
                    )

                if link not in context.visited_urls:
                    queue.append(link)

        return candidates

    def _download(
        self,
        context: DiscoveryContext,
        url: str,
    ):

        try:

            response = context.session.get(
                url,
                timeout=15,
                headers={
                    "User-Agent":
                    "Mozilla/5.0 (DiscoveryEngine)"
                },
            )

            if response.status_code != 200:
                return None

            if "text/html" not in response.headers.get(
                "Content-Type",
                "",
            ):
                return None

            return BeautifulSoup(
                response.text,
                "html.parser",
            )

        except Exception:
            return None

    def _normalize(
        self,
        url: str,
    ) -> str:

        parsed = urlparse(url)

        return (
            f"{parsed.scheme}://"
            f"{parsed.netloc}"
            f"{parsed.path}"
        ).rstrip("/")