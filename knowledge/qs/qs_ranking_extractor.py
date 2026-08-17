from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from bs4 import BeautifulSoup
from curl_cffi import requests as curl_requests


class QSRankingExtractor:
    """
    Extract ranking information from QS TopUniversities
    Drupal AJAX ranking endpoints.

    Pipeline:

        profile_data.json
                ↓
        discovered ranking endpoints
                ↓
        download every AJAX response
                ↓
        preserve raw responses
                ↓
        extract HTML fragments
                ↓
        parse ranking information
                ↓
        rankings_data.json
    """

    BASE_URL = "https://www.topuniversities.com"

    DEFAULT_HEADERS = {
        "Accept": (
            "application/json, text/javascript, "
            "*/*; q=0.01"
        ),
        "Accept-Language": (
            "en-US,en;q=0.9"
        ),
        "Referer": (
            "https://www.topuniversities.com/"
        ),
        "X-Requested-With": (
            "XMLHttpRequest"
        ),
    }

    # Ranking values supported:
    #
    # 61
    # #61
    # =61
    # #=61
    # 51-100
    # 51–100
    # 51+
    #
    RANK_PATTERN = re.compile(
        r"""
        (?:
            \#?
            =?
            \s*
            \d{1,4}
            (?:
                \s*
                [-–—]
                \s*
                \d{1,4}
            )?
            \+?
        )
        """,
        re.VERBOSE,
    )

    YEAR_PATTERN = re.compile(
        r"\b(?:19|20)\d{2}\b"
    )

    SCORE_PATTERN = re.compile(
        r"""
        (?:
            score
            |
            overall
            |
            points?
        )
        \s*
        [:]?
        \s*
        (?P<score>
            \d{
                1,
                3
            }
            (?:
                \.\d+
            )?
        )
        """,
        re.IGNORECASE | re.VERBOSE,
    )

    def __init__(
        self,
        timeout: int = 45,
        output_directory: str | Path = "data/qs",
        save_raw_responses: bool = True,
    ) -> None:

        self.timeout = timeout

        self.output_directory = Path(
            output_directory
        )

        self.save_raw_responses = (
            save_raw_responses
        )

    # ========================================================
    # PUBLIC API
    # ========================================================

    def extract_from_profile_file(
        self,
        profile_file: str | Path,
    ) -> Dict[str, Any]:
        """
        Load profile_data.json and extract all rankings
        from its discovered ranking endpoints.
        """

        profile_file = Path(
            profile_file
        )

        if not profile_file.exists():

            raise FileNotFoundError(
                "QS profile data file was not found: "
                f"{profile_file}"
            )

        with profile_file.open(
            "r",
            encoding="utf-8",
        ) as file:

            profile_data = json.load(
                file
            )

        return self.extract(
            profile_data=profile_data
        )

    def extract(
        self,
        profile_data: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Extract ranking information from all ranking
        endpoints discovered by QSProfileExtractor.
        """

        source = profile_data.get(
            "source",
            {}
        )

        identifiers = profile_data.get(
            "identifiers",
            {}
        )

        university = profile_data.get(
            "university",
            {}
        )

        ranking_data = profile_data.get(
            "ranking",
            {}
        )

        endpoints = ranking_data.get(
            "discovered_endpoints",
            []
        )

        university_slug = source.get(
            "university_slug"
        )

        if not university_slug:

            raise ValueError(
                "University slug is missing from "
                "profile data."
            )

        if not isinstance(
            endpoints,
            list,
        ):

            raise TypeError(
                "'discovered_endpoints' must be "
                "a list."
            )

        if not endpoints:
            print("  [WARN] No QS ranking endpoints were found in profile data.")
            return {"rankings": []}

        unique_endpoints = (
            self._deduplicate_endpoints(
                endpoints
            )
        )

        rankings = []

        failed_endpoints = []

        for endpoint_index, endpoint in enumerate(
            unique_endpoints,
            start=1,
        ):

            ranking_id = endpoint.get(
                "ranking_id"
            )

            endpoint_url = endpoint.get(
                "url"
            )

            if not endpoint_url:

                failed_endpoints.append(
                    {
                        "ranking_id": (
                            ranking_id
                        ),
                        "url": None,
                        "error": (
                            "Ranking endpoint URL "
                            "is missing."
                        ),
                    }
                )

                continue

            try:

                raw_response = (
                    self.fetch_ranking_endpoint(
                        endpoint_url=(
                            endpoint_url
                        ),
                        profile_url=(
                            source.get(
                                "profile_url"
                            )
                        ),
                    )
                )

                if self.save_raw_responses:

                    self.save_raw_response(
                        raw_response=(
                            raw_response
                        ),
                        university_slug=(
                            university_slug
                        ),
                        ranking_id=(
                            ranking_id
                        ),
                        endpoint_index=(
                            endpoint_index
                        ),
                    )

                parsed_ranking = (
                    self.parse_ranking_response(
                        raw_response=(
                            raw_response
                        ),
                        endpoint=endpoint,
                    )
                )

                rankings.append(
                    parsed_ranking
                )

            except Exception as error:

                failed_endpoints.append(
                    {
                        "ranking_id": (
                            ranking_id
                        ),
                        "url": (
                            endpoint_url
                        ),
                        "error": (
                            f"{type(error).__name__}: "
                            f"{error}"
                        ),
                    }
                )

        result = {
            "source": {
                "provider": (
                    source.get(
                        "provider",
                        "QS TopUniversities",
                    )
                ),
                "profile_url": (
                    source.get(
                        "profile_url"
                    )
                ),
                "university_slug": (
                    university_slug
                ),
            },
            "identifiers": {
                "qs_profile_id": (
                    identifiers.get(
                        "qs_profile_id"
                    )
                ),
                "drupal_node_id": (
                    identifiers.get(
                        "drupal_node_id"
                    )
                ),
            },
            "university": {
                "name": (
                    university.get(
                        "name"
                    )
                ),
            },
            "rankings": rankings,
            "extraction": {
                "endpoints_discovered": (
                    len(endpoints)
                ),
                "unique_endpoints": (
                    len(unique_endpoints)
                ),
                "endpoints_processed": (
                    len(rankings)
                ),
                "endpoints_failed": (
                    len(
                        failed_endpoints
                    )
                ),
                "ranking_records_found": (
                    sum(
                        len(
                            ranking.get(
                                "ranking_history",
                                []
                            )
                        )
                        for ranking
                        in rankings
                    )
                ),
                "failed_endpoints": (
                    failed_endpoints
                ),
                "extracted_at": (
                    datetime.now(
                        timezone.utc
                    ).isoformat()
                ),
            },
        }

        return result

    # ========================================================
    # HTTP
    # ========================================================

    def fetch_ranking_endpoint(
        self,
        endpoint_url: str,
        profile_url: Optional[str] = None,
    ) -> str:
        """
        Download a QS Drupal AJAX ranking response.

        curl_cffi is used because normal requests may
        receive HTTP 403 from QS.
        """

        headers = dict(
            self.DEFAULT_HEADERS
        )

        if profile_url:

            headers["Referer"] = (
                profile_url
            )

        response = curl_requests.get(
            endpoint_url,
            headers=headers,
            impersonate="chrome",
            timeout=self.timeout,
            allow_redirects=True,
        )

        if response.status_code != 200:

            preview = (
                response.text[:500]
                .replace(
                    "\n",
                    " "
                )
            )

            raise RuntimeError(
                "\n"
                "QS ranking request failed.\n"
                f"URL: {endpoint_url}\n"
                f"HTTP status: "
                f"{response.status_code}\n"
                f"Response preview: "
                f"{preview}"
            )

        return response.text

    # ========================================================
    # RESPONSE PARSING
    # ========================================================

    def parse_ranking_response(
        self,
        raw_response: str,
        endpoint: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Parse one QS Drupal AJAX ranking response.

        Ranking history is read from QS json_data first
        because it is cleaner and more reliable than
        repeatedly parsing the rendered HTML.
        """

        response_data = self._load_response_json(
            raw_response
        )

        html_fragments = self._extract_html_fragments(
            response_data
        )

        combined_html = "\n".join(
            html_fragments
        )

        soup = BeautifulSoup(
            combined_html,
            "lxml",
        )

        ranking_id = endpoint.get(
            "ranking_id"
        )

        ranking_name = self._resolve_ranking_name(
            ranking_id=ranking_id,
            soup=soup,
        )

        ranking_history = (
            self._extract_history_from_json_data(
                response_data
            )
        )

        # HTML fallback for QS responses that do not
        # contain settings.qs_profiles.json_data.
        if not ranking_history:

            ranking_history = (
                self._extract_ranking_history(
                    soup
                )
            )

        ranking_history = [
            record
            for record in ranking_history
            if record.get("year") is not None
        ]

        ranking_history = (
            self._deduplicate_history(
                ranking_history
            )
        )

        criteria = (
            self._extract_qs_progress_criteria(
                soup
            )
        )

        # Generic fallback for alternative QS layouts.
        if not criteria:

            criteria = (
                self._extract_criteria(
                    soup
                )
            )

        current_ranking = (
            self._select_current_ranking(
                ranking_history
            )
        )

        overall_score = None

        for criterion in criteria:

            if (
                str(
                    criterion.get(
                        "name",
                        ""
                    )
                ).strip().lower()
                == "overall"
            ):

                overall_score = (
                    criterion.get(
                        "score"
                    )
                )

                break

        if (
            current_ranking
            and overall_score is not None
        ):

            current_ranking = dict(
                current_ranking
            )

            current_ranking[
                "score"
            ] = overall_score

        return {
            "ranking_id": ranking_id,
            "profile_id": endpoint.get(
                "profile_id"
            ),
            "offset": endpoint.get(
                "offset"
            ),
            "endpoint_url": endpoint.get(
                "url"
            ),
            "ranking_name": ranking_name,
            "current_ranking": (
                current_ranking
            ),
            "overall_score": (
                overall_score
            ),
            "ranking_history": (
                ranking_history
            ),
            "criteria": criteria,
            "extraction": {
                "html_fragments_found": (
                    len(
                        html_fragments
                    )
                ),
                "ranking_records_found": (
                    len(
                        ranking_history
                    )
                ),
                "criteria_found": (
                    len(
                        criteria
                    )
                ),
                "history_source": (
                    "qs_json_data"
                    if self._extract_history_from_json_data(
                        response_data
                    )
                    else "html"
                ),
            },
        }
    
    def _extract_history_from_json_data(
        self,
        response_data: Any,
    ) -> List[Dict[str, Any]]:
        """
        Extract clean ranking history from:

        settings
            → qs_profiles
            → json_data

        Example:

        {
            "x": 2027,
            "y": 61,
            "r": "61"
        }
        """

        history = []

        def walk(
            value: Any,
        ) -> None:

            if isinstance(
                value,
                dict,
            ):

                json_data = value.get(
                    "json_data"
                )

                if isinstance(
                    json_data,
                    list,
                ):

                    for item in json_data:

                        if not isinstance(
                            item,
                            dict,
                        ):

                            continue

                        year = item.get(
                            "x"
                        )

                        numeric_rank = item.get(
                            "y"
                        )

                        display_rank = (
                            item.get(
                                "r"
                            )
                        )

                        if year is None:

                            continue

                        if (
                            display_rank is None
                            and numeric_rank is None
                        ):

                            continue

                        if display_rank is None:

                            display_rank = str(
                                numeric_rank
                            )

                        display_rank = (
                            str(
                                display_rank
                            ).strip()
                        )

                        if not display_rank.startswith(
                            "#"
                        ):

                            display_rank = (
                                f"#{display_rank}"
                            )

                        history.append(
                            self._build_rank_record(
                                year=year,
                                rank=display_rank,
                            )
                        )

                for nested_value in (
                    value.values()
                ):

                    walk(
                        nested_value
                    )

            elif isinstance(
                value,
                list,
            ):

                for item in value:

                    walk(
                        item
                    )

        walk(
            response_data
        )

        return self._deduplicate_history(
            history
        )
    
    def _extract_qs_progress_criteria(
        self,
        soup: BeautifulSoup,
    ) -> List[Dict[str, Any]]:
        """
        Extract QS ranking criteria from progress cards.

        Example:

        <div class="progress-container">
            <div class="progress-title">
                Academic Reputation
            </div>

            <div
                class="progress-bar"
                data-progress="97.3">
            </div>

            <div class="progress-score">
                97.3
            </div>
        </div>
        """

        criteria = []

        seen = set()

        for container in soup.select(
            ".progress-container"
        ):

            title_element = (
                container.select_one(
                    ".progress-title"
                )
            )

            score_element = (
                container.select_one(
                    ".progress-score"
                )
            )

            progress_element = (
                container.select_one(
                    "[data-progress]"
                )
            )

            if not title_element:

                continue

            name = self._clean_text(
                title_element.get_text(
                    " ",
                    strip=True,
                )
            )

            score = None

            if score_element:

                score = self._to_number(
                    score_element.get_text(
                        " ",
                        strip=True,
                    )
                )

            if (
                score is None
                and progress_element
            ):

                score = self._to_number(
                    progress_element.get(
                        "data-progress"
                    )
                )

            if not name:

                continue

            duplicate_key = (
                name.lower(),
                score,
            )

            if duplicate_key in seen:

                continue

            seen.add(
                duplicate_key
            )

            criteria.append(
                {
                    "name": name,
                    "score": score,
                }
            )

        return criteria
    
    def _resolve_ranking_name(
        self,
        ranking_id: Any,
        soup: BeautifulSoup,
    ) -> Optional[str]:
        """
        Resolve known QS ranking products.

        QS AJAX responses often show only
        'Ranking criteria', not the ranking name.
        """

        known_rankings = {
            513: (
                "QS World University Rankings"
            ),
            4085: (
                "QS Sustainability Rankings"
            ),
            4093: (
                "QS Europe University Rankings"
            ),
        }

        try:

            normalized_id = int(
                ranking_id
            )

        except (
            TypeError,
            ValueError,
        ):

            normalized_id = None

        if normalized_id in known_rankings:

            return known_rankings[
                normalized_id
            ]

        extracted_name = (
            self._extract_ranking_name(
                soup=soup,
                response_data={},
            )
        )

        if extracted_name:

            normalized_name = (
                extracted_name
                .strip()
                .lower()
            )

            generic_names = {
                "ranking criteria",
                "rankings",
                "ranking",
            }

            if (
                normalized_name
                not in generic_names
            ):

                return extracted_name

        return (
            f"QS Ranking {ranking_id}"
            if ranking_id is not None
            else "QS Ranking"
        )

    def _load_response_json(
        self,
        raw_response: str,
    ) -> Any:
        """
        Load the Drupal AJAX response.

        QS normally returns JSON, but raw HTML is
        accepted as a fallback.
        """

        try:

            return json.loads(
                raw_response
            )

        except json.JSONDecodeError:

            return {
                "html": raw_response
            }

    def _extract_html_fragments(
        self,
        response_data: Any,
    ) -> List[str]:
        """
        Recursively collect HTML fragments from the
        Drupal AJAX response.

        Drupal responses often contain commands such as:

        {
            "command": "insert",
            "data": "<div>...</div>"
        }
        """

        fragments = []

        seen = set()

        def add_fragment(
            value: str,
        ) -> None:

            cleaned_value = (
                value.strip()
            )

            if not cleaned_value:

                return

            if not self._looks_like_html(
                cleaned_value
            ):

                return

            if cleaned_value in seen:

                return

            seen.add(
                cleaned_value
            )

            fragments.append(
                cleaned_value
            )

        def walk(
            value: Any,
        ) -> None:

            if isinstance(
                value,
                dict,
            ):

                preferred_keys = (
                    "data",
                    "html",
                    "content",
                    "markup",
                )

                for key in preferred_keys:

                    item = value.get(
                        key
                    )

                    if isinstance(
                        item,
                        str,
                    ):

                        add_fragment(
                            item
                        )

                for nested_value in (
                    value.values()
                ):

                    walk(
                        nested_value
                    )

            elif isinstance(
                value,
                list,
            ):

                for item in value:

                    walk(
                        item
                    )

            elif isinstance(
                value,
                str,
            ):

                add_fragment(
                    value
                )

        walk(
            response_data
        )

        return fragments

    def _looks_like_html(
        self,
        value: str,
    ) -> bool:

        return bool(
            re.search(
                r"<[a-zA-Z][^>]*>",
                value,
            )
        )

    # ========================================================
    # RANKING NAME
    # ========================================================

    def _extract_ranking_name(
        self,
        soup: BeautifulSoup,
        response_data: Any,
    ) -> Optional[str]:
        """
        Extract the ranking product name from headings,
        labels, attributes, or response metadata.
        """

        selectors = [
            "[data-ranking-name]",
            ".ranking-name",
            ".rank-title",
            ".ranking-title",
            ".field--name-title",
            "h1",
            "h2",
            "h3",
            "h4",
        ]

        candidates = []

        for selector in selectors:

            for element in soup.select(
                selector
            ):

                attribute_value = (
                    element.get(
                        "data-ranking-name"
                    )
                )

                if attribute_value:

                    candidates.append(
                        attribute_value
                    )

                text = (
                    element.get_text(
                        " ",
                        strip=True,
                    )
                )

                if text:

                    candidates.append(
                        text
                    )

        response_strings = (
            self._collect_strings(
                response_data
            )
        )

        candidates.extend(
            response_strings
        )

        for candidate in candidates:

            cleaned = (
                self._clean_text(
                    candidate
                )
            )

            lower = (
                cleaned.lower()
            )

            if (
                "ranking" in lower
                or "rankings" in lower
            ):

                if len(
                    cleaned
                ) <= 250:

                    return cleaned

        return None

    # ========================================================
    # RANKING HISTORY
    # ========================================================

    def _extract_ranking_history(
        self,
        soup: BeautifulSoup,
    ) -> List[Dict[str, Any]]:
        """
        Extract ranking history from tables, cards,
        lists, and embedded text.
        """

        records = []

        records.extend(
            self._extract_history_from_tables(
                soup
            )
        )

        records.extend(
            self._extract_history_from_elements(
                soup
            )
        )

        records.extend(
            self._extract_history_from_text(
                soup
            )
        )

        return self._deduplicate_history(
            records
        )

    def _extract_history_from_tables(
        self,
        soup: BeautifulSoup,
    ) -> List[Dict[str, Any]]:

        records = []

        for table in soup.find_all(
            "table"
        ):

            headers = [
                self._clean_text(
                    cell.get_text(
                        " ",
                        strip=True,
                    )
                ).lower()
                for cell
                in table.select(
                    "thead th"
                )
            ]

            rows = table.select(
                "tbody tr"
            )

            if not rows:

                rows = table.find_all(
                    "tr"
                )

            for row in rows:

                cells = [
                    self._clean_text(
                        cell.get_text(
                            " ",
                            strip=True,
                        )
                    )
                    for cell
                    in row.find_all(
                        [
                            "th",
                            "td",
                        ]
                    )
                ]

                if not cells:

                    continue

                row_text = " | ".join(
                    cells
                )

                record = (
                    self._parse_history_text(
                        row_text
                    )
                )

                if record:

                    if headers:

                        record[
                            "table_headers"
                        ] = headers

                    records.append(
                        record
                    )

        return records

    def _extract_history_from_elements(
        self,
        soup: BeautifulSoup,
    ) -> List[Dict[str, Any]]:

        records = []

        selectors = [
            "[data-rank]",
            "[data-ranking]",
            "[data-year]",
            ".rank",
            ".ranking",
            ".ranking-item",
            ".rank-item",
            ".ranking-history",
            ".rank-history",
            ".views-row",
        ]

        seen_text = set()

        for selector in selectors:

            for element in soup.select(
                selector
            ):

                text = (
                    self._clean_text(
                        element.get_text(
                            " ",
                            strip=True,
                        )
                    )
                )

                if (
                    not text
                    or text in seen_text
                ):

                    continue

                seen_text.add(
                    text
                )

                year = (
                    element.get(
                        "data-year"
                    )
                )

                rank = (
                    element.get(
                        "data-rank"
                    )
                    or element.get(
                        "data-ranking"
                    )
                )

                if rank:

                    record = (
                        self._build_rank_record(
                            year=year,
                            rank=rank,
                            source_text=text,
                        )
                    )

                else:

                    record = (
                        self._parse_history_text(
                            text
                        )
                    )

                if record:

                    records.append(
                        record
                    )

        return records

    def _extract_history_from_text(
        self,
        soup: BeautifulSoup,
    ) -> List[Dict[str, Any]]:

        records = []

        text_blocks = []

        for element in soup.find_all(
            [
                "li",
                "p",
                "div",
                "span",
            ]
        ):

            text = (
                self._clean_text(
                    element.get_text(
                        " ",
                        strip=True,
                    )
                )
            )

            if not text:

                continue

            if len(text) > 500:

                continue

            text_blocks.append(
                text
            )

        seen = set()

        for text in text_blocks:

            if text in seen:

                continue

            seen.add(
                text
            )

            record = (
                self._parse_history_text(
                    text
                )
            )

            if record:

                records.append(
                    record
                )

        return records

    def _parse_history_text(
        self,
        text: str,
    ) -> Optional[Dict[str, Any]]:

        cleaned_text = (
            self._clean_text(
                text
            )
        )

        year_match = (
            self.YEAR_PATTERN.search(
                cleaned_text
            )
        )

        rank_match = (
            self._find_rank_value(
                cleaned_text
            )
        )

        if not rank_match:

            return None

        year = None

        if year_match:

            year = int(
                year_match.group()
            )

        rank = (
            rank_match
        )

        # Prevent the year itself from being interpreted
        # as the rank.
        if (
            year is not None
            and self._strip_rank_symbols(
                rank
            ) == str(year)
        ):

            remaining_text = (
                cleaned_text.replace(
                    year_match.group(),
                    " ",
                    1,
                )
            )

            rank = (
                self._find_rank_value(
                    remaining_text
                )
            )

            if not rank:

                return None

        return self._build_rank_record(
            year=year,
            rank=rank,
            source_text=cleaned_text,
        )

    def _find_rank_value(
        self,
        text: str,
    ) -> Optional[str]:

        rank_keywords = [
            "rank",
            "ranking",
            "position",
        ]

        lower = text.lower()

        for keyword in rank_keywords:

            position = lower.find(
                keyword
            )

            if position == -1:

                continue

            nearby_text = text[
                position:
                position + 100
            ]

            match = (
                self.RANK_PATTERN.search(
                    nearby_text
                )
            )

            if match:

                return self._clean_rank(
                    match.group()
                )

        # Fallback:
        # Find values after removing years.
        without_years = (
            self.YEAR_PATTERN.sub(
                " ",
                text,
            )
        )

        match = (
            self.RANK_PATTERN.search(
                without_years
            )
        )

        if not match:

            return None

        return self._clean_rank(
            match.group()
        )

    def _build_rank_record(
        self,
        year: Any,
        rank: Any,
        source_text: Optional[str] = None,
    ) -> Dict[str, Any]:

        rank_text = (
            self._clean_rank(
                str(rank)
            )
        )

        normalized_year = (
            self._normalize_year(
                year
            )
        )

        rank_details = (
            self._parse_rank_details(
                rank_text
            )
        )

        score = (
            self._extract_score(
                source_text
            )
            if source_text
            else None
        )

        return {
            "year": (
                normalized_year
            ),
            "rank": (
                rank_text
            ),
            "rank_numeric": (
                rank_details.get(
                    "rank_numeric"
                )
            ),
            "rank_min": (
                rank_details.get(
                    "rank_min"
                )
            ),
            "rank_max": (
                rank_details.get(
                    "rank_max"
                )
            ),
            "is_tied": (
                rank_details.get(
                    "is_tied",
                    False,
                )
            ),
            "is_range": (
                rank_details.get(
                    "is_range",
                    False,
                )
            ),
            "score": (
                score
            ),
        }

    def _parse_rank_details(
        self,
        rank: str,
    ) -> Dict[str, Any]:

        cleaned = (
            rank.strip()
        )

        is_tied = (
            "=" in cleaned
        )

        numeric_values = [
            int(value)
            for value
            in re.findall(
                r"\d+",
                cleaned,
            )
        ]

        is_range = (
            bool(
                re.search(
                    r"[-–—]",
                    cleaned,
                )
            )
            and len(
                numeric_values
            ) >= 2
        )

        rank_numeric = None

        rank_min = None

        rank_max = None

        if is_range:

            rank_min = (
                numeric_values[0]
            )

            rank_max = (
                numeric_values[1]
            )

        elif numeric_values:

            rank_numeric = (
                numeric_values[0]
            )

        return {
            "rank_numeric": (
                rank_numeric
            ),
            "rank_min": (
                rank_min
            ),
            "rank_max": (
                rank_max
            ),
            "is_tied": (
                is_tied
            ),
            "is_range": (
                is_range
            ),
        }

    def _select_current_ranking(
        self,
        history: List[
            Dict[str, Any]
        ],
    ) -> Optional[Dict[str, Any]]:

        if not history:

            return None

        records_with_year = [
            record
            for record
            in history
            if isinstance(
                record.get(
                    "year"
                ),
                int,
            )
        ]

        if records_with_year:

            return max(
                records_with_year,
                key=lambda item: (
                    item["year"]
                ),
            )

        return history[0]

    # ========================================================
    # CRITERIA
    # ========================================================

    def _extract_criteria(
        self,
        soup: BeautifulSoup,
    ) -> List[Dict[str, Any]]:
        """
        Extract ranking criteria/indicator scores when
        they are present in the response.
        """

        criteria = []

        selectors = [
            ".criteria",
            ".criterion",
            ".indicator",
            ".ranking-indicator",
            ".score-item",
            "[data-score]",
        ]

        seen = set()

        for selector in selectors:

            for element in soup.select(
                selector
            ):

                text = (
                    self._clean_text(
                        element.get_text(
                            " ",
                            strip=True,
                        )
                    )
                )

                if (
                    not text
                    or text in seen
                ):

                    continue

                seen.add(
                    text
                )

                score = (
                    element.get(
                        "data-score"
                    )
                )

                if score is None:

                    score = (
                        self._extract_score(
                            text
                        )
                    )

                name = (
                    self._extract_criterion_name(
                        element=element,
                        text=text,
                    )
                )

                if (
                    not name
                    and score is None
                ):

                    continue

                criteria.append(
                    {
                        "name": (
                            name
                        ),
                        "score": (
                            self._to_number(
                                score
                            )
                        ),
                    }
                )

        return self._deduplicate_dicts(
            criteria
        )

    def _extract_criterion_name(
        self,
        element: Any,
        text: str,
    ) -> Optional[str]:

        selectors = [
            ".name",
            ".title",
            ".label",
            ".indicator-name",
            ".criteria-name",
        ]

        for selector in selectors:

            child = (
                element.select_one(
                    selector
                )
            )

            if child:

                name = (
                    self._clean_text(
                        child.get_text(
                            " ",
                            strip=True,
                        )
                    )
                )

                if name:

                    return name

        cleaned = re.sub(
            r"""
            (?:
                score
                |
                overall
                |
                points?
            )
            \s*
            [:]?
            \s*
            \d{
                1,
                3
            }
            (?:
                \.\d+
            )?
            """,
            "",
            text,
            flags=(
                re.IGNORECASE
                | re.VERBOSE
            ),
        )

        cleaned = (
            self._clean_text(
                cleaned
            )
        )

        return cleaned or None

    # ========================================================
    # SAVING
    # ========================================================

    def save_raw_response(
        self,
        raw_response: str,
        university_slug: str,
        ranking_id: Any,
        endpoint_index: int,
    ) -> Path:
        """
        Save the untouched QS AJAX response.
        """

        output_directory = (
            self.output_directory
            / university_slug
            / "raw"
            / "rankings"
        )

        output_directory.mkdir(
            parents=True,
            exist_ok=True,
        )

        safe_ranking_id = (
            ranking_id
            if ranking_id is not None
            else f"unknown_{endpoint_index}"
        )

        output_file = (
            output_directory
            / (
                f"ranking_"
                f"{safe_ranking_id}"
                f".json"
            )
        )

        output_file.write_text(
            raw_response,
            encoding="utf-8",
        )

        return output_file

    def save_json(
        self,
        data: Dict[str, Any],
        university_slug: Optional[str] = None,
    ) -> Path:
        """
        Save combined extracted ranking data.
        """

        if not university_slug:

            university_slug = (
                data.get(
                    "source",
                    {}
                ).get(
                    "university_slug"
                )
            )

        if not university_slug:

            raise ValueError(
                "University slug is required "
                "to save ranking data."
            )

        output_directory = (
            self.output_directory
            / university_slug
            / "extracted"
        )

        output_directory.mkdir(
            parents=True,
            exist_ok=True,
        )

        output_file = (
            output_directory
            / "rankings_data.json"
        )

        with output_file.open(
            "w",
            encoding="utf-8",
        ) as file:

            json.dump(
                data,
                file,
                ensure_ascii=False,
                indent=2,
            )

        return output_file

    # ========================================================
    # HELPERS
    # ========================================================

    def _deduplicate_endpoints(
        self,
        endpoints: List[
            Dict[str, Any]
        ],
    ) -> List[Dict[str, Any]]:

        unique = []

        seen = set()

        for endpoint in endpoints:

            key = (
                endpoint.get(
                    "url"
                )
                or (
                    endpoint.get(
                        "ranking_id"
                    ),
                    endpoint.get(
                        "profile_id"
                    ),
                    endpoint.get(
                        "offset"
                    ),
                )
            )

            if key in seen:

                continue

            seen.add(
                key
            )

            unique.append(
                endpoint
            )

        return unique

    def _deduplicate_history(
        self,
        records: List[
            Dict[str, Any]
        ],
    ) -> List[Dict[str, Any]]:

        unique = []

        seen = set()

        for record in records:

            key = (
                record.get(
                    "year"
                ),
                record.get(
                    "rank"
                ),
                record.get(
                    "score"
                ),
            )

            if key in seen:

                continue

            seen.add(
                key
            )

            # Internal parsing information should not
            # appear in final output.
            record.pop(
                "table_headers",
                None,
            )

            unique.append(
                record
            )

        return sorted(
            unique,
            key=lambda item: (
                item.get(
                    "year"
                )
                if isinstance(
                    item.get(
                        "year"
                    ),
                    int,
                )
                else -1
            ),
            reverse=True,
        )

    def _deduplicate_dicts(
        self,
        items: List[
            Dict[str, Any]
        ],
    ) -> List[Dict[str, Any]]:

        unique = []

        seen = set()

        for item in items:

            key = json.dumps(
                item,
                ensure_ascii=False,
                sort_keys=True,
            )

            if key in seen:

                continue

            seen.add(
                key
            )

            unique.append(
                item
            )

        return unique

    def _collect_strings(
        self,
        value: Any,
    ) -> List[str]:

        strings = []

        def walk(
            item: Any,
        ) -> None:

            if isinstance(
                item,
                dict,
            ):

                for nested_value in (
                    item.values()
                ):

                    walk(
                        nested_value
                    )

            elif isinstance(
                item,
                list,
            ):

                for nested_value in item:

                    walk(
                        nested_value
                    )

            elif isinstance(
                item,
                str,
            ):

                strings.append(
                    item
                )

        walk(
            value
        )

        return strings

    def _extract_score(
        self,
        text: Optional[str],
    ) -> Optional[
        int | float
    ]:

        if not text:

            return None

        match = (
            self.SCORE_PATTERN.search(
                text
            )
        )

        if not match:

            return None

        return self._to_number(
            match.group(
                "score"
            )
        )

    def _normalize_year(
        self,
        value: Any,
    ) -> Optional[int]:

        if value is None:

            return None

        match = (
            self.YEAR_PATTERN.search(
                str(value)
            )
        )

        if not match:

            return None

        return int(
            match.group()
        )

    def _to_number(
        self,
        value: Any,
    ) -> Optional[
        int | float
    ]:

        if value is None:

            return None

        text = (
            str(value)
            .strip()
            .replace(
                ",",
                ""
            )
        )

        try:

            number = float(
                text
            )

        except ValueError:

            return None

        if number.is_integer():

            return int(
                number
            )

        return number

    def _clean_rank(
        self,
        value: str,
    ) -> str:

        cleaned = (
            self._clean_text(
                value
            )
        )

        cleaned = re.sub(
            r"\s*([-–—])\s*",
            r"\1",
            cleaned,
        )

        cleaned = re.sub(
            r"\s+",
            "",
            cleaned,
        )

        return cleaned

    def _strip_rank_symbols(
        self,
        value: str,
    ) -> str:

        return re.sub(
            r"[^\d]",
            "",
            value,
        )

    def _clean_text(
        self,
        value: Any,
    ) -> str:

        if value is None:

            return ""

        return " ".join(
            str(value).split()
        )   