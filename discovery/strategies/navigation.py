from urllib.parse import urljoin, urlparse

from bs4 import BeautifulSoup

from discovery.context import DiscoveryContext
from discovery.models import CandidateURL
from discovery.strategies.base import DiscoveryStrategy


class NavigationStrategy(DiscoveryStrategy):
    """
    Discover high-value pages by analysing the site's primary navigation.

    Instead of crawling the whole website, this strategy only inspects
    the homepage navigation and footer for likely entry points such as
    Academics, Study, Programs, Admissions, Schools, etc.
    """

    NAVIGATION_KEYWORDS = [
        "study",
        "studies",
        "academics",
        "academic",
        "program",
        "programs",
        "degree",
        "degrees",
        "course",
        "courses",
        "admission",
        "admissions",
        "education",
        "schools",
        "faculties",
        "faculty",
        "departments",
        "department",
        "graduate",
        "undergraduate",
        "research",
    ]

    def discover(
        self,
        context: DiscoveryContext,
    ) -> list[CandidateURL]:

        soup = self._download(context)

        if soup is None:
            return []

        discovered = []
        seen = set()

        selectors = [
            "nav",
            "header",
            "footer",
        ]

        for selector in selectors:

            for section in soup.select(selector):

                for a in section.find_all("a", href=True):

                    href = a["href"].strip()

                    if not href:
                        continue

                    text = a.get_text(" ", strip=True).lower()

                    url = urljoin(
                        context.base_url,
                        href,
                    )

                    url = self._normalize(url)

                    if url in seen:
                        continue

                    if not self._is_relevant(
                        text,
                        url,
                    ):
                        continue

                    seen.add(url)

                    context.discovered_urls.add(url)

                    discovered.append(
                        CandidateURL(
                            url=url,
                            source="navigation",
                            metadata={
                                "anchor_text": text,
                            },
                        )
                    )

        return discovered

    def _download(
        self,
        context: DiscoveryContext,
    ):

        try:

            response = context.session.get(
                context.base_url,
                timeout=15,
                headers={
                    "User-Agent":
                    "Mozilla/5.0 (DiscoveryEngine)"
                },
            )

            if response.status_code != 200:
                return None

            return BeautifulSoup(
                response.text,
                "html.parser",
            )

        except Exception:
            return None

    def _is_relevant(
        self,
        text: str,
        url: str,
    ) -> bool:

        value = (
            text
            + " "
            + urlparse(url).path.lower()
        )

        return any(
            keyword in value
            for keyword in self.NAVIGATION_KEYWORDS
        )

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