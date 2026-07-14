"""
PDF Evidence Builder Test
=========================

Tests the complete PDF evidence-building pipeline:

Azure Document Intelligence output
        ↓
document_data.json + document.md
        ↓
PDFEvidenceBuilder
        ↓
Structure-aware evidence chunks
        ↓
pdf_evidence_chunks.json

Run from the project root:

    python test_pdf_evidence_builder.py
"""

from __future__ import annotations

import json
import sys
import traceback

from collections import Counter
from pathlib import Path
from typing import Any, Dict, List


# ====================================================================
# Project imports
# ====================================================================

from knowledge.pdf.pdf_evidence_builder import (
    PDFEvidenceBuilder,
)


# ====================================================================
# Test configuration
# ====================================================================

PROGRAM_ID = "0001"
PAGE_ID = "0002"
DOCUMENT_ID = "source"

UNIVERSITY_NAME = None
PROGRAM_NAME = None

DOCUMENT_DATA_PATH = Path(
    "data"
) / PROGRAM_ID / "pdf" / PAGE_ID / DOCUMENT_ID / (
    "extracted"
) / "document_data.json"

EXTRACTED_DIRECTORY = (
    DOCUMENT_DATA_PATH.parent
)

SOURCE_PDF_PATH = (
    Path("data")
    / PROGRAM_ID
    / "pages"
    / PAGE_ID
    / "assets"
    / "source.pdf"
)

OUTPUT_DIRECTORY = (
    Path("data")
    / PROGRAM_ID
    / "pdf"
    / PAGE_ID
    / DOCUMENT_ID
    / "evidence"
)

OUTPUT_FILE = (
    OUTPUT_DIRECTORY
    / "pdf_evidence_chunks.json"
)


# ====================================================================
# Evidence-builder configuration
# ====================================================================

TARGET_CHUNK_CHARACTERS = 6500

MAX_CHUNK_CHARACTERS = 9000

MIN_CHUNK_CHARACTERS = 250

OVERLAP_CHARACTERS = 350

REMOVE_REPEATED_NOISE = True

PRESERVE_TABLES = True

OVERWRITE_EXISTING_OUTPUT = True


# ====================================================================
# Display configuration
# ====================================================================

SEPARATOR_WIDTH = 80

CHUNK_PREVIEW_CHARACTERS = 500

MAX_CHUNKS_TO_DISPLAY = 20

MAX_SECTION_TYPES_TO_DISPLAY = 30

MAX_REPEATED_NOISE_LINES_TO_DISPLAY = 20


# ====================================================================
# Console helpers
# ====================================================================


def print_header(
    title: str,
) -> None:
    """
    Print a major console section.
    """

    print()
    print(
        "=" * SEPARATOR_WIDTH
    )
    print(
        title
    )
    print(
        "=" * SEPARATOR_WIDTH
    )
    print()


def print_subheader(
    title: str,
) -> None:
    """
    Print a smaller console section.
    """

    print()
    print(
        title
    )
    print(
        "-" * SEPARATOR_WIDTH
    )


def print_field(
    label: str,
    value: Any,
) -> None:
    """
    Print one aligned label-value pair.
    """

    if value is None:
        value = "Not found"

    elif value == "":
        value = "Not found"

    print(
        f"{label:<32}: {value}"
    )


