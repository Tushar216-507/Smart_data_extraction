"""
PDF Fact Extractor Test
=======================

Tests:

    pdf_evidence_chunks.json
                ↓
        PDFFactExtractor
                ↓
       LLM extraction per chunk
                ↓
       pdf_program_facts.json

Current test document:

    Program ID:
        0001

    Source page ID:
        0002

    Document ID:
        source

Input:

    data/0001/pdf/0002/source/evidence/
        pdf_evidence_chunks.json

Output:

    data/0001/pdf/0002/source/facts/
        pdf_program_facts.json
"""

from __future__ import annotations

import json
import os
import sys
import traceback
from collections import Counter
from pathlib import Path
from typing import Any

from dotenv import load_dotenv

from knowledge.pdf.pdf_fact_extractor import (
    PDFFactExtractor,
)

from knowledge.billing.usage_tracker import UsageTracker
from knowledge.llm.client import LLMClient
from knowledge.llm.nvidia_provider import NvidiaProvider


# =============================================================================
# CONFIGURATION
# =============================================================================

PROGRAM_ID = "0001"
PAGE_ID = "0002"
DOCUMENT_ID = "source"

UNIVERSITY_NAME = (
    "Ludwig-Maximilians-Universität München"
)

PROGRAM_NAME = "Egyptology and Coptology"

DOCUMENT_DIRECTORY = (
    Path("data")
    / PROGRAM_ID
    / "pdf"
    / PAGE_ID
    / DOCUMENT_ID
)

EVIDENCE_FILE = (
    DOCUMENT_DIRECTORY
    / "evidence"
    / "pdf_evidence_chunks.json"
)

FACTS_DIRECTORY = (
    DOCUMENT_DIRECTORY
    / "facts"
)

OUTPUT_FILE = (
    FACTS_DIRECTORY
    / "pdf_program_facts.json"
)


# =============================================================================
# TERMINAL HELPERS
# =============================================================================

LINE_WIDTH = 80


def print_header(
    title: str,
) -> None:
    """
    Print a major terminal section.
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
    Print a smaller terminal section.
    """

    print()
    print(title)
    print("-" * LINE_WIDTH)


def print_value(
    label: str,
    value: Any,
    width: int = 32,
) -> None:
    """
    Print a consistently aligned label and value.
    """

    print(
        f"{label:<{width}}: {value}"
    )


def print_success(
    message: str,
) -> None:
    """
    Print a successful validation message.
    """

    print(f"✓ {message}")


def print_warning(
    message: str,
) -> None:
    """
    Print a non-fatal warning.
    """

    print(f"⚠ {message}")


def print_failure(
    message: str,
) -> None:
    """
    Print a failed validation message.
    """

    print(f"✗ {message}")


def format_list(
    values: Any,
) -> str:
    """
    Format a list for terminal output.
    """

    if not values:
        return "None"

    if not isinstance(
        values,
        (list, tuple, set),
    ):
        return str(values)

    return ", ".join(
        str(value)
        for value in values
    )


def truncate(
    value: Any,
    maximum_length: int = 150,
) -> str:
    """
    Shorten long values for terminal previews.
    """

    if value is None:
        return "None"

    if isinstance(
        value,
        (dict, list),
    ):
        text = json.dumps(
            value,
            ensure_ascii=False,
        )

    else:
        text = str(value)

    text = " ".join(
        text.split()
    )

    if len(text) <= maximum_length:
        return text

    return (
        text[:maximum_length - 3]
        + "..."
    )


# =============================================================================
# JSON HELPERS
# =============================================================================

def load_json(
    file_path: Path,
) -> dict[str, Any]:
    """
    Load and validate a JSON object.
    """

    with file_path.open(
        "r",
        encoding="utf-8",
    ) as file:
        data = json.load(file)

    if not isinstance(data, dict):
        raise ValueError(
            "Expected a JSON object in "
            f"{file_path}"
        )

    return data


def count_values(
    values: list[str],
) -> dict[str, int]:
    """
    Count values and sort by descending count.
    """

    counts = Counter(values)

    return dict(
        sorted(
            counts.items(),
            key=lambda item: (
                -item[1],
                item[0],
            ),
        )
    )


