import json
from pathlib import Path

from knowledge.qs.qs_ranking_extractor import (
    QSRankingExtractor,
)


# ============================================================
# TEST CONFIGURATION
# ============================================================

UNIVERSITY_SLUG = (
    "ludwig-maximilians-universitat-munchen"
)

QS_DIRECTORY = Path(
    "data/qs"
)

PROFILE_FILE = (
    QS_DIRECTORY
    / UNIVERSITY_SLUG
    / "extracted"
    / "profile_data.json"
)


# ============================================================
# DISPLAY HELPERS
# ============================================================

def print_separator() -> None:

    print()
    print("=" * 80)


def print_value(
    label: str,
    value,
) -> None:

    if value is None:

        value = "Not found"

    print(
        f"{label:<32}: {value}"
    )


# ============================================================
# VALIDATION
# ============================================================

def validate_input_file() -> None:

    if not PROFILE_FILE.exists():

        raise FileNotFoundError(
            "\n"
            "QS profile data was not found.\n"
            f"Expected file: {PROFILE_FILE}\n\n"
            "Run test_qs_profile_extractor.py first."
        )

    with PROFILE_FILE.open(
        "r",
        encoding="utf-8",
    ) as file:

        profile_data = json.load(
            file
        )

    endpoints = (
        profile_data
        .get(
            "ranking",
            {}
        )
        .get(
            "discovered_endpoints",
            []
        )
    )

    if not endpoints:

        raise ValueError(
            "No ranking endpoints were found "
            "inside profile_data.json."
        )

    print(
        "✓ QS profile data exists."
    )

    print(
        "✓ QS profile data contains "
        f"{len(endpoints)} ranking endpoints."
    )


def validate_output(
    result: dict,
    output_file: Path,
) -> None:

    print_separator()

    print(
        "VALIDATION"
    )

    print(
        "=" * 80
    )

    print()

    if not isinstance(
        result,
        dict,
    ):

        raise AssertionError(
            "Ranking result must be a dictionary."
        )

    rankings = result.get(
        "rankings"
    )

    if not isinstance(
        rankings,
        list,
    ):

        raise AssertionError(
            "'rankings' must be a list."
        )

    if not output_file.exists():

        raise FileNotFoundError(
            "rankings_data.json was not created: "
            f"{output_file}"
        )

    with output_file.open(
        "r",
        encoding="utf-8",
    ) as file:

        saved_data = json.load(
            file
        )

    if not isinstance(
        saved_data,
        dict,
    ):

        raise AssertionError(
            "Saved ranking data must be "
            "a JSON object."
        )

    print(
        "✓ Ranking result has a valid structure."
    )

    print(
        "✓ rankings_data.json exists."
    )

    print(
        "✓ rankings_data.json contains valid JSON."
    )


# ============================================================
# PRINT RANKINGS
# ============================================================

def print_rankings(
    rankings: list,
) -> None:

    print_separator()

    print(
        "EXTRACTED RANKINGS"
    )

    print(
        "=" * 80
    )

    if not rankings:

        print()
        print(
            "No ranking records were extracted."
        )

        return

    for index, ranking in enumerate(
        rankings,
        start=1,
    ):

        print()
        print(
            f"RANKING {index}"
        )

        print(
            "-" * 80
        )

        print_value(
            "Ranking ID",
            ranking.get(
                "ranking_id"
            ),
        )

        print_value(
            "Ranking name",
            ranking.get(
                "ranking_name"
            ),
        )

        print_value(
            "QS profile ID",
            ranking.get(
                "profile_id"
            ),
        )

        print_value(
            "Offset",
            ranking.get(
                "offset"
            ),
        )

        current_ranking = (
            ranking.get(
                "current_ranking"
            )
        )

        if current_ranking:

            print_value(
                "Current year",
                current_ranking.get(
                    "year"
                ),
            )

            print_value(
                "Current rank",
                current_ranking.get(
                    "rank"
                ),
            )

            print_value(
                "Numeric rank",
                current_ranking.get(
                    "rank_numeric"
                ),
            )

            print_value(
                "Rank minimum",
                current_ranking.get(
                    "rank_min"
                ),
            )

            print_value(
                "Rank maximum",
                current_ranking.get(
                    "rank_max"
                ),
            )

            print_value(
                "Is tied",
                current_ranking.get(
                    "is_tied"
                ),
            )

            print_value(
                "Is range",
                current_ranking.get(
                    "is_range"
                ),
            )

            print_value(
                "Score",
                current_ranking.get(
                    "score"
                ),
            )

        else:

            print_value(
                "Current ranking",
                None,
            )

        history = ranking.get(
            "ranking_history",
            []
        )

        criteria = ranking.get(
            "criteria",
            []
        )

        print_value(
            "History records",
            len(
                history
            ),
        )

        print_value(
            "Criteria found",
            len(
                criteria
            ),
        )

        print_value(
            "Endpoint URL",
            ranking.get(
                "endpoint_url"
            ),
        )

        if history:

            print()
            print(
                "Ranking history:"
            )

            for record in history:

                print(
                    "  "
                    f"Year: "
                    f"{record.get('year')} | "
                    f"Rank: "
                    f"{record.get('rank')} | "
                    f"Score: "
                    f"{record.get('score')}"
                )

        if criteria:

            print()
            print(
                "Ranking criteria:"
            )

            for criterion in criteria:

                print(
                    "  "
                    f"{criterion.get('name')} "
                    f"= "
                    f"{criterion.get('score')}"
                )


