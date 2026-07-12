import json
from pathlib import Path

from knowledge.qs.qs_profile_extractor import (
    QSProfileExtractor,
)


# ============================================================
# TEST CONFIGURATION
# ============================================================

QS_PROFILE_URL = (
    "https://www.topuniversities.com/"
    "universities/"
    "ludwig-maximilians-universitat-munchen"
)

UNIVERSITY_SLUG = (
    "ludwig-maximilians-universitat-munchen"
)

OUTPUT_DIRECTORY = Path(
    "data/qs"
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
        f"{label:<30}: {value}"
    )


def print_address(
    address: dict,
) -> None:

    print_separator()
    print("UNIVERSITY ADDRESS")
    print("=" * 80)
    print()

    if not address:

        print(
            "No university address was extracted."
        )

        return

    for key, value in address.items():

        print_value(
            key.replace(
                "_",
                " ",
            ).title(),
            value,
        )


def print_campuses(
    campuses: list,
) -> None:

    print_separator()
    print("CAMPUSES")
    print("=" * 80)
    print()

    if not campuses:

        print(
            "No campus information was extracted."
        )

        return

    print(
        f"Total campuses found: "
        f"{len(campuses)}"
    )

    for index, campus in enumerate(
        campuses,
        start=1,
    ):

        print()
        print(
            f"Campus {index}"
        )

        print(
            "-" * 80
        )

        print_value(
            "Name",
            campus.get(
                "name"
            ),
        )

        address = campus.get(
            "address",
            {},
        )

        if address:

            print(
                "Address:"
            )

            for key, value in address.items():

                print(
                    f"  "
                    f"{key.replace('_', ' ').title():<20}"
                    f": {value}"
                )

        coordinates = campus.get(
            "coordinates",
            {},
        )

        if coordinates:

            print_value(
                "Latitude",
                coordinates.get(
                    "latitude"
                ),
            )

            print_value(
                "Longitude",
                coordinates.get(
                    "longitude"
                ),
            )

        if campus.get(
            "url"
        ):

            print_value(
                "URL",
                campus.get(
                    "url"
                ),
            )


def print_social_links(
    social_links: list,
) -> None:

    print_separator()
    print("SOCIAL LINKS")
    print("=" * 80)
    print()

    if not social_links:

        print(
            "No social-media links were extracted."
        )

        return

    for index, link in enumerate(
        social_links,
        start=1,
    ):

        print(
            f"{index:>2}. {link}"
        )


def print_images(
    image_urls: list,
) -> None:

    print_separator()
    print("UNIVERSITY IMAGES")
    print("=" * 80)
    print()

    if not image_urls:

        print(
            "No university images were extracted."
        )

        return

    print(
        f"Total images found: "
        f"{len(image_urls)}"
    )

    for index, image_url in enumerate(
        image_urls,
        start=1,
    ):

        print(
            f"{index:>2}. {image_url}"
        )


def print_ranking_endpoints(
    ranking_endpoints: list,
) -> None:

    print_separator()
    print("DISCOVERED RANKING ENDPOINTS")
    print("=" * 80)
    print()

    if not ranking_endpoints:

        print(
            "No ranking AJAX endpoints were "
            "discovered in the profile HTML."
        )

        return

    print(
        f"Total ranking endpoints found: "
        f"{len(ranking_endpoints)}"
    )

    for index, endpoint in enumerate(
        ranking_endpoints,
        start=1,
    ):

        print()
        print(
            f"Ranking endpoint {index}"
        )

        print(
            "-" * 80
        )

        print_value(
            "Ranking ID",
            endpoint.get(
                "ranking_id"
            ),
        )

        print_value(
            "QS profile ID",
            endpoint.get(
                "profile_id"
            ),
        )

        print_value(
            "Offset",
            endpoint.get(
                "offset"
            ),
        )

        print_value(
            "Endpoint URL",
            endpoint.get(
                "url"
            ),
        )


# ============================================================
# VALIDATION
# ============================================================

def validate_result(
    result: dict,
) -> None:

    print_separator()
    print("VALIDATION")
    print("=" * 80)
    print()

    errors = []

    source = result.get(
        "source",
        {},
    )

    university = result.get(
        "university",
        {},
    )

    if not source.get(
        "profile_url"
    ):

        errors.append(
            "QS profile URL is missing."
        )

    if not university.get(
        "name"
    ):

        errors.append(
            "University name is missing."
        )

    if errors:

        for error in errors:

            print(
                f"✗ {error}"
            )

        raise AssertionError(
            "QS profile extraction validation failed."
        )

    print(
        "✓ QS profile URL was preserved."
    )

    print(
        "✓ University name was extracted."
    )

    print(
        "✓ Extracted result has a valid structure."
    )


def validate_saved_json(
    json_file: Path,
) -> None:

    print_separator()
    print("VALIDATING SAVED JSON")
    print("=" * 80)
    print()

    if not json_file.exists():

        raise FileNotFoundError(
            f"Extracted JSON file was not created: "
            f"{json_file}"
        )

    with json_file.open(
        "r",
        encoding="utf-8",
    ) as file:

        loaded_data = json.load(
            file
        )

    if not isinstance(
        loaded_data,
        dict,
    ):

        raise AssertionError(
            "Saved profile JSON must contain "
            "a JSON object."
        )

    print(
        "✓ Extracted profile JSON exists."
    )

    print(
        "✓ Extracted profile JSON is valid."
    )

    print(
        "✓ Extracted profile JSON was loaded "
        "successfully."
    )


