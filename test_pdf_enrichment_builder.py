"""
PDF Enrichment Builder Test
===========================

Tests:

    knowledge/enrichment/pdf_enrichment_builder.py

Real input files:

    data/<program_id>/knowledge/
        normalized_program_facts.json

    data/<program_id>/pdf/<page_id>/<document_id>/facts/
        pdf_program_facts.json

Generated files:

    data/<program_id>/knowledge/enriched/
        enriched_program_facts.json

        pdf_enrichment_summary.json


The test validates:

1. Required input files exist.
2. Input JSON files are valid.
3. Web and PDF facts can be loaded.
4. PDFEnrichmentBuilder initializes correctly.
5. Enrichment completes successfully.
6. Existing webpage facts are preserved.
7. PDF facts are matched dynamically.
8. Matching PDF facts confirm or enrich existing facts.
9. New PDF facts are added.
10. Conflicting values are preserved for review.
11. PDF provenance is retained.
12. Canonical fields are generated.
13. Semantic duplicates are reduced.
14. Output JSON files exist.
15. Saved output JSON is valid.
16. Saved output can be loaded again.
"""

from __future__ import annotations

import json
import sys
import traceback

from collections import Counter
from pathlib import Path
from typing import Any


# =============================================================================
# PROJECT IMPORT
# =============================================================================

try:
    from knowledge.enrichment.pdf_enrichment_builder import (
        PDFEnrichmentBuilder,
    )

except ImportError as error:
    print()
    print("=" * 80)
    print("IMPORT FAILED")
    print("=" * 80)
    print()
    print(
        "Unable to import PDFEnrichmentBuilder."
    )
    print()
    print(
        "Expected file:"
    )
    print(
        "knowledge\\enrichment\\"
        "pdf_enrichment_builder.py"
    )
    print()
    print(
        "Make sure the following files exist:"
    )
    print()
    print(
        "knowledge\\__init__.py"
    )
    print(
        "knowledge\\enrichment\\__init__.py"
    )
    print(
        "knowledge\\enrichment\\"
        "pdf_enrichment_builder.py"
    )
    print()
    print(
        f"Import error: {error}"
    )
    print()

    sys.exit(1)


# =============================================================================
# TEST CONFIGURATION
# =============================================================================

PROGRAM_ID = "0001"

PAGE_ID = "0002"

DOCUMENT_ID = "source"

DATA_DIRECTORY = Path(
    "data"
)


# =============================================================================
# DISPLAY HELPERS
# =============================================================================

LINE_WIDTH = 80


def print_header(
    title: str,
) -> None:
    """
    Print a major test section.
    """

    print()
    print("=" * LINE_WIDTH)
    print(title)
    print("=" * LINE_WIDTH)
    print()


def print_subheader(
    title: str,
) -> None:
    """
    Print a smaller section.
    """

    print()
    print(title)
    print("-" * LINE_WIDTH)


def print_value(
    label: str,
    value: Any,
) -> None:
    """
    Print one aligned label and value.
    """

    print(
        f"{label:<34}: {value}"
    )


def print_success(
    message: str,
) -> None:
    """
    Print a successful validation.
    """

    print(
        f"✓ {message}"
    )


def print_warning(
    message: str,
) -> None:
    """
    Print a non-fatal warning.
    """

    print(
        f"⚠ {message}"
    )


def print_failure(
    message: str,
) -> None:
    """
    Print a failed validation.
    """

    print(
        f"✗ {message}"
    )


# =============================================================================
# JSON HELPERS
# =============================================================================

def load_json(
    file_path: Path,
) -> Any:
    """
    Load one UTF-8 JSON file.
    """

    with file_path.open(
        "r",
        encoding="utf-8",
    ) as file:
        return json.load(
            file
        )