# =============================================================================
# CONFIGURATION
# =============================================================================

def resolve_provider_configuration(
) -> dict[str, Any]:
    """
    Resolve the configured LLM provider.

    Provider priority:

        1. NVIDIA
        2. OpenAI-compatible custom endpoint
        3. OpenAI

    The extractor itself performs the final client initialization.
    """

    nvidia_api_key = (
        os.getenv("NVIDIA_API_KEY")
        or ""
    ).strip()

    nvidia_base_url = (
        os.getenv("NVIDIA_BASE_URL")
        or "https://integrate.api.nvidia.com/v1"
    ).strip()

    openai_api_key = (
        os.getenv("OPENAI_API_KEY")
        or ""
    ).strip()

    openai_base_url = (
        os.getenv("OPENAI_BASE_URL")
        or ""
    ).strip()

    configured_model = (
        os.getenv("PDF_EXTRACTION_MODEL")
        or os.getenv("OPENAI_MODEL")
        or ""
    ).strip()

    if nvidia_api_key:
        return {
            "provider": "NVIDIA",
            "api_key": nvidia_api_key,
            "base_url": nvidia_base_url,
            "model": (
                configured_model
                or "meta/llama-3.1-70b-instruct"
            ),
        }

    if (
        openai_api_key
        and openai_base_url
    ):
        return {
            "provider": (
                "OpenAI-compatible endpoint"
            ),
            "api_key": openai_api_key,
            "base_url": openai_base_url,
            "model": (
                configured_model
                or "openai/gpt-oss-120b"
            ),
        }

    if openai_api_key:
        return {
            "provider": "OpenAI",
            "api_key": openai_api_key,
            "base_url": None,
            "model": (
                configured_model
                or "openai/gpt-oss-120b"
            ),
        }

    raise RuntimeError(
        "No LLM API key was found.\n\n"
        "Configure NVIDIA:\n"
        "NVIDIA_API_KEY=your_key\n"
        "NVIDIA_BASE_URL="
        "https://integrate.api.nvidia.com/v1\n"
        "PDF_EXTRACTION_MODEL="
        "your_model_name\n\n"
        "Or configure OpenAI:\n"
        "OPENAI_API_KEY=your_key\n"
        "OPENAI_MODEL=openai/gpt-oss-120b"
    )


# =============================================================================
# INPUT VALIDATION
# =============================================================================

def validate_evidence_file(
    evidence_file: Path,
) -> dict[str, Any]:
    """
    Validate the evidence-builder output before using the LLM.
    """

    if not evidence_file.exists():
        raise FileNotFoundError(
            "PDF evidence file was not found:\n"
            f"{evidence_file}\n\n"
            "Run test_pdf_evidence_builder.py first."
        )

    if not evidence_file.is_file():
        raise ValueError(
            "The PDF evidence path is not a file:\n"
            f"{evidence_file}"
        )

    evidence_data = load_json(
        evidence_file
    )

    chunks = evidence_data.get(
        "chunks"
    )

    if not isinstance(chunks, list):
        raise ValueError(
            "The evidence JSON does not contain "
            "a valid 'chunks' list."
        )

    if not chunks:
        raise ValueError(
            "The evidence JSON contains no chunks."
        )

    empty_chunks: list[int] = []

    missing_chunk_ids: list[int] = []

    for index, chunk in enumerate(
        chunks,
        start=1,
    ):
        if not isinstance(chunk, dict):
            raise ValueError(
                f"Evidence chunk {index} "
                "is not a JSON object."
            )

        content = (
            chunk.get("content")
            or chunk.get("text")
            or ""
        )

        if not str(content).strip():
            empty_chunks.append(index)

        chunk_id = (
            chunk.get("chunk_id")
            or chunk.get("id")
        )

        if not chunk_id:
            missing_chunk_ids.append(
                index
            )

    if empty_chunks:
        raise ValueError(
            "Empty evidence chunks were found: "
            f"{empty_chunks}"
        )

    if missing_chunk_ids:
        print_warning(
            "Some chunks have no explicit chunk ID. "
            "The extractor will generate fallback IDs: "
            f"{missing_chunk_ids}"
        )

    return evidence_data


