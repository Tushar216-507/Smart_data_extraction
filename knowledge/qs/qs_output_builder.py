from __future__ import annotations

import json
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Set


class QSOutputBuilder:
    """
    Build one clean QS university output from:

    - profile_data.json
    - rankings_data.json

    Expected input structure:

    data/
    └── qs/
        └── <university-slug>/
            └── extracted/
                ├── profile_data.json
                └── rankings_data.json

    Generated output:

    data/
    └── qs/
        └── <university-slug>/
            └── final/
                └── qs_data.json
    """

    OUTPUT_FILE_NAME = "qs_data.json"

    GENERIC_RANKING_NAMES = {
        "",
        "ranking",
        "rankings",
        "ranking criteria",
        "qs ranking",
    }

    GENERIC_SCHOLARSHIP_CONTENT_TYPES = {
        "generic_qs_scholarship_advice",
        "qs_scholarship_advice",
        "generic_qs_content",
    }

    def __init__(
        self,
        qs_directory: str | Path = "data/qs",
        indent: int = 2,
        ensure_ascii: bool = False,
    ) -> None:
        """
        Initialize the QS output builder.

        Parameters
        ----------
        qs_directory:
            Root directory containing QS university folders.

        indent:
            JSON indentation level.

        ensure_ascii:
            Whether JSON should escape non-ASCII characters.
            False preserves names such as München.
        """

        self.qs_directory = Path(
            qs_directory
        )

        self.indent = indent

        self.ensure_ascii = ensure_ascii

    # =========================================================
    # PUBLIC API
    # =========================================================

    def build(
        self,
        university_slug: str,
        profile_data_path: Optional[
            str | Path
        ] = None,
        rankings_data_path: Optional[
            str | Path
        ] = None,
        output_directory: Optional[
            str | Path
        ] = None,
    ) -> Dict[str, Any]:
        """
        Build and save the final QS output.

        Parameters
        ----------
        university_slug:
            Stable QS university slug.

        profile_data_path:
            Optional custom profile_data.json path.

        rankings_data_path:
            Optional custom rankings_data.json path.

        output_directory:
            Optional custom final output directory.

        Returns
        -------
        dict
            Build result containing status, output path,
            summary, and generated QS data.
        """

        normalized_slug = self._normalize_slug(
            university_slug
        )

        paths = self._build_paths(
            university_slug=normalized_slug,
            profile_data_path=profile_data_path,
            rankings_data_path=rankings_data_path,
            output_directory=output_directory,
        )

        profile_data = self._load_required_json(
            paths["profile_data"]
        )

        rankings_data = self._load_optional_json(
            paths["rankings_data"]
        )

        final_data = self.build_data(
            university_slug=normalized_slug,
            profile_data=profile_data,
            rankings_data=rankings_data,
        )

        self._write_json(
            path=paths["output_file"],
            data=final_data,
        )

        validation = self.validate(
            final_data
        )

        return {
            "status": (
                "success"
                if validation["valid"]
                else "completed_with_warnings"
            ),
            "university_slug": normalized_slug,
            "university_name": (
                final_data
                .get("university", {})
                .get("name")
            ),
            "output_file": str(
                paths["output_file"]
            ),
            "input_files": {
                "profile_data": str(
                    paths["profile_data"]
                ),
                "rankings_data": (
                    str(
                        paths["rankings_data"]
                    )
                    if paths[
                        "rankings_data"
                    ].exists()
                    else None
                ),
            },
            "summary": (
                final_data.get(
                    "build_summary",
                    {}
                )
            ),
            "validation": validation,
            "data": final_data,
        }

    def build_data(
        self,
        university_slug: str,
        profile_data: Dict[str, Any],
        rankings_data: Optional[
            Dict[str, Any]
        ] = None,
    ) -> Dict[str, Any]:
        """
        Build final QS data without writing a file.

        This method is useful when the main pipeline
        already has profile and ranking dictionaries
        loaded in memory.
        """

        rankings_data = (
            rankings_data
            if isinstance(
                rankings_data,
                dict,
            )
            else {}
        )

        source = self._build_source(
            university_slug=university_slug,
            profile_data=profile_data,
            rankings_data=rankings_data,
        )

        identifiers = self._build_identifiers(
            profile_data
        )

        university = self._build_university(
            profile_data
        )

        overview = self._build_overview(
            profile_data
        )

        locations = self._build_locations(
            profile_data
        )

        statistics = self._build_statistics(
            profile_data
        )

        cost_of_living = (
            self._build_cost_of_living(
                profile_data
            )
        )

        rankings = self._build_rankings(
            profile_data=profile_data,
            rankings_data=rankings_data,
        )

        programmes = self._build_programmes(
            profile_data
        )

        scholarships = (
            self._build_scholarships(
                profile_data
            )
        )

        social_links = (
            self._build_social_links(
                profile_data
            )
        )

        media = self._build_media(
            profile_data
        )

        supplementary_content = (
            self._build_supplementary_content(
                profile_data
            )
        )

        extraction = (
            self._build_extraction_metadata(
                profile_data=profile_data,
                rankings_data=rankings_data,
            )
        )

        final_data = {
            "schema": {
                "name": (
                    "qs_university_data"
                ),
                "version": "1.0",
            },
            "source": source,
            "identifiers": identifiers,
            "university": university,
            "overview": overview,
            "locations": locations,
            "statistics": statistics,
            "cost_of_living": (
                cost_of_living
            ),
            "rankings": rankings,
            "programmes": programmes,
            "scholarships": scholarships,
            "social_links": social_links,
            "media": media,
            "supplementary_content": (
                supplementary_content
            ),
            "extraction": extraction,
        }

        final_data = self._remove_empty_values(
            final_data,
            preserve_empty_keys={
                "rankings",
                "social_links",
            },
        )

        final_data["build_summary"] = (
            self._build_summary(
                final_data
            )
        )

        return final_data

    def validate(
        self,
        data: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Validate the generated QS output.
        """

        errors: List[str] = []

        warnings: List[str] = []

        if not isinstance(
            data,
            dict,
        ):
            return {
                "valid": False,
                "errors": [
                    (
                        "Final QS output must "
                        "be a dictionary."
                    )
                ],
                "warnings": [],
            }

        university = data.get(
            "university"
        )

        if not isinstance(
            university,
            dict,
        ):
            errors.append(
                (
                    "The university section "
                    "is missing."
                )
            )

        elif not university.get(
            "name"
        ):
            errors.append(
                (
                    "University name is "
                    "missing."
                )
            )

        source = data.get(
            "source"
        )

        if not isinstance(
            source,
            dict,
        ):
            errors.append(
                "Source metadata is missing."
            )

        elif not source.get(
            "profile_url"
        ):
            warnings.append(
                (
                    "QS profile URL is "
                    "missing."
                )
            )

        rankings = data.get(
            "rankings",
            [],
        )

        if not isinstance(
            rankings,
            list,
        ):
            errors.append(
                (
                    "Rankings must be "
                    "stored as a list."
                )
            )

        elif not rankings:
            warnings.append(
                (
                    "No detailed QS rankings "
                    "were included."
                )
            )

        statistics = data.get(
            "statistics"
        )

        if not statistics:
            warnings.append(
                (
                    "No student or faculty "
                    "statistics were included."
                )
            )

        return {
            "valid": not errors,
            "errors": errors,
            "warnings": warnings,
        }

    # =========================================================
    # PATHS
    # =========================================================

    def _build_paths(
        self,
        university_slug: str,
        profile_data_path: Optional[
            str | Path
        ],
        rankings_data_path: Optional[
            str | Path
        ],
        output_directory: Optional[
            str | Path
        ],
    ) -> Dict[str, Path]:

        university_directory = (
            self.qs_directory
            / university_slug
        )

        extracted_directory = (
            university_directory
            / "extracted"
        )

        final_directory = (
            Path(
                output_directory
            )
            if output_directory
            else (
                university_directory
                / "final"
            )
        )

        profile_file = (
            Path(
                profile_data_path
            )
            if profile_data_path
            else (
                extracted_directory
                / "profile_data.json"
            )
        )

        rankings_file = (
            Path(
                rankings_data_path
            )
            if rankings_data_path
            else (
                extracted_directory
                / "rankings_data.json"
            )
        )

        output_file = (
            final_directory
            / self.OUTPUT_FILE_NAME
        )

        return {
            "university_directory": (
                university_directory
            ),
            "extracted_directory": (
                extracted_directory
            ),
            "final_directory": (
                final_directory
            ),
            "profile_data": profile_file,
            "rankings_data": rankings_file,
            "output_file": output_file,
        }

    # =========================================================
    # SOURCE AND IDENTITY
    # =========================================================

    def _build_source(
        self,
        university_slug: str,
        profile_data: Dict[str, Any],
        rankings_data: Dict[str, Any],
    ) -> Dict[str, Any]:

        profile_source = (
            profile_data.get(
                "source",
                {}
            )
        )

        ranking_source = (
            rankings_data.get(
                "source",
                {}
            )
        )

        profile_url = self._first_value(
            profile_source.get(
                "profile_url"
            ),
            profile_data.get(
                "profile_url"
            ),
            ranking_source.get(
                "profile_url"
            ),
        )

        return {
            "provider": (
                self._first_value(
                    profile_source.get(
                        "provider"
                    ),
                    ranking_source.get(
                        "provider"
                    ),
                    "QS TopUniversities",
                )
            ),
            "profile_url": profile_url,
            "university_slug": (
                university_slug
            ),
            "retrieved_at": (
                self._first_value(
                    profile_source.get(
                        "retrieved_at"
                    ),
                    ranking_source.get(
                        "retrieved_at"
                    ),
                )
            ),
            "built_at": (
                datetime.now(
                    timezone.utc
                ).isoformat()
            ),
        }

    def _build_identifiers(
        self,
        profile_data: Dict[str, Any],
    ) -> Dict[str, Any]:

        identifiers = deepcopy(
            profile_data.get(
                "identifiers",
                {}
            )
        )

        return (
            identifiers
            if isinstance(
                identifiers,
                dict,
            )
            else {}
        )

    def _build_university(
        self,
        profile_data: Dict[str, Any],
    ) -> Dict[str, Any]:

        university_data = (
            profile_data.get(
                "university",
                {}
            )
        )

        if not isinstance(
            university_data,
            dict,
        ):
            university_data = {}

        return {
            "name": self._first_value(
                university_data.get(
                    "name"
                ),
                profile_data.get(
                    "university_name"
                ),
            ),
            "description": (
                university_data.get(
                    "description"
                )
            ),
            "website_urls": (
                self._unique_strings(
                    university_data.get(
                        "website_urls",
                        []
                    )
                )
            ),
            "logo_url": (
                university_data.get(
                    "logo_url"
                )
            ),
        }

    # =========================================================
    # PROFILE SECTIONS
    # =========================================================

    def _build_overview(
        self,
        profile_data: Dict[str, Any],
    ) -> Dict[str, Any]:

        university_data = (
            profile_data.get(
                "university",
                {}
            )
        )

        overview = self._first_value(
            profile_data.get(
                "overview"
            ),
            university_data.get(
                "overview"
            ),
            university_data.get(
                "description"
            ),
        )

        badges = self._first_value(
            profile_data.get(
                "badges"
            ),
            university_data.get(
                "badges"
            ),
            [],
        )

        return {
            "content": overview,
            "profile_badges": (
                deepcopy(
                    badges
                )
                if isinstance(
                    badges,
                    (
                        list,
                        dict,
                    ),
                )
                else []
            ),
        }

    def _build_locations(
        self,
        profile_data: Dict[str, Any],
    ) -> Dict[str, Any]:

        university_data = (
            profile_data.get(
                "university",
                {}
            )
        )

        address = self._first_value(
            university_data.get(
                "address"
            ),
            profile_data.get(
                "address"
            ),
            {},
        )

        campuses = self._first_value(
            university_data.get(
                "campuses"
            ),
            profile_data.get(
                "campuses"
            ),
            [],
        )

        cleaned_campuses = (
            self._deduplicate_dicts(
                campuses
                if isinstance(
                    campuses,
                    list,
                )
                else []
            )
        )

        return {
            "primary_address": (
                deepcopy(
                    address
                )
                if isinstance(
                    address,
                    dict,
                )
                else {}
            ),
            "campuses": (
                cleaned_campuses
            ),
        }

    def _build_statistics(
        self,
        profile_data: Dict[str, Any],
    ) -> Dict[str, Any]:

        statistics = self._first_value(
            profile_data.get(
                "statistics"
            ),
            (
                profile_data
                .get(
                    "university",
                    {}
                )
                .get(
                    "statistics"
                )
            ),
            {},
        )

        return (
            deepcopy(
                statistics
            )
            if isinstance(
                statistics,
                dict,
            )
            else {}
        )

    def _build_cost_of_living(
        self,
        profile_data: Dict[str, Any],
    ) -> Dict[str, Any]:

        cost_data = self._first_value(
            profile_data.get(
                "cost_of_living"
            ),
            (
                profile_data
                .get(
                    "university",
                    {}
                )
                .get(
                    "cost_of_living"
                )
            ),
            {},
        )

        return (
            deepcopy(
                cost_data
            )
            if isinstance(
                cost_data,
                dict,
            )
            else {}
        )

    def _build_programmes(
        self,
        profile_data: Dict[str, Any],
    ) -> Dict[str, Any]:

        programmes = self._first_value(
            profile_data.get(
                "programmes"
            ),
            profile_data.get(
                "programs"
            ),
            (
                profile_data
                .get(
                    "university",
                    {}
                )
                .get(
                    "programmes"
                )
            ),
            {},
        )

        if isinstance(
            programmes,
            dict,
        ):
            return deepcopy(
                programmes
            )

        if isinstance(
            programmes,
            list,
        ):
            return {
                "items": deepcopy(
                    programmes
                )
            }

        if isinstance(
            programmes,
            str,
        ):
            return {
                "raw_content": (
                    programmes
                )
            }

        return {}

    def _build_scholarships(
        self,
        profile_data: Dict[str, Any],
    ) -> Dict[str, Any]:

        scholarships = (
            profile_data.get(
                "scholarships",
                {}
            )
        )

        if not isinstance(
            scholarships,
            dict,
        ):
            return {}

        result = deepcopy(
            scholarships
        )

        content_type = str(
            result.get(
                "content_type",
                ""
            )
        ).strip().lower()

        if (
            content_type
            in self.GENERIC_SCHOLARSHIP_CONTENT_TYPES
        ):

            result[
                "university_scholarships_confirmed"
            ] = False

            result[
                "qs_advice_available"
            ] = bool(
                result.get(
                    "sections"
                )
                or result.get(
                    "links"
                )
            )

            result.pop(
                "available",
                None,
            )

        return result

    def _build_social_links(
        self,
        profile_data: Dict[str, Any],
    ) -> List[Dict[str, Any]]:

        social_links = self._first_value(
            profile_data.get(
                "social_links"
            ),
            (
                profile_data
                .get(
                    "university",
                    {}
                )
                .get(
                    "social_links"
                )
            ),
            [],
        )

        if not isinstance(
            social_links,
            list,
        ):
            return []

        return self._deduplicate_dicts(
            social_links
        )

    def _build_media(
        self,
        profile_data: Dict[str, Any],
    ) -> Dict[str, Any]:

        university_data = (
            profile_data.get(
                "university",
                {}
            )
        )

        logo_url = self._first_value(
            university_data.get(
                "logo_url"
            ),
            profile_data.get(
                "logo_url"
            ),
        )

        image_urls = self._first_value(
            university_data.get(
                "image_urls"
            ),
            profile_data.get(
                "image_urls"
            ),
            [],
        )

        cleaned_images = (
            self._unique_strings(
                image_urls
                if isinstance(
                    image_urls,
                    list,
                )
                else []
            )
        )

        return {
            "logo_url": logo_url,
            "image_urls": (
                cleaned_images
            ),
            "image_count": len(
                cleaned_images
            ),
        }

    # =========================================================
    # RANKINGS
    # =========================================================

    def _build_rankings(
        self,
        profile_data: Dict[str, Any],
        rankings_data: Dict[str, Any],
    ) -> List[Dict[str, Any]]:

        ranking_items = self._find_ranking_list(
            rankings_data
        )

        cleaned_rankings = []

        seen = set()

        for ranking in ranking_items:

            if not isinstance(
                ranking,
                dict,
            ):
                continue

            ranking_id = ranking.get(
                "ranking_id"
            )

            ranking_name = (
                self._clean_ranking_name(
                    ranking.get(
                        "ranking_name"
                    ),
                    ranking_id=ranking_id,
                )
            )

            current_ranking = deepcopy(
                ranking.get(
                    "current_ranking"
                )
                or {}
            )

            overall_score = (
                self._first_value(
                    ranking.get(
                        "overall_score"
                    ),
                    current_ranking.get(
                        "score"
                    ),
                )
            )

            if (
                current_ranking
                and overall_score is not None
            ):
                current_ranking[
                    "score"
                ] = overall_score

            history = (
                self._clean_ranking_history(
                    ranking.get(
                        "ranking_history",
                        []
                    )
                )
            )

            criteria = (
                self._clean_ranking_criteria(
                    ranking.get(
                        "criteria",
                        []
                    )
                )
            )

            duplicate_key = (
                str(
                    ranking_id
                ),
                str(
                    ranking.get(
                        "profile_id"
                    )
                ),
                str(
                    ranking.get(
                        "offset"
                    )
                ),
            )

            if duplicate_key in seen:
                continue

            seen.add(
                duplicate_key
            )

            cleaned_rankings.append(
                {
                    "ranking_id": (
                        ranking_id
                    ),
                    "name": ranking_name,
                    "current": (
                        current_ranking
                    ),
                    "overall_score": (
                        overall_score
                    ),
                    "history": history,
                    "criteria": criteria,
                    "source": {
                        "profile_id": (
                            ranking.get(
                                "profile_id"
                            )
                        ),
                        "offset": (
                            ranking.get(
                                "offset"
                            )
                        ),
                        "endpoint_url": (
                            ranking.get(
                                "endpoint_url"
                            )
                        ),
                    },
                }
            )

        cleaned_rankings.sort(
            key=self._ranking_sort_key
        )

        return cleaned_rankings

    def _find_ranking_list(
        self,
        rankings_data: Dict[str, Any],
    ) -> List[Dict[str, Any]]:

        possible_keys = (
            "rankings",
            "ranking_data",
            "results",
            "items",
        )

        for key in possible_keys:

            value = rankings_data.get(
                key
            )

            if isinstance(
                value,
                list,
            ):
                return value

        return []

    def _clean_ranking_name(
        self,
        name: Any,
        ranking_id: Any,
    ) -> str:

        cleaned_name = str(
            name or ""
        ).strip()

        if (
            cleaned_name.lower()
            not in self.GENERIC_RANKING_NAMES
        ):
            return cleaned_name

        return (
            f"QS Ranking {ranking_id}"
            if ranking_id is not None
            else "QS Ranking"
        )

    def _clean_ranking_history(
        self,
        history: Any,
    ) -> List[Dict[str, Any]]:

        if not isinstance(
            history,
            list,
        ):
            return []

        cleaned_history = []

        seen = set()

        for record in history:

            if not isinstance(
                record,
                dict,
            ):
                continue

            year = record.get(
                "year"
            )

            rank = self._first_value(
                record.get(
                    "rank"
                ),
                record.get(
                    "display_rank"
                ),
            )

            if (
                year is None
                or rank is None
            ):
                continue

            duplicate_key = (
                str(
                    year
                ),
                str(
                    rank
                ),
            )

            if duplicate_key in seen:
                continue

            seen.add(
                duplicate_key
            )

            cleaned_history.append(
                deepcopy(
                    record
                )
            )

        cleaned_history.sort(
            key=lambda item: (
                self._safe_integer(
                    item.get(
                        "year"
                    )
                )
                or 0
            ),
            reverse=True,
        )

        return cleaned_history

    def _clean_ranking_criteria(
        self,
        criteria: Any,
    ) -> List[Dict[str, Any]]:

        if not isinstance(
            criteria,
            list,
        ):
            return []

        cleaned_criteria = []

        seen = set()

        for criterion in criteria:

            if not isinstance(
                criterion,
                dict,
            ):
                continue

            name = str(
                criterion.get(
                    "name",
                    ""
                )
            ).strip()

            score = criterion.get(
                "score"
            )

            if not name:
                continue

            duplicate_key = (
                name.lower(),
                str(
                    score
                ),
            )

            if duplicate_key in seen:
                continue

            seen.add(
                duplicate_key
            )

            cleaned_criteria.append(
                {
                    "name": name,
                    "score": score,
                }
            )

        return cleaned_criteria

    def _ranking_sort_key(
        self,
        ranking: Dict[str, Any],
    ) -> tuple:

        current = ranking.get(
            "current",
            {}
        )

        year = self._safe_integer(
            current.get(
                "year"
            )
        )

        ranking_id = (
            self._safe_integer(
                ranking.get(
                    "ranking_id"
                )
            )
        )

        return (
            -(
                year
                or 0
            ),
            ranking_id
            or 0,
        )

    # =========================================================
    # SUPPLEMENTARY CONTENT
    # =========================================================

    def _build_supplementary_content(
        self,
        profile_data: Dict[str, Any],
    ) -> Dict[str, Any]:

        possible_keys = (
            "additional_sections",
            "information_sections",
            "sections",
            "facilities",
            "student_life",
            "about",
        )

        supplementary = {}

        for key in possible_keys:

            value = profile_data.get(
                key
            )

            if self._has_value(
                value
            ):

                supplementary[
                    key
                ] = deepcopy(
                    value
                )

        return supplementary

    # =========================================================
    # EXTRACTION AND SUMMARY
    # =========================================================

    def _build_extraction_metadata(
        self,
        profile_data: Dict[str, Any],
        rankings_data: Dict[str, Any],
    ) -> Dict[str, Any]:

        return {
            "profile": deepcopy(
                profile_data.get(
                    "extraction",
                    {}
                )
            ),
            "rankings": deepcopy(
                rankings_data.get(
                    "extraction",
                    rankings_data.get(
                        "summary",
                        {}
                    ),
                )
            ),
        }

    def _build_summary(
        self,
        final_data: Dict[str, Any],
    ) -> Dict[str, Any]:

        rankings = final_data.get(
            "rankings",
            [],
        )

        total_history_records = sum(
            len(
                ranking.get(
                    "history",
                    []
                )
            )
            for ranking in rankings
            if isinstance(
                ranking,
                dict,
            )
        )

        total_criteria = sum(
            len(
                ranking.get(
                    "criteria",
                    []
                )
            )
            for ranking in rankings
            if isinstance(
                ranking,
                dict,
            )
        )

        locations = final_data.get(
            "locations",
            {}
        )

        social_links = final_data.get(
            "social_links",
            [],
        )

        media = final_data.get(
            "media",
            {}
        )

        statistics = final_data.get(
            "statistics",
            {}
        )

        return {
            "ranking_count": len(
                rankings
            ),
            "ranking_history_records": (
                total_history_records
            ),
            "ranking_criteria_count": (
                total_criteria
            ),
            "campus_count": len(
                locations.get(
                    "campuses",
                    []
                )
            ),
            "social_link_count": len(
                social_links
            ),
            "image_count": (
                media.get(
                    "image_count",
                    0
                )
            ),
            "statistics_sections": len(
                statistics
            ),
            "has_cost_of_living": bool(
                final_data.get(
                    "cost_of_living"
                )
            ),
            "has_programmes": bool(
                final_data.get(
                    "programmes"
                )
            ),
        }

    # =========================================================
    # JSON HELPERS
    # =========================================================

    def _load_required_json(
        self,
        path: Path,
    ) -> Dict[str, Any]:

        if not path.exists():

            raise FileNotFoundError(
                (
                    "Required QS JSON file "
                    f"was not found: {path}"
                )
            )

        return self._load_json(
            path
        )

    def _load_optional_json(
        self,
        path: Path,
    ) -> Dict[str, Any]:

        if not path.exists():
            return {}

        return self._load_json(
            path
        )

    def _load_json(
        self,
        path: Path,
    ) -> Dict[str, Any]:

        with path.open(
            "r",
            encoding="utf-8",
        ) as file:

            data = json.load(
                file
            )

        if not isinstance(
            data,
            dict,
        ):

            raise ValueError(
                (
                    "Expected a JSON object "
                    f"in: {path}"
                )
            )

        return data

    def _write_json(
        self,
        path: Path,
        data: Dict[str, Any],
    ) -> None:

        path.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        temporary_file = (
            path.with_suffix(
                f"{path.suffix}.tmp"
            )
        )

        with temporary_file.open(
            "w",
            encoding="utf-8",
        ) as file:

            json.dump(
                data,
                file,
                ensure_ascii=(
                    self.ensure_ascii
                ),
                indent=self.indent,
            )

            file.write(
                "\n"
            )

        temporary_file.replace(
            path
        )

    # =========================================================
    # GENERAL HELPERS
    # =========================================================

    def _normalize_slug(
        self,
        value: str,
    ) -> str:

        normalized = str(
            value
        ).strip()

        if not normalized:

            raise ValueError(
                (
                    "University slug cannot "
                    "be empty."
                )
            )

        return normalized

    def _first_value(
        self,
        *values: Any,
    ) -> Any:

        for value in values:

            if self._has_value(
                value
            ):

                return value

        return None

    def _has_value(
        self,
        value: Any,
    ) -> bool:

        if value is None:
            return False

        if isinstance(
            value,
            str,
        ):

            return bool(
                value.strip()
            )

        if isinstance(
            value,
            (
                list,
                tuple,
                set,
                dict,
            ),
        ):

            return bool(
                value
            )

        return True

    def _unique_strings(
        self,
        values: List[Any],
    ) -> List[str]:

        unique_values = []

        seen: Set[str] = set()

        for value in values:

            cleaned_value = str(
                value
            ).strip()

            if not cleaned_value:
                continue

            duplicate_key = (
                cleaned_value.lower()
            )

            if duplicate_key in seen:
                continue

            seen.add(
                duplicate_key
            )

            unique_values.append(
                cleaned_value
            )

        return unique_values

    def _deduplicate_dicts(
        self,
        values: List[Any],
    ) -> List[Dict[str, Any]]:

        unique_values = []

        seen = set()

        for value in values:

            if not isinstance(
                value,
                dict,
            ):
                continue

            duplicate_key = json.dumps(
                value,
                ensure_ascii=False,
                sort_keys=True,
                default=str,
            )

            if duplicate_key in seen:
                continue

            seen.add(
                duplicate_key
            )

            unique_values.append(
                deepcopy(
                    value
                )
            )

        return unique_values

    def _safe_integer(
        self,
        value: Any,
    ) -> Optional[int]:

        if value is None:
            return None

        try:

            return int(
                value
            )

        except (
            TypeError,
            ValueError,
        ):

            return None

    def _remove_empty_values(
        self,
        value: Any,
        preserve_empty_keys: Optional[
            Set[str]
        ] = None,
    ) -> Any:
        """
        Recursively remove empty values.

        Numeric zero and False are preserved because
        they may be valid extracted values.
        """

        preserve_empty_keys = (
            preserve_empty_keys
            or set()
        )

        if isinstance(
            value,
            dict,
        ):

            cleaned_dictionary = {}

            for key, item in value.items():

                cleaned_item = (
                    self._remove_empty_values(
                        item,
                        preserve_empty_keys=(
                            preserve_empty_keys
                        ),
                    )
                )

                if (
                    key in preserve_empty_keys
                ):

                    cleaned_dictionary[
                        key
                    ] = cleaned_item

                    continue

                if self._has_value(
                    cleaned_item
                ):

                    cleaned_dictionary[
                        key
                    ] = cleaned_item

            return cleaned_dictionary

        if isinstance(
            value,
            list,
        ):

            cleaned_list = []

            for item in value:

                cleaned_item = (
                    self._remove_empty_values(
                        item,
                        preserve_empty_keys=(
                            preserve_empty_keys
                        ),
                    )
                )

                if self._has_value(
                    cleaned_item
                ):

                    cleaned_list.append(
                        cleaned_item
                    )

            return cleaned_list

        return value