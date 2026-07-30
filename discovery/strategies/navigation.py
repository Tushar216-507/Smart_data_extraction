from urllib.parse import urljoin, urlparse

from bs4 import BeautifulSoup

from discovery.context import DiscoveryContext
from discovery.models import CandidateURL
from discovery.strategies.base import DiscoveryStrategy
print(">>> USING NavigationStrategy:", __file__)


class NavigationStrategy(DiscoveryStrategy):
    """
    Discover high-value pages by analysing the site's primary navigation.

    Instead of crawling the whole website, this strategy only inspects
    the homepage navigation and footer for likely entry points such as
    Academics, Study, Programs, Admissions, Schools, etc.
    """

    NAVIGATION_KEYWORDS = [
        # Study
        "study",
        "studies",
        "education",
        "learn",

        # Academics
        "academic",
        "academics",

        # Programmes
        "program",
        "programs",
        "programme",
        "programmes",
        "degree",
        "degrees",
        "course",
        "courses",
        "curriculum",

        # Student journey
        "admission",
        "admissions",
        "apply",
        "application",
        "prospective",
        "future students",

        # Organization
        "school",
        "schools",
        "faculty",
        "faculties",
        "department",
        "departments",
        "college",
        "institute",

        # Levels
        "undergraduate",
        "graduate",
        "postgraduate",
        "master",
        "masters",
        "bachelor",
        "bachelors",
        "phd",
        "doctorate",

        # Common university wording
        "disciplines",
        "fields of study",
        "subject areas",
        "find your programme",
        "find your program",
        "degree finder",
    ]

    def discover(
        self,
        context: DiscoveryContext,
    ) -> list[CandidateURL]:

        soup = self._download(context)

        if soup is None:
            return []

        print("\n===== Navigation Debug =====")
        print("Title:", soup.title)
        print("Total links:", len(soup.find_all("a")))
        print("Total href links:", len(soup.find_all("a", href=True)))
        print("Total nav tags:", len(soup.find_all("nav")))
        print("Total header tags:", len(soup.find_all("header")))
        print("Total footer tags:", len(soup.find_all("footer")))
        print("============================\n")
        discovered = []
        seen = set()

        selectors = [
            # Traditional navigation
            "nav",
            "header",
            "footer",

            # Modern university layouts
            "main",
            "section",
            "aside",

            # Common navigation/menu containers
            '[role="navigation"]',
            '[class*="nav"]',
            '[class*="menu"]',
            '[class*="mega"]',
            '[class*="study"]',
            '[class*="academ"]',
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
                    "Mozilla/5.0"
                },
            )

            print(
                "[NavigationStrategy]",
                response.status_code,
                response.headers.get("Content-Type")
            )

            if response.status_code != 200:
                return None

            return BeautifulSoup(
                response.text,
                "html.parser",
            )

        except Exception as e:
            print(f"[NavigationStrategy] Download failed: {e}")
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