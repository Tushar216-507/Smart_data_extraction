import json
import sys
from pathlib import Path

from knowledge.qs.qs_output_builder import (
    QSOutputBuilder,
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

UNIVERSITY_DIRECTORY = (
    QS_DIRECTORY
    / UNIVERSITY_SLUG
)

EXTRACTED_DIRECTORY = (
    UNIVERSITY_DIRECTORY
    / "extracted"
)

FINAL_DIRECTORY = (
    UNIVERSITY_DIRECTORY
    / "final"
)

PROFILE_DATA_FILE = (
    EXTRACTED_DIRECTORY
    / "profile_data.json"
)

RANKINGS_DATA_FILE = (
    EXTRACTED_DIRECTORY
    / "rankings_data.json"
)

OUTPUT_FILE = (
    FINAL_DIRECTORY
    / "qs_data.json"
)


# ============================================================
# DISPLAY HELPERS
# ============================================================

def print_heading(
    title: str,
) -> None:

    print()

    print(
        "=" * 80
    )

    print(
        title
    )

    print(
        "=" * 80
    )

    print()


def print_subheading(
    title: str,
) -> None:

    print()

    print(
        title
    )

    print(
        "-" * 80
    )


def print_value(
    label: str,
    value,
) -> None:

    print(
        f"{label:<32}: {value}"
    )


def format_value(
    value,
    default: str = "Not found",
) -> str:

    if value is None:
        return default

    if isinstance(
        value,
        str,
    ):

        value = value.strip()

        if not value:
            return default

    return str(
        value
    )


# ============================================================
# JSON HELPERS
# ============================================================

def load_json(
    file_path: Path,
):

    with file_path.open(
        "r",
        encoding="utf-8",
    ) as file:

        return json.load(
            file
        )


def validate_json_file(
    file_path: Path,
) -> dict:

    if not file_path.exists():

        raise AssertionError(
            (
                "Generated JSON file "
                f"does not exist: {file_path}"
            )
        )

    data = load_json(
        file_path
    )

    if not isinstance(
        data,
        dict,
    ):

        raise AssertionError(
            (
                "Generated QS JSON must "
                "contain one JSON object."
            )
        )

    return data


# ============================================================
# DATA HELPERS
# ============================================================

def get_nested(
    data: dict,
    *keys,
    default=None,
):

    current = data

    for key in keys:

        if not isinstance(
            current,
            dict,
        ):

            return default

        current = current.get(
            key
        )

        if current is None:

            return default

    return current


def count_ranking_history(
    rankings: list,
) -> int:

    return sum(

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


def count_ranking_criteria(
    rankings: list,
) -> int:

    return sum(

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


def find_ranking(
    rankings: list,
    ranking_id: int,
):

    for ranking in rankings:

        if not isinstance(
            ranking,
            dict,
        ):

            continue

        current_id = ranking.get(
            "ranking_id"
        )

        try:

            current_id = int(
                current_id
            )

        except (
            TypeError,
            ValueError,
        ):

            continue

        if current_id == ranking_id:

            return ranking

    return None


def get_current_rank(
    ranking: dict,
):

    current = ranking.get(
        "current",
        {}
    )

    if not isinstance(
        current,
        dict,
    ):

        return None

    return (
        current.get(
            "rank"
        )
        or current.get(
            "display_rank"
        )
    )


def get_current_year(
    ranking: dict,
):

    current = ranking.get(
        "current",
        {}
    )

    if not isinstance(
        current,
        dict,
    ):

        return None

    return current.get(
        "year"
    )


def get_current_score(
    ranking: dict,
):

    current = ranking.get(
        "current",
        {}
    )

    if isinstance(
        current,
        dict,
    ):

        score = current.get(
            "score"
        )

        if score is not None:

            return score

    return ranking.get(
        "overall_score"
    )


# ============================================================
# MAIN TEST
# ============================================================

def main() -> None:

    print_heading(
        "QS OUTPUT BUILDER TEST"
    )

    print_value(
        "University slug",
        UNIVERSITY_SLUG,
    )

    print_value(
        "QS directory",
        QS_DIRECTORY,
    )

    print_value(
        "Profile data",
        PROFILE_DATA_FILE,
    )

    print_value(
        "Ranking data",
        RANKINGS_DATA_FILE,
    )

    print_value(
        "Final directory",
        FINAL_DIRECTORY,
    )

    print_value(
        "Expected output",
        OUTPUT_FILE,
    )

    # ========================================================
    # VALIDATE INPUT FILES
    # ========================================================

    print_heading(
        "VALIDATING INPUT FILES"
    )

    if not PROFILE_DATA_FILE.exists():

        raise FileNotFoundError(
            (
                "QS profile data was not "
                f"found: {PROFILE_DATA_FILE}"
            )
        )

    print(
        "✓ QS profile data exists."
    )

    profile_data = load_json(
        PROFILE_DATA_FILE
    )

    if not isinstance(
        profile_data,
        dict,
    ):

        raise AssertionError(
            (
                "profile_data.json must "
                "contain a JSON object."
            )
        )

    print(
        "✓ QS profile data contains valid JSON."
    )

    if not RANKINGS_DATA_FILE.exists():

        raise FileNotFoundError(
            (
                "QS ranking data was not "
                f"found: {RANKINGS_DATA_FILE}"
            )
        )

    print(
        "✓ QS ranking data exists."
    )

    rankings_data = load_json(
        RANKINGS_DATA_FILE
    )

    if not isinstance(
        rankings_data,
        dict,
    ):

        raise AssertionError(
            (
                "rankings_data.json must "
                "contain a JSON object."
            )
        )

    print(
        "✓ QS ranking data contains valid JSON."
    )

    input_rankings = (
        rankings_data.get(
            "rankings",
            []
        )
    )

    if not isinstance(
        input_rankings,
        list,
    ):

        raise AssertionError(
            (
                "The rankings field in "
                "rankings_data.json must "
                "be a list."
            )
        )

    print_value(
        "Input rankings found",
        len(
            input_rankings
        ),
    )

    # ========================================================
    # BUILD FINAL QS OUTPUT
    # ========================================================

    print_heading(
        "BUILDING FINAL QS OUTPUT"
    )

    builder = QSOutputBuilder(
        qs_directory=QS_DIRECTORY,
        indent=2,
        ensure_ascii=False,
    )

    print(
        "Combining profile_data.json "
        "and rankings_data.json..."
    )

    result = builder.build(
        university_slug=(
            UNIVERSITY_SLUG
        ),
    )

    print(
        "✓ QS output build completed."
    )

    print(
        "✓ Final QS data was saved."
    )

    # ========================================================
    # BUILD RESULT
    # ========================================================

    print_heading(
        "BUILD RESULT"
    )

    print_value(
        "Status",
        result.get(
            "status"
        ),
    )

    print_value(
        "University slug",
        result.get(
            "university_slug"
        ),
    )

    print_value(
        "University name",
        result.get(
            "university_name"
        ),
    )

    print_value(
        "Output file",
        result.get(
            "output_file"
        ),
    )

    # ========================================================
    # VALIDATE GENERATED JSON
    # ========================================================

    print_heading(
        "VALIDATING GENERATED JSON"
    )

    final_data = validate_json_file(
        OUTPUT_FILE
    )

    print(
        "✓ qs_data.json exists."
    )

    print(
        "✓ qs_data.json contains valid JSON."
    )

    print(
        "✓ Generated QS data was loaded successfully."
    )

    # ========================================================
    # UNIVERSITY PROFILE
    # ========================================================

    print_heading(
        "UNIVERSITY PROFILE"
    )

    university = final_data.get(
        "university",
        {}
    )

    identifiers = final_data.get(
        "identifiers",
        {}
    )

    source = final_data.get(
        "source",
        {}
    )

    print_value(
        "University name",
        format_value(
            university.get(
                "name"
            )
        ),
    )

    print_value(
        "QS profile ID",
        format_value(
            identifiers.get(
                "qs_profile_id"
            )
        ),
    )

    print_value(
        "Drupal node ID",
        format_value(
            identifiers.get(
                "drupal_node_id"
            )
        ),
    )

    print_value(
        "University slug",
        format_value(
            source.get(
                "university_slug"
            )
        ),
    )

    print_value(
        "QS profile URL",
        format_value(
            source.get(
                "profile_url"
            )
        ),
    )

    print_value(
        "Logo URL",
        format_value(
            university.get(
                "logo_url"
            )
        ),
    )

    # ========================================================
    # LOCATIONS
    # ========================================================

    print_heading(
        "LOCATIONS"
    )

    locations = final_data.get(
        "locations",
        {}
    )

    campuses = locations.get(
        "campuses",
        []
    )

    primary_address = (
        locations.get(
            "primary_address",
            {}
        )
    )

    print_value(
        "Primary address available",
        bool(
            primary_address
        ),
    )

    print_value(
        "Campuses found",
        len(
            campuses
        ),
    )

    for index, campus in enumerate(
        campuses,
        start=1,
    ):

        print_subheading(
            f"Campus {index}"
        )

        print_value(
            "Name",
            format_value(
                campus.get(
                    "name"
                )
            ),
        )

        address = campus.get(
            "address",
            {}
        )

        if isinstance(
            address,
            dict,
        ):

            print_value(
                "Street",
                format_value(
                    address.get(
                        "street"
                    )
                ),
            )

            print_value(
                "City",
                format_value(
                    address.get(
                        "city"
                    )
                ),
            )

            print_value(
                "Postal code",
                format_value(
                    address.get(
                        "postal_code"
                    )
                ),
            )

            print_value(
                "Country",
                format_value(
                    address.get(
                        "country"
                    )
                ),
            )

    # ========================================================
    # STATISTICS
    # ========================================================

    print_heading(
        "UNIVERSITY STATISTICS"
    )

    statistics = final_data.get(
        "statistics",
        {}
    )

    if statistics:

        print(
            json.dumps(
                statistics,
                ensure_ascii=False,
                indent=2,
            )
        )

    else:

        print(
            "No university statistics found."
        )

    # ========================================================
    # COST OF LIVING
    # ========================================================

    print_heading(
        "COST OF LIVING"
    )

    cost_of_living = (
        final_data.get(
            "cost_of_living",
            {}
        )
    )

    if cost_of_living:

        print(
            json.dumps(
                cost_of_living,
                ensure_ascii=False,
                indent=2,
            )
        )

    else:

        print(
            "No cost-of-living data found."
        )

    # ========================================================
    # QS RANKINGS
    # ========================================================

    print_heading(
        "QS RANKINGS"
    )

    rankings = final_data.get(
        "rankings",
        []
    )

    print_value(
        "Rankings found",
        len(
            rankings
        ),
    )

    print_value(
        "History records",
        count_ranking_history(
            rankings
        ),
    )

    print_value(
        "Ranking criteria",
        count_ranking_criteria(
            rankings
        ),
    )

    for index, ranking in enumerate(
        rankings,
        start=1,
    ):

        print_subheading(
            f"Ranking {index}"
        )

        print_value(
            "Ranking ID",
            format_value(
                ranking.get(
                    "ranking_id"
                )
            ),
        )

        print_value(
            "Ranking name",
            format_value(
                ranking.get(
                    "name"
                )
            ),
        )

        print_value(
            "Current year",
            format_value(
                get_current_year(
                    ranking
                )
            ),
        )

        print_value(
            "Current rank",
            format_value(
                get_current_rank(
                    ranking
                )
            ),
        )

        print_value(
            "Overall score",
            format_value(
                get_current_score(
                    ranking
                )
            ),
        )

        print_value(
            "History records",
            len(
                ranking.get(
                    "history",
                    []
                )
            ),
        )

        print_value(
            "Criteria found",
            len(
                ranking.get(
                    "criteria",
                    []
                )
            ),
        )

    # ========================================================
    # SOCIAL LINKS AND MEDIA
    # ========================================================

    print_heading(
        "SOCIAL LINKS AND MEDIA"
    )

    social_links = final_data.get(
        "social_links",
        []
    )

    media = final_data.get(
        "media",
        {}
    )

    image_urls = media.get(
        "image_urls",
        []
    )

    print_value(
        "Social links",
        len(
            social_links
        ),
    )

    print_value(
        "University images",
        len(
            image_urls
        ),
    )

    print_value(
        "Logo available",
        bool(
            media.get(
                "logo_url"
            )
        ),
    )

    # ========================================================
    # PROGRAMMES AND SCHOLARSHIPS
    # ========================================================

    print_heading(
        "PROGRAMMES AND SCHOLARSHIPS"
    )

    programmes = final_data.get(
        "programmes",
        {}
    )

    scholarships = final_data.get(
        "scholarships",
        {}
    )

    print_value(
        "Programme data available",
        bool(
            programmes
        ),
    )

    print_value(
        "Scholarship data available",
        bool(
            scholarships
        ),
    )

    # ========================================================
    # BUILD SUMMARY
    # ========================================================

    print_heading(
        "BUILD SUMMARY"
    )

    build_summary = final_data.get(
        "build_summary",
        {}
    )

    for key, value in (
        build_summary.items()
    ):

        readable_key = (
            key
            .replace(
                "_",
                " "
            )
            .title()
        )

        print_value(
            readable_key,
            value,
        )

    # ========================================================
    # VALIDATION
    # ========================================================

    print_heading(
        "VALIDATION"
    )

    validation = builder.validate(
        final_data
    )

    if validation.get(
        "valid"
    ):

        print(
            "✓ Final QS output has a valid structure."
        )

    else:

        print(
            "✗ Final QS output validation failed."
        )

    errors = validation.get(
        "errors",
        []
    )

    warnings = validation.get(
        "warnings",
        []
    )

    if errors:

        print()

        print(
            "Errors:"
        )

        for error in errors:

            print(
                f"  ✗ {error}"
            )

    if warnings:

        print()

        print(
            "Warnings:"
        )

        for warning in warnings:

            print(
                f"  ! {warning}"
            )

    # ========================================================
    # ASSERTIONS
    # ========================================================

    print_heading(
        "RUNNING DATA-PRESERVATION CHECKS"
    )

    assert validation.get(
        "valid"
    ), (
        "Generated QS output failed "
        "structural validation."
    )

    assert (
        university.get(
            "name"
        )
    ), (
        "University name was not "
        "preserved."
    )

    print(
        "✓ University name was preserved."
    )

    assert (
        source.get(
            "profile_url"
        )
    ), (
        "QS profile URL was not "
        "preserved."
    )

    print(
        "✓ QS profile URL was preserved."
    )

    assert len(
        rankings
    ) == len(
        input_rankings
    ), (
        "The final ranking count does "
        "not match the extracted input."
    )

    print(
        (
            "✓ All extracted ranking "
            "groups were preserved."
        )
    )

    input_history_count = sum(

        len(
            ranking.get(
                "ranking_history",
                []
            )
        )

        for ranking in input_rankings

        if isinstance(
            ranking,
            dict,
        )

    )

    final_history_count = (
        count_ranking_history(
            rankings
        )
    )

    assert (
        final_history_count
        == input_history_count
    ), (
        "Ranking-history records were "
        "lost while building final output. "
        f"Input: {input_history_count}, "
        f"Final: {final_history_count}"
    )

    print(
        (
            "✓ All ranking-history "
            "records were preserved."
        )
    )

    input_criteria_count = sum(

        len(
            ranking.get(
                "criteria",
                []
            )
        )

        for ranking in input_rankings

        if isinstance(
            ranking,
            dict,
        )

    )

    final_criteria_count = (
        count_ranking_criteria(
            rankings
        )
    )

    assert (
        final_criteria_count
        == input_criteria_count
    ), (
        "Ranking criteria were lost "
        "while building final output. "
        f"Input: {input_criteria_count}, "
        f"Final: {final_criteria_count}"
    )

    print(
        (
            "✓ All ranking criteria "
            "were preserved."
        )
    )

    assert statistics, (
        "University statistics were "
        "not preserved."
    )

    print(
        "✓ University statistics were preserved."
    )

    assert cost_of_living, (
        "Cost-of-living data was "
        "not preserved."
    )

    print(
        "✓ Cost-of-living data was preserved."
    )

    assert campuses, (
        "Campus data was not preserved."
    )

    print(
        "✓ Campus data was preserved."
    )

    assert social_links, (
        "Social links were not preserved."
    )

    print(
        "✓ Social links were preserved."
    )

    assert image_urls, (
        "University images were not "
        "preserved."
    )

    print(
        "✓ University images were preserved."
    )

    world_ranking = find_ranking(
        rankings,
        ranking_id=513,
    )

    assert world_ranking is not None, (
        "QS World University Ranking "
        "was not preserved."
    )

    print(
        (
            "✓ QS World University "
            "Ranking was preserved."
        )
    )

    assert (
        get_current_rank(
            world_ranking
        )
        == "#61"
    ), (
        "Expected current QS World "
        "University Ranking to be #61."
    )

    print(
        (
            "✓ Current QS World University "
            "Ranking is #61."
        )
    )

    assert (
        get_current_score(
            world_ranking
        )
        == 79.6
    ), (
        "Expected QS World University "
        "Ranking score to be 79.6."
    )

    print(
        (
            "✓ QS World University "
            "Ranking score is 79.6."
        )
    )

    # ========================================================
    # GENERATED FILES
    # ========================================================

    print_heading(
        "GENERATED FILES"
    )

    print_value(
        "Final QS output",
        OUTPUT_FILE,
    )

    print_heading(
        "✓ QS OUTPUT BUILD COMPLETED SUCCESSFULLY"
    )

    print(
        "✓ profile_data.json and "
        "rankings_data.json were combined."
    )

    print(
        "✓ qs_data.json contains valid JSON."
    )

    print(
        "✓ University profile data was preserved."
    )

    print(
        "✓ Ranking history and criteria were preserved."
    )

    print(
        "✓ Statistics and cost-of-living data were preserved."
    )


if __name__ == "__main__":

    try:

        main()

    except Exception as error:

        print_heading(
            "✗ QS OUTPUT BUILDER TEST FAILED"
        )

        print(
            f"{type(error).__name__}: "
            f"{error}"
        )

        sys.exit(
            1
        )