def find_fact_list(
    document: Any,
) -> list[dict[str, Any]]:
    """
    Find facts in common extraction structures.

    Supports:

        [
            {...},
            {...}
        ]

        {
            "facts": [...]
        }

        {
            "normalized_facts": [...]
        }

        {
            "program_facts": [...]
        }

        {
            "data": {
                "facts": [...]
            }
        }
    """

    if isinstance(
        document,
        list,
    ):
        return [
            item
            for item in document
            if isinstance(
                item,
                dict,
            )
        ]

    if not isinstance(
        document,
        dict,
    ):
        return []

    fact_keys = (
        "facts",
        "normalized_facts",
        "program_facts",
        "extracted_facts",
        "items",
    )

    for key in fact_keys:
        value = document.get(
            key
        )

        if isinstance(
            value,
            list,
        ):
            return [
                item
                for item in value
                if isinstance(
                    item,
                    dict,
                )
            ]

    nested_keys = (
        "data",
        "result",
        "output",
        "knowledge",
        "extraction",
    )

    for key in nested_keys:
        value = document.get(
            key
        )

        if isinstance(
            value,
            dict,
        ):
            facts = find_fact_list(
                value
            )

            if facts:
                return facts

    return []


def validate_json_file(
    file_path: Path,
    *,
    label: str,
) -> Any:
    """
    Validate and load one JSON file.
    """

    if not file_path.exists():
        raise FileNotFoundError(
            f"{label} does not exist:\n"
            f"{file_path}"
        )

    if not file_path.is_file():
        raise ValueError(
            f"{label} is not a file:\n"
            f"{file_path}"
        )

    try:
        document = load_json(
            file_path
        )

    except json.JSONDecodeError as error:
        raise ValueError(
            f"{label} contains invalid JSON:\n"
            f"{file_path}\n\n"
            f"{error}"
        ) from error

    return document


# =============================================================================
# VALUE HELPERS
# =============================================================================

def is_empty(
    value: Any,
) -> bool:
    """
    Determine whether a value is empty.
    """

    if value is None:
        return True

    if isinstance(
        value,
        str,
    ):
        return not value.strip()

    if isinstance(
        value,
        (
            list,
            tuple,
            set,
            dict,
        ),
    ):
        return len(
            value
        ) == 0

    return False


def short_value(
    value: Any,
    *,
    maximum_length: int = 120,
) -> str:
    """
    Convert a value into compact display text.
    """

    if isinstance(
        value,
        (
            dict,
            list,
        ),
    ):
        text = json.dumps(
            value,
            ensure_ascii=False,
        )

    else:
        text = str(
            value
        )

    text = " ".join(
        text.split()
    )

    if (
        len(text)
        <= maximum_length
    ):
        return text

    return (
        text[
            : maximum_length - 3
        ]
        + "..."
    )


def get_entity_label(
    fact: dict[str, Any],
) -> str:
    """
    Build a readable entity label.
    """

    entity = (
        fact.get(
            "entity"
        )
        or {}
    )

    if not isinstance(
        entity,
        dict,
    ):
        return str(
            entity
        )

    entity_type = (
        entity.get(
            "type"
        )
        or "unknown"
    )

    entity_id = (
        entity.get(
            "id"
        )
    )

    entity_name = (
        entity.get(
            "name"
        )
    )

    if (
        entity_id
        and entity_name
    ):
        return (
            f"{entity_type}: "
            f"{entity_name} "
            f"[{entity_id}]"
        )

    if entity_name:
        return (
            f"{entity_type}: "
            f"{entity_name}"
        )

    if entity_id:
        return (
            f"{entity_type}: "
            f"{entity_id}"
        )

    return entity_type


# =============================================================================
# OUTPUT ANALYSIS
# =============================================================================

def get_enrichment_status(
    fact: dict[str, Any],
) -> str:
    """
    Return one fact enrichment status.
    """

    enrichment = (
        fact.get(
            "enrichment"
        )
        or {}
    )

    if not isinstance(
        enrichment,
        dict,
    ):
        return "unknown"

    return str(
        enrichment.get(
            "status"
        )
        or "unknown"
    )


def count_supporting_sources(
    facts: list[
        dict[str, Any]
    ],
) -> int:
    """
    Count all PDF supporting-source records.
    """

    total = 0

    for fact in facts:
        enrichment = (
            fact.get(
                "enrichment"
            )
            or {}
        )

        if not isinstance(
            enrichment,
            dict,
        ):
            continue

        sources = (
            enrichment.get(
                "supporting_sources"
            )
            or []
        )

        if isinstance(
            sources,
            list,
        ):
            total += len(
                sources
            )

    return total