# =============================================================================
# FACT VALIDATION
# =============================================================================

def validate_fact(
    fact: Any,
    fact_number: int,
) -> list[str]:
    """
    Validate one generated PDF fact.

    Returns validation issues without stopping immediately,
    allowing the complete output to be inspected.
    """

    issues: list[str] = []

    if not isinstance(fact, dict):
        return [
            f"Fact {fact_number} is not "
            "a JSON object."
        ]

    required_keys = [
        "fact_id",
        "category",
        "field",
        "value",
        "original_value",
        "entity",
        "confidence",
        "source",
        "evidence",
    ]

    for key in required_keys:
        if key not in fact:
            issues.append(
                f"Fact {fact_number} is "
                f"missing '{key}'."
            )

    if not fact.get("fact_id"):
        issues.append(
            f"Fact {fact_number} has no fact ID."
        )

    if not fact.get("category"):
        issues.append(
            f"Fact {fact_number} has "
            "no category."
        )

    if not fact.get("field"):
        issues.append(
            f"Fact {fact_number} has "
            "no field."
        )

    value = fact.get("value")

    if value is None:
        issues.append(
            f"Fact {fact_number} has "
            "a null value."
        )

    elif (
        isinstance(value, str)
        and not value.strip()
    ):
        issues.append(
            f"Fact {fact_number} has "
            "an empty value."
        )

    elif (
        isinstance(
            value,
            (list, dict),
        )
        and not value
    ):
        issues.append(
            f"Fact {fact_number} has "
            "an empty structured value."
        )

    entity = fact.get("entity")

    if not isinstance(entity, dict):
        issues.append(
            f"Fact {fact_number} has "
            "an invalid entity."
        )

    else:
        if not entity.get("type"):
            issues.append(
                f"Fact {fact_number} entity "
                "has no type."
            )

    confidence = fact.get(
        "confidence"
    )

    if not isinstance(
        confidence,
        (int, float),
    ):
        issues.append(
            f"Fact {fact_number} has "
            "an invalid confidence value."
        )

    elif not 0 <= confidence <= 1:
        issues.append(
            f"Fact {fact_number} confidence "
            "is outside 0.0-1.0."
        )

    source = fact.get("source")

    if not isinstance(source, dict):
        issues.append(
            f"Fact {fact_number} has "
            "an invalid source."
        )

    else:
        if (
            source.get("source_type")
            != "pdf"
        ):
            issues.append(
                f"Fact {fact_number} source "
                "type is not 'pdf'."
            )

        if not source.get("chunk_id"):
            issues.append(
                f"Fact {fact_number} source "
                "has no chunk ID."
            )

        if not source.get(
            "content_sha256"
        ):
            issues.append(
                f"Fact {fact_number} source "
                "has no content hash."
            )

    evidence = fact.get("evidence")

    if not isinstance(evidence, dict):
        issues.append(
            f"Fact {fact_number} has "
            "invalid evidence."
        )

    else:
        if not evidence.get("text"):
            issues.append(
                f"Fact {fact_number} has "
                "no evidence text."
            )

        if not evidence.get("chunk_id"):
            issues.append(
                f"Fact {fact_number} evidence "
                "has no chunk ID."
            )

    return issues


def find_duplicate_fact_ids(
    facts: list[dict[str, Any]],
) -> list[str]:
    """
    Find repeated fact IDs.
    """

    fact_ids = [
        fact.get("fact_id")
        for fact in facts
        if isinstance(fact, dict)
        and fact.get("fact_id")
    ]

    counts = Counter(fact_ids)

    return [
        fact_id
        for fact_id, count
        in counts.items()
        if count > 1
    ]


# =============================================================================
# OUTPUT DISPLAY
# =============================================================================

