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
        base_domain = domain[4:] if domain.startswith("www.") else domain

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

                if self._should_skip(link):
                    continue

                anchor_text = a.get_text(" ",strip=True)

                parsed = urlparse(link)

                if not parsed.netloc.endswith(base_domain):
                    continue

                if link not in context.discovered_urls:

                    context.discovered_urls.add(link)

                    if self._looks_like_program_page(link, anchor_text):
                        candidates.append(
                            CandidateURL(
                                url=link,
                                source="crawler",
                            )
                        )

                if link not in context.visited_urls:

                    if self._should_follow_link(link, anchor_text):
                        queue.appendleft(link)
                    else:
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
    
    PROGRAM_PAGE_KEYWORDS = [
        "bachelor",
        "bachelors",
        "undergraduate",
        "master",
        "masters",
        "graduate",
        "phd",
        "doctorate",
        "degree",
        "program",
        "programme",
    ]

    SKIP_KEYWORDS = [
        "news",
        "event",
        "calendar",
        "contact",
        "privacy",
        "terms",
        "login",
        "signin",
        "register",
        "facebook",
        "twitter",
        "linkedin",
        "instagram",
        "youtube",
    ]

    def _should_skip(self, url: str) -> bool:
        path = urlparse(url).path.lower()
        return any(keyword in path for keyword in self.SKIP_KEYWORDS)

    def _looks_like_program_page(self, url: str, text: str = "") -> bool:
        """
        Returns True only for likely individual programme pages,
        not programme hubs.
        """
        path = urlparse(url).path.lower()
        anchor = text.lower().strip()

        # Must contain at least one programme keyword
        if not any(keyword in (path + " " + anchor) for keyword in self.PROGRAM_PAGE_KEYWORDS):
            return False

        # Generic hub pages
        hub_patterns = [
            "/programs",
            "/programmes",
            "/degrees",
            "/courses",
            "/graduate-programs",
            "/undergraduate-programs",
            "/fields-of-study",
            "/academics",
        ]

        if any(path.endswith(pattern) for pattern in hub_patterns):
            return False

        # Individual programme pages usually have deeper URLs
        return len([p for p in path.split("/") if p]) >= 2
    
    def _should_follow_link(self, url: str, text: str = "") -> bool:
        """
        Returns True if the crawler should continue exploring this link.
        """

        content = f"{url} {text}".lower()

        follow_keywords = [
            "academics",
            "academic",
            "study",
            "studies",
            "program",
            "programme",
            "degree",
            "course",
            "graduate",
            "undergraduate",
            "master",
            "bachelor",
            "phd",
            "doctorate",
            "school",
            "faculty",
            "department",
            "college",
            "field",
            "discipline",
        ]

        return any(keyword in content for keyword in follow_keywords)