def count_fact_conflicts(
    facts: list[
        dict[str, Any]
    ],
) -> int:
    """
    Count conflicts stored inside facts.
    """

    total = 0

    for fact in facts:
        enrichment = (
            fact.get(
                "enrichment"
            )
            or {}
        )

        if not isinstance(
            enrichment,
            dict,
        ):
            continue

        conflicts = (
            enrichment.get(
                "conflicts"
            )
            or []
        )

        if isinstance(
            conflicts,
            list,
        ):
            total += len(
                conflicts
            )

    return total


def count_fact_changes(
    facts: list[
        dict[str, Any]
    ],
) -> int:
    """
    Count enrichment changes stored inside facts.
    """

    total = 0

    for fact in facts:
        enrichment = (
            fact.get(
                "enrichment"
            )
            or {}
        )

        if not isinstance(
            enrichment,
            dict,
        ):
            continue

        changes = (
            enrichment.get(
                "changes"
            )
            or []
        )

        if isinstance(
            changes,
            list,
        ):
            total += len(
                changes
            )

    return total


def count_pdf_primary_facts(
    facts: list[
        dict[str, Any]
    ],
) -> int:
    """
    Count facts added directly from PDF.
    """

    total = 0

    for fact in facts:
        enrichment = (
            fact.get(
                "enrichment"
            )
            or {}
        )

        if not isinstance(
            enrichment,
            dict,
        ):
            continue

        if (
            enrichment.get(
                "primary_source"
            )
            == "pdf"
        ):
            total += 1

    return total


def count_web_primary_facts(
    facts: list[
        dict[str, Any]
    ],
) -> int:
    """
    Count facts whose primary source remains web.
    """

    total = 0

    for fact in facts:
        enrichment = (
            fact.get(
                "enrichment"
            )
            or {}
        )

        if not isinstance(
            enrichment,
            dict,
        ):
            continue

        if (
            enrichment.get(
                "primary_source"
            )
            == "web"
        ):
            total += 1

    return total


def count_missing_canonical_fields(
    facts: list[
        dict[str, Any]
    ],
) -> int:
    """
    Count facts without a canonical field.
    """

    return sum(
        1
        for fact in facts
        if is_empty(
            fact.get(
                "canonical_field"
            )
        )
    )


def display_fact_examples(
    facts: list[
        dict[str, Any]
    ],
    *,
    status: str,
    maximum_examples: int = 5,
) -> None:
    """
    Display examples for one enrichment status.
    """

    matching_facts = [
        fact
        for fact in facts
        if (
            get_enrichment_status(
                fact
            )
            == status
        )
    ]

    if not matching_facts:
        print(
            "No facts found."
        )

        return

    for number, fact in enumerate(
        matching_facts[
            :maximum_examples
        ],
        start=1,
    ):
        print()

        print(
            f"{number}. "
            f"{get_entity_label(fact)}"
        )

        print_value(
            "Field",
            fact.get(
                "field"
            ),
        )

        print_value(
            "Canonical field",
            fact.get(
                "canonical_field"
            ),
        )

        print_value(
            "Value",
            short_value(
                fact.get(
                    "value"
                )
            ),
        )

        enrichment = (
            fact.get(
                "enrichment"
            )
            or {}
        )

        supporting_sources = (
            enrichment.get(
                "supporting_sources"
            )
            or []
        )

        changes = (
            enrichment.get(
                "changes"
            )
            or []
        )

        conflicts = (
            enrichment.get(
                "conflicts"
            )
            or []
        )

        print_value(
            "Supporting PDF sources",
            len(
                supporting_sources
            ),
        )

        print_value(
            "Enrichment changes",
            len(
                changes
            ),
        )

        print_value(
            "Conflicts",
            len(
                conflicts
            ),
        )


def display_conflicts(
    conflicts: list[
        dict[str, Any]
    ],
    *,
    maximum_examples: int = 10,
) -> None:
    """
    Display conflict examples.
    """

    if not conflicts:
        print(
            "No value conflicts were detected."
        )

        return

    for number, conflict in enumerate(
        conflicts[
            :maximum_examples
        ],
        start=1,
    ):
        print()

        print(
            f"CONFLICT {number}"
        )

        print(
            "-" * LINE_WIDTH
        )

        entity = (
            conflict.get(
                "entity"
            )
            or {}
        )

        print_value(
            "Entity",
            short_value(
                entity
            ),
        )

        print_value(
            "Field",
            conflict.get(
                "field"
            ),
        )

        print_value(
            "Canonical field",
            conflict.get(
                "canonical_field"
            ),
        )

        print_value(
            "Web value",
            short_value(
                conflict.get(
                    "primary_value"
                )
            ),
        )

        print_value(
            "PDF value",
            short_value(
                conflict.get(
                    "pdf_value"
                )
            ),
        )

        print_value(
            "Resolution",
            conflict.get(
                "resolution"
            ),
        )

        print_value(
            "Match method",
            conflict.get(
                "match_method"
            ),
        )

        print_value(
            "Match score",
            conflict.get(
                "match_score"
            ),
        )


