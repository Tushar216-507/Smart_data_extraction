"""
Azure Document Extractor Test
=============================

Tests:

PDF
    ↓
Azure Document Intelligence
    ↓
Raw Azure response
    ↓
Markdown
    ↓
Plain text
    ↓
Structured document data
    ↓
Tables

Usage
-----

Option 1:
Place a PDF inside:

    data/test/

Then run:

    python test_azure_document_extractor.py


Option 2:
Pass a PDF path:

    python test_azure_document_extractor.py "path/to/document.pdf"


Example:

    python test_azure_document_extractor.py "data/test/program_handbook.pdf"
"""

from __future__ import annotations

import json
import sys
import traceback

from pathlib import Path
from typing import Any, Dict, List, Optional

from config import Config

from knowledge.pdf.azure_document_extractor import (
    AzureDocumentExtractionError,
    AzureDocumentExtractor,
)


# ====================================================================
# Test configuration
# ====================================================================

PROGRAM_ID = "0001"
PAGE_ID = "0002"

DEFAULT_PDF_DIRECTORY = (
    Path("data")
    / PROGRAM_ID
    / "pages"
    / PAGE_ID
    / "assets"
)

OUTPUT_ROOT = (
    Path("data")
    / PROGRAM_ID
    / "pdf"
)

SHOW_MARKDOWN_PREVIEW = True
SHOW_TEXT_PREVIEW = True

MARKDOWN_PREVIEW_CHARACTERS = 2000
TEXT_PREVIEW_CHARACTERS = 1500


# ====================================================================
# Console helpers
# ====================================================================

def print_header(
    title: str,
) -> None:
    """
    Print a large section header.
    """

    print()
    print("=" * 80)
    print(title)
    print("=" * 80)
    print()


def print_subheader(
    title: str,
) -> None:
    """
    Print a smaller section header.
    """

    print()
    print(title)
    print("-" * 80)