def display_fact_preview(
    facts: list[dict[str, Any]],
    maximum_facts: int = 20,
) -> None:
    """
    Display a readable sample of generated facts.
    """

    if not facts:
        print(
            "No facts were extracted."
        )
        return

    preview_count = min(
        len(facts),
        maximum_facts,
    )

    print_value(
        "Facts displayed",
        f"{preview_count} of {len(facts)}",
    )

    for index, fact in enumerate(
        facts[:preview_count],
        start=1,
    ):
        print()
        print(
            f"FACT {index}"
        )
        print("-" * LINE_WIDTH)

        entity = (
            fact.get("entity")
            or {}
        )

        parent_entity = (
            fact.get("parent_entity")
            or {}
        )

        source = (
            fact.get("source")
            or {}
        )

        print_value(
            "Fact ID",
            fact.get("fact_id"),
        )

        print_value(
            "Category",
            fact.get("category"),
        )

        print_value(
            "Field",
            fact.get("field"),
        )

        print_value(
            "Value",
            truncate(
                fact.get("value")
            ),
        )

        print_value(
            "Original value",
            truncate(
                fact.get(
                    "original_value"
                )
            ),
        )

        print_value(
            "Unit",
            (
                fact.get("unit")
                or "None"
            ),
        )

        print_value(
            "Entity type",
            entity.get("type"),
        )

        print_value(
            "Entity ID",
            (
                entity.get("id")
                or "None"
            ),
        )

        print_value(
            "Entity name",
            truncate(
                entity.get("name")
            ),
        )

        print_value(
            "Parent type",
            (
                parent_entity.get("type")
                or "None"
            ),
        )

        print_value(
            "Parent ID",
            (
                parent_entity.get("id")
                or "None"
            ),
        )

        print_value(
            "Parent name",
            truncate(
                parent_entity.get("name")
            ),
        )

        print_value(
            "Confidence",
            fact.get("confidence"),
        )

        print_value(
            "Chunk ID",
            source.get("chunk_id"),
        )

        print_value(
            "Section",
            (
                source.get(
                    "section_title"
                )
                or "None"
            ),
        )

        print_value(
            "Pages",
            format_list(
                source.get("pages")
            ),
        )


def display_distribution(
    title: str,
    distribution: dict[str, Any],
) -> None:
    """
    Display a fact distribution.
    """

    print_subheader(title)

    if not distribution:
        print("No data.")
        return

    for key, count in distribution.items():
        print(
            f"{key:<48}"
            f"{count:>8}"
        )


# =============================================================================
# MAIN TEST
# =============================================================================

