from urllib.parse import urlencode, urlparse

from bs4 import BeautifulSoup

from discovery.context import DiscoveryContext
from discovery.models import CandidateURL
from discovery.strategies.base import DiscoveryStrategy


class SearchStrategy(DiscoveryStrategy):
    """
    Attempts to discover additional catalog/program pages
    using common university search endpoints.
    """

    SEARCH_TERMS = [
        "program",
        "programme",
        "degree",
        "course",
        "bachelor",
        "master",
        "graduate",
        "undergraduate",
        "study",
        "study programs",
        "degree programs",
    ]

    SEARCH_PATHS = [
        "/search",
        "/search/",
        "/find",
        "/finder",
        "/program-search",
        "/programme-search",
    ]

    def discover(
        self,
        context: DiscoveryContext,
    ) -> list[CandidateURL]:

        discovered = []
        seen = set()

        for path in self.SEARCH_PATHS:

            for term in self.SEARCH_TERMS:

                url = (
                    context.base_url.rstrip("/")
                    + path
                    + "?"
                    + urlencode({"q": term})
                )

                soup = self._download(
                    context,
                    url,
                )

                if soup is None:
                    continue

                for a in soup.find_all("a", href=True):

                    href = a.get("href")

                    if not href:
                        continue

                    if href.startswith("/"):
                        href = (
                            context.base_url.rstrip("/")
                            + href
                        )

                    href = self._normalize(href)

                    if href in seen:
                        continue

                    seen.add(href)

                    discovered.append(
                        CandidateURL(
                            url=href,
                            source="search",
                            metadata={
                                "query": term,
                            },
                        )
                    )

        return discovered

    def _download(
        self,
        context,
        url,
    ):

        try:

            response = context.session.get(
                url,
                timeout=15,
                headers={
                    "User-Agent": "Mozilla/5.0 (DiscoveryEngine)"
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

    def _normalize(
        self,
        url,
    ):

        parsed = urlparse(url)

        return (
            f"{parsed.scheme}://"
            f"{parsed.netloc}"
            f"{parsed.path}"
        ).rstrip("/")