def print_field(
    label: str,
    value: Any,
    width: int = 32,
) -> None:
    """
    Print an aligned label and value.
    """

    if value is None:
        display_value = "Not found"

    elif value == "":
        display_value = "Not found"

    else:
        display_value = str(
            value
        )

    print(
        f"{label:<{width}}: "
        f"{display_value}"
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


def print_failure(
    message: str,
) -> None:
    """
    Print a failed validation message.
    """

    print(
        f"✗ {message}"
    )


# ====================================================================
# PDF discovery
# ====================================================================

def resolve_pdf_path() -> Path:
    """
    Resolve the PDF used by the test.

    Priority:

    1. Command-line PDF path
    2. First PDF found under data/test/
    """

    if len(
        sys.argv
    ) > 1:
        pdf_path = Path(
            sys.argv[1]
        )

        return pdf_path

    if not DEFAULT_PDF_DIRECTORY.exists():
        raise FileNotFoundError(
            "\nNo PDF path was provided and the default test "
            "directory does not exist.\n\n"
            "Create this directory:\n\n"
            f"    {DEFAULT_PDF_DIRECTORY}\n\n"
            "Place a PDF inside it, then run:\n\n"
            "    python test_azure_document_extractor.py\n\n"
            "Or provide the PDF path directly:\n\n"
            "    python test_azure_document_extractor.py "
            "\"path/to/document.pdf\"\n"
        )

    pdf_files = sorted(
        DEFAULT_PDF_DIRECTORY.rglob(
            "*.pdf"
        )
    )

    if not pdf_files:
        raise FileNotFoundError(
            "\nNo PDF files were found under:\n\n"
            f"    {DEFAULT_PDF_DIRECTORY}\n\n"
            "Place a university PDF in that directory or pass "
            "a PDF path directly:\n\n"
            "    python test_azure_document_extractor.py "
            "\"path/to/document.pdf\"\n"
        )

    return pdf_files[0]


def validate_pdf(
    pdf_path: Path,
) -> None:
    """
    Validate the source PDF.
    """

    if not pdf_path.exists():
        raise FileNotFoundError(
            f"PDF does not exist: {pdf_path}"
        )

    if not pdf_path.is_file():
        raise ValueError(
            f"PDF path is not a file: {pdf_path}"
        )

    if (
        pdf_path.suffix.lower()
        != ".pdf"
    ):
        raise ValueError(
            "The test file must have a .pdf extension. "
            f"Received: {pdf_path.name}"
        )

    file_size = (
        pdf_path.stat().st_size
    )

    if file_size <= 0:
        raise ValueError(
            f"PDF is empty: {pdf_path}"
        )


# ====================================================================
# Configuration validation
# ====================================================================

def validate_azure_configuration() -> None:
    """
    Validate Azure PDF credentials without displaying secrets.
    """

    endpoint = getattr(
        Config,
        "AZURE_PDF_ENDPOINT",
        None,
    )

    api_key = getattr(
        Config,
        "AZURE_PDF_KEY",
        None,
    )

    if not endpoint:
        raise ValueError(
            "Config.AZURE_PDF_ENDPOINT is empty.\n\n"
            "Add this to your .env file:\n\n"
            "AZURE_PDF_ENDPOINT="
            "\"https://<resource>.cognitiveservices.azure.com\""
        )

    if not api_key:
        raise ValueError(
            "Config.AZURE_PDF_KEY is empty.\n\n"
            "Add this to your .env file:\n\n"
            "AZURE_PDF_KEY=\"<your-secret-key>\""
        )

    endpoint = str(
        endpoint
    ).strip()

    if not endpoint.startswith(
        (
            "https://",
            "http://",
        )
    ):
        raise ValueError(
            "Config.AZURE_PDF_ENDPOINT is not a valid URL."
        )


def get_safe_endpoint() -> str:
    """
    Return the configured endpoint.

    The endpoint is safe to print because it does not contain the API
    key. The secret key is never displayed.
    """

    endpoint = str(
        getattr(
            Config,
            "AZURE_PDF_ENDPOINT",
            "",
        )
    ).strip()

    return endpoint


# ====================================================================
# Result helpers
# ====================================================================

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

        current = current.get(
            key,
            default,
        )

    return current


def validate_json_file(
    file_path: Path,
) -> Dict[str, Any]:
    """
    Validate and load a JSON file.
    """

    if not file_path.exists():
        raise FileNotFoundError(
            f"Expected JSON file was not generated: {file_path}"
        )

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
        raise ValueError(
            f"Expected a JSON object in: {file_path}"
        )

    return payload


def validate_text_file(
    file_path: Path,
) -> str:
    """
    Validate and load a text file.
    """

    if not file_path.exists():
        raise FileNotFoundError(
            f"Expected text file was not generated: {file_path}"
        )

    return file_path.read_text(
        encoding="utf-8"
    )


def print_preview(
    content: str,
    max_characters: int,
) -> None:
    """
    Print a limited content preview.
    """

    cleaned_content = (
        content.strip()
    )

    if not cleaned_content:
        print(
            "No content was extracted."
        )
        return

    preview = cleaned_content[
        :max_characters
    ]

    print(
        preview
    )

    if (
        len(cleaned_content)
        > max_characters
    ):
        print()
        print(
            "... preview truncated ..."
        )


def get_table_page_numbers(
    table: Dict[str, Any],
) -> List[int]:
    """
    Return unique page numbers for a table.
    """

    page_numbers = set()

    bounding_regions = (
        table.get(
            "bounding_regions",
            [],
        )
    )

    if not isinstance(
        bounding_regions,
        list,
    ):
        return []

    for region in bounding_regions:
        if not isinstance(
            region,
            dict,
        ):
            continue

        page_number = (
            region.get(
                "pageNumber"
            )
        )

        if page_number is None:
            continue

        try:
            page_numbers.add(
                int(
                    page_number
                )
            )
        except (
            TypeError,
            ValueError,
        ):
            continue

    return sorted(
        page_numbers
    )


# ====================================================================
# Result display
# ====================================================================

def display_document_summary(
    result: Dict[str, Any],
) -> None:
    """
    Display document metadata.
    """

    print_header(
        "DOCUMENT INFORMATION"
    )

    print_field(
        "Document ID",
        get_nested(
            result,
            "document",
            "document_id",
        ),
    )

    print_field(
        "Filename",
        get_nested(
            result,
            "document",
            "filename",
        ),
    )

    print_field(
        "File type",
        get_nested(
            result,
            "document",
            "file_type",
        ),
    )

    print_field(
        "Page count",
        get_nested(
            result,
            "document",
            "page_count",
            default=0,
        ),
    )

    print_field(
        "Source title",
        get_nested(
            result,
            "source",
            "source_title",
        ),
    )

    print_field(
        "Source provider",
        get_nested(
            result,
            "source",
            "provider",
        ),
    )

    print_field(
        "Extraction status",
        get_nested(
            result,
            "extraction",
            "status",
        ),
    )

    print_field(
        "Extracted at",
        get_nested(
            result,
            "extraction",
            "extracted_at",
        ),
    )


def display_content_statistics(
    result: Dict[str, Any],
) -> None:
    """
    Display extracted content statistics.
    """

    print_header(
        "CONTENT STATISTICS"
    )

    print_field(
        "Content format",
        get_nested(
            result,
            "content",
            "format",
        ),
    )

    print_field(
        "Markdown characters",
        get_nested(
            result,
            "content",
            "character_count",
            default=0,
        ),
    )

    print_field(
        "Plain-text characters",
        get_nested(
            result,
            "content",
            "text_character_count",
            default=0,
        ),
    )

    print_field(
        "Estimated words",
        get_nested(
            result,
            "content",
            "word_count",
            default=0,
        ),
    )


def display_structure_statistics(
    result: Dict[str, Any],
) -> None:
    """
    Display extracted structure statistics.
    """

    print_header(
        "DOCUMENT STRUCTURE"
    )

    statistics = result.get(
        "statistics",
        {},
    )

    print_field(
        "Pages",
        statistics.get(
            "pages",
            0,
        ),
    )

    print_field(
        "Paragraphs",
        statistics.get(
            "paragraphs",
            0,
        ),
    )

    print_field(
        "Sections",
        statistics.get(
            "sections",
            0,
        ),
    )

    print_field(
        "Tables",
        statistics.get(
            "tables",
            0,
        ),
    )

    print_field(
        "Table cells",
        statistics.get(
            "table_cells",
            0,
        ),
    )

    print_field(
        "Figures",
        statistics.get(
            "figures",
            0,
        ),
    )

    print_field(
        "Languages",
        statistics.get(
            "languages",
            0,
        ),
    )

    print_field(
        "Styles",
        statistics.get(
            "styles",
            0,
        ),
    )


def display_pages(
    result: Dict[str, Any],
) -> None:
    """
    Display page summaries.
    """

    print_header(
        "EXTRACTED PAGES"
    )

    pages = get_nested(
        result,
        "structure",
        "pages",
        default=[],
    )

    if not pages:
        print(
            "No page objects were extracted."
        )
        return

    print_field(
        "Total pages",
        len(
            pages
        ),
    )

    for page in pages:
        print_subheader(
            f"Page "
            f"{page.get('page_number', 'Unknown')}"
        )

        print_field(
            "Dimensions",
            (
                f"{page.get('width')} "
                f"x "
                f"{page.get('height')} "
                f"{page.get('unit') or ''}"
            ).strip(),
        )

        print_field(
            "Angle",
            page.get(
                "angle"
            ),
        )

        print_field(
            "Lines",
            page.get(
                "line_count",
                0,
            ),
        )

        print_field(
            "Words",
            page.get(
                "word_count",
                0,
            ),
        )


def display_tables(
    result: Dict[str, Any],
) -> None:
    """
    Display extracted table summaries.
    """

    print_header(
        "EXTRACTED TABLES"
    )

    tables = get_nested(
        result,
        "structure",
        "tables",
        default=[],
    )

    if not tables:
        print(
            "No tables were detected in this PDF."
        )
        return

    print_field(
        "Total tables",
        len(
            tables
        ),
    )

    for table_number, table in enumerate(
        tables,
        start=1,
    ):
        print_subheader(
            f"Table {table_number}"
        )

        print_field(
            "Table ID",
            table.get(
                "table_id"
            ),
        )

        print_field(
            "Rows",
            table.get(
                "row_count",
                0,
            ),
        )

        print_field(
            "Columns",
            table.get(
                "column_count",
                0,
            ),
        )

        print_field(
            "Cells",
            table.get(
                "cell_count",
                0,
            ),
        )

        page_numbers = (
            get_table_page_numbers(
                table
            )
        )

        print_field(
            "Pages",
            (
                ", ".join(
                    str(
                        page_number
                    )
                    for page_number
                    in page_numbers
                )
                if page_numbers
                else "Not found"
            ),
        )

        headers = table.get(
            "headers",
            [],
        )

        if headers:
            print_field(
                "Headers",
                " | ".join(
                    headers
                ),
            )

        rows = table.get(
            "rows",
            [],
        )

        if rows:
            print()
            print(
                "First rows:"
            )

            for row in rows[:5]:
                print(
                    "  "
                    + " | ".join(
                        str(
                            value
                        )
                        for value in row
                    )
                )

            if len(
                rows
            ) > 5:
                print(
                    "  ... additional rows omitted ..."
                )


def display_azure_information(
    result: Dict[str, Any],
) -> None:
    """
    Display Azure extraction information.
    """

    print_header(
        "AZURE DOCUMENT INTELLIGENCE"
    )

    print_field(
        "Model ID",
        get_nested(
            result,
            "azure",
            "model_id",
        ),
    )

    print_field(
        "API version",
        get_nested(
            result,
            "azure",
            "api_version",
        ),
    )

    print_field(
        "Content format",
        get_nested(
            result,
            "azure",
            "content_format",
        ),
    )

    print_field(
        "String index type",
        get_nested(
            result,
            "azure",
            "string_index_type",
        ),
    )


def display_generated_files(
    result: Dict[str, Any],
) -> None:
    """
    Display generated file paths.
    """

    print_header(
        "GENERATED FILES"
    )

    generated_files = result.get(
        "generated_files",
        {},
    )

    if not generated_files:
        print(
            "No generated files were reported."
        )
        return

    labels = {
        "raw_azure_response": (
            "Raw Azure response"
        ),
        "markdown": (
            "Extracted Markdown"
        ),
        "text": (
            "Extracted plain text"
        ),
        "tables": (
            "Extracted tables"
        ),
        "document_data": (
            "Structured document JSON"
        ),
    }

    for key, file_path in (
        generated_files.items()
    ):
        print_field(
            labels.get(
                key,
                key,
            ),
            file_path,
        )


# ====================================================================
# Validation
# ====================================================================

def validate_result(
    result: Dict[str, Any],
) -> List[str]:
    """
    Validate the in-memory extraction result.

    Returns:
        List of validation failures.
    """

    failures = []

    if not isinstance(
        result,
        dict,
    ):
        return [
            "Extraction result is not a dictionary."
        ]

    status = get_nested(
        result,
        "extraction",
        "status",
    )

    if status != "success":
        failures.append(
            "Extraction status is not 'success'."
        )

    document_id = get_nested(
        result,
        "document",
        "document_id",
    )

    if not document_id:
        failures.append(
            "Document ID is missing."
        )

    filename = get_nested(
        result,
        "document",
        "filename",
    )

    if not filename:
        failures.append(
            "Document filename is missing."
        )

    page_count = get_nested(
        result,
        "document",
        "page_count",
        default=0,
    )

    if not isinstance(
        page_count,
        int,
    ):
        failures.append(
            "Page count is not an integer."
        )

    markdown = get_nested(
        result,
        "content",
        "markdown",
        default="",
    )

    if not markdown.strip():
        failures.append(
            "No Markdown content was extracted."
        )

    plain_text = get_nested(
        result,
        "content",
        "text",
        default="",
    )

    if not plain_text.strip():
        failures.append(
            "No plain-text content was generated."
        )

    structure = result.get(
        "structure"
    )

    if not isinstance(
        structure,
        dict,
    ):
        failures.append(
            "Document structure is missing."
        )

    statistics = result.get(
        "statistics"
    )

    if not isinstance(
        statistics,
        dict,
    ):
        failures.append(
            "Extraction statistics are missing."
        )

    return failures


def validate_generated_files(
    result: Dict[str, Any],
) -> List[str]:
    """
    Validate all generated output files.

    Returns:
        List of validation failures.
    """

    failures = []

    generated_files = result.get(
        "generated_files",
        {},
    )

    expected_files = {
        "raw_azure_response": (
            "Raw Azure response"
        ),
        "markdown": (
            "Markdown output"
        ),
        "text": (
            "Plain-text output"
        ),
        "tables": (
            "Tables output"
        ),
        "document_data": (
            "Structured document output"
        ),
    }

    for key, label in (
        expected_files.items()
    ):
        file_value = (
            generated_files.get(
                key
            )
        )

        if not file_value:
            failures.append(
                f"{label} path was not returned."
            )
            continue

        file_path = Path(
            file_value
        )

        if not file_path.exists():
            failures.append(
                f"{label} does not exist: {file_path}"
            )

    return failures


def validate_saved_content(
    result: Dict[str, Any],
) -> List[str]:
    """
    Validate generated file contents.

    Returns:
        List of validation failures.
    """

    failures = []

    generated_files = result.get(
        "generated_files",
        {},
    )

    try:
        raw_file = Path(
            generated_files[
                "raw_azure_response"
            ]
        )

        raw_payload = validate_json_file(
            raw_file
        )

        if (
            raw_payload.get(
                "status"
            )
            != "succeeded"
        ):
            failures.append(
                "Raw Azure response does not have "
                "status='succeeded'."
            )

    except Exception as error:
        failures.append(
            "Raw Azure response validation failed: "
            f"{error}"
        )

    try:
        markdown_file = Path(
            generated_files[
                "markdown"
            ]
        )

        markdown = validate_text_file(
            markdown_file
        )

        if not markdown.strip():
            failures.append(
                "Generated Markdown file is empty."
            )

    except Exception as error:
        failures.append(
            "Markdown validation failed: "
            f"{error}"
        )

    try:
        text_file = Path(
            generated_files[
                "text"
            ]
        )

        plain_text = validate_text_file(
            text_file
        )

        if not plain_text.strip():
            failures.append(
                "Generated plain-text file is empty."
            )

    except Exception as error:
        failures.append(
            "Plain-text validation failed: "
            f"{error}"
        )

    try:
        tables_file = Path(
            generated_files[
                "tables"
            ]
        )

        tables_payload = (
            validate_json_file(
                tables_file
            )
        )

        if "tables" not in (
            tables_payload
        ):
            failures.append(
                "tables.json does not contain "
                "a 'tables' field."
            )

    except Exception as error:
        failures.append(
            "Tables validation failed: "
            f"{error}"
        )

    try:
        document_file = Path(
            generated_files[
                "document_data"
            ]
        )

        document_payload = (
            validate_json_file(
                document_file
            )
        )

        if (
            document_payload.get(
                "extraction",
                {},
            ).get(
                "status"
            )
            != "success"
        ):
            failures.append(
                "document_data.json does not have "
                "extraction.status='success'."
            )

    except Exception as error:
        failures.append(
            "Structured document validation failed: "
            f"{error}"
        )

    return failures


# ====================================================================
# Main test
# ====================================================================

def main() -> None:
    """
    Run the complete Azure document extraction test.
    """

    print_header(
        "AZURE DOCUMENT EXTRACTOR TEST"
    )

    # ---------------------------------------------------------------
    # Resolve and validate source PDF
    # ---------------------------------------------------------------

    pdf_path = resolve_pdf_path()

    validate_pdf(
        pdf_path
    )

    file_size_bytes = (
        pdf_path.stat().st_size
    )

    file_size_mb = (
        file_size_bytes
        / (
            1024 * 1024
        )
    )

    document_id = (
        pdf_path.stem
    )

    output_dir = (
        OUTPUT_ROOT
        / PAGE_ID
        / document_id
    )

    print_field(
        "Source PDF",
        pdf_path,
    )

    print_field(
        "PDF size",
        f"{file_size_mb:.2f} MB",
    )

    print_field(
        "Document ID",
        document_id,
    )

    print_field(
        "Output directory",
        output_dir,
    )

    # ---------------------------------------------------------------
    # Validate Azure configuration
    # ---------------------------------------------------------------

    print_header(
        "VALIDATING AZURE CONFIGURATION"
    )

    validate_azure_configuration()

    print_success(
        "AZURE_PDF_ENDPOINT is configured."
    )

    print_success(
        "AZURE_PDF_KEY is configured."
    )

    print_field(
        "Azure endpoint",
        get_safe_endpoint(),
    )

    print(
        "✓ Azure PDF key is available "
        "(secret value hidden)."
    )

    # ---------------------------------------------------------------
    # Initialize extractor
    # ---------------------------------------------------------------

    print_header(
        "INITIALIZING EXTRACTOR"
    )

    extractor = AzureDocumentExtractor(
        model_id="prebuilt-layout",
        output_content_format="markdown",
        request_timeout=120,
        polling_interval=2.0,
        polling_timeout=600,
        max_retries=3,
        retry_delay=2.0,
        save_raw_response=True,
        save_markdown=True,
        save_text=True,
        save_structured_data=True,
        save_tables=True,
    )

    print_success(
        "AzureDocumentExtractor initialized."
    )

    print_field(
        "Model",
        extractor.model_id,
    )

    print_field(
        "API version",
        extractor.api_version,
    )

    print_field(
        "Output content format",
        extractor.output_content_format,
    )

    # ---------------------------------------------------------------
    # Extract PDF
    # ---------------------------------------------------------------

    print_header(
        "EXTRACTING PDF"
    )

    print(
        "Uploading PDF to Azure Document Intelligence..."
    )

    print(
        "Waiting for document analysis to complete..."
    )

    result = extractor.extract(
        pdf_path=pdf_path,
        output_dir=output_dir,
        document_id=document_id,
        source_title=pdf_path.stem,
        overwrite=True,
    )

    print_success(
        "Azure document analysis completed."
    )

    print_success(
        "Extraction outputs were saved."
    )

    # ---------------------------------------------------------------
    # Display extraction result
    # ---------------------------------------------------------------

    display_document_summary(
        result
    )

    display_content_statistics(
        result
    )

    display_structure_statistics(
        result
    )

    display_azure_information(
        result
    )

    display_pages(
        result
    )

    display_tables(
        result
    )

    # ---------------------------------------------------------------
    # Content previews
    # ---------------------------------------------------------------

    if SHOW_MARKDOWN_PREVIEW:
        print_header(
            "MARKDOWN PREVIEW"
        )

        markdown = get_nested(
            result,
            "content",
            "markdown",
            default="",
        )

        print_preview(
            content=markdown,
            max_characters=(
                MARKDOWN_PREVIEW_CHARACTERS
            ),
        )

    if SHOW_TEXT_PREVIEW:
        print_header(
            "PLAIN-TEXT PREVIEW"
        )

        plain_text = get_nested(
            result,
            "content",
            "text",
            default="",
        )

        print_preview(
            content=plain_text,
            max_characters=(
                TEXT_PREVIEW_CHARACTERS
            ),
        )

    # ---------------------------------------------------------------
    # Validate in-memory result
    # ---------------------------------------------------------------

    print_header(
        "VALIDATING EXTRACTION RESULT"
    )

    result_failures = (
        validate_result(
            result
        )
    )

    if result_failures:
        for failure in (
            result_failures
        ):
            print_failure(
                failure
            )

    else:
        print_success(
            "Extraction status is successful."
        )

        print_success(
            "Document metadata is valid."
        )

        print_success(
            "Markdown content was extracted."
        )

        print_success(
            "Plain-text content was generated."
        )

        print_success(
            "Document structure is valid."
        )

        print_success(
            "Extraction statistics are valid."
        )

    # ---------------------------------------------------------------
    # Validate generated files
    # ---------------------------------------------------------------

    display_generated_files(
        result
    )

    print_header(
        "VALIDATING GENERATED FILES"
    )

    file_failures = (
        validate_generated_files(
            result
        )
    )

    if file_failures:
        for failure in (
            file_failures
        ):
            print_failure(
                failure
            )

    else:
        print_success(
            "Raw Azure response exists."
        )

        print_success(
            "Extracted Markdown exists."
        )

        print_success(
            "Extracted plain text exists."
        )

        print_success(
            "Extracted tables JSON exists."
        )

        print_success(
            "Structured document JSON exists."
        )

    # ---------------------------------------------------------------
    # Validate generated file contents
    # ---------------------------------------------------------------

    print_header(
        "VALIDATING SAVED CONTENT"
    )

    content_failures = (
        validate_saved_content(
            result
        )
    )

    if content_failures:
        for failure in (
            content_failures
        ):
            print_failure(
                failure
            )

    else:
        print_success(
            "Raw Azure response contains valid JSON."
        )

        print_success(
            "Azure analysis status is succeeded."
        )

        print_success(
            "Markdown output is not empty."
        )

        print_success(
            "Plain-text output is not empty."
        )

        print_success(
            "Tables output contains valid JSON."
        )

        print_success(
            "Structured document output contains valid JSON."
        )

    # ---------------------------------------------------------------
    # Final result
    # ---------------------------------------------------------------

    all_failures = (
        result_failures
        + file_failures
        + content_failures
    )

    print_header(
        "TEST RESULT"
    )

    if all_failures:
        print_failure(
            "Azure document extraction completed "
            "with validation failures."
        )

        print()
        print_field(
            "Total failures",
            len(
                all_failures
            ),
        )

        print()
        print(
            "Review the validation messages above."
        )

        raise SystemExit(
            1
        )

    print_success(
        "Azure PDF extraction completed successfully."
    )

    print_success(
        "Raw Azure analysis was preserved."
    )

    print_success(
        "Extracted Markdown is valid."
    )

    print_success(
        "Extracted plain text is valid."
    )

    print_success(
        "Document structure is valid."
    )

    print_success(
        "All generated JSON files are valid."
    )

    print()
    print(
        "=" * 80
    )

    print(
        "✓ Azure Document Extractor test passed."
    )

    print(
        "✓ The extracted document is ready for "
        "PDF evidence building."
    )

    print(
        "=" * 80
    )


# ====================================================================
# Entry point
# ====================================================================

if __name__ == "__main__":
    try:
        main()

    except AzureDocumentExtractionError as error:
        print_header(
            "AZURE EXTRACTION FAILED"
        )

        print_failure(
            str(
                error
            )
        )

        print()
        print(
            "Check:"
        )

        print(
            "1. AZURE_PDF_ENDPOINT belongs to the "
            "Azure Document Intelligence resource."
        )

        print(
            "2. AZURE_PDF_KEY belongs to the same "
            "Azure resource."
        )

        print(
            "3. The Azure resource supports "
            "Document Intelligence."
        )

        print(
            "4. Your Azure quota has not been exhausted."
        )

        print(
            "5. The PDF is valid and is not password protected."
        )

        raise SystemExit(
            1
        )

    except KeyboardInterrupt:
        print()
        print_warning(
            "Test was stopped by the user."
        )

        raise SystemExit(
            130
        )

    except Exception as error:
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

        traceback.print_exc()

        raise SystemExit(
            1
        )