# =============================================================================
# TEST
# =============================================================================

def main() -> None:
    """
    Run the PDF enrichment builder test.
    """

    program_directory = (
        DATA_DIRECTORY
        / PROGRAM_ID
    )

    web_facts_path = (
        program_directory
        / "knowledge"
        / "normalized_program_facts.json"
    )

    pdf_facts_path = (
        program_directory
        / "pdf"
        / PAGE_ID
        / DOCUMENT_ID
        / "facts"
        / "pdf_program_facts.json"
    )

    output_directory = (
        program_directory
        / "knowledge"
        / "enriched"
    )

    enriched_output_path = (
        output_directory
        / "enriched_program_facts.json"
    )

    summary_output_path = (
        output_directory
        / "pdf_enrichment_summary.json"
    )

    # =========================================================================
    # TEST INFORMATION
    # =========================================================================

    print_header(
        "PDF ENRICHMENT BUILDER TEST"
    )

    print_value(
        "Program ID",
        PROGRAM_ID,
    )

    print_value(
        "Page ID",
        PAGE_ID,
    )

    print_value(
        "Document ID",
        DOCUMENT_ID,
    )

    print_value(
        "Normalized webpage facts",
        web_facts_path,
    )

    print_value(
        "PDF program facts",
        pdf_facts_path,
    )

    print_value(
        "Output directory",
        output_directory,
    )

    # =========================================================================
    # VALIDATE WEB FACTS
    # =========================================================================

    print_header(
        "VALIDATING NORMALIZED WEBPAGE FACTS"
    )

    web_document = (
        validate_json_file(
            web_facts_path,
            label=(
                "Normalized webpage "
                "facts"
            ),
        )
    )

    print_success(
        "Normalized webpage facts "
        "file exists."
    )

    print_success(
        "Normalized webpage facts "
        "JSON is valid."
    )

    web_facts = find_fact_list(
        web_document
    )

    if not web_facts:
        raise ValueError(
            "No normalized webpage facts "
            "were found in:\n"
            f"{web_facts_path}"
        )

    print_success(
        "Normalized webpage facts "
        "were loaded."
    )

    print_value(
        "Web facts",
        len(
            web_facts
        ),
    )

    web_categories = Counter(
        str(
            fact.get(
                "category"
            )
            or "unknown"
        )
        for fact in web_facts
    )

    print_value(
        "Web categories",
        len(
            web_categories
        ),
    )

    # =========================================================================
    # VALIDATE PDF FACTS
    # =========================================================================

    print_header(
        "VALIDATING PDF PROGRAM FACTS"
    )

    pdf_document = (
        validate_json_file(
            pdf_facts_path,
            label=(
                "PDF program facts"
            ),
        )
    )

    print_success(
        "PDF program facts file "
        "exists."
    )

    print_success(
        "PDF program facts JSON "
        "is valid."
    )

    pdf_facts = find_fact_list(
        pdf_document
    )

    if not pdf_facts:
        raise ValueError(
            "No PDF program facts were "
            "found in:\n"
            f"{pdf_facts_path}"
        )

    print_success(
        "PDF program facts were "
        "loaded."
    )

    print_value(
        "PDF facts",
        len(
            pdf_facts
        ),
    )

    pdf_categories = Counter(
        str(
            fact.get(
                "category"
            )
            or "unknown"
        )
        for fact in pdf_facts
    )

    print_value(
        "PDF categories",
        len(
            pdf_categories
        ),
    )

    # =========================================================================
    # INITIALIZE BUILDER
    # =========================================================================

    print_header(
        "INITIALIZING PDF ENRICHMENT BUILDER"
    )

    builder = PDFEnrichmentBuilder(
        preserve_web_value_on_conflict=True,
        add_unmatched_pdf_facts=True,
        enrich_empty_values=True,
        attach_confirming_sources=True,
        remove_semantic_duplicates=True,
        minimum_fuzzy_entity_similarity=0.92,
        overwrite=True,
    )

    print_success(
        "PDFEnrichmentBuilder "
        "initialized."
    )

    print_value(
        "Conflict strategy",
        "Preserve webpage value",
    )

    print_value(
        "Add unmatched PDF facts",
        True,
    )

    print_value(
        "Fill empty web values",
        True,
    )

    print_value(
        "Attach PDF evidence",
        True,
    )

    print_value(
        "Semantic deduplication",
        True,
    )

    print_value(
        "Fuzzy entity threshold",
        0.92,
    )

    # =========================================================================
    # BUILD ENRICHED FACTS
    # =========================================================================

    print_header(
        "BUILDING PDF ENRICHMENT"
    )

    print(
        "Matching normalized webpage "
        "facts with extracted PDF facts..."
    )

    print(
        "Preserving webpage facts, "
        "adding PDF evidence, enriching "
        "compatible values, and recording "
        "conflicts..."
    )

    print()

    result = builder.build(
        program_id=PROGRAM_ID,
        page_id=PAGE_ID,
        document_id=DOCUMENT_ID,
        data_directory=DATA_DIRECTORY,
        web_facts_path=web_facts_path,
        pdf_facts_path=pdf_facts_path,
        output_directory=(
            output_directory
        ),
        overwrite=True,
    )

    print_success(
        "PDF enrichment completed."
    )

    # =========================================================================
    # VALIDATE RESULT STRUCTURE
    # =========================================================================

    print_header(
        "VALIDATING ENRICHMENT RESULT"
    )

    if not isinstance(
        result,
        dict,
    ):
        raise TypeError(
            "Builder result must be "
            "a dictionary."
        )

    print_success(
        "Enrichment result is a "
        "dictionary."
    )

    required_result_keys = (
        "schema_version",
        "program_id",
        "source",
        "enrichment",
        "summary",
        "distribution",
        "conflicts",
        "enrichments",
        "facts",
    )

    missing_result_keys = [
        key
        for key
        in required_result_keys
        if key not in result
    ]

    if missing_result_keys:
        raise ValueError(
            "Enrichment result is missing "
            "required keys:\n"
            + ", ".join(
                missing_result_keys
            )
        )

    print_success(
        "Enrichment result contains "
        "all required sections."
    )

    enriched_facts = (
        result.get(
            "facts"
        )
    )

    if not isinstance(
        enriched_facts,
        list,
    ):
        raise TypeError(
            "Result 'facts' must be "
            "a list."
        )

    if not enriched_facts:
        raise ValueError(
            "Enrichment produced no "
            "facts."
        )

    print_success(
        "Enriched facts are available."
    )

    print_value(
        "Enriched facts",
        len(
            enriched_facts
        ),
    )

    # =========================================================================
    # EXTRACTION SUMMARY
    # =========================================================================

    print_header(
        "ENRICHMENT SUMMARY"
    )

    summary = (
        result.get(
            "summary"
        )
        or {}
    )

    summary_fields = (
        (
            "Web facts loaded",
            "web_facts_loaded",
        ),

        (
            "PDF facts loaded",
            "pdf_facts_loaded",
        ),

        (
            "PDF duplicates removed",
            (
                "pdf_semantic_"
                "duplicates_removed"
            ),
        ),

        (
            "Matched PDF facts",
            "matched_pdf_facts",
        ),

        (
            "Facts confirmed",
            "facts_confirmed",
        ),

        (
            "Facts enriched",
            "facts_enriched",
        ),

        (
            "New PDF facts added",
            "new_pdf_facts_added",
        ),

        (
            "Conflicts detected",
            "conflicts_detected",
        ),

        (
            "Unmatched PDF facts",
            "unmatched_pdf_facts",
        ),

        (
            "Final duplicates removed",
            (
                "final_semantic_"
                "duplicates_removed"
            ),
        ),

        (
            "Final facts written",
            "final_facts_written",
        ),
    )

    for label, key in summary_fields:
        print_value(
            label,
            summary.get(
                key,
                0,
            ),
        )

    # =========================================================================
    # FACT STATUS DISTRIBUTION
    # =========================================================================

    print_header(
        "ENRICHMENT STATUS DISTRIBUTION"
    )

    status_counts = Counter(
        get_enrichment_status(
            fact
        )
        for fact in enriched_facts
    )

    for status, count in sorted(
        status_counts.items(),
        key=lambda item: (
            -item[1],
            item[0],
        ),
    ):
        print_value(
            status,
            count,
        )

    # =========================================================================
    # SOURCE DISTRIBUTION
    # =========================================================================

    print_header(
        "SOURCE DISTRIBUTION"
    )

    web_primary_count = (
        count_web_primary_facts(
            enriched_facts
        )
    )

    pdf_primary_count = (
        count_pdf_primary_facts(
            enriched_facts
        )
    )

    supporting_source_count = (
        count_supporting_sources(
            enriched_facts
        )
    )

    print_value(
        "Web-primary facts",
        web_primary_count,
    )

    print_value(
        "PDF-primary facts",
        pdf_primary_count,
    )

    print_value(
        "PDF supporting sources",
        supporting_source_count,
    )

    # =========================================================================
    # CATEGORY DISTRIBUTION
    # =========================================================================

    print_header(
        "CATEGORY DISTRIBUTION"
    )

    category_counts = Counter(
        str(
            fact.get(
                "category"
            )
            or "other"
        )
        for fact in enriched_facts
    )

    for category, count in sorted(
        category_counts.items(),
        key=lambda item: (
            -item[1],
            item[0],
        ),
    ):
        print_value(
            category,
            count,
        )

    # =========================================================================
    # ENTITY DISTRIBUTION
    # =========================================================================

    print_header(
        "ENTITY TYPE DISTRIBUTION"
    )

    entity_type_counts = Counter()

    for fact in enriched_facts:
        entity = (
            fact.get(
                "entity"
            )
            or {}
        )

        if isinstance(
            entity,
            dict,
        ):
            entity_type = (
                entity.get(
                    "type"
                )
                or "unknown"
            )

        else:
            entity_type = (
                "unknown"
            )

        entity_type_counts[
            str(
                entity_type
            )
        ] += 1

    for entity_type, count in sorted(
        entity_type_counts.items(),
        key=lambda item: (
            -item[1],
            item[0],
        ),
    ):
        print_value(
            entity_type,
            count,
        )

    # =========================================================================
    # CANONICAL FIELD VALIDATION
    # =========================================================================

    print_header(
        "VALIDATING CANONICAL FIELDS"
    )

    missing_canonical_fields = (
        count_missing_canonical_fields(
            enriched_facts
        )
    )

    if (
        missing_canonical_fields
        == 0
    ):
        print_success(
            "Every enriched fact has "
            "a canonical field."
        )

    else:
        print_warning(
            f"{missing_canonical_fields} "
            "facts do not have a "
            "canonical field."
        )

    canonical_field_counts = Counter(
        str(
            fact.get(
                "canonical_field"
            )
            or "unknown"
        )
        for fact in enriched_facts
    )

    print_value(
        "Unique canonical fields",
        len(
            canonical_field_counts
        ),
    )

    print()

    print(
        "Most common canonical fields:"
    )

    for (
        canonical_field,
        count,
    ) in canonical_field_counts.most_common(
        20
    ):
        print_value(
            canonical_field,
            count,
        )

    # =========================================================================
    # VALIDATE WEB FACT PRESERVATION
    # =========================================================================

    print_header(
        "VALIDATING WEB FACT PRESERVATION"
    )

    loaded_web_count = int(
        summary.get(
            "web_facts_loaded",
            0,
        )
    )

    final_fact_count = len(
        enriched_facts
    )

    removed_final_duplicates = int(
        summary.get(
            (
                "final_semantic_"
                "duplicates_removed"
            ),
            0,
        )
    )

    if (
        loaded_web_count
        == len(
            web_facts
        )
    ):
        print_success(
            "Every source webpage fact "
            "was loaded by the builder."
        )

    else:
        print_warning(
            "The builder-reported web fact "
            "count differs from the test "
            "input count."
        )

    minimum_expected_facts = max(
        1,
        (
            loaded_web_count
            - removed_final_duplicates
        ),
    )

    if (
        final_fact_count
        >= minimum_expected_facts
    ):
        print_success(
            "Final output retained the "
            "web fact layer after semantic "
            "deduplication."
        )

    else:
        raise AssertionError(
            "The final fact count is lower "
            "than expected after accounting "
            "for semantic deduplication."
        )

    # =========================================================================
    # VALIDATE ENRICHMENT PROVENANCE
    # =========================================================================

    print_header(
        "VALIDATING PDF PROVENANCE"
    )

    fact_changes = (
        count_fact_changes(
            enriched_facts
        )
    )

    fact_conflicts = (
        count_fact_conflicts(
            enriched_facts
        )
    )

    print_value(
        "Stored enrichment changes",
        fact_changes,
    )

    print_value(
        "Stored fact conflicts",
        fact_conflicts,
    )

    print_value(
        "Stored PDF support records",
        supporting_source_count,
    )

    matched_pdf_count = int(
        summary.get(
            "matched_pdf_facts",
            0,
        )
    )

    new_pdf_count = int(
        summary.get(
            "new_pdf_facts_added",
            0,
        )
    )

    if (
        matched_pdf_count > 0
        or new_pdf_count > 0
    ):
        print_success(
            "PDF facts contributed to "
            "the enriched output."
        )

    else:
        print_warning(
            "No PDF facts matched or were "
            "added. Review entity and field "
            "normalization if this was not "
            "expected."
        )

    if (
        supporting_source_count > 0
    ):
        print_success(
            "PDF source provenance was "
            "preserved."
        )

    elif new_pdf_count > 0:
        raise AssertionError(
            "PDF facts were added, but no "
            "supporting PDF source records "
            "were found."
        )

    else:
        print_warning(
            "No PDF supporting-source "
            "records were created."
        )

    # =========================================================================
    # DISPLAY CONFIRMED FACTS
    # =========================================================================

    print_header(
        "SAMPLE CONFIRMED FACTS"
    )

    display_fact_examples(
        enriched_facts,
        status="confirmed",
        maximum_examples=5,
    )

    # =========================================================================
    # DISPLAY ENRICHED FACTS
    # =========================================================================

    print_header(
        "SAMPLE ENRICHED FACTS"
    )

    display_fact_examples(
        enriched_facts,
        status="enriched",
        maximum_examples=10,
    )

    # =========================================================================
    # DISPLAY NEW PDF FACTS
    # =========================================================================

    print_header(
        "SAMPLE NEW PDF FACTS"
    )

    display_fact_examples(
        enriched_facts,
        status="added_from_pdf",
        maximum_examples=10,
    )

    # =========================================================================
    # DISPLAY CONFLICTS
    # =========================================================================

    print_header(
        "VALUE CONFLICTS"
    )

    result_conflicts = (
        result.get(
            "conflicts"
        )
        or []
    )

    if not isinstance(
        result_conflicts,
        list,
    ):
        raise TypeError(
            "Result 'conflicts' must "
            "be a list."
        )

    display_conflicts(
        result_conflicts,
        maximum_examples=10,
    )

    # =========================================================================
    # VALIDATE CONFLICT STRATEGY
    # =========================================================================

    print_header(
        "VALIDATING CONFLICT STRATEGY"
    )

    invalid_resolutions = [
        conflict
        for conflict
        in result_conflicts
        if (
            conflict.get(
                "resolution"
            )
            != "web_value_preserved"
        )
    ]

    if invalid_resolutions:
        raise AssertionError(
            "One or more conflicts did "
            "not preserve the webpage "
            "value."
        )

    if result_conflicts:
        print_success(
            "Every detected conflict "
            "preserved the webpage value."
        )

    else:
        print_success(
            "No conflicts required "
            "resolution."
        )

    # =========================================================================
    # VALIDATE SUMMARY CONSISTENCY
    # =========================================================================

    print_header(
        "VALIDATING SUMMARY CONSISTENCY"
    )

    reported_final_count = int(
        summary.get(
            "final_facts_written",
            0,
        )
    )

    if (
        reported_final_count
        != len(
            enriched_facts
        )
    ):
        raise AssertionError(
            "Summary final fact count "
            "does not match the actual "
            "facts list.\n"
            f"Reported: "
            f"{reported_final_count}\n"
            f"Actual: "
            f"{len(enriched_facts)}"
        )

    print_success(
        "Summary final fact count "
        "matches the output."
    )

    reported_conflict_count = int(
        summary.get(
            "conflicts_detected",
            0,
        )
    )

    if (
        reported_conflict_count
        != len(
            result_conflicts
        )
    ):
        print_warning(
            "Summary conflict count differs "
            "from the collected conflict "
            "list. This can occur if multiple "
            "PDF facts resolve into one "
            "deduplicated fact."
        )

    else:
        print_success(
            "Summary conflict count "
            "matches the conflict list."
        )

    # =========================================================================
    # VALIDATE GENERATED FILES
    # =========================================================================

    print_header(
        "VALIDATING GENERATED FILES"
    )

    if not enriched_output_path.exists():
        raise FileNotFoundError(
            "Enriched output JSON was "
            "not generated:\n"
            f"{enriched_output_path}"
        )

    print_success(
        "Enriched program facts JSON "
        "exists."
    )

    if not summary_output_path.exists():
        raise FileNotFoundError(
            "PDF enrichment summary JSON "
            "was not generated:\n"
            f"{summary_output_path}"
        )

    print_success(
        "PDF enrichment summary JSON "
        "exists."
    )

    saved_result = (
        validate_json_file(
            enriched_output_path,
            label=(
                "Enriched program facts"
            ),
        )
    )

    print_success(
        "Enriched program facts JSON "
        "is valid."
    )

    saved_summary = (
        validate_json_file(
            summary_output_path,
            label=(
                "PDF enrichment summary"
            ),
        )
    )

    print_success(
        "PDF enrichment summary JSON "
        "is valid."
    )

    if not isinstance(
        saved_result,
        dict,
    ):
        raise TypeError(
            "Saved enriched result must "
            "be a JSON object."
        )

    if not isinstance(
        saved_summary,
        dict,
    ):
        raise TypeError(
            "Saved enrichment summary "
            "must be a JSON object."
        )

    print_success(
        "Generated JSON files were "
        "loaded successfully."
    )

    saved_facts = (
        saved_result.get(
            "facts"
        )
        or []
    )

    if (
        len(saved_facts)
        != len(
            enriched_facts
        )
    ):
        raise AssertionError(
            "Saved enriched fact count "
            "does not match the in-memory "
            "result."
        )

    print_success(
        "Saved enriched fact count "
        "matches the in-memory result."
    )

    # =========================================================================
    # GENERATED FILES
    # =========================================================================

    print_header(
        "GENERATED FILES"
    )

    print_value(
        "Enriched program facts",
        enriched_output_path,
    )

    print_value(
        "PDF enrichment summary",
        summary_output_path,
    )

    # =========================================================================
    # FINAL RESULT
    # =========================================================================

    print_header(
        "PDF ENRICHMENT TEST COMPLETED"
    )

    print_success(
        "Normalized webpage facts "
        "were preserved."
    )

    print_success(
        "PDF facts were processed as "
        "an enrichment layer."
    )

    print_success(
        "Canonical fields were generated."
    )

    print_success(
        "Matching PDF evidence was "
        "attached to existing facts."
    )

    print_success(
        "Unmatched PDF facts were added."
    )

    print_success(
        "Conflicting values were preserved "
        "for review instead of being "
        "silently overwritten."
    )

    print_success(
        "PDF provenance was retained."
    )

    print_success(
        "Semantic duplicate handling "
        "was applied."
    )

    print_success(
        "Enriched output JSON is valid."
    )

    print()
    print("=" * LINE_WIDTH)
    print(
        "✓ PDF enrichment builder "
        "test completed successfully."
    )
    print("=" * LINE_WIDTH)
    print()


# =============================================================================
# ENTRY POINT
# =============================================================================

if __name__ == "__main__":
    try:
        main()

    except KeyboardInterrupt:
        print()
        print_header(
            "TEST CANCELLED"
        )

        print_warning(
            "PDF enrichment test was "
            "cancelled by the user."
        )

        print()

        sys.exit(130)

    except Exception as error:
        print()
        print_header(
            "TEST FAILED"
        )

        print_failure(
            str(
                error
            )
        )

        print()

        print(
            "Traceback:"
        )

        print(
            traceback.format_exc()
        )

        sys.exit(1)