from urllib.parse import urljoin
from xml.etree import ElementTree as ET
import gzip

from discovery.context import DiscoveryContext
from discovery.models import CandidateURL
from discovery.strategies.base import DiscoveryStrategy


class SitemapStrategy(DiscoveryStrategy):
    """
    Discover URLs from sitemap.xml, sitemap indexes and robots.txt.
    """

    COMMON_SITEMAPS = [
        "/sitemap.xml",
        "/sitemap_index.xml",
        "/sitemap-index.xml",
        "/sitemap/sitemap.xml",
    ]

    def discover(self, context: DiscoveryContext) -> list[CandidateURL]:

        sitemap_urls = self._discover_sitemaps(context)

        candidates = []

        visited = set()

        while sitemap_urls:

            sitemap = sitemap_urls.pop(0)

            if sitemap in visited:
                continue

            visited.add(sitemap)

            xml = self._download(context, sitemap)

            if xml is None:
                continue

            pages, children = self._parse(xml)

            sitemap_urls.extend(children)

            for page in pages:

                page_lower = page.lower()

                # Ignore obviously irrelevant sitemap entries
                if any(skip in page_lower for skip in (
                    "/news",
                    "/events",
                    "/event",
                    "/blog",
                    "/press",
                    "/media",
                    "/library",
                    "/contact",
                    "/privacy",
                    "/terms",
                    "/login",
                    "/jobs",
                    "/careers",
                    "/staff",
                    "/about",
                    "/alumni",
                    "/giving",
                    "/donate",
                )):
                    continue

                candidates.append(
                    CandidateURL(
                        url=page,
                        source="sitemap",
                    )
                )

        return candidates

    def _discover_sitemaps(
        self,
        context: DiscoveryContext,
    ) -> list[str]:

        discovered = []

        robots = self._download(
            context,
            urljoin(context.base_url, "/robots.txt"),
        )

        if robots:

            try:

                text = robots.decode(
                    "utf-8",
                    errors="ignore",
                )

                for line in text.splitlines():

                    if line.lower().startswith("sitemap:"):

                        discovered.append(
                            line.split(":", 1)[1].strip()
                        )

            except Exception:
                pass

        for path in self.COMMON_SITEMAPS:

            discovered.append(
                urljoin(
                    context.base_url,
                    path,
                )
            )

        return list(dict.fromkeys(discovered))

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

            content = response.content

            if (
                url.endswith(".gz")
                or content[:2] == b"\x1f\x8b"
            ):
                try:
                    content = gzip.decompress(content)
                except Exception:
                    pass

            return content

        except Exception:
            return None

    def _parse(
        self,
        xml: bytes,
    ):

        page_urls = []

        child_sitemaps = []

        try:

            root = ET.fromstring(xml)

        except ET.ParseError:

            return page_urls, child_sitemaps

        for child in root:

            tag = child.tag.lower()

            if tag.endswith("url"):

                loc = child.find("{*}loc")

                if loc is not None and loc.text:

                    page_urls.append(
                        loc.text.strip()
                    )

            elif tag.endswith("sitemap"):

                loc = child.find("{*}loc")

                if loc is not None and loc.text:

                    child_sitemaps.append(
                        loc.text.strip()
                    )

        return page_urls, child_sitemaps