# ============================================================
# MAIN TEST
# ============================================================

def main() -> None:

    print_separator()
    print("QS PROFILE EXTRACTOR TEST")
    print("=" * 80)
    print()

    print_value(
        "University",
        "Ludwig Maximilian University of Munich",
    )

    print_value(
        "QS profile URL",
        QS_PROFILE_URL,
    )

    print_value(
        "Output directory",
        OUTPUT_DIRECTORY,
    )

    # --------------------------------------------------------
    # Create extractor
    # --------------------------------------------------------

    extractor = QSProfileExtractor(

        timeout=45,

        output_directory=(
            OUTPUT_DIRECTORY
        ),

        save_raw_html=True,
    )

    # --------------------------------------------------------
    # Download and extract QS profile
    # --------------------------------------------------------

    print_separator()
    print("DOWNLOADING QS PROFILE")
    print("=" * 80)
    print()

    print(
        "Requesting the QS university profile..."
    )

    result = extractor.extract(

        profile_url=QS_PROFILE_URL,

        university_slug=(
            UNIVERSITY_SLUG
        ),
    )

    print(
        "✓ QS profile downloaded successfully."
    )

    # --------------------------------------------------------
    # Save extracted JSON
    # --------------------------------------------------------

    json_file = extractor.save_json(

        data=result,

        university_slug=(
            UNIVERSITY_SLUG
        ),
    )

    raw_html_file = (

        OUTPUT_DIRECTORY

        / UNIVERSITY_SLUG

        / "raw"

        / "profile.html"
    )

    # --------------------------------------------------------
    # Extract sections
    # --------------------------------------------------------

    source = result.get(
        "source",
        {},
    )

    identifiers = result.get(
        "identifiers",
        {},
    )

    university = result.get(
        "university",
        {},
    )

    ranking = result.get(
        "ranking",
        {},
    )

    extraction = result.get(
        "extraction",
        {},
    )

    # --------------------------------------------------------
    # Print university information
    # --------------------------------------------------------

    print_separator()
    print("UNIVERSITY PROFILE")
    print("=" * 80)
    print()

    print_value(
        "University name",
        university.get(
            "name"
        ),
    )

    print_value(
        "QS profile URL",
        source.get(
            "profile_url"
        ),
    )

    print_value(
        "University slug",
        source.get(
            "university_slug"
        ),
    )

    print_value(
        "QS profile ID",
        identifiers.get(
            "qs_profile_id"
        ),
    )

    print_value(
        "Drupal node ID",
        identifiers.get(
            "drupal_node_id"
        ),
    )

    print_value(
        "Logo URL",
        university.get(
            "logo_url"
        ),
    )

    print()
    print(
        "Description:"
    )

    print(
        university.get(
            "description",
            "Not found",
        )
    )

    # --------------------------------------------------------
    # Print extracted information
    # --------------------------------------------------------

    print_address(

        university.get(
            "address",
            {},
        )
    )

    print_campuses(

        university.get(
            "campuses",
            [],
        )
    )

    print_social_links(

        university.get(
            "social_links",
            [],
        )
    )

    print_images(

        university.get(
            "image_urls",
            [],
        )
    )

    print_ranking_endpoints(

        ranking.get(
            "discovered_endpoints",
            [],
        )
    )

    # --------------------------------------------------------
    # Print extraction summary
    # --------------------------------------------------------

    print_separator()
    print("EXTRACTION SUMMARY")
    print("=" * 80)
    print()

    print_value(
        "JSON-LD objects found",
        extraction.get(
            "json_ld_items_found",
            0,
        ),
    )

    print_value(
        "Campuses found",
        len(
            university.get(
                "campuses",
                [],
            )
        ),
    )

    print_value(
        "Social links found",
        len(
            university.get(
                "social_links",
                [],
            )
        ),
    )

    print_value(
        "Images found",
        len(
            university.get(
                "image_urls",
                [],
            )
        ),
    )

    print_value(
        "Ranking endpoints found",
        extraction.get(
            "ranking_endpoints_found",
            0,
        ),
    )

    # --------------------------------------------------------
    # Validate result
    # --------------------------------------------------------

    validate_result(
        result
    )

    validate_saved_json(
        json_file
    )

    # --------------------------------------------------------
    # Print generated files
    # --------------------------------------------------------

    print_separator()
    print("GENERATED FILES")
    print("=" * 80)
    print()

    print_value(
        "Raw QS profile",
        raw_html_file,
    )

    print_value(
        "Extracted profile JSON",
        json_file,
    )

    # --------------------------------------------------------
    # Complete
    # --------------------------------------------------------

    print_separator()

    print(
        "✓ QS profile extraction completed."
    )

    print(
        "✓ Raw QS HTML was preserved."
    )

    print(
        "✓ Extracted QS profile JSON is valid."
    )

    print("=" * 80)
    print()


if __name__ == "__main__":

    main()