def print_success(
    message: str,
) -> None:
    """
    Print a successful validation message.
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


def print_error(
    message: str,
) -> None:
    """
    Print an error message.
    """

    print(
        f"✗ {message}"
    )


# ====================================================================
# JSON helpers
# ====================================================================


def load_json(
    file_path: Path,
) -> Dict[str, Any]:
    """
    Load and validate a JSON object.
    """

    with file_path.open(
        "r",
        encoding="utf-8",
    ) as file:
        payload = json.load(
            file
        )

    if not isinstance(
        payload,
        dict,
    ):
        raise TypeError(
            "Expected a JSON object in "
            f"{file_path}."
        )

    return payload


def get_nested(
    payload: Dict[str, Any],
    *keys: str,
    default: Any = None,
) -> Any:
    """
    Safely retrieve a nested dictionary value.
    """

    current: Any = payload

    for key in keys:
        if not isinstance(
            current,
            dict,
        ):
            return default

        if key not in current:
            return default

        current = current[
            key
        ]

    return current


# ====================================================================
# Text helpers
# ====================================================================


def create_preview(
    content: str,
    maximum_characters: int,
) -> str:
    """
    Create a readable one-line content preview.
    """

    cleaned = " ".join(
        str(
            content
        ).split()
    )

    if (
        len(
            cleaned
        )
        <= maximum_characters
    ):
        return cleaned

    return (
        cleaned[
            :maximum_characters
        ].rstrip()
        + "..."
    )


def format_page_numbers(
    page_numbers: Any,
) -> str:
    """
    Format page references for console output.
    """

    if not isinstance(
        page_numbers,
        list,
    ):
        return "Not mapped"

    valid_pages = [
        page
        for page in page_numbers
        if isinstance(
            page,
            int,
        )
    ]

    if not valid_pages:
        return "Not mapped"

    if len(
        valid_pages
    ) == 1:
        return str(
            valid_pages[0]
        )

    consecutive = all(
        valid_pages[index]
        == valid_pages[index - 1]
        + 1
        for index in range(
            1,
            len(
                valid_pages
            ),
        )
    )

    if consecutive:
        return (
            f"{valid_pages[0]}"
            f"-"
            f"{valid_pages[-1]}"
        )

    return ", ".join(
        str(
            page
        )
        for page in valid_pages
    )


# ====================================================================
# Input validation
# ====================================================================


def validate_input_files() -> None:
    """
    Validate all required evidence-builder inputs.
    """

    print_header(
        "VALIDATING INPUT FILES"
    )

    print_field(
        "Document data",
        DOCUMENT_DATA_PATH,
    )

    print_field(
        "Extracted directory",
        EXTRACTED_DIRECTORY,
    )

    print_field(
        "Source PDF",
        SOURCE_PDF_PATH,
    )

    print_field(
        "Output directory",
        OUTPUT_DIRECTORY,
    )

    print()

    if not DOCUMENT_DATA_PATH.exists():
        raise FileNotFoundError(
            "Azure document data was not found:\n"
            f"{DOCUMENT_DATA_PATH}\n\n"
            "Run test_azure_document_extractor.py "
            "before running this test."
        )

    if not DOCUMENT_DATA_PATH.is_file():
        raise RuntimeError(
            "The document-data path exists but "
            "is not a file:\n"
            f"{DOCUMENT_DATA_PATH}"
        )

    print_success(
        "document_data.json exists."
    )

    markdown_path = (
        EXTRACTED_DIRECTORY
        / "document.md"
    )

    if markdown_path.exists():
        print_success(
            "document.md exists."
        )

        markdown_size = (
            markdown_path.stat().st_size
        )

        print_field(
            "Markdown size",
            (
                f"{markdown_size:,} bytes"
            ),
        )

    else:
        print_warning(
            "document.md was not found. "
            "The builder will attempt to use "
            "Markdown embedded in document_data.json."
        )

    text_path = (
        EXTRACTED_DIRECTORY
        / "document.txt"
    )

    if text_path.exists():
        print_success(
            "document.txt exists."
        )

    else:
        print_warning(
            "document.txt was not found."
        )

    tables_path = (
        EXTRACTED_DIRECTORY
        / "tables.json"
    )

    if tables_path.exists():
        print_success(
            "tables.json exists."
        )

    else:
        print_warning(
            "tables.json was not found. "
            "This is not fatal because tables may "
            "already exist in document.md."
        )

    if SOURCE_PDF_PATH.exists():
        print_success(
            "Original source PDF exists."
        )

        pdf_size_mb = (
            SOURCE_PDF_PATH.stat().st_size
            / (
                1024
                * 1024
            )
        )

        print_field(
            "Source PDF size",
            f"{pdf_size_mb:.2f} MB",
        )

    else:
        print_warning(
            "Original source PDF was not found at "
            f"{SOURCE_PDF_PATH}. Evidence generation "
            "can continue because Azure extraction "
            "output already exists."
        )

    input_payload = load_json(
        DOCUMENT_DATA_PATH
    )

    print_success(
        "document_data.json contains valid JSON."
    )

    print_field(
        "Top-level JSON keys",
        len(
            input_payload
        ),
    )


# ====================================================================
# Builder initialization
# ====================================================================


def create_builder() -> PDFEvidenceBuilder:
    """
    Initialize and display PDFEvidenceBuilder configuration.
    """

    print_header(
        "INITIALIZING PDF EVIDENCE BUILDER"
    )

    builder = PDFEvidenceBuilder(
        target_chunk_characters=(
            TARGET_CHUNK_CHARACTERS
        ),
        max_chunk_characters=(
            MAX_CHUNK_CHARACTERS
        ),
        min_chunk_characters=(
            MIN_CHUNK_CHARACTERS
        ),
        overlap_characters=(
            OVERLAP_CHARACTERS
        ),
        remove_repeated_noise=(
            REMOVE_REPEATED_NOISE
        ),
        preserve_tables=(
            PRESERVE_TABLES
        ),
    )

    print_success(
        "PDFEvidenceBuilder initialized."
    )

    print_field(
        "Target chunk characters",
        TARGET_CHUNK_CHARACTERS,
    )

    print_field(
        "Maximum chunk characters",
        MAX_CHUNK_CHARACTERS,
    )

    print_field(
        "Minimum chunk characters",
        MIN_CHUNK_CHARACTERS,
    )

    print_field(
        "Chunk overlap",
        OVERLAP_CHARACTERS,
    )

    print_field(
        "Remove repeated noise",
        REMOVE_REPEATED_NOISE,
    )

    print_field(
        "Preserve complete tables",
        PRESERVE_TABLES,
    )

    print_field(
        "Overwrite existing output",
        OVERWRITE_EXISTING_OUTPUT,
    )

    return builder


# ====================================================================
# Evidence generation
# ====================================================================


def build_evidence(
    builder: PDFEvidenceBuilder,
) -> Dict[str, Any]:
    """
    Run the complete PDF evidence-building pipeline.
    """

    print_header(
        "BUILDING PDF EVIDENCE"
    )

    print(
        "Reading Azure document extraction..."
    )

    print(
        "Cleaning repeated document noise..."
    )

    print(
        "Detecting headings and logical sections..."
    )

    print(
        "Preserving Markdown and HTML tables..."
    )

    print(
        "Building structure-aware evidence chunks..."
    )

    print(
        "Attaching source and page metadata..."
    )

    print()

    result = builder.build(
        document_data_path=(
            DOCUMENT_DATA_PATH
        ),
        output_dir=(
            OUTPUT_DIRECTORY
        ),
        program_id=(
            PROGRAM_ID
        ),
        page_id=(
            PAGE_ID
        ),
        document_id=(
            DOCUMENT_ID
        ),
        source_pdf_path=(
            SOURCE_PDF_PATH
            if SOURCE_PDF_PATH.exists()
            else None
        ),
        university_name=(
            UNIVERSITY_NAME
        ),
        program_name=(
            PROGRAM_NAME
        ),
        overwrite=(
            OVERWRITE_EXISTING_OUTPUT
        ),
    )

    print_success(
        "PDF evidence generation completed."
    )

    print_success(
        "Evidence chunks were created."
    )

    print_success(
        "Evidence output was saved."
    )

    return result


# ====================================================================
# Result display
# ====================================================================


def display_document_identity(
    result: Dict[str, Any],
) -> None:
    """
    Display source and identity metadata.
    """

    print_header(
        "DOCUMENT IDENTITY"
    )

    identity = result.get(
        "identity",
        {},
    )

    source = result.get(
        "source",
        {},
    )

    print_field(
        "University",
        identity.get(
            "university_name"
        ),
    )

    print_field(
        "Program",
        identity.get(
            "program_name"
        ),
    )

    print_field(
        "Program ID",
        identity.get(
            "program_id"
        ),
    )

    print_field(
        "Page ID",
        identity.get(
            "page_id"
        ),
    )

    print_field(
        "Document ID",
        identity.get(
            "document_id"
        ),
    )

    print_field(
        "Source type",
        source.get(
            "source_type"
        ),
    )

    print_field(
        "Provider",
        source.get(
            "provider"
        ),
    )

    print_field(
        "Source filename",
        source.get(
            "filename"
        ),
    )

    print_field(
        "PDF pages",
        source.get(
            "page_count"
        ),
    )

    print_field(
        "Source PDF",
        source.get(
            "pdf_path"
        ),
    )

    print_field(
        "Document data",
        source.get(
            "document_data_path"
        ),
    )


def display_extraction_statistics(
    result: Dict[str, Any],
) -> None:
    """
    Display evidence-generation statistics.
    """

    print_header(
        "EVIDENCE EXTRACTION SUMMARY"
    )

    statistics = result.get(
        "statistics",
        {},
    )

    print_field(
        "Original characters",
        (
            f"{statistics.get('original_character_count', 0):,}"
        ),
    )

    print_field(
        "Cleaned characters",
        (
            f"{statistics.get('cleaned_character_count', 0):,}"
        ),
    )

    print_field(
        "Characters removed",
        (
            f"{statistics.get('characters_removed', 0):,}"
        ),
    )

    print_field(
        "Sections detected",
        statistics.get(
            "sections_detected",
            0,
        ),
    )

    print_field(
        "Evidence chunks created",
        statistics.get(
            "chunks_created",
            0,
        ),
    )

    print_field(
        "Total chunk characters",
        (
            f"{statistics.get('total_chunk_characters', 0):,}"
        ),
    )

    print_field(
        "Total chunk words",
        (
            f"{statistics.get('total_chunk_words', 0):,}"
        ),
    )

    print_field(
        "Chunks with page references",
        statistics.get(
            "chunks_with_page_references",
            0,
        ),
    )

    print_field(
        "Chunks without page references",
        statistics.get(
            "chunks_without_page_references",
            0,
        ),
    )

    print_field(
        "Chunks containing tables",
        statistics.get(
            "chunks_containing_tables",
            0,
        ),
    )

    print_field(
        "Repeated noise lines removed",
        statistics.get(
            "repeated_noise_lines_removed",
            0,
        ),
    )


def display_section_types(
    result: Dict[str, Any],
) -> None:
    """
    Display classified section counts.
    """

    print_header(
        "DETECTED SECTION TYPES"
    )

    section_counts = get_nested(
        result,
        "statistics",
        "section_type_counts",
        default={},
    )

    if not isinstance(
        section_counts,
        dict,
    ):
        section_counts = {}

    if not section_counts:
        print_warning(
            "No classified section types were found."
        )

        return

    sorted_sections = sorted(
        section_counts.items(),
        key=lambda item: (
            -item[1],
            item[0],
        ),
    )

    for index, (
        section_type,
        count,
    ) in enumerate(
        sorted_sections[
            :MAX_SECTION_TYPES_TO_DISPLAY
        ],
        start=1,
    ):
        print(
            f"{index:>2}. "
            f"{section_type:<28} "
            f"{count}"
        )


def display_chunks(
    result: Dict[str, Any],
) -> None:
    """
    Display evidence chunk metadata and previews.
    """

    print_header(
        "GENERATED EVIDENCE CHUNKS"
    )

    chunks = result.get(
        "chunks",
        [],
    )

    if not isinstance(
        chunks,
        list,
    ):
        chunks = []

    print_field(
        "Total chunks",
        len(
            chunks
        ),
    )

    if not chunks:
        print()

        print_warning(
            "No evidence chunks were generated."
        )

        return

    chunks_to_display = chunks[
        :MAX_CHUNKS_TO_DISPLAY
    ]

    for chunk in chunks_to_display:
        print_subheader(
            (
                f"CHUNK "
                f"{chunk.get('chunk_index', '?')}"
                f" / "
                f"{chunk.get('total_chunks', '?')}"
            )
        )

        section = chunk.get(
            "section",
            {},
        )

        location = chunk.get(
            "location",
            {},
        )

        statistics = chunk.get(
            "statistics",
            {},
        )

        traceability = chunk.get(
            "traceability",
            {},
        )

        content = str(
            chunk.get(
                "content",
                ""
            )
        )

        print_field(
            "Chunk ID",
            chunk.get(
                "chunk_id"
            ),
        )

        print_field(
            "Section title",
            section.get(
                "title"
            ),
        )

        print_field(
            "Section type",
            section.get(
                "type"
            ),
        )

        print_field(
            "Section part",
            (
                f"{section.get('part_number', 1)}"
                f" / "
                f"{section.get('part_count', 1)}"
            ),
        )

        print_field(
            "Pages",
            format_page_numbers(
                location.get(
                    "page_numbers"
                )
            ),
        )

        print_field(
            "Characters",
            statistics.get(
                "character_count"
            ),
        )

        print_field(
            "Words",
            statistics.get(
                "word_count"
            ),
        )

        print_field(
            "Contains table",
            statistics.get(
                "contains_table"
            ),
        )

        print_field(
            "Table count",
            statistics.get(
                "table_count"
            ),
        )

        content_hash = str(
            traceability.get(
                "content_sha256",
                "",
            )
        )

        print_field(
            "Content SHA-256",
            (
                content_hash[:20]
                + "..."
                if len(
                    content_hash
                ) > 20
                else content_hash
            ),
        )

        print()

        print(
            "Content preview:"
        )

        print(
            create_preview(
                content,
                CHUNK_PREVIEW_CHARACTERS,
            )
        )

    if (
        len(
            chunks
        )
        > MAX_CHUNKS_TO_DISPLAY
    ):
        print()

        print_warning(
            (
                f"Only the first "
                f"{MAX_CHUNKS_TO_DISPLAY} "
                f"of {len(chunks)} chunks "
                f"were displayed."
            )
        )


# ====================================================================
# Validation
# ====================================================================


def validate_result(
    result: Dict[str, Any],
) -> List[str]:
    """
    Validate the generated in-memory evidence payload.

    Returns:
        List of validation warning messages.
    """

    print_header(
        "VALIDATING EVIDENCE RESULT"
    )

    warnings: List[str] = []

    if not isinstance(
        result,
        dict,
    ):
        raise TypeError(
            "Evidence result is not a dictionary."
        )

    print_success(
        "Evidence result is a dictionary."
    )

    required_top_level_keys = [
        "schema_version",
        "builder",
        "identity",
        "source",
        "configuration",
        "statistics",
        "quality",
        "generated_files",
        "chunks",
    ]

    missing_keys = [
        key
        for key in required_top_level_keys
        if key not in result
    ]

    if missing_keys:
        raise AssertionError(
            "Missing required top-level keys: "
            + ", ".join(
                missing_keys
            )
        )

    print_success(
        "All required top-level keys exist."
    )

    chunks = result.get(
        "chunks"
    )

    if not isinstance(
        chunks,
        list,
    ):
        raise TypeError(
            "The chunks field is not a list."
        )

    print_success(
        "The chunks field is a list."
    )

    if not chunks:
        raise AssertionError(
            "No evidence chunks were generated."
        )

    print_success(
        "At least one evidence chunk was generated."
    )

    empty_chunks = []

    duplicate_chunk_ids = []

    missing_hashes = []

    missing_section_titles = []

    missing_section_types = []

    oversized_chunks = []

    invalid_page_references = []

    invalid_character_counts = []

    invalid_word_counts = []

    chunk_ids = set()

    for chunk in chunks:
        chunk_id = chunk.get(
            "chunk_id"
        )

        content = str(
            chunk.get(
                "content",
                ""
            )
        )

        section = chunk.get(
            "section",
            {},
        )

        location = chunk.get(
            "location",
            {},
        )

        statistics = chunk.get(
            "statistics",
            {},
        )

        traceability = chunk.get(
            "traceability",
            {},
        )

        if not content.strip():
            empty_chunks.append(
                chunk_id
            )

        if chunk_id in chunk_ids:
            duplicate_chunk_ids.append(
                chunk_id
            )

        chunk_ids.add(
            chunk_id
        )

        if not traceability.get(
            "content_sha256"
        ):
            missing_hashes.append(
                chunk_id
            )

        if not section.get(
            "title"
        ):
            missing_section_titles.append(
                chunk_id
            )

        if not section.get(
            "type"
        ):
            missing_section_types.append(
                chunk_id
            )

        character_count = statistics.get(
            "character_count"
        )

        if (
            not isinstance(
                character_count,
                int,
            )
            or character_count
            != len(
                content
            )
        ):
            invalid_character_counts.append(
                chunk_id
            )

        word_count = statistics.get(
            "word_count"
        )

        if (
            not isinstance(
                word_count,
                int,
            )
            or word_count < 0
        ):
            invalid_word_counts.append(
                chunk_id
            )

        contains_table = bool(
            statistics.get(
                "contains_table"
            )
        )

        if (
            isinstance(
                character_count,
                int,
            )
            and character_count
            > MAX_CHUNK_CHARACTERS
        ):
            if contains_table:
                warnings.append(
                    (
                        f"{chunk_id} exceeds "
                        f"{MAX_CHUNK_CHARACTERS:,} "
                        "characters because a complete "
                        "table was preserved."
                    )
                )

            else:
                oversized_chunks.append(
                    chunk_id
                )

        page_numbers = location.get(
            "page_numbers"
        )

        if not isinstance(
            page_numbers,
            list,
        ):
            invalid_page_references.append(
                chunk_id
            )

        elif any(
            (
                not isinstance(
                    page,
                    int,
                )
                or page <= 0
            )
            for page in page_numbers
        ):
            invalid_page_references.append(
                chunk_id
            )

    if empty_chunks:
        raise AssertionError(
            "Empty evidence chunks found: "
            + ", ".join(
                str(
                    chunk_id
                )
                for chunk_id in empty_chunks
            )
        )

    print_success(
        "No empty evidence chunks were found."
    )

    if duplicate_chunk_ids:
        raise AssertionError(
            "Duplicate chunk IDs found: "
            + ", ".join(
                str(
                    chunk_id
                )
                for chunk_id
                in duplicate_chunk_ids
            )
        )

    print_success(
        "All chunk IDs are unique."
    )

    if missing_hashes:
        raise AssertionError(
            "Chunks with missing content hashes: "
            + ", ".join(
                str(
                    chunk_id
                )
                for chunk_id
                in missing_hashes
            )
        )

    print_success(
        "All evidence chunks have content hashes."
    )

    if missing_section_titles:
        raise AssertionError(
            "Chunks with missing section titles: "
            + ", ".join(
                str(
                    chunk_id
                )
                for chunk_id
                in missing_section_titles
            )
        )

    print_success(
        "All chunks have section titles."
    )

    if missing_section_types:
        raise AssertionError(
            "Chunks with missing section types: "
            + ", ".join(
                str(
                    chunk_id
                )
                for chunk_id
                in missing_section_types
            )
        )

    print_success(
        "All chunks have section classifications."
    )

    if invalid_character_counts:
        raise AssertionError(
            "Invalid chunk character counts: "
            + ", ".join(
                str(
                    chunk_id
                )
                for chunk_id
                in invalid_character_counts
            )
        )

    print_success(
        "All stored character counts are correct."
    )

    if invalid_word_counts:
        raise AssertionError(
            "Invalid chunk word counts: "
            + ", ".join(
                str(
                    chunk_id
                )
                for chunk_id
                in invalid_word_counts
            )
        )

    print_success(
        "All stored word counts are valid."
    )

    if oversized_chunks:
        raise AssertionError(
            "Oversized non-table chunks found: "
            + ", ".join(
                str(
                    chunk_id
                )
                for chunk_id
                in oversized_chunks
            )
        )

    print_success(
        "No oversized non-table chunks were found."
    )

    if invalid_page_references:
        raise AssertionError(
            "Invalid page-reference structures found: "
            + ", ".join(
                str(
                    chunk_id
                )
                for chunk_id
                in invalid_page_references
            )
        )

    print_success(
        "All page-reference structures are valid."
    )

    expected_chunk_count = get_nested(
        result,
        "statistics",
        "chunks_created",
        default=None,
    )

    if (
        expected_chunk_count
        != len(
            chunks
        )
    ):
        raise AssertionError(
            "The stored chunk count does not match "
            "the generated chunk list."
        )

    print_success(
        "Stored chunk count matches the chunk list."
    )

    quality = result.get(
        "quality",
        {},
    )

    if not quality.get(
        "all_chunks_have_content"
    ):
        raise AssertionError(
            "The quality report says that some "
            "chunks have no content."
        )

    print_success(
        "Quality report confirms that all chunks "
        "contain evidence."
    )

    if not quality.get(
        "all_chunks_have_hashes"
    ):
        raise AssertionError(
            "The quality report says that some "
            "chunks have no content hash."
        )

    print_success(
        "Quality report confirms traceability hashes."
    )

    return warnings


def validate_saved_output(
    in_memory_result: Dict[str, Any],
) -> None:
    """
    Validate the generated evidence JSON file.
    """

    print_header(
        "VALIDATING SAVED EVIDENCE JSON"
    )

    if not OUTPUT_FILE.exists():
        raise FileNotFoundError(
            "Expected evidence output was not created:\n"
            f"{OUTPUT_FILE}"
        )

    print_success(
        "pdf_evidence_chunks.json exists."
    )

    if not OUTPUT_FILE.is_file():
        raise RuntimeError(
            "Evidence output exists but is not a file:\n"
            f"{OUTPUT_FILE}"
        )

    saved_result = load_json(
        OUTPUT_FILE
    )

    print_success(
        "pdf_evidence_chunks.json contains valid JSON."
    )

    print_success(
        "Saved evidence JSON was loaded successfully."
    )

    saved_chunks = saved_result.get(
        "chunks",
        [],
    )

    in_memory_chunks = (
        in_memory_result.get(
            "chunks",
            [],
        )
    )

    if (
        len(
            saved_chunks
        )
        != len(
            in_memory_chunks
        )
    ):
        raise AssertionError(
            "Saved chunk count differs from the "
            "in-memory chunk count."
        )

    print_success(
        "Saved and in-memory chunk counts match."
    )

    saved_chunk_ids = [
        chunk.get(
            "chunk_id"
        )
        for chunk in saved_chunks
    ]

    in_memory_chunk_ids = [
        chunk.get(
            "chunk_id"
        )
        for chunk in in_memory_chunks
    ]

    if (
        saved_chunk_ids
        != in_memory_chunk_ids
    ):
        raise AssertionError(
            "Saved chunk IDs differ from the "
            "in-memory chunk IDs."
        )

    print_success(
        "Saved and in-memory chunk IDs match."
    )

    output_size = (
        OUTPUT_FILE.stat().st_size
    )

    print_field(
        "Evidence JSON size",
        f"{output_size:,} bytes",
    )


# ====================================================================
# Chunk analysis
# ====================================================================


def analyze_chunk_sizes(
    result: Dict[str, Any],
) -> None:
    """
    Analyze evidence chunk-size distribution.
    """

    print_header(
        "CHUNK SIZE ANALYSIS"
    )

    chunks = result.get(
        "chunks",
        [],
    )

    if not chunks:
        print_warning(
            "No chunks are available for size analysis."
        )

        return

    character_counts = [
        get_nested(
            chunk,
            "statistics",
            "character_count",
            default=0,
        )
        for chunk in chunks
    ]

    word_counts = [
        get_nested(
            chunk,
            "statistics",
            "word_count",
            default=0,
        )
        for chunk in chunks
    ]

    minimum_characters = min(
        character_counts
    )

    maximum_characters = max(
        character_counts
    )

    average_characters = (
        sum(
            character_counts
        )
        / len(
            character_counts
        )
    )

    minimum_words = min(
        word_counts
    )

    maximum_words = max(
        word_counts
    )

    average_words = (
        sum(
            word_counts
        )
        / len(
            word_counts
        )
    )

    print_field(
        "Smallest chunk",
        f"{minimum_characters:,} characters",
    )

    print_field(
        "Largest chunk",
        f"{maximum_characters:,} characters",
    )

    print_field(
        "Average chunk",
        f"{average_characters:,.2f} characters",
    )

    print_field(
        "Fewest words",
        f"{minimum_words:,}",
    )

    print_field(
        "Most words",
        f"{maximum_words:,}",
    )

    print_field(
        "Average words",
        f"{average_words:,.2f}",
    )

    very_small_chunks = [
        chunk
        for chunk in chunks
        if get_nested(
            chunk,
            "statistics",
            "character_count",
            default=0,
        )
        < MIN_CHUNK_CHARACTERS
    ]

    oversized_chunks = [
        chunk
        for chunk in chunks
        if get_nested(
            chunk,
            "statistics",
            "character_count",
            default=0,
        )
        > MAX_CHUNK_CHARACTERS
    ]

    print_field(
        "Chunks below minimum target",
        len(
            very_small_chunks
        ),
    )

    print_field(
        "Chunks above maximum target",
        len(
            oversized_chunks
        ),
    )

    if very_small_chunks:
        print()

        print_warning(
            "Some small chunks remain. This may be "
            "correct when they belong to a different "
            "semantic section."
        )

    if oversized_chunks:
        table_oversized = sum(
            1
            for chunk in oversized_chunks
            if get_nested(
                chunk,
                "statistics",
                "contains_table",
                default=False,
            )
        )

        print_field(
            "Oversized table chunks",
            table_oversized,
        )


def analyze_section_distribution(
    result: Dict[str, Any],
) -> None:
    """
    Analyze section-title and section-type distribution.
    """

    print_header(
        "SECTION DISTRIBUTION"
    )

    chunks = result.get(
        "chunks",
        [],
    )

    section_title_counter = Counter(
        get_nested(
            chunk,
            "section",
            "title",
            default="Unknown",
        )
        for chunk in chunks
    )

    section_type_counter = Counter(
        get_nested(
            chunk,
            "section",
            "type",
            default="general",
        )
        for chunk in chunks
    )

    print(
        "Chunks by section type:"
    )

    print()

    for (
        section_type,
        count,
    ) in section_type_counter.most_common():
        print(
            f"  {section_type:<30} {count}"
        )

    print()

    print(
        "Largest section groups:"
    )

    print()

    for (
        section_title,
        count,
    ) in section_title_counter.most_common(
        15
    ):
        print(
            f"  {section_title[:55]:<57} {count}"
        )


def analyze_page_coverage(
    result: Dict[str, Any],
) -> None:
    """
    Analyze page-reference coverage.
    """

    print_header(
        "PAGE REFERENCE COVERAGE"
    )

    chunks = result.get(
        "chunks",
        [],
    )

    chunks_with_pages = [
        chunk
        for chunk in chunks
        if get_nested(
            chunk,
            "location",
            "page_numbers",
            default=[],
        )
    ]

    chunks_without_pages = [
        chunk
        for chunk in chunks
        if not get_nested(
            chunk,
            "location",
            "page_numbers",
            default=[],
        )
    ]

    total_chunks = len(
        chunks
    )

    coverage_percentage = (
        (
            len(
                chunks_with_pages
            )
            / total_chunks
        )
        * 100
        if total_chunks
        else 0.0
    )

    all_pages = sorted(
        {
            page
            for chunk in chunks_with_pages
            for page in get_nested(
                chunk,
                "location",
                "page_numbers",
                default=[],
            )
        }
    )

    print_field(
        "Chunks with mapped pages",
        len(
            chunks_with_pages
        ),
    )

    print_field(
        "Chunks without mapped pages",
        len(
            chunks_without_pages
        ),
    )

    print_field(
        "Page mapping coverage",
        f"{coverage_percentage:.2f}%",
    )

    print_field(
        "Unique referenced pages",
        len(
            all_pages
        ),
    )

    if all_pages:
        print_field(
            "First referenced page",
            min(
                all_pages
            ),
        )

        print_field(
            "Last referenced page",
            max(
                all_pages
            ),
        )

    if chunks_without_pages:
        print()

        print_warning(
            "Some evidence chunks do not have page "
            "references. This can happen when Azure "
            "page spans cannot be aligned with cleaned "
            "Markdown. The evidence content is still "
            "preserved."
        )


def analyze_table_preservation(
    result: Dict[str, Any],
) -> None:
    """
    Analyze table-containing chunks.
    """

    print_header(
        "TABLE PRESERVATION"
    )

    chunks = result.get(
        "chunks",
        [],
    )

    table_chunks = [
        chunk
        for chunk in chunks
        if get_nested(
            chunk,
            "statistics",
            "contains_table",
            default=False,
        )
    ]

    total_tables = sum(
        get_nested(
            chunk,
            "statistics",
            "table_count",
            default=0,
        )
        for chunk in chunks
    )

    print_field(
        "Chunks containing tables",
        len(
            table_chunks
        ),
    )

    print_field(
        "Tables represented",
        total_tables,
    )

    print_field(
        "Table preservation enabled",
        PRESERVE_TABLES,
    )

    if table_chunks:
        print()

        print_success(
            "Structured table evidence was preserved."
        )

        print()

        print(
            "Table-containing chunks:"
        )

        for chunk in table_chunks[
            :15
        ]:
            print(
                "  "
                f"{chunk.get('chunk_id')}"
                " | "
                f"{get_nested(chunk, 'section', 'title', default='Unknown')}"
                " | "
                f"{get_nested(chunk, 'statistics', 'table_count', default=0)} "
                "table(s)"
            )

    else:
        print_warning(
            "No table-containing evidence chunks "
            "were detected. Check document.md if the "
            "source PDF is expected to contain tables."
        )


# ====================================================================
# Final report
# ====================================================================


def display_quality_report(
    result: Dict[str, Any],
    validation_warnings: List[str],
) -> None:
    """
    Display final quality information.
    """

    print_header(
        "QUALITY REPORT"
    )

    quality = result.get(
        "quality",
        {},
    )

    print_field(
        "All chunks have content",
        quality.get(
            "all_chunks_have_content"
        ),
    )

    print_field(
        "All chunks have hashes",
        quality.get(
            "all_chunks_have_hashes"
        ),
    )

    print_field(
        "Page mapping available",
        quality.get(
            "page_mapping_available"
        ),
    )

    print_field(
        "Tables preserved",
        quality.get(
            "tables_preserved"
        ),
    )

    print_field(
        "Validation warnings",
        len(
            validation_warnings
        ),
    )

    if validation_warnings:
        print()

        for warning in validation_warnings:
            print_warning(
                warning
            )

    else:
        print()

        print_success(
            "No validation warnings were generated."
        )


def display_generated_files() -> None:
    """
    Display generated evidence paths.
    """

    print_header(
        "GENERATED FILES"
    )

    print_field(
        "Azure document data",
        DOCUMENT_DATA_PATH,
    )

    print_field(
        "Evidence directory",
        OUTPUT_DIRECTORY,
    )

    print_field(
        "Evidence chunks JSON",
        OUTPUT_FILE,
    )


# ====================================================================
# Main
# ====================================================================


def main() -> None:
    """
    Run the complete PDF evidence-builder test.
    """

    print_header(
        "PDF EVIDENCE BUILDER TEST"
    )

    print_field(
        "Program ID",
        PROGRAM_ID,
    )

    print_field(
        "Page ID",
        PAGE_ID,
    )

    print_field(
        "Document ID",
        DOCUMENT_ID,
    )

    print_field(
        "Document data",
        DOCUMENT_DATA_PATH,
    )

    print_field(
        "Source PDF",
        SOURCE_PDF_PATH,
    )

    print_field(
        "Output directory",
        OUTPUT_DIRECTORY,
    )

    try:
        validate_input_files()

        builder = create_builder()

        result = build_evidence(
            builder
        )

        display_document_identity(
            result
        )

        display_extraction_statistics(
            result
        )

        display_section_types(
            result
        )

        display_chunks(
            result
        )

        validation_warnings = (
            validate_result(
                result
            )
        )

        validate_saved_output(
            result
        )

        analyze_chunk_sizes(
            result
        )

        analyze_section_distribution(
            result
        )

        analyze_page_coverage(
            result
        )

        analyze_table_preservation(
            result
        )

        display_quality_report(
            result,
            validation_warnings,
        )

        display_generated_files()

        print_header(
            "✓ PDF EVIDENCE BUILDER TEST COMPLETED"
        )

        print_success(
            "Azure document extraction was loaded."
        )

        print_success(
            "Document sections were detected."
        )

        print_success(
            "Evidence chunks were generated."
        )

        print_success(
            "Tables were preserved where detected."
        )

        print_success(
            "Source metadata and traceability "
            "hashes were attached."
        )

        print_success(
            "pdf_evidence_chunks.json is valid."
        )

        print()

        print(
            "The PDF evidence layer is ready for "
            "the PDF fact extractor."
        )

        print()

    except Exception as error:
        print_header(
            "TEST FAILED"
        )

        print_error(
            str(
                error
            )
        )

        print()

        print(
            "Traceback:"
        )

        traceback.print_exc()

        sys.exit(
            1
        )


if __name__ == "__main__":
    main()