# ============================================================
# MAIN TEST
# ============================================================

def main() -> None:

    print_separator()

    print(
        "QS RANKING EXTRACTOR TEST"
    )

    print(
        "=" * 80
    )

    print()

    print_value(
        "University slug",
        UNIVERSITY_SLUG,
    )

    print_value(
        "Profile data",
        PROFILE_FILE,
    )

    print_value(
        "QS directory",
        QS_DIRECTORY,
    )

    # --------------------------------------------------------
    # Validate profile data
    # --------------------------------------------------------

    print_separator()

    print(
        "VALIDATING PROFILE DATA"
    )

    print(
        "=" * 80
    )

    print()

    validate_input_file()

    # --------------------------------------------------------
    # Create ranking extractor
    # --------------------------------------------------------

    extractor = QSRankingExtractor(

        timeout=45,

        output_directory=(
            QS_DIRECTORY
        ),

        save_raw_responses=True,
    )

    # --------------------------------------------------------
    # Extract all rankings
    # --------------------------------------------------------

    print_separator()

    print(
        "DOWNLOADING QS RANKINGS"
    )

    print(
        "=" * 80
    )

    print()

    print(
        "Reading ranking endpoints from "
        "profile_data.json..."
    )

    print(
        "Downloading and parsing all "
        "discovered ranking endpoints..."
    )

    result = (
        extractor.extract_from_profile_file(
            PROFILE_FILE
        )
    )

    print(
        "✓ Ranking endpoint processing completed."
    )

    # --------------------------------------------------------
    # Save final ranking data
    # --------------------------------------------------------

    output_file = (
        extractor.save_json(
            result
        )
    )

    print(
        "✓ Combined ranking data saved."
    )

    # --------------------------------------------------------
    # Print rankings
    # --------------------------------------------------------

    rankings = result.get(
        "rankings",
        []
    )

    print_rankings(
        rankings
    )

    # --------------------------------------------------------
    # Print extraction summary
    # --------------------------------------------------------

    extraction = result.get(
        "extraction",
        {}
    )

    print_separator()

    print(
        "EXTRACTION SUMMARY"
    )

    print(
        "=" * 80
    )

    print()

    print_value(
        "Endpoints discovered",
        extraction.get(
            "endpoints_discovered"
        ),
    )

    print_value(
        "Unique endpoints",
        extraction.get(
            "unique_endpoints"
        ),
    )

    print_value(
        "Endpoints processed",
        extraction.get(
            "endpoints_processed"
        ),
    )

    print_value(
        "Endpoints failed",
        extraction.get(
            "endpoints_failed"
        ),
    )

    print_value(
        "Ranking records found",
        extraction.get(
            "ranking_records_found"
        ),
    )

    # --------------------------------------------------------
    # Print endpoint failures
    # --------------------------------------------------------

    failures = extraction.get(
        "failed_endpoints",
        []
    )

    if failures:

        print_separator()

        print(
            "FAILED ENDPOINTS"
        )

        print(
            "=" * 80
        )

        for failure in failures:

            print()

            print_value(
                "Ranking ID",
                failure.get(
                    "ranking_id"
                ),
            )

            print_value(
                "Endpoint URL",
                failure.get(
                    "url"
                ),
            )

            print_value(
                "Error",
                failure.get(
                    "error"
                ),
            )

    # --------------------------------------------------------
    # Validate output
    # --------------------------------------------------------

    validate_output(
        result=result,
        output_file=output_file,
    )

    # --------------------------------------------------------
    # Generated files
    # --------------------------------------------------------

    print_separator()

    print(
        "GENERATED FILES"
    )

    print(
        "=" * 80
    )

    print()

    raw_directory = (
        QS_DIRECTORY
        / UNIVERSITY_SLUG
        / "raw"
        / "rankings"
    )

    print_value(
        "Raw ranking directory",
        raw_directory,
    )

    print_value(
        "Extracted ranking JSON",
        output_file,
    )

    # --------------------------------------------------------
    # Complete
    # --------------------------------------------------------

    print_separator()

    print(
        "✓ QS ranking extraction test completed."
    )

    print(
        "✓ Raw ranking responses were preserved."
    )

    print(
        "✓ Combined ranking JSON is valid."
    )

    print(
        "=" * 80
    )

    print()


if __name__ == "__main__":

    main()