def main() -> None:
    """
    Execute the complete PDF fact extractor test.
    """

    load_dotenv()

    print_header(
        "PDF FACT EXTRACTOR TEST"
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
        "University",
        UNIVERSITY_NAME,
    )

    print_value(
        "Program",
        PROGRAM_NAME,
    )

    print_value(
        "Evidence file",
        EVIDENCE_FILE,
    )

    print_value(
        "Output directory",
        FACTS_DIRECTORY,
    )

    # =========================================================================
    # VALIDATE EVIDENCE
    # =========================================================================

    print_header(
        "VALIDATING PDF EVIDENCE"
    )

    evidence_data = (
        validate_evidence_file(
            EVIDENCE_FILE
        )
    )

    chunks = evidence_data.get(
        "chunks",
        [],
    )

    print_success(
        "PDF evidence file exists."
    )

    print_success(
        "PDF evidence JSON is valid."
    )

    print_success(
        "PDF evidence contains "
        f"{len(chunks)} chunks."
    )

    total_characters = sum(
        len(
            str(
                chunk.get("content")
                or chunk.get("text")
                or ""
            )
        )
        for chunk in chunks
    )

    print_value(
        "Evidence chunks",
        len(chunks),
    )

    print_value(
        "Evidence characters",
        f"{total_characters:,}",
    )

    # =========================================================================
    # CONFIGURATION
    # =========================================================================

    print_header(
        "VALIDATING LLM CONFIGURATION"
    )

    provider_config = (
        resolve_provider_configuration()
    )

    print_success(
        "LLM API key is configured."
    )

    print_value(
        "Provider",
        provider_config["provider"],
    )

    print_value(
        "Model",
        provider_config["model"],
    )

    print_value(
        "Base URL",
        provider_config["base_url"] or "Default provider endpoint",
    )

    print_success(
        "API key is available "
        "(secret value hidden)."
    )

    # =========================================================================
    # INITIALIZE
    # =========================================================================

    print_header(
        "INITIALIZING PDF FACT EXTRACTOR"
    )

    tracker = UsageTracker()

    provider = NvidiaProvider(
        api_key=provider_config["api_key"],
        model=provider_config["model"],
        max_tokens=12000,
    )

    client = LLMClient(
        provider=provider,
        usage_tracker=tracker,
        stage="PDF Extraction",
        program_id=PROGRAM_ID,
    )

    extractor = PDFFactExtractor(
        client=client,
        temperature=0.0,
        request_timeout=180.0,
        max_retries=3,
        retry_delay=2.0,
        overwrite=True,
        continue_on_error=True,
        remove_exact_duplicates=True,
        save_raw_responses=True,
    )

    print_success(
        "PDFFactExtractor initialized."
    )

    print_value(
        "Model",
        extractor.model,
    )

    print_value(
        "Temperature",
        extractor.temperature,
    )

    print_value(
        "Maximum output tokens",
        extractor.max_tokens,
    )

    print_value(
        "Maximum retries",
        extractor.max_retries,
    )

    print_value(
        "Continue on chunk error",
        extractor.continue_on_error,
    )

    print_value(
        "Remove exact duplicates",
        extractor.remove_exact_duplicates,
    )

    print_value(
        "Save raw responses",
        extractor.save_raw_responses,
    )

    # =========================================================================
    # EXTRACT
    # =========================================================================

    print_header(
        "EXTRACTING PDF PROGRAM FACTS"
    )

    print(
        "Processing every PDF evidence "
        "chunk independently..."
    )

    print(
        "This may take several minutes "
        "depending on the configured model."
    )

    result = extractor.extract(
        evidence_path=EVIDENCE_FILE,
        output_dir=FACTS_DIRECTORY,
        program_id=PROGRAM_ID,
        page_id=PAGE_ID,
        document_id=DOCUMENT_ID,
        university_name=(
            UNIVERSITY_NAME
        ),
        program_name=PROGRAM_NAME,
        overwrite=True,
    )

    print()

    print_success(
        "PDF evidence chunk processing "
        "completed."
    )

    print_success(
        "PDF program facts were built."
    )

    # =========================================================================
    # RESULT STRUCTURE
    # =========================================================================

    print_header(
        "EXTRACTION SUMMARY"
    )

    summary = (
        result.get("summary")
        or {}
    )

    print_value(
        "Evidence chunks available",
        summary.get(
            "evidence_chunks_available",
            0,
        ),
    )

    print_value(
        "Evidence chunks processed",
        summary.get(
            "evidence_chunks_processed",
            0,
        ),
    )

    print_value(
        "Successful chunks",
        summary.get(
            "successful_chunks",
            0,
        ),
    )

    print_value(
        "Failed chunks",
        summary.get(
            "failed_chunks",
            0,
        ),
    )

    print_value(
        "Chunks with facts",
        summary.get(
            "chunks_with_facts",
            0,
        ),
    )

    print_value(
        "Facts before deduplication",
        summary.get(
            "facts_before_deduplication",
            0,
        ),
    )

    print_value(
        "Exact duplicates removed",
        summary.get(
            "exact_duplicates_removed",
            0,
        ),
    )

    print_value(
        "Facts written",
        summary.get(
            "facts_written",
            0,
        ),
    )

    print_value(
        "Unique pages referenced",
        summary.get(
            "unique_pages_referenced",
            0,
        ),
    )

    print_value(
        "Page numbers",
        format_list(
            summary.get(
                "page_numbers"
            )
        ),
    )

    # =========================================================================
    # CHUNK RESULTS
    # =========================================================================

    print_header(
        "CHUNK EXTRACTION RESULTS"
    )

    chunk_results = (
        result.get("chunk_results")
        or []
    )

    if not chunk_results:
        print_warning(
            "No chunk processing results "
            "were returned."
        )

    for index, chunk_result in enumerate(
        chunk_results,
        start=1,
    ):
        status = (
            chunk_result.get("status")
            or "unknown"
        )

        marker = (
            "✓"
            if status == "success"
            else "✗"
        )

        chunk_id = (
            chunk_result.get("chunk_id")
            or f"chunk_{index:04d}"
        )

        fact_count = (
            chunk_result.get(
                "facts_extracted",
                0,
            )
        )

        attempts = (
            chunk_result.get(
                "attempts",
                0,
            )
        )

        print(
            f"{marker} "
            f"{chunk_id:<34} "
            f"Facts: {fact_count:<6} "
            f"Attempts: {attempts}"
        )

        error = (
            chunk_result.get("error")
        )

        if error:
            print(
                "  Error: "
                f"{truncate(error, 180)}"
            )

    # =========================================================================
    # FACT DISTRIBUTION
    # =========================================================================

    distribution = (
        result.get("distribution")
        or {}
    )

    display_distribution(
        title="FACTS BY CATEGORY",
        distribution=(
            distribution.get(
                "by_category"
            )
            or {}
        ),
    )

    display_distribution(
        title="FACTS BY ENTITY TYPE",
        distribution=(
            distribution.get(
                "by_entity_type"
            )
            or {}
        ),
    )

    display_distribution(
        title="FACTS BY FIELD",
        distribution=(
            distribution.get(
                "by_field"
            )
            or {}
        ),
    )

    # =========================================================================
    # FACT PREVIEW
    # =========================================================================

    print_header(
        "EXTRACTED FACT PREVIEW"
    )

    facts = (
        result.get("facts")
        or []
    )

    display_fact_preview(
        facts=facts,
        maximum_facts=20,
    )

    # =========================================================================
    # VALIDATE FACTS
    # =========================================================================

    print_header(
        "VALIDATING EXTRACTED FACTS"
    )

    validation_issues: list[str] = []

    if not isinstance(facts, list):
        validation_issues.append(
            "The result 'facts' field "
            "is not a list."
        )

        facts = []

    for fact_number, fact in enumerate(
        facts,
        start=1,
    ):
        validation_issues.extend(
            validate_fact(
                fact=fact,
                fact_number=fact_number,
            )
        )

    duplicate_fact_ids = (
        find_duplicate_fact_ids(
            facts
        )
    )

    if duplicate_fact_ids:
        validation_issues.append(
            "Duplicate fact IDs found: "
            f"{duplicate_fact_ids}"
        )

    if facts:
        print_success(
            f"{len(facts)} facts were "
            "extracted."
        )

    else:
        print_warning(
            "No facts were extracted."
        )

    if duplicate_fact_ids:
        print_failure(
            "Duplicate fact IDs were found."
        )

    else:
        print_success(
            "All fact IDs are unique."
        )

    facts_with_chunk_ids = sum(
        1
        for fact in facts
        if (
            fact.get("source")
            or {}
        ).get("chunk_id")
    )

    facts_with_hashes = sum(
        1
        for fact in facts
        if (
            fact.get("source")
            or {}
        ).get("content_sha256")
    )

    facts_with_pages = sum(
        1
        for fact in facts
        if (
            fact.get("source")
            or {}
        ).get("pages")
    )

    facts_with_entities = sum(
        1
        for fact in facts
        if isinstance(
            fact.get("entity"),
            dict,
        )
    )

    facts_with_parent_entities = sum(
        1
        for fact in facts
        if isinstance(
            fact.get(
                "parent_entity"
            ),
            dict,
        )
    )

    print_value(
        "Facts with chunk IDs",
        (
            f"{facts_with_chunk_ids}"
            f"/{len(facts)}"
        ),
    )

    print_value(
        "Facts with content hashes",
        (
            f"{facts_with_hashes}"
            f"/{len(facts)}"
        ),
    )

    print_value(
        "Facts with page references",
        (
            f"{facts_with_pages}"
            f"/{len(facts)}"
        ),
    )

    print_value(
        "Facts with entities",
        (
            f"{facts_with_entities}"
            f"/{len(facts)}"
        ),
    )

    print_value(
        "Facts with parent entities",
        (
            f"{facts_with_parent_entities}"
            f"/{len(facts)}"
        ),
    )

    if validation_issues:
        print()

        print_warning(
            f"{len(validation_issues)} "
            "validation issue(s) found."
        )

        for issue in validation_issues[
            :50
        ]:
            print(
                f"  - {issue}"
            )

        if len(validation_issues) > 50:
            print(
                "  - Additional issues hidden: "
                f"{len(validation_issues) - 50}"
            )

    else:
        print_success(
            "All extracted facts passed "
            "structural validation."
        )

    # =========================================================================
    # QUALITY
    # =========================================================================

    print_header(
        "QUALITY SUMMARY"
    )

    quality = (
        result.get("quality")
        or {}
    )

    for key, value in quality.items():
        label = (
            key.replace("_", " ")
            .capitalize()
        )

        marker = (
            "✓"
            if value
            else "⚠"
        )

        print(
            f"{marker} "
            f"{label:<48}"
            f"{value}"
        )

    # =========================================================================
    # SAVED OUTPUT
    # =========================================================================

    print_header(
        "VALIDATING SAVED JSON"
    )

    if not OUTPUT_FILE.exists():
        raise FileNotFoundError(
            "Expected output JSON was not "
            f"created:\n{OUTPUT_FILE}"
        )

    print_success(
        "pdf_program_facts.json exists."
    )

    saved_result = load_json(
        OUTPUT_FILE
    )

    print_success(
        "pdf_program_facts.json contains "
        "valid JSON."
    )

    if saved_result == result:
        print_success(
            "Saved JSON exactly matches "
            "the returned extraction result."
        )

    else:
        raise AssertionError(
            "Saved JSON does not match "
            "the returned extraction result."
        )

    saved_facts = (
        saved_result.get("facts")
        or []
    )

    if len(saved_facts) == len(facts):
        print_success(
            "Saved fact count matches "
            "the extraction result."
        )

    else:
        raise AssertionError(
            "Saved fact count does not "
            "match the extraction result."
        )

    # =========================================================================
    # GENERATED FILES
    # =========================================================================

    print_header(
        "GENERATED FILES"
    )

    print_value(
        "Evidence input",
        EVIDENCE_FILE,
    )

    print_value(
        "Extracted PDF facts",
        OUTPUT_FILE,
    )

    raw_response_directory = (
        FACTS_DIRECTORY
        / "raw_responses"
    )

    print_value(
        "Raw LLM responses",
        raw_response_directory,
    )

    raw_response_count = 0

    if raw_response_directory.exists():
        raw_response_count = len(
            list(
                raw_response_directory.glob(
                    "*.json"
                )
            )
        )

    print_value(
        "Raw response files",
        raw_response_count,
    )

    # =========================================================================
    # FINAL RESULT
    # =========================================================================

    print_header(
        "PDF FACT EXTRACTION TEST RESULT"
    )

    failed_chunk_count = (
        summary.get(
            "failed_chunks",
            0,
        )
    )

    if validation_issues:
        print_warning(
            "PDF fact extraction completed "
            "with validation warnings."
        )

    else:
        print_success(
            "PDF fact extraction completed "
            "successfully."
        )

    if failed_chunk_count:
        print_warning(
            f"{failed_chunk_count} evidence "
            "chunk(s) failed extraction."
        )

    else:
        print_success(
            "Every evidence chunk was "
            "processed successfully."
        )

    print_success(
        "Generated PDF fact JSON is valid."
    )

    print_success(
        "PDF source provenance was "
        "preserved."
    )

    print_success(
        "Fact-level chunk traceability "
        "was preserved."
    )

    print_success(
        "The PDF enrichment layer can now "
        "consume pdf_program_facts.json."
    )

    print()
    print("=" * LINE_WIDTH)


# =============================================================================
# ENTRY POINT
# =============================================================================

if __name__ == "__main__":
    try:
        main()

    except KeyboardInterrupt:
        print_header(
            "TEST CANCELLED"
        )

        print_warning(
            "PDF fact extraction was "
            "cancelled by the user."
        )

        sys.exit(130)

    except Exception as error:
        print_header(
            "TEST FAILED"
        )

        print_failure(
            str(error)
        )

        print()
        print("Traceback:")
        print(
            traceback.format_exc()
        )

        sys.exit(1)