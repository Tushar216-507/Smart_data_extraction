import concurrent.futures
from urllib.parse import urljoin, urlparse

from bs4 import BeautifulSoup

from discovery.context import DiscoveryContext
from discovery.models import CandidateURL
from discovery.strategies.base import DiscoveryStrategy


class CatalogStrategy(DiscoveryStrategy):
    """
    Discover program catalog pages by inspecting previously
    discovered navigation pages.
    """

    CATALOG_KEYWORDS = [
        "program",
        "programs",
        "degree",
        "degrees",
        "course",
        "courses",
        "catalog",
        "catalogue",
        "bachelor",
        "bachelors",
        "master",
        "masters",
        "undergraduate",
        "postgraduate",
        "graduate",
        "curriculum",
        "major",
        "minor",
    ]

    def discover(
        self,
        context: DiscoveryContext,
    ) -> list[CandidateURL]:

        discovered = []
        seen = set()
        
        def process_candidate(candidate) -> list[CandidateURL]:
            local_discovered = []
            
            SKIP_SECTIONS = (
                "/news",
                "/events",
                "/about",
                "/staff",
                "/admin",
                "/admin-services",
                "/ict",
                "/library",
                "/governance",
                "/benefits",
                "/pay-and-pensions",
                "/contact",
                "/jobs",
                "/careers",
            )

            if any(section in candidate.url.lower() for section in SKIP_SECTIONS):
                return []

            print(f"CatalogStrategy -> {candidate.url}")
            soup = self._download(context, candidate.url)

            if soup is None:
                return []

            for a in soup.find_all("a", href=True):
                href = a["href"].strip()
                if not href:
                    continue
                if href.startswith(("mailto:", "tel:", "javascript:")):
                    continue
                
                anchor_text = a.get_text(" ", strip=True).lower()
                if len(anchor_text) < 3:
                    continue
                
                url = urljoin(candidate.url, href)
                url = self._normalize(url)

                if not self._looks_like_catalog(url, anchor_text):
                    continue

                local_discovered.append(
                    CandidateURL(
                        url=url,
                        source="catalog",
                        metadata={"parent": candidate.url},
                    )
                )
            
            return local_discovered

        # Parallelize the downloads with a max of 10 workers
        with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
            futures = [
                executor.submit(process_candidate, candidate)
                for candidate in context.candidate_urls.values()
            ]
            
            for future in concurrent.futures.as_completed(futures):
                try:
                    results = future.result()
                    for cand in results:
                        if cand.url not in seen:
                            seen.add(cand.url)
                            discovered.append(cand)
                except Exception as e:
                    print(f"CatalogStrategy Error processing candidate: {e}")

        return discovered

    def _download(self, context, url):

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

    def _looks_like_catalog(self, url,anchor_text=""):

        try:
            path = urlparse(url).path.lower()
        except ValueError:
            print(f"\nInvalid URL: {url}\n")
            raise

        value = f"{path} {anchor_text.lower()}"

        return any(
            keyword in value
            for keyword in self.CATALOG_KEYWORDS
        )

    def _normalize(self, url):

        parsed = urlparse(url)

        return (
            f"{parsed.scheme}://"
            f"{parsed.netloc}"
            f"{parsed.path}"
        ).rstrip("/")