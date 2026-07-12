from __future__ import annotations

import json
import re
from copy import deepcopy
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Set
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup, Tag


# =============================================================================
# CONSTANTS
# =============================================================================

DEFAULT_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/150.0.0.0 Safari/537.36"
    ),
    "Accept": (
        "text/html,application/xhtml+xml,"
        "application/xml;q=0.9,"
        "image/avif,image/webp,image/apng,*/*;q=0.8"
    ),
    "Accept-Language": "en-US,en;q=0.9",
    "Accept-Encoding": "gzip, deflate, br",
    "Cache-Control": "no-cache",
    "Pragma": "no-cache",
    "DNT": "1",
    "Upgrade-Insecure-Requests": "1"
}


QS_BASE_URL = "https://www.topuniversities.com"


RANKING_ENDPOINT_PATTERN = re.compile(
    r"""
    (?P<path>
        /qs-profiles/rank-data/
        (?P<ranking_id>\d+)/
        (?P<profile_id>\d+)/
        (?P<offset>\d+)
        (?:\?_wrapper_format=drupal_ajax)?
    )
    """,
    re.IGNORECASE | re.VERBOSE,
)


SOCIAL_DOMAINS = {
    "facebook": (
        "facebook.com",
        "facebook.de",
        "fb.com",
    ),
    "instagram": (
        "instagram.com",
    ),
    "linkedin": (
        "linkedin.com",
    ),
    "youtube": (
        "youtube.com",
        "youtu.be",
    ),
    "twitter": (
        "twitter.com",
        "twitter.de",
        "x.com",
    ),
    "tiktok": (
        "tiktok.com",
    ),
    "threads": (
        "threads.net",
    ),
}


QS_OWN_SOCIAL_MARKERS = (
    "topuniversities",
    "topunis",
    "qs-world-university-rankings",
    "company/243103",
    "qstopuniversities",
)


IMAGE_EXTENSIONS = (
    ".jpg",
    ".jpeg",
    ".png",
    ".webp",
    ".gif",
    ".avif",
)


IGNORED_IMAGE_MARKERS = (
    "/themes/",
    "/icons/",
    "/icon/",
    "/images/social",
    "/images/fb_",
    "/images/twitter_",
    "/images/linkedin_",
    "/images/whatsapp_",
    "/images/mail_",
    "/images/copy_",
    "favicon",
    "sprite",
    "pixel",
    "tracker",
    "banner",
    "advert",
    "placeholder",
    "loading",
    "spinner",
    "qs-logo",
)


PROGRAMME_LABELS = {
    "undergraduate programmes": "undergraduate_programmes",
    "undergraduate programs": "undergraduate_programmes",
    "ug programmes": "undergraduate_programmes",
    "ug programs": "undergraduate_programmes",
    "postgraduate programmes": "postgraduate_programmes",
    "postgraduate programs": "postgraduate_programmes",
    "pg programmes": "postgraduate_programmes",
    "pg programs": "postgraduate_programmes",
}


STATISTIC_LABELS = {
    "total students": "total_students",
    "international students": "international_students",
    "total faculty staff": "total_faculty_staff",
    "faculty staff": "total_faculty_staff",
}


BREAKDOWN_LABELS = {
    "ug students": "undergraduate_percentage",
    "undergraduate students": "undergraduate_percentage",
    "pg students": "postgraduate_percentage",
    "postgraduate students": "postgraduate_percentage",
    "domestic staff": "domestic_percentage",
    "international staff": "international_percentage",
}



# =============================================================================
# DATA CLASSES
# =============================================================================

@dataclass
class ExtractionPaths:
    root: Path
    raw_directory: Path
    extracted_directory: Path
    raw_profile_file: Path
    extracted_profile_file: Path


# =============================================================================
# EXTRACTOR
# =============================================================================

class QSProfileExtractor:
    """
    Downloads and extracts structured university-profile information from
    QS TopUniversities profile pages.

    Extraction strategy:

    1. Preserve the complete raw HTML.
    2. Parse JSON-LD for identity, campuses, social links, and images.
    3. Parse visible HTML for overview, badges, statistics, costs,
       scholarships, university information, and ranking summaries.
    4. Discover QS ranking AJAX endpoints for the ranking extractor.
    5. Preserve source display values while also creating normalized values.

    No LLM is required.
    """

    INVALID_CAMPUS_VALUES = {
        "campus location",
        "campus locations",
        "location",
        "locations",
        "open map",
        "open the map",
        "view map",
        "view on map",
        "show map",
    }

    def __init__(
        self,
        output_directory: str | Path = "data/qs",
        timeout: int = 30,
        headers: Optional[Dict[str, str]] = None,
        session: Optional[requests.Session] = None,
        save_raw_html: bool = True,
    ):
        """
        Initialize the QS profile extractor.

        Parameters
        ----------
        output_directory:
            Root directory where QS data will be stored.

        timeout:
            Maximum request timeout in seconds.

        headers:
            Optional custom HTTP request headers.

        session:
            Optional requests.Session instance.

        save_raw_html:
            If True, preserve the complete downloaded QS profile HTML.
            Enabled by default for debugging, reproducibility, and future
            reprocessing without downloading the page again.
        """

        self.output_directory = Path(
            output_directory
        )

        self.timeout = timeout

        self.save_raw_html = save_raw_html

        self.session = (
            session
            or requests.Session()
        )

        self.session.headers.clear()

        self.session.headers.update(
            headers
            or DEFAULT_HEADERS
        )

    # =========================================================================
    # PUBLIC API
    # =========================================================================

    def extract(
        self,
        profile_url: str,
        university_name: Optional[str] = None,
        university_slug: Optional[str] = None,
        output_directory: Optional[str | Path] = None,
    ) -> Dict[str, Any]:

        normalized_profile_url = self._normalize_profile_url(
            profile_url
        )

        resolved_university_slug = (
            university_slug
            or self._extract_slug(
                normalized_profile_url
            )
        )

        paths = self._build_paths(
            university_slug=resolved_university_slug,
            output_directory=output_directory,
        )

        # ---------------------------------------------------------
        # Load cached HTML first
        # ---------------------------------------------------------

        html_content = self._load_existing_raw_html(
            university_slug=resolved_university_slug,
            output_directory=output_directory,
        )

        if html_content:

            print(
                "✓ Existing raw QS profile HTML loaded."
            )

        else:

            print(
                "No cached QS HTML found. "
                "Downloading the profile..."
            )

            html_content = self.fetch_profile(
                normalized_profile_url
            )

        # ---------------------------------------------------------
        # Preserve raw HTML
        # ---------------------------------------------------------

        if self.save_raw_html:

            self._write_text(
                paths.raw_profile_file,
                html_content,
            )

        # ---------------------------------------------------------
        # Extract profile information
        # ---------------------------------------------------------

        result = self.parse_profile(
            html_content=html_content,
            profile_url=normalized_profile_url,
            university_name=university_name,
        )

        result["files"] = {
            "raw_profile": (
                str(
                    paths.raw_profile_file
                )
                if self.save_raw_html
                else None
            ),
            "extracted_profile": str(
                paths.extracted_profile_file
            ),
        }

        # ---------------------------------------------------------
        # Save extracted profile JSON
        # ---------------------------------------------------------

        self._write_json(
            paths.extracted_profile_file,
            result,
        )

        return result

    def _clean_campuses(
        self,
        campuses: List[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        """
        Remove navigation labels and map controls that
        were incorrectly detected as university campuses.
        """

        cleaned_campuses = []

        seen = set()

        for campus in campuses:

            if not isinstance(
                campus,
                dict,
            ):
                continue

            name = str(
                campus.get(
                    "name",
                    ""
                )
            ).strip()

            address = (
                campus.get(
                    "address"
                )
                or {}
            )

            full_address = str(
                address.get(
                    "full_address",
                    ""
                )
            ).strip()

            normalized_name = (
                name.lower()
            )

            normalized_address = (
                full_address.lower()
            )

            if (
                normalized_name
                in self.INVALID_CAMPUS_VALUES
            ):
                continue

            if (
                normalized_address
                in self.INVALID_CAMPUS_VALUES
            ):
                continue

            # A record with no useful name and no address
            # should not be retained.
            useful_address_values = [
                value
                for value
                in address.values()
                if str(value).strip()
            ]

            if (
                not name
                and not useful_address_values
            ):
                continue

            duplicate_key = (
                normalized_name,
                tuple(
                    sorted(
                        (
                            str(key).lower(),
                            str(value).lower(),
                        )
                        for key, value
                        in address.items()
                    )
                ),
            )

            if duplicate_key in seen:
                continue

            seen.add(
                duplicate_key
            )

            cleaned_campuses.append(
                campus
            )

        return cleaned_campuses

    def save_json(
        self,
        data: Dict[str, Any],
        university_slug: str,
        output_directory: Optional[str | Path] = None,
    ) -> Path:
        """
        Save extracted QS profile data as JSON.

        Parameters
        ----------
        data:
            Complete extracted QS profile data.

        university_slug:
            Stable university folder name.

        output_directory:
            Optional output root. Uses the extractor's configured
            output directory when not provided.

        Returns
        -------
        Path
            Path of the generated profile_data.json file.
        """

        root_directory = Path(
            output_directory
            or self.output_directory
        )

        extracted_directory = (
            root_directory
            / university_slug
            / "extracted"
        )

        extracted_directory.mkdir(
            parents=True,
            exist_ok=True,
        )

        json_file = (
            extracted_directory
            / "profile_data.json"
        )

        self._write_json(
            json_file,
            data,
        )

        return json_file

    def _load_existing_raw_html(
        self,
        university_slug: str,
        output_directory: Optional[str | Path] = None,
    ) -> Optional[str]:
        """
        Load a previously downloaded QS profile page.

        Returns None when the cached HTML file does not exist
        or contains no usable content.
        """

        root_directory = Path(
            output_directory
            or self.output_directory
        )

        raw_html_file = (
            root_directory
            / university_slug
            / "raw"
            / "profile.html"
        )

        if not raw_html_file.exists():
            return None

        html_content = raw_html_file.read_text(
            encoding="utf-8"
        )

        if not html_content.strip():
            return None

        return html_content

    def fetch_profile(
        self,
        profile_url: str,
    ) -> str:
        """
        Download the QS university profile.

        Uses a simple browser-like request. Avoids manually
        supplied browser client-hint headers because they can
        conflict with Python requests' network fingerprint.
        """

        try:
            response = self.session.get(
                profile_url,
                headers={
                    "Referer": (
                        "https://www.google.com/"
                    ),
                },
                timeout=self.timeout,
                allow_redirects=True,
            )

            if response.status_code == 403:
                raise RuntimeError(
                    "QS returned HTTP 403 Forbidden. "
                    "The profile request was blocked."
                )

            response.raise_for_status()

            response.encoding = (
                response.apparent_encoding
                or "utf-8"
            )

            html_content = response.text

            if not html_content.strip():
                raise RuntimeError(
                    "QS returned an empty profile page."
                )

            return html_content

        except requests.RequestException as error:
            raise RuntimeError(
                "Failed to download the QS profile: "
                f"{error}"
            ) from error

    def parse_profile(
        self,
        html_content: str,
        profile_url: str,
        university_name: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Parse already-downloaded QS profile HTML.

        This method is useful for local tests because it does not make a
        network request.
        """

        soup = BeautifulSoup(
            html_content,
            "lxml",
        )

        university_slug = self._extract_slug(
            profile_url
        )

        json_ld_items = self._extract_json_ld_items(
            soup
        )

        university_json_ld = (
            self._find_university_json_ld(
                json_ld_items
            )
        )

        page_name = (
            self._extract_university_name(
                soup=soup,
                university_json_ld=university_json_ld,
            )
            or university_name
            or self._slug_to_name(university_slug)
        )

        qs_profile_id = self._extract_qs_profile_id(
            soup=soup,
            html_content=html_content,
            university_json_ld=university_json_ld,
        )

        drupal_node_id = self._extract_drupal_node_id(
            soup=soup,
            html_content=html_content,
        )

        meta_description = self._extract_meta_description(
            soup
        )

        overview = self._extract_overview(
            soup=soup,
            university_name=page_name,
        )

        badges = self._extract_profile_badges(
            soup
        )

        programme_summary = (
            self._extract_programme_summary(
                badges=badges,
                soup=soup,
            )
        )

        campuses = self._extract_campuses(
            soup=soup,
            university_json_ld=university_json_ld,
        )

        campuses = self._clean_campuses(
            campuses
        )

        social_links = self._extract_social_links(
            soup=soup,
            university_json_ld=university_json_ld,
        )

        website_urls = self._extract_university_websites(
            soup=soup,
            university_json_ld=university_json_ld,
            profile_url=profile_url,
        )

        logo_url = self._extract_logo_url(
            soup=soup,
            university_json_ld=university_json_ld,
        )

        image_urls = self._extract_university_images(
            soup=soup,
            university_json_ld=university_json_ld,
            logo_url=logo_url,
        )

        statistics = self._extract_statistics(
            soup=soup,
        )

        cost_of_living = (
            self._extract_cost_of_living(
                soup
            )
        )

        scholarships = self._extract_scholarships(
            soup=soup,
            profile_url=profile_url,
        )

        university_information = (
            self._extract_university_information(
                soup=soup,
                profile_url=profile_url,
            )
        )

        ranking_summary = (
            self._extract_ranking_summary(
                soup
            )
        )

        ranking_endpoints = (
            self._extract_ranking_endpoints(
                html_content=html_content,
                profile_url=profile_url,
            )
        )

        additional_sections = (
            self._extract_additional_sections(
                soup=soup,
                excluded_titles={
                    "about",
                    "university information",
                    "cost of living",
                    "scholarships",
                    "rankings & ratings",
                    "rankings and ratings",
                    "campus locations",
                    "similar universities",
                },
            )
        )

        result = {
            "source": {
                "provider": "QS TopUniversities",
                "profile_url": profile_url,
                "university_slug": university_slug,
            },
            "identifiers": {
                "qs_profile_id": qs_profile_id,
                "drupal_node_id": drupal_node_id,
            },
            "university": {
                "name": page_name,
                "description": meta_description,
                "overview": overview,
                "profile_badges": badges,
                "programme_summary": programme_summary,
                "campuses": campuses,
                "social_links": social_links,
                "website_urls": website_urls,
                "logo_url": logo_url,
                "image_urls": image_urls,
                "information": university_information,
            },
            "statistics": statistics,
            "cost_of_living": cost_of_living,
            "scholarships": scholarships,
            "ranking": {
                "summary": ranking_summary,
                "discovered_endpoints": ranking_endpoints,
            },
            "additional_sections": additional_sections,
            "extraction": {
                "json_ld_items_found": len(
                    json_ld_items
                ),
                "profile_badges_found": len(
                    badges
                ),
                "campuses_found": len(
                    campuses
                ),
                "social_links_found": len(
                    social_links
                ),
                "website_urls_found": len(
                    website_urls
                ),
                "images_found": len(
                    image_urls
                ),
                "statistics_found": self._count_non_empty(
                    statistics
                ),
                "cost_items_found": len(
                    cost_of_living.get(
                        "items",
                        [],
                    )
                ),
                "scholarship_sections_found": len(
                    scholarships.get(
                        "sections",
                        [],
                    )
                ),
                "university_information_sections_found": len(
                    university_information
                ),
                "ranking_summaries_found": len(
                    ranking_summary
                ),
                "ranking_endpoints_found": len(
                    ranking_endpoints
                ),
                "additional_sections_found": len(
                    additional_sections
                ),
            },
        }

        return self._remove_internal_empty_values(
            result
        )

    # =========================================================================
    # PATHS AND FILES
    # =========================================================================

    def _build_paths(
        self,
        university_slug: str,
        output_directory: Optional[str | Path],
    ) -> ExtractionPaths:
        root = Path(
            output_directory
            or self.output_directory
        )

        university_root = (
            root
            / university_slug
        )

        raw_directory = (
            university_root
            / "raw"
        )

        extracted_directory = (
            university_root
            / "extracted"
        )

        raw_directory.mkdir(
            parents=True,
            exist_ok=True,
        )

        extracted_directory.mkdir(
            parents=True,
            exist_ok=True,
        )

        return ExtractionPaths(
            root=university_root,
            raw_directory=raw_directory,
            extracted_directory=extracted_directory,
            raw_profile_file=(
                raw_directory
                / "profile.html"
            ),
            extracted_profile_file=(
                extracted_directory
                / "profile_data.json"
            ),
        )

    @staticmethod
    def _write_text(
        path: Path,
        content: str,
    ) -> None:
        path.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        path.write_text(
            content,
            encoding="utf-8",
        )

    @staticmethod
    def _write_json(
        path: Path,
        data: Dict[str, Any],
    ) -> None:
        path.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        path.write_text(
            json.dumps(
                data,
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )

    # =========================================================================
    # JSON-LD
    # =========================================================================

    def _extract_json_ld_items(
        self,
        soup: BeautifulSoup,
    ) -> List[Dict[str, Any]]:
        items: List[Dict[str, Any]] = []

        scripts = soup.find_all(
            "script",
            attrs={
                "type": re.compile(
                    r"application/ld\+json",
                    re.IGNORECASE,
                )
            },
        )

        for script in scripts:
            raw_content = (
                script.string
                or script.get_text()
                or ""
            ).strip()

            if not raw_content:
                continue

            parsed = self._safe_json_loads(
                raw_content
            )

            if parsed is None:
                continue

            items.extend(
                self._flatten_json_ld(
                    parsed
                )
            )

        return items

    def _flatten_json_ld(
        self,
        value: Any,
    ) -> List[Dict[str, Any]]:
        output: List[Dict[str, Any]] = []

        if isinstance(value, list):
            for item in value:
                output.extend(
                    self._flatten_json_ld(
                        item
                    )
                )

            return output

        if not isinstance(value, dict):
            return output

        graph = value.get("@graph")

        if isinstance(graph, list):
            for item in graph:
                output.extend(
                    self._flatten_json_ld(
                        item
                    )
                )

        output.append(value)

        main_entity = value.get(
            "mainEntity"
        )

        if isinstance(
            main_entity,
            (dict, list),
        ):
            output.extend(
                self._flatten_json_ld(
                    main_entity
                )
            )

        return output

    def _find_university_json_ld(
        self,
        items: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        accepted_types = {
            "collegeoruniversity",
            "educationalorganization",
            "university",
        }

        for item in items:
            item_types = item.get(
                "@type",
                [],
            )

            if isinstance(
                item_types,
                str,
            ):
                item_types = [
                    item_types
                ]

            normalized_types = {
                self._normalize_label(
                    item_type
                ).replace(
                    " ",
                    "",
                )
                for item_type
                in item_types
            }

            if (
                normalized_types
                & accepted_types
            ):
                return item

        return {}

    # =========================================================================
    # IDENTITY
    # =========================================================================

    def _extract_university_name(
        self,
        soup: BeautifulSoup,
        university_json_ld: Dict[str, Any],
    ) -> Optional[str]:
        json_name = self._clean_text(
            university_json_ld.get(
                "name"
            )
        )

        if json_name:
            return json_name

        selectors = (
            "h1",
            ".university-name",
            ".uni-name",
            ".profile-name",
            "[class*='university-name']",
        )

        for selector in selectors:
            element = soup.select_one(
                selector
            )

            value = self._element_text(
                element
            )

            if value:
                return value

        og_title = soup.find(
            "meta",
            property="og:title",
        )

        if og_title:
            title = self._clean_text(
                og_title.get(
                    "content"
                )
            )

            if title:
                return re.sub(
                    r"\s*\|\s*Top Universities.*$",
                    "",
                    title,
                    flags=re.IGNORECASE,
                ).strip()

        return None

    def _extract_meta_description(
        self,
        soup: BeautifulSoup,
    ) -> str:
        candidates = [
            soup.find(
                "meta",
                attrs={
                    "name": "description"
                },
            ),
            soup.find(
                "meta",
                property="og:description",
            ),
            soup.find(
                "meta",
                attrs={
                    "name": "twitter:description"
                },
            ),
        ]

        for candidate in candidates:
            if not candidate:
                continue

            value = self._clean_text(
                candidate.get(
                    "content"
                )
            )

            if value:
                return value

        return ""

    def _extract_qs_profile_id(
        self,
        soup: BeautifulSoup,
        html_content: str,
        university_json_ld: Dict[str, Any],
    ) -> Optional[int]:
        patterns = (
            r"/profiles/logos/[^\"']*_(\d+)_large\.",
            r"/qs-profiles/rank-data/\d+/(\d+)/\d+",
            r"\bprofile[_-]?id[\"'\s:=]+(\d+)",
        )

        for pattern in patterns:
            match = re.search(
                pattern,
                html_content,
                flags=re.IGNORECASE,
            )

            if match:
                return self._to_int(
                    match.group(1)
                )

        image_values = self._ensure_list(
            university_json_ld.get(
                "image"
            )
        )

        for image_value in image_values:
            image_url = self._extract_url_value(
                image_value
            )

            if not image_url:
                continue

            match = re.search(
                r"_(\d+)_large\.",
                image_url,
                flags=re.IGNORECASE,
            )

            if match:
                return self._to_int(
                    match.group(1)
                )

        return None

    def _extract_drupal_node_id(
        self,
        soup: BeautifulSoup,
        html_content: str,
    ) -> Optional[int]:
        selectors = (
            "[data-nid]",
            "[data-node-id]",
            "[data-entity-id]",
        )

        attributes = (
            "data-nid",
            "data-node-id",
            "data-entity-id",
        )

        for selector in selectors:
            for element in soup.select(
                selector
            ):
                for attribute in attributes:
                    value = self._to_int(
                        element.get(
                            attribute
                        )
                    )

                    if value:
                        return value

        patterns = (
            r"/signup\?nid=(\d+)",
            r"\bnid[\"'\s:=]+(\d+)",
            r"\bnode[_-]?id[\"'\s:=]+(\d+)",
        )

        for pattern in patterns:
            match = re.search(
                pattern,
                html_content,
                flags=re.IGNORECASE,
            )

            if match:
                return self._to_int(
                    match.group(1)
                )

        return None

    # =========================================================================
    # OVERVIEW
    # =========================================================================

    def _extract_overview(
        self,
        soup: BeautifulSoup,
        university_name: str,
    ) -> str:
        selectors = (
            "#about-block-heading",
            "[id*='about-block-heading']",
            ".about_section .textsection",
            ".abt-overview-read",
            "[class*='about-overview']",
        )

        candidates: List[str] = []

        for selector in selectors:
            for element in soup.select(
                selector
            ):
                target = element

                if (
                    element.name
                    in {
                        "h1",
                        "h2",
                        "h3",
                        "h4",
                        "h5",
                        "h6",
                    }
                ):
                    target = (
                        element.find_next_sibling()
                        or element.parent
                    )

                text = self._extract_content_text(
                    target
                )

                if text:
                    candidates.append(
                        text
                    )

        heading_pattern = re.compile(
            r"^about\b",
            re.IGNORECASE,
        )

        for heading in soup.find_all(
            re.compile(
                r"^h[1-6]$"
            )
        ):
            heading_text = (
                self._element_text(
                    heading
                )
            )

            if not heading_pattern.search(
                heading_text
            ):
                continue

            section_text = (
                self._extract_section_after_heading(
                    heading
                )
            )

            if section_text:
                candidates.append(
                    section_text
                )

        candidates = self._deduplicate_strings(
            candidates
        )

        if not candidates:
            return ""

        return max(
            candidates,
            key=len,
        )

    # =========================================================================
    # PROFILE BADGES AND PROGRAMMES
    # =========================================================================

    def _extract_profile_badges(
        self,
        soup: BeautifulSoup,
    ) -> List[Dict[str, Any]]:
        badges: List[Dict[str, Any]] = []

        selectors = (
            ".badge-section .single-badge",
            ".single-badge",
            "[class*='profile-box'] [class*='badge']",
        )

        seen: Set[str] = set()

        for selector in selectors:
            for badge in soup.select(
                selector
            ):
                text = self._element_text(
                    badge
                )

                if not text:
                    continue

                title_element = badge.select_one(
                    ".single-badge-title"
                )

                label = self._element_text(
                    title_element
                )

                if not label:
                    label = self._remove_leading_value(
                        text
                    )

                value = self._extract_leading_value(
                    text
                )

                if (
                    not label
                    and not value
                ):
                    continue

                key = (
                    self._normalize_label(
                        label
                    )
                    + "|"
                    + str(value)
                )

                if key in seen:
                    continue

                seen.add(key)

                badge_data = {
                    "label": label,
                    "display_value": value,
                    "value": self._parse_numeric_value(
                        value
                    ),
                }

                badges.append(
                    self._remove_internal_empty_values(
                        badge_data
                    )
                )

        return badges

    def _extract_programme_summary(
        self,
        badges: List[Dict[str, Any]],
        soup: BeautifulSoup,
    ) -> Dict[str, Any]:
        output: Dict[str, Any] = {}

        for badge in badges:
            label = self._normalize_label(
                badge.get(
                    "label"
                )
            )

            field_name = (
                PROGRAMME_LABELS.get(
                    label
                )
            )

            if not field_name:
                continue

            output[field_name] = {
                "display_value": (
                    badge.get(
                        "display_value"
                    )
                ),
                "value": badge.get(
                    "value"
                ),
            }

        page_text = self._element_text(
            soup
        )

        for label, field_name in (
            PROGRAMME_LABELS.items()
        ):
            if field_name in output:
                continue

            pattern = re.compile(
                rf"""
                (?P<value>\d[\d,.\s]*)
                \s*
                {re.escape(label)}
                """,
                re.IGNORECASE
                | re.VERBOSE,
            )

            match = pattern.search(
                page_text
            )

            if not match:
                continue

            display_value = (
                match.group(
                    "value"
                ).strip()
            )

            output[field_name] = {
                "display_value": (
                    display_value
                ),
                "value": self._to_int(
                    display_value
                ),
            }

        return output

    # =========================================================================
    # CAMPUSES
    # =========================================================================

    def _extract_campuses(
        self,
        soup: BeautifulSoup,
        university_json_ld: Dict[str, Any],
    ) -> List[Dict[str, Any]]:
        campuses: List[Dict[str, Any]] = []

        campuses.extend(
            self._extract_json_ld_campuses(
                university_json_ld
            )
        )

        campuses.extend(
            self._extract_html_campuses(
                soup
            )
        )

        return self._deduplicate_objects(
            campuses,
            key_fields=(
                "name",
                "address.street",
                "address.city",
                "address.postal_code",
            ),
        )

    def _extract_json_ld_campuses(
        self,
        university_json_ld: Dict[str, Any],
    ) -> List[Dict[str, Any]]:
        campuses: List[Dict[str, Any]] = []

        location_values = []

        for field_name in (
            "location",
            "department",
            "subOrganization",
        ):
            location_values.extend(
                self._ensure_list(
                    university_json_ld.get(
                        field_name
                    )
                )
            )

        address = university_json_ld.get(
            "address"
        )

        if address:
            location_values.append(
                {
                    "name": (
                        university_json_ld.get(
                            "name"
                        )
                    ),
                    "address": address,
                }
            )

        for location in location_values:
            if not isinstance(
                location,
                dict,
            ):
                continue

            address_data = location.get(
                "address"
            )

            if not isinstance(
                address_data,
                dict,
            ):
                continue

            campus = {
                "name": self._clean_text(
                    location.get(
                        "name"
                    )
                ),
                "address": {
                    "street": self._clean_text(
                        address_data.get(
                            "streetAddress"
                        )
                    ),
                    "city": self._clean_text(
                        address_data.get(
                            "addressLocality"
                        )
                    ),
                    "region": self._clean_text(
                        address_data.get(
                            "addressRegion"
                        )
                    ),
                    "postal_code": self._clean_text(
                        address_data.get(
                            "postalCode"
                        )
                    ),
                    "country": self._extract_country_name(
                        address_data.get(
                            "addressCountry"
                        )
                    ),
                },
            }

            campuses.append(
                self._remove_internal_empty_values(
                    campus
                )
            )

        return campuses

    def _extract_html_campuses(
        self,
        soup: BeautifulSoup,
    ) -> List[Dict[str, Any]]:
        campuses: List[Dict[str, Any]] = []

        selectors = (
            "[class*='campus-location']",
            "[class*='campus-card']",
            "[class*='campus-item']",
            ".campus-location",
        )

        for selector in selectors:
            for element in soup.select(
                selector
            ):
                text = self._element_text(
                    element
                )

                if not text:
                    continue

                name_element = element.find(
                    re.compile(
                        r"^h[1-6]$"
                    )
                )

                name = self._element_text(
                    name_element
                )

                address_element = (
                    element.find(
                        "address"
                    )
                    or element.select_one(
                        "[class*='address']"
                    )
                )

                address_text = (
                    self._element_text(
                        address_element
                    )
                )

                if (
                    not name
                    and not address_text
                ):
                    continue

                campus = {
                    "name": name,
                    "address": {
                        "full_address": (
                            address_text
                        )
                    },
                }

                campuses.append(
                    self._remove_internal_empty_values(
                        campus
                    )
                )

        return campuses

    # =========================================================================
    # SOCIAL LINKS AND WEBSITES
    # =========================================================================

    def _extract_social_links(
        self,
        soup: BeautifulSoup,
        university_json_ld: Dict[str, Any],
    ) -> List[Dict[str, Any]]:
        candidates: List[str] = []

        candidates.extend(
            self._extract_same_as_urls(
                university_json_ld
            )
        )

        follow_containers = (
            self._find_follow_university_containers(
                soup
            )
        )

        for container in follow_containers:
            for anchor in container.select(
                "a[href]"
            ):
                candidates.append(
                    anchor.get(
                        "href",
                        ""
                    )
                )

        output: List[Dict[str, Any]] = []
        seen: Set[str] = set()

        for source_url in candidates:
            source_url = self._clean_text(
                source_url
            )

            if not source_url:
                continue

            normalized_url = (
                self._normalize_external_url(
                    source_url
                )
            )

            platform = self._detect_social_platform(
                normalized_url
            )

            if not platform:
                continue

            if self._is_qs_social_url(
                normalized_url
            ):
                continue

            dedupe_key = (
                platform
                + "|"
                + normalized_url.lower()
            )

            if dedupe_key in seen:
                continue

            seen.add(
                dedupe_key
            )

            output.append(
                {
                    "platform": platform,
                    "url": normalized_url,
                    "source_url": source_url,
                }
            )

        return output

    def _find_follow_university_containers(
        self,
        soup: BeautifulSoup,
    ) -> List[Tag]:
        containers: List[Tag] = []

        text_nodes = soup.find_all(
            string=re.compile(
                r"\bfollow university\b",
                re.IGNORECASE,
            )
        )

        for text_node in text_nodes:
            parent = text_node.parent

            if not isinstance(
                parent,
                Tag,
            ):
                continue

            container = parent

            for _ in range(5):
                if (
                    container
                    and container.find(
                        "a",
                        href=True,
                    )
                ):
                    break

                container = (
                    container.parent
                    if container
                    else None
                )

            if (
                isinstance(
                    container,
                    Tag,
                )
                and container not in containers
            ):
                containers.append(
                    container
                )

        return containers

    def _extract_university_websites(
        self,
        soup: BeautifulSoup,
        university_json_ld: Dict[str, Any],
        profile_url: str,
    ) -> List[str]:
        candidates: List[str] = []

        for field_name in (
            "url",
            "sameAs",
        ):
            candidates.extend(
                self._ensure_list(
                    university_json_ld.get(
                        field_name
                    )
                )
            )

        selectors = (
            "a[class*='website'][href]",
            "a[title*='website' i][href]",
            "a[aria-label*='website' i][href]",
        )

        for selector in selectors:
            for anchor in soup.select(
                selector
            ):
                candidates.append(
                    anchor.get(
                        "href",
                        ""
                    )
                )

        output: List[str] = []

        profile_host = (
            urlparse(
                profile_url
            ).netloc.lower()
        )

        for candidate in candidates:
            url = self._extract_url_value(
                candidate
            )

            if not url:
                continue

            normalized_url = (
                self._normalize_external_url(
                    url
                )
            )

            parsed = urlparse(
                normalized_url
            )

            if not parsed.netloc:
                continue

            if (
                parsed.netloc.lower()
                == profile_host
            ):
                continue

            if self._detect_social_platform(
                normalized_url
            ):
                continue

            output.append(
                normalized_url
            )

        return self._deduplicate_strings(
            output,
            case_sensitive=False,
        )

    # =========================================================================
    # IMAGES
    # =========================================================================

    def _extract_logo_url(
        self,
        soup: BeautifulSoup,
        university_json_ld: Dict[str, Any],
    ) -> Optional[str]:
        logo = university_json_ld.get(
            "logo"
        )

        logo_url = self._extract_url_value(
            logo
        )

        if logo_url:
            return self._normalize_url(
                logo_url
            )

        selectors = (
            "img[class*='university-logo']",
            "img[class*='profile-logo']",
            "img[src*='/profiles/logos/']",
        )

        for selector in selectors:
            image = soup.select_one(
                selector
            )

            if not image:
                continue

            source = self._extract_image_source(
                image
            )

            if source:
                return self._normalize_url(
                    source
                )

        html_text = str(soup)

        match = re.search(
            r"""
            (?P<url>
                https?://
                [^"'\\\s]+
                /profiles/logos/
                [^"'\\\s]+
            )
            """,
            html_text,
            flags=re.IGNORECASE
            | re.VERBOSE,
        )

        if match:
            return self._normalize_url(
                match.group(
                    "url"
                )
            )

        return None

    def _extract_university_images(
        self,
        soup: BeautifulSoup,
        university_json_ld: Dict[str, Any],
        logo_url: Optional[str],
    ) -> List[str]:
        candidates: List[str] = []

        for image_value in self._ensure_list(
            university_json_ld.get(
                "image"
            )
        ):
            image_url = self._extract_url_value(
                image_value
            )

            if image_url:
                candidates.append(
                    image_url
                )

        selectors = (
            "img[src*='/profiles-slideshow/']",
            "img[data-src*='/profiles-slideshow/']",
            "img[src*='/profiles/logos/']",
            "img[data-src*='/profiles/logos/']",
            "[class*='gallery'] img",
            "[class*='slideshow'] img",
        )

        for selector in selectors:
            for image in soup.select(
                selector
            ):
                source = self._extract_image_source(
                    image
                )

                if source:
                    candidates.append(
                        source
                    )

        if logo_url:
            candidates.append(
                logo_url
            )

        output: List[str] = []

        for candidate in candidates:
            normalized_url = self._normalize_url(
                candidate
            )

            if not normalized_url:
                continue

            if not self._looks_like_university_image(
                normalized_url
            ):
                continue

            output.append(
                normalized_url
            )

        return self._deduplicate_strings(
            output,
            case_sensitive=False,
        )
    
    # =========================================================================
    # HELPERS
    # =========================================================================
    
    def _parse_integer(
        self,
        value: Any,
    ) -> Optional[int]:
        """
        Convert values such as '35,596' into 35596.
        """

        if value is None:
            return None

        cleaned_value = re.sub(
            r"[^\d]",
            "",
            str(value),
        )

        if not cleaned_value:
            return None

        return int(
            cleaned_value
        )
    
    def _extract_international_student_percentage(
        self,
        soup: BeautifulSoup,
    ) -> Optional[float]:
        """
        Extract the international-student percentage
        from the QS profile badge.
        """

        page_text = soup.get_text(
            " ",
            strip=True,
        )

        match = re.search(
            r"""
            International\s+students
            \s*
            (?P<percentage>[\d.]+)
            \s*%
            """,
            page_text,
            flags=(
                re.IGNORECASE
                | re.VERBOSE
            ),
        )

        if not match:
            return None

        return float(
            match.group(
                "percentage"
            )
        )

    # =========================================================================
    # STATISTICS
    # =========================================================================

    def _extract_statistics(
        self,
        soup: BeautifulSoup,
    ) -> Dict[str, Any]:
        """
        Extract QS student and faculty statistics.

        QS commonly presents the data in this order:

        Total students
        35,596
        UG students
        62.8%
        PG students
        37.2%

        International students
        7,403
        UG students
        49.5%
        PG students
        50.5%

        Total faculty staff
        3,569
        Domestic staff
        70%
        Int'l staff
        30%

        The parser uses section-aware matching so percentages
        are not assigned to the wrong statistic.
        """

        statistics: Dict[str, Any] = {}

        page_text = soup.get_text(
            "\n",
            strip=True,
        )

        page_text = re.sub(
            r"[ \t]+",
            " ",
            page_text,
        )

        # ---------------------------------------------------------
        # Total students
        # ---------------------------------------------------------

        total_students_match = re.search(
            r"""
            Total\s+students
            \s*
            (?P<total>[\d,]+)
            .*?
            UG\s+students
            \s*
            (?P<ug>[\d.]+)\s*%
            .*?
            PG\s+students
            \s*
            (?P<pg>[\d.]+)\s*%
            """,
            page_text,
            flags=(
                re.IGNORECASE
                | re.DOTALL
                | re.VERBOSE
            ),
        )

        if total_students_match:

            total_display = (
                total_students_match
                .group("total")
            )

            statistics["total_students"] = {
                "display_value": total_display,
                "value": self._parse_integer(
                    total_display
                ),
                "breakdown": {
                    "undergraduate_percentage": float(
                        total_students_match.group(
                            "ug"
                        )
                    ),
                    "postgraduate_percentage": float(
                        total_students_match.group(
                            "pg"
                        )
                    ),
                },
            }

        # ---------------------------------------------------------
        # International students
        # ---------------------------------------------------------

        international_match = re.search(
            r"""
            International\s+students
            \s*
            (?P<total>[\d,]+)
            .*?
            (?:
                UG\s+students
                \s*
            )?
            (?P<ug>[\d.]+)\s*%
            .*?
            (?:
                PG\s+students
                \s*
            )?
            (?P<pg>[\d.]+)\s*%
            """,
            page_text,
            flags=(
                re.IGNORECASE
                | re.DOTALL
                | re.VERBOSE
            ),
        )

        if international_match:

            international_display = (
                international_match
                .group("total")
            )

            international_data = {
                "display_value": (
                    international_display
                ),
                "value": self._parse_integer(
                    international_display
                ),
                "breakdown": {
                    "undergraduate_percentage": float(
                        international_match.group(
                            "ug"
                        )
                    ),
                    "postgraduate_percentage": float(
                        international_match.group(
                            "pg"
                        )
                    ),
                },
            }

            # QS profile badge:
            # "International students 21%"
            international_percentage = (
                self._extract_international_student_percentage(
                    soup
                )
            )

            if international_percentage is not None:

                international_data[
                    "percentage_of_total_students"
                ] = international_percentage

            statistics[
                "international_students"
            ] = international_data

        # ---------------------------------------------------------
        # Faculty staff
        # ---------------------------------------------------------

        faculty_match = re.search(
            r"""
            Total\s+faculty\s+staff
            \s*
            (?P<total>[\d,]+)
            .*?
            Domestic\s+staff
            \s*
            (?P<domestic>[\d.]+)\s*%
            .*?
            (?:
                Int(?:ernational)?['’]?\s*l?
                |
                International
            )
            \s+staff
            \s*
            (?P<international>[\d.]+)\s*%
            """,
            page_text,
            flags=(
                re.IGNORECASE
                | re.DOTALL
                | re.VERBOSE
            ),
        )

        if faculty_match:

            faculty_display = (
                faculty_match.group(
                    "total"
                )
            )

            statistics[
                "total_faculty_staff"
            ] = {
                "display_value": faculty_display,
                "value": self._parse_integer(
                    faculty_display
                ),
                "breakdown": {
                    "domestic_percentage": float(
                        faculty_match.group(
                            "domestic"
                        )
                    ),
                    "international_percentage": float(
                        faculty_match.group(
                            "international"
                        )
                    ),
                },
            }

        return statistics
    
    def _extract_statistic_breakdown(
        self,
        section: Tag,
    ) -> Dict[str, Any]:
        breakdown: Dict[str, Any] = {}

        parent_elements = section.select(
            ".color-code-parent"
        )

        if not parent_elements:
            parent_elements = section.find_all(
                [
                    "div",
                    "li",
                ]
            )

        for element in parent_elements:
            label_element = element.find(
                "label"
            )

            if not label_element:
                continue

            label = self._normalize_label(
                self._element_text(
                    label_element
                )
            )

            field_name = (
                BREAKDOWN_LABELS.get(
                    label
                )
            )

            if not field_name:
                continue

            value_element = (
                element.select_one(
                    ".total-count"
                )
                or label_element.find_next(
                    class_=re.compile(
                        r"(total-count|percentage|value)",
                        re.IGNORECASE,
                    )
                )
            )

            display_value = (
                self._element_text(
                    value_element
                )
            )

            percentage = self._to_float(
                display_value
            )

            if percentage is None:
                continue

            breakdown[field_name] = (
                percentage
            )

        return breakdown

    # =========================================================================
    # COST OF LIVING
    # =========================================================================

    def _extract_cost_of_living(
        self,
        soup: BeautifulSoup,
    ) -> Dict[str, Any]:
        container = self._find_section_container(
            soup=soup,
            ids=(
                "p2-costofliving",
                "costOfLiving",
                "accordionCostOfLiving",
            ),
            title_patterns=(
                r"^cost of living$",
            ),
        )

        if not container:
            return {
                "currency_symbol": None,
                "currency_code": None,
                "period": None,
                "items": [],
            }

        items: List[Dict[str, Any]] = []

        card_selectors = (
            ".costCards .card",
            ".cost-sections .card",
            "#costOfLiving .card",
            "[class*='cost'] [class*='card']",
        )

        processed: Set[int] = set()

        for selector in card_selectors:
            for card in container.select(
                selector
            ):
                card_id = id(
                    card
                )

                if card_id in processed:
                    continue

                processed.add(
                    card_id
                )

                title_element = card.find(
                    [
                        "h3",
                        "h4",
                        "h5",
                        "h6",
                    ]
                )

                value_element = (
                    card.select_one(
                        ".value"
                    )
                    or card.select_one(
                        "[class*='amount']"
                    )
                )

                note_element = card.find(
                    "label"
                )

                category = self._element_text(
                    title_element
                )

                display_value = (
                    self._element_text(
                        value_element
                    )
                )

                note = self._element_text(
                    note_element
                )

                if (
                    not category
                    or not display_value
                ):
                    continue

                currency_symbol = (
                    self._extract_currency_symbol(
                        display_value
                    )
                )

                item = {
                    "category": self._to_snake_case(
                        category
                    ),
                    "label": category,
                    "display_value": (
                        display_value
                    ),
                    "amount": self._to_float(
                        display_value
                    ),
                    "currency_symbol": (
                        currency_symbol
                    ),
                    "note": note,
                }

                items.append(
                    self._remove_internal_empty_values(
                        item
                    )
                )

        items = self._deduplicate_objects(
            items,
            key_fields=(
                "category",
                "display_value",
            ),
        )

        currency_symbols = [
            item.get(
                "currency_symbol"
            )
            for item in items
            if item.get(
                "currency_symbol"
            )
        ]

        currency_symbol = (
            currency_symbols[0]
            if currency_symbols
            else None
        )

        return self._remove_internal_empty_values(
            {
                "currency_symbol": (
                    currency_symbol
                ),
                "currency_code": (
                    self._currency_code_from_symbol(
                        currency_symbol
                    )
                ),
                "period": (
                    self._extract_cost_period(
                        container
                    )
                ),
                "items": items,
            }
        )

    # =========================================================================
    # SCHOLARSHIPS
    # =========================================================================

    def _extract_scholarships(
        self,
        soup: BeautifulSoup,
        profile_url: str,
    ) -> Dict[str, Any]:
        container = self._find_section_container(
            soup=soup,
            ids=(
                "p2-scholarships",
                "scholarships",
            ),
            title_patterns=(
                r"^scholarships?$",
            ),
        )

        if not container:
            return {
                "available": None,
                "sections": [],
                "links": [],
            }

        sections = (
            self._extract_structured_content(
                container
            )
        )

        links = self._extract_links(
            container=container,
            base_url=profile_url,
        )

        text = self._extract_content_text(
            container
        )

        available: Optional[bool] = None

        if text:
            negative_patterns = (
                r"\bno scholarships?\b",
                r"\bnot available\b",
                r"\bnone available\b",
            )

            if any(
                re.search(
                    pattern,
                    text,
                    flags=re.IGNORECASE,
                )
                for pattern
                in negative_patterns
            ):
                available = False
            else:
                available = True

        return {
            "available": available,
            "sections": sections,
            "links": links,
        }

    # =========================================================================
    # UNIVERSITY INFORMATION
    # =========================================================================

    def _extract_university_information(
        self,
        soup: BeautifulSoup,
        profile_url: str,
    ) -> List[Dict[str, Any]]:
        container = self._find_section_container(
            soup=soup,
            ids=(
                "p2-university-information",
                "university-information",
            ),
            title_patterns=(
                r"^university information$",
            ),
        )

        if not container:
            return []

        sections = (
            self._extract_structured_content(
                container
            )
        )

        links = self._extract_links(
            container=container,
            base_url=profile_url,
        )

        if links:
            sections.append(
                {
                    "title": "links",
                    "links": links,
                }
            )

        return sections

    # =========================================================================
    # RANKING SUMMARY AND ENDPOINTS
    # =========================================================================

    def _extract_ranking_summary(
        self,
        soup: BeautifulSoup,
    ) -> List[Dict[str, Any]]:
        rankings: List[Dict[str, Any]] = []

        selectors = (
            ".single-badge",
            "[class*='ranking-card']",
            "[class*='ranking'] [class*='badge']",
        )

        for selector in selectors:
            for element in soup.select(
                selector
            ):
                text = self._element_text(
                    element
                )

                if (
                    "ranking"
                    not in text.lower()
                ):
                    continue

                title_element = (
                    element.select_one(
                        ".single-badge-title"
                    )
                    or element.find(
                        [
                            "h3",
                            "h4",
                            "h5",
                        ]
                    )
                )

                title = self._element_text(
                    title_element
                )

                if (
                    title
                    and re.search(
                        r"#?\s*[=]?\d",
                        title,
                    )
                ):
                    title = self._remove_leading_value(
                        title
                    )

                rank_match = re.search(
                    r"""
                    \#
                    \s*
                    (?P<rank>
                        =?
                        \d+
                        (?:-\d+)?
                    )
                    """,
                    text,
                    flags=re.VERBOSE,
                )

                if not rank_match:
                    continue

                raw_rank = (
                    "#"
                    + rank_match.group(
                        "rank"
                    )
                )

                parsed_rank = (
                    self._parse_rank(
                        raw_rank
                    )
                )

                ranking = {
                    "name": (
                        title
                        or self._remove_leading_value(
                            text
                        )
                    ),
                    "rank": raw_rank,
                    **parsed_rank,
                }

                rankings.append(
                    self._remove_internal_empty_values(
                        ranking
                    )
                )

        return self._deduplicate_objects(
            rankings,
            key_fields=(
                "name",
                "rank",
            ),
        )

    def _extract_ranking_endpoints(
        self,
        html_content: str,
        profile_url: str,
    ) -> List[Dict[str, Any]]:
        endpoints: List[Dict[str, Any]] = []

        seen: Set[
            tuple[int, int, int]
        ] = set()

        decoded_html = (
            html_content
            .replace(
                "\\/",
                "/",
            )
            .replace(
                "&amp;",
                "&",
            )
        )

        for match in (
            RANKING_ENDPOINT_PATTERN
            .finditer(
                decoded_html
            )
        ):
            ranking_id = self._to_int(
                match.group(
                    "ranking_id"
                )
            )

            profile_id = self._to_int(
                match.group(
                    "profile_id"
                )
            )

            offset = self._to_int(
                match.group(
                    "offset"
                )
            )

            if (
                ranking_id is None
                or profile_id is None
                or offset is None
            ):
                continue

            key = (
                ranking_id,
                profile_id,
                offset,
            )

            if key in seen:
                continue

            seen.add(key)

            path = match.group(
                "path"
            )

            endpoint_url = urljoin(
                profile_url,
                path,
            )

            if (
                "_wrapper_format="
                not in endpoint_url
            ):
                separator = (
                    "&"
                    if "?"
                    in endpoint_url
                    else "?"
                )

                endpoint_url += (
                    separator
                    + "_wrapper_format="
                    + "drupal_ajax"
                )

            endpoints.append(
                {
                    "ranking_id": (
                        ranking_id
                    ),
                    "profile_id": (
                        profile_id
                    ),
                    "offset": offset,
                    "url": endpoint_url,
                }
            )

        return endpoints

    # =========================================================================
    # ADDITIONAL SECTIONS
    # =========================================================================

    def _extract_additional_sections(
        self,
        soup: BeautifulSoup,
        excluded_titles: Set[str],
    ) -> List[Dict[str, Any]]:
        output: List[Dict[str, Any]] = []

        normalized_exclusions = {
            self._normalize_label(
                title
            )
            for title
            in excluded_titles
        }

        headings = soup.find_all(
            [
                "h2",
                "h3",
                "h4",
            ],
            class_=re.compile(
                r"(univ-block-heading|sec_name)",
                re.IGNORECASE,
            ),
        )

        for heading in headings:
            title = self._element_text(
                heading
            )

            normalized_title = (
                self._normalize_label(
                    title
                )
            )

            if not title:
                continue

            if any(
                excluded
                in normalized_title
                for excluded
                in normalized_exclusions
            ):
                continue

            content = (
                self._extract_section_after_heading(
                    heading
                )
            )

            if not content:
                continue

            output.append(
                {
                    "title": title,
                    "content": content,
                }
            )

        return self._deduplicate_objects(
            output,
            key_fields=(
                "title",
                "content",
            ),
        )

    # =========================================================================
    # GENERIC STRUCTURED CONTENT
    # =========================================================================

    def _extract_structured_content(
        self,
        container: Tag,
    ) -> List[Dict[str, Any]]:
        sections: List[Dict[str, Any]] = []

        headings = container.find_all(
            [
                "h2",
                "h3",
                "h4",
                "h5",
                "h6",
            ]
        )

        for heading in headings:
            title = self._element_text(
                heading
            )

            if not title:
                continue

            content = (
                self._extract_section_after_heading(
                    heading
                )
            )

            if not content:
                continue

            sections.append(
                {
                    "title": title,
                    "content": content,
                }
            )

        if not sections:
            content = self._extract_content_text(
                container
            )

            if content:
                sections.append(
                    {
                        "title": "",
                        "content": content,
                    }
                )

        return self._deduplicate_objects(
            sections,
            key_fields=(
                "title",
                "content",
            ),
        )

    def _extract_links(
        self,
        container: Tag,
        base_url: str,
    ) -> List[Dict[str, str]]:
        links: List[Dict[str, str]] = []

        for anchor in container.select(
            "a[href]"
        ):
            href = self._clean_text(
                anchor.get(
                    "href"
                )
            )

            if not href:
                continue

            if href.startswith(
                (
                    "#",
                    "javascript:",
                )
            ):
                continue

            url = urljoin(
                base_url,
                href,
            )

            label = self._element_text(
                anchor
            )

            links.append(
                {
                    "label": label,
                    "url": url,
                }
            )

        return self._deduplicate_objects(
            links,
            key_fields=(
                "url",
            ),
        )

    # =========================================================================
    # SECTION DISCOVERY
    # =========================================================================

    def _find_section_container(
        self,
        soup: BeautifulSoup,
        ids: Iterable[str],
        title_patterns: Iterable[str],
    ) -> Optional[Tag]:
        for element_id in ids:
            element = soup.find(
                id=element_id
            )

            if not element:
                continue

            return self._expand_section_container(
                element
            )

        compiled_patterns = [
            re.compile(
                pattern,
                re.IGNORECASE,
            )
            for pattern
            in title_patterns
        ]

        for heading in soup.find_all(
            [
                "h2",
                "h3",
                "h4",
                "h5",
                "h6",
            ]
        ):
            title = self._element_text(
                heading
            )

            if not any(
                pattern.search(
                    title
                )
                for pattern
                in compiled_patterns
            ):
                continue

            return self._expand_section_container(
                heading
            )

        return None

    def _expand_section_container(
        self,
        element: Tag,
    ) -> Tag:
        if element.name not in {
            "h1",
            "h2",
            "h3",
            "h4",
            "h5",
            "h6",
        }:
            if len(
                self._element_text(
                    element
                )
            ) > 100:
                return element

        current = element

        for _ in range(5):
            parent = current.parent

            if not isinstance(
                parent,
                Tag,
            ):
                break

            parent_text = self._element_text(
                parent
            )

            if (
                len(parent_text)
                > len(
                    self._element_text(
                        current
                    )
                )
            ):
                current = parent

            classes = " ".join(
                current.get(
                    "class",
                    [],
                )
            ).lower()

            if any(
                marker in classes
                for marker in (
                    "block",
                    "section",
                    "card-content",
                    "accordion",
                )
            ):
                break

        return current

    # =========================================================================
    # TEXT HELPERS
    # =========================================================================

    def _extract_section_after_heading(
        self,
        heading: Tag,
    ) -> str:
        content_parts: List[str] = []

        current = (
            heading.next_sibling
        )

        while current is not None:
            if (
                isinstance(
                    current,
                    Tag,
                )
                and current.name
                in {
                    "h1",
                    "h2",
                    "h3",
                    "h4",
                    "h5",
                    "h6",
                }
            ):
                break

            if isinstance(
                current,
                Tag,
            ):
                text = (
                    self._extract_content_text(
                        current
                    )
                )

                if text:
                    content_parts.append(
                        text
                    )

            current = (
                current.next_sibling
            )

        if not content_parts:
            sibling = (
                heading.find_next_sibling()
            )

            if sibling:
                text = (
                    self._extract_content_text(
                        sibling
                    )
                )

                if text:
                    content_parts.append(
                        text
                    )

        return self._clean_text(
            "\n".join(
                content_parts
            )
        )

    def _extract_content_text(
        self,
        element: Optional[Tag],
    ) -> str:
        if not element:
            return ""

        clone = BeautifulSoup(
            str(element),
            "lxml",
        )

        for unwanted in clone.select(
            "script, style, noscript, svg"
        ):
            unwanted.decompose()

        text = clone.get_text(
            "\n",
            strip=True,
        )

        lines = [
            self._clean_text(
                line
            )
            for line
            in text.splitlines()
        ]

        lines = [
            line
            for line
            in lines
            if line
        ]

        return "\n".join(
            self._deduplicate_strings(
                lines
            )
        )

    @staticmethod
    def _element_text(
        element: Optional[Any],
    ) -> str:
        if element is None:
            return ""

        if isinstance(
            element,
            str,
        ):
            value = element
        elif hasattr(
            element,
            "get_text",
        ):
            value = element.get_text(
                " ",
                strip=True,
            )
        else:
            value = str(
                element
            )

        return QSProfileExtractor._clean_text(
            value
        )

    @staticmethod
    def _clean_text(
        value: Any,
    ) -> str:
        if value is None:
            return ""

        text = str(
            value
        )

        text = (
            text
            .replace(
                "\xa0",
                " ",
            )
            .replace(
                "\u200b",
                "",
            )
        )

        text = re.sub(
            r"[ \t]+",
            " ",
            text,
        )

        text = re.sub(
            r"\s*\n\s*",
            "\n",
            text,
        )

        return text.strip()

    @staticmethod
    def _normalize_label(
        value: Any,
    ) -> str:
        text = (
            QSProfileExtractor
            ._clean_text(
                value
            )
            .lower()
        )

        text = text.replace(
            "&",
            " and ",
        )

        text = re.sub(
            r"[^a-z0-9]+",
            " ",
            text,
        )

        return re.sub(
            r"\s+",
            " ",
            text,
        ).strip()

    @staticmethod
    def _to_snake_case(
        value: str,
    ) -> str:
        normalized = (
            QSProfileExtractor
            ._normalize_label(
                value
            )
        )

        return normalized.replace(
            " ",
            "_",
        )

    # =========================================================================
    # NUMERIC HELPERS
    # =========================================================================

    @staticmethod
    def _to_int(
        value: Any,
    ) -> Optional[int]:
        if value is None:
            return None

        if isinstance(
            value,
            bool,
        ):
            return None

        if isinstance(
            value,
            int,
        ):
            return value

        if isinstance(
            value,
            float,
        ):
            return int(
                value
            )

        text = str(
            value
        ).strip()

        match = re.search(
            r"-?\d[\d,\s]*",
            text,
        )

        if not match:
            return None

        cleaned = re.sub(
            r"[,\s]",
            "",
            match.group(0),
        )

        try:
            return int(
                cleaned
            )
        except ValueError:
            return None

    @staticmethod
    def _to_float(
        value: Any,
    ) -> Optional[float]:
        if value is None:
            return None

        if isinstance(
            value,
            bool,
        ):
            return None

        if isinstance(
            value,
            (int, float),
        ):
            return float(
                value
            )

        text = str(
            value
        ).strip()

        match = re.search(
            r"-?\d[\d,\s]*(?:\.\d+)?",
            text,
        )

        if not match:
            return None

        cleaned = re.sub(
            r"[,\s]",
            "",
            match.group(0),
        )

        try:
            return float(
                cleaned
            )
        except ValueError:
            return None

    def _parse_numeric_value(
        self,
        value: Any,
    ) -> Optional[float | int]:
        if not value:
            return None

        number = self._to_float(
            value
        )

        if number is None:
            return None

        if number.is_integer():
            return int(
                number
            )

        return number

    @staticmethod
    def _extract_leading_value(
        text: str,
    ) -> str:
        match = re.match(
            r"""
            ^\s*
            (?P<value>
                \#?\s*
                =?
                \d[\d,.\s]*
                (?:%)?
            )
            """,
            text,
            flags=re.VERBOSE,
        )

        if not match:
            return ""

        return re.sub(
            r"\s+",
            " ",
            match.group(
                "value"
            ),
        ).strip()

    def _remove_leading_value(
        self,
        text: str,
    ) -> str:
        return re.sub(
            r"""
            ^\s*
            \#?\s*
            =?
            \d[\d,.\s]*
            (?:%)?
            \s*
            """,
            "",
            text,
            count=1,
            flags=re.VERBOSE,
        ).strip()

    def _find_badge_percentage(
        self,
        badges: List[Dict[str, Any]],
        label_pattern: str,
    ) -> Optional[float]:
        pattern = re.compile(
            label_pattern,
            re.IGNORECASE,
        )

        for badge in badges:
            label = self._clean_text(
                badge.get(
                    "label"
                )
            )

            if not pattern.search(
                label
            ):
                continue

            display_value = (
                badge.get(
                    "display_value"
                )
            )

            if (
                display_value
                and "%"
                in str(
                    display_value
                )
            ):
                return self._to_float(
                    display_value
                )

        return None

    # =========================================================================
    # RANK HELPERS
    # =========================================================================

    def _parse_rank(
        self,
        raw_rank: str,
    ) -> Dict[str, Any]:
        cleaned = (
            raw_rank
            .replace(
                "#",
                "",
            )
            .strip()
        )

        is_tied = cleaned.startswith(
            "="
        )

        cleaned_without_tie = (
            cleaned.lstrip(
                "="
            )
        )

        range_match = re.fullmatch(
            r"(\d+)-(\d+)",
            cleaned_without_tie,
        )

        if range_match:
            minimum = int(
                range_match.group(1)
            )

            maximum = int(
                range_match.group(2)
            )

            return {
                "numeric_rank": minimum,
                "rank_minimum": minimum,
                "rank_maximum": maximum,
                "is_tied": is_tied,
                "is_range": True,
            }

        numeric_rank = self._to_int(
            cleaned_without_tie
        )

        return {
            "numeric_rank": numeric_rank,
            "rank_minimum": None,
            "rank_maximum": None,
            "is_tied": is_tied,
            "is_range": False,
        }

    # =========================================================================
    # URL HELPERS
    # =========================================================================

    @staticmethod
    def _normalize_profile_url(
        profile_url: str,
    ) -> str:
        profile_url = (
            profile_url.strip()
        )

        if not profile_url.startswith(
            (
                "http://",
                "https://",
            )
        ):
            profile_url = (
                "https://"
                + profile_url
            )

        return profile_url

    @staticmethod
    def _extract_slug(
        profile_url: str,
    ) -> str:
        path = urlparse(
            profile_url
        ).path.rstrip(
            "/"
        )

        slug = path.split(
            "/"
        )[-1]

        return (
            slug
            or "unknown-university"
        )

    @staticmethod
    def _slug_to_name(
        slug: str,
    ) -> str:
        return (
            slug
            .replace(
                "-",
                " ",
            )
            .strip()
            .title()
        )

    @staticmethod
    def _normalize_url(
        value: str,
    ) -> str:
        value = (
            QSProfileExtractor
            ._clean_text(
                value
            )
        )

        if not value:
            return ""

        value = (
            value
            .replace(
                "\\/",
                "/",
            )
            .replace(
                "\\u0026",
                "&",
            )
        )

        if value.startswith(
            "//"
        ):
            return (
                "https:"
                + value
            )

        if value.startswith(
            "/"
        ):
            return urljoin(
                QS_BASE_URL,
                value,
            )

        return value

    @staticmethod
    def _normalize_external_url(
        value: str,
    ) -> str:
        value = (
            QSProfileExtractor
            ._clean_text(
                value
            )
        )

        if not value:
            return ""

        value = value.strip(
            " \t\r\n\"'"
        )

        if value.startswith(
            "//"
        ):
            return (
                "https:"
                + value
            )

        if value.startswith(
            (
                "http://",
                "https://",
            )
        ):
            return value

        if re.match(
            r"^(www\.)?[a-z0-9.-]+\.[a-z]{2,}",
            value,
            flags=re.IGNORECASE,
        ):
            return (
                "https://"
                + value
            )

        return value

    def _extract_same_as_urls(
        self,
        university_json_ld: Dict[str, Any],
    ) -> List[str]:
        output: List[str] = []

        for value in self._ensure_list(
            university_json_ld.get(
                "sameAs"
            )
        ):
            url = self._extract_url_value(
                value
            )

            if url:
                output.append(
                    url
                )

        return output

    @staticmethod
    def _extract_url_value(
        value: Any,
    ) -> str:
        if isinstance(
            value,
            str,
        ):
            return value

        if isinstance(
            value,
            dict,
        ):
            for field_name in (
                "url",
                "contentUrl",
                "@id",
            ):
                field_value = value.get(
                    field_name
                )

                if isinstance(
                    field_value,
                    str,
                ):
                    return field_value

        return ""

    def _detect_social_platform(
        self,
        url: str,
    ) -> Optional[str]:
        lower_url = url.lower()

        for (
            platform,
            domains,
        ) in SOCIAL_DOMAINS.items():
            if any(
                domain
                in lower_url
                for domain
                in domains
            ):
                return platform

        return None

    @staticmethod
    def _is_qs_social_url(
        url: str,
    ) -> bool:
        lower_url = url.lower()

        return any(
            marker
            in lower_url
            for marker
            in QS_OWN_SOCIAL_MARKERS
        )

    # =========================================================================
    # IMAGE HELPERS
    # =========================================================================

    def _extract_image_source(
        self,
        image: Tag,
    ) -> str:
        for attribute in (
            "src",
            "data-src",
            "data-original",
            "data-lazy-src",
        ):
            value = image.get(
                attribute
            )

            if value:
                return value

        srcset = (
            image.get(
                "srcset"
            )
            or image.get(
                "data-srcset"
            )
        )

        if srcset:
            first_item = (
                srcset
                .split(",")[0]
                .strip()
                .split(" ")[0]
            )

            return first_item

        return ""

    @staticmethod
    def _looks_like_university_image(
        url: str,
    ) -> bool:
        lower_url = url.lower()

        if any(
            marker
            in lower_url
            for marker
            in IGNORED_IMAGE_MARKERS
        ):
            return False

        if (
            "/profiles-slideshow/"
            in lower_url
        ):
            return True

        if (
            "/profiles/logos/"
            in lower_url
        ):
            return True

        parsed_path = urlparse(
            lower_url
        ).path

        return parsed_path.endswith(
            IMAGE_EXTENSIONS
        )

    # =========================================================================
    # COST HELPERS
    # =========================================================================

    @staticmethod
    def _extract_currency_symbol(
        value: str,
    ) -> Optional[str]:
        symbols = (
            "$",
            "€",
            "£",
            "¥",
            "₹",
            "₩",
            "₽",
            "₺",
            "₫",
        )

        for symbol in symbols:
            if symbol in value:
                return symbol

        code_match = re.search(
            r"\b(USD|EUR|GBP|INR|JPY|CAD|AUD|CHF)\b",
            value,
            flags=re.IGNORECASE,
        )

        if code_match:
            return code_match.group(
                1
            ).upper()

        return None

    @staticmethod
    def _currency_code_from_symbol(
        symbol: Optional[str],
    ) -> Optional[str]:
        mapping = {
            "$": "USD",
            "€": "EUR",
            "£": "GBP",
            "¥": "JPY",
            "₹": "INR",
            "₩": "KRW",
            "₽": "RUB",
            "₺": "TRY",
            "₫": "VND",
        }

        if not symbol:
            return None

        if len(
            symbol
        ) == 3:
            return symbol.upper()

        return mapping.get(
            symbol
        )

    def _extract_cost_period(
        self,
        container: Tag,
    ) -> Optional[str]:
        text = self._element_text(
            container
        ).lower()

        patterns = {
            "per year": (
                r"\bper year\b",
                r"\bannually\b",
                r"\bannual\b",
            ),
            "per month": (
                r"\bper month\b",
                r"\bmonthly\b",
            ),
            "per week": (
                r"\bper week\b",
                r"\bweekly\b",
            ),
        }

        for (
            period,
            period_patterns,
        ) in patterns.items():
            if any(
                re.search(
                    pattern,
                    text,
                )
                for pattern
                in period_patterns
            ):
                return period

        return None

    # =========================================================================
    # GENERAL HELPERS
    # =========================================================================

    @staticmethod
    def _safe_json_loads(
        value: str,
    ) -> Optional[Any]:
        try:
            return json.loads(
                value
            )
        except json.JSONDecodeError:
            cleaned = (
                value
                .strip()
                .rstrip(
                    ";"
                )
            )

            try:
                return json.loads(
                    cleaned
                )
            except json.JSONDecodeError:
                return None

    @staticmethod
    def _ensure_list(
        value: Any,
    ) -> List[Any]:
        if value is None:
            return []

        if isinstance(
            value,
            list,
        ):
            return value

        return [
            value
        ]

    @staticmethod
    def _extract_country_name(
        value: Any,
    ) -> str:
        if isinstance(
            value,
            str,
        ):
            return (
                QSProfileExtractor
                ._clean_text(
                    value
                )
            )

        if isinstance(
            value,
            dict,
        ):
            return (
                QSProfileExtractor
                ._clean_text(
                    value.get(
                        "name"
                    )
                    or value.get(
                        "@id"
                    )
                )
            )

        return ""

    def _deduplicate_strings(
        self,
        values: Iterable[str],
        case_sensitive: bool = True,
    ) -> List[str]:
        output: List[str] = []
        seen: Set[str] = set()

        for value in values:
            cleaned = self._clean_text(
                value
            )

            if not cleaned:
                continue

            key = (
                cleaned
                if case_sensitive
                else cleaned.lower()
            )

            if key in seen:
                continue

            seen.add(key)
            output.append(
                cleaned
            )

        return output

    def _deduplicate_objects(
        self,
        values: List[Dict[str, Any]],
        key_fields: Iterable[str],
    ) -> List[Dict[str, Any]]:
        output: List[Dict[str, Any]] = []

        seen: Set[
            tuple[Any, ...]
        ] = set()

        for value in values:
            cleaned_value = (
                self._remove_internal_empty_values(
                    value
                )
            )

            key_parts = []

            for field_name in key_fields:
                field_value = (
                    self._get_nested_value(
                        cleaned_value,
                        field_name,
                    )
                )

                if isinstance(
                    field_value,
                    str,
                ):
                    field_value = (
                        field_value
                        .strip()
                        .lower()
                    )

                key_parts.append(
                    field_value
                )

            key = tuple(
                key_parts
            )

            if (
                not any(
                    part not in (
                        None,
                        "",
                        [],
                        {},
                    )
                    for part
                    in key
                )
            ):
                continue

            if key in seen:
                continue

            seen.add(key)

            output.append(
                cleaned_value
            )

        return output

    @staticmethod
    def _get_nested_value(
        data: Dict[str, Any],
        path: str,
    ) -> Any:
        current: Any = data

        for part in path.split(
            "."
        ):
            if not isinstance(
                current,
                dict,
            ):
                return None

            current = current.get(
                part
            )

        return current

    def _remove_internal_empty_values(
        self,
        value: Any,
    ) -> Any:
        """
        Remove empty optional values from nested structures while preserving
        important empty collections such as rankings and cost items.
        """

        if isinstance(
            value,
            dict,
        ):
            output = {}

            for key, item in value.items():
                cleaned_item = (
                    self._remove_internal_empty_values(
                        item
                    )
                )

                if cleaned_item is None:
                    continue

                if (
                    cleaned_item == ""
                    and key
                    not in {
                        "description",
                        "overview",
                    }
                ):
                    continue

                output[key] = (
                    cleaned_item
                )

            return output

        if isinstance(
            value,
            list,
        ):
            return [
                self._remove_internal_empty_values(
                    item
                )
                for item
                in value
                if item is not None
            ]

        return value

    def _count_non_empty(
        self,
        value: Dict[str, Any],
    ) -> int:
        return sum(
            1
            for item
            in value.values()
            if item
            not in (
                None,
                "",
                [],
                {},
            )
        )