"""
Azure Document Extractor
========================

Extracts structured content from PDF documents using Azure AI
Document Intelligence.

Azure is responsible only for document understanding:

PDF
    ↓
Azure Document Intelligence
    ↓
Markdown + text + tables + document structure
    ↓
Existing evidence/extraction/normalization pipeline

No LLM is used in this module.

Expected environment variables:

AZURE_PDF_ENDPOINT=https://<resource>.cognitiveservices.azure.com
AZURE_PDF_KEY=<secret>

Expected Config attributes:

Config.AZURE_PDF_ENDPOINT
Config.AZURE_PDF_KEY
"""

from __future__ import annotations

import copy
import json
import re
import time

from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Union
from urllib.parse import urljoin

import requests

from config import Config


class AzureDocumentExtractionError(RuntimeError):
    """
    Raised when Azure Document Intelligence cannot process a document.
    """


class AzureDocumentExtractor:
    """
    Extracts structured PDF content with Azure Document Intelligence.

    The extractor:

    1. Sends PDF bytes to Azure.
    2. Receives an asynchronous operation URL.
    3. Polls Azure until processing finishes.
    4. Preserves the complete Azure response.
    5. Extracts:
       - Markdown
       - Plain text
       - Pages
       - Paragraphs
       - Sections
       - Tables
       - Figures
       - Languages
       - Styles
    6. Optionally writes all outputs to disk.

    This class performs document extraction only. Semantic fact
    extraction should remain in the existing knowledge pipeline.
    """

    DEFAULT_API_VERSION = "2024-11-30"
    DEFAULT_MODEL_ID = "prebuilt-layout"

    TERMINAL_STATUSES = {
        "succeeded",
        "failed",
        "canceled",
        "cancelled",
    }

    RETRYABLE_STATUS_CODES = {
        408,
        429,
        500,
        502,
        503,
        504,
    }

    def __init__(
        self,
        endpoint: Optional[str] = None,
        api_key: Optional[str] = None,
        api_version: str = DEFAULT_API_VERSION,
        model_id: str = DEFAULT_MODEL_ID,
        output_content_format: str = "markdown",
        request_timeout: int = 120,
        polling_interval: float = 2.0,
        polling_timeout: int = 600,
        max_retries: int = 3,
        retry_delay: float = 2.0,
        save_raw_response: bool = True,
        save_markdown: bool = True,
        save_text: bool = True,
        save_structured_data: bool = True,
        save_tables: bool = True,
        session: Optional[requests.Session] = None,
    ) -> None:
        """
        Initialize the Azure document extractor.

        Args:
            endpoint:
                Azure Document Intelligence resource endpoint.

            api_key:
                Azure Document Intelligence API key.

            api_version:
                Azure Document Intelligence REST API version.

            model_id:
                Azure model ID. `prebuilt-layout` is recommended for
                university brochures, module catalogues, regulations,
                admissions PDFs, and curriculum documents.

            output_content_format:
                Azure content output format. Markdown preserves document
                structure better than plain text.

            request_timeout:
                HTTP timeout in seconds.

            polling_interval:
                Seconds between operation-status requests.

            polling_timeout:
                Maximum total time to wait for Azure processing.

            max_retries:
                Number of retries for temporary request failures.

            retry_delay:
                Initial retry delay. Exponential backoff is used.

            save_raw_response:
                Save the complete Azure response.

            save_markdown:
                Save extracted Markdown.

            save_text:
                Save plain text derived from Markdown.

            save_structured_data:
                Save normalized document structure.

            save_tables:
                Save tables separately.

            session:
                Optional requests session.
        """

        self.endpoint = (
            endpoint
            or getattr(
                Config,
                "AZURE_PDF_ENDPOINT",
                None,
            )
            or ""
        ).strip()

        self.api_key = (
            api_key
            or getattr(
                Config,
                "AZURE_PDF_KEY",
                None,
            )
            or ""
        ).strip()

        self.api_version = api_version.strip()
        self.model_id = model_id.strip()

        self.output_content_format = (
            output_content_format.strip().lower()
        )

        self.request_timeout = max(
            1,
            int(request_timeout),
        )

        self.polling_interval = max(
            0.5,
            float(polling_interval),
        )

        self.polling_timeout = max(
            10,
            int(polling_timeout),
        )

        self.max_retries = max(
            0,
            int(max_retries),
        )

        self.retry_delay = max(
            0.5,
            float(retry_delay),
        )

        self.save_raw_response = save_raw_response
        self.save_markdown = save_markdown
        self.save_text = save_text
        self.save_structured_data = save_structured_data
        self.save_tables = save_tables

        self.session = session or requests.Session()

        self._validate_configuration()

        self.endpoint = self.endpoint.rstrip("/")

    # ================================================================
    # Public API
    # ================================================================

    def extract(
        self,
        pdf_path: Union[str, Path],
        output_dir: Optional[Union[str, Path]] = None,
        document_id: Optional[str] = None,
        source_url: Optional[str] = None,
        source_title: Optional[str] = None,
        overwrite: bool = True,
    ) -> Dict[str, Any]:
        """
        Extract a local PDF.

        Args:
            pdf_path:
                Path to the source PDF.

            output_dir:
                Optional directory where extraction outputs are saved.

            document_id:
                Stable document identifier.

            source_url:
                Original PDF URL when available.

            source_title:
                Human-readable source title.

            overwrite:
                If False and a structured output already exists, load
                and return it instead of calling Azure again.

        Returns:
            Structured extraction result.
        """

        source_path = Path(pdf_path)

        if not source_path.exists():
            raise FileNotFoundError(
                f"PDF file does not exist: {source_path}"
            )

        if not source_path.is_file():
            raise ValueError(
                f"PDF path is not a file: {source_path}"
            )

        if source_path.suffix.lower() != ".pdf":
            raise ValueError(
                "AzureDocumentExtractor currently accepts PDF files only. "
                f"Received: {source_path.name}"
            )

        resolved_output_dir = (
            Path(output_dir)
            if output_dir is not None
            else None
        )

        if (
            resolved_output_dir is not None
            and not overwrite
        ):
            cached_result = self._load_cached_result(
                resolved_output_dir
            )

            if cached_result is not None:
                cached_result.setdefault(
                    "extraction",
                    {},
                )

                cached_result["extraction"][
                    "loaded_from_cache"
                ] = True

                return cached_result

        pdf_bytes = source_path.read_bytes()

        if not pdf_bytes:
            raise ValueError(
                f"PDF file is empty: {source_path}"
            )

        return self.extract_bytes(
            pdf_bytes=pdf_bytes,
            filename=source_path.name,
            output_dir=resolved_output_dir,
            document_id=document_id,
            source_url=source_url,
            source_title=source_title,
        )

    def extract_bytes(
        self,
        pdf_bytes: bytes,
        filename: str = "document.pdf",
        output_dir: Optional[Union[str, Path]] = None,
        document_id: Optional[str] = None,
        source_url: Optional[str] = None,
        source_title: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Extract a PDF already loaded into memory.

        Args:
            pdf_bytes:
                Raw PDF bytes.

            filename:
                Original filename.

            output_dir:
                Optional output directory.

            document_id:
                Stable internal document ID.

            source_url:
                Original source URL.

            source_title:
                Human-readable source title.

        Returns:
            Structured extraction result.
        """

        if not isinstance(
            pdf_bytes,
            (bytes, bytearray),
        ):
            raise TypeError(
                "pdf_bytes must be bytes or bytearray."
            )

        if not pdf_bytes:
            raise ValueError(
                "Cannot extract an empty PDF."
            )

        safe_filename = (
            Path(filename).name
            if filename
            else "document.pdf"
        )

        resolved_document_id = (
            document_id
            or self._create_document_id(
                safe_filename
            )
        )

        analyze_url = self._build_analyze_url()

        operation_url = self._submit_document(
            analyze_url=analyze_url,
            pdf_bytes=bytes(pdf_bytes),
        )

        raw_response = self._poll_operation(
            operation_url=operation_url
        )

        result = self._build_result(
            raw_response=raw_response,
            filename=safe_filename,
            document_id=resolved_document_id,
            source_url=source_url,
            source_title=source_title,
            operation_url=operation_url,
        )

        if output_dir is not None:
            generated_files = self.save_outputs(
                result=result,
                raw_response=raw_response,
                output_dir=output_dir,
            )

            result["generated_files"] = (
                generated_files
            )

        return result

    def save_outputs(
        self,
        result: Dict[str, Any],
        raw_response: Dict[str, Any],
        output_dir: Union[str, Path],
    ) -> Dict[str, str]:
        """
        Save extraction outputs.

        Directory structure:

        output_dir/
        ├── raw/
        │   └── azure_analysis.json
        └── extracted/
            ├── document.md
            ├── document.txt
            ├── document_data.json
            └── tables.json
        """

        base_dir = Path(output_dir)

        raw_dir = base_dir / "raw"
        extracted_dir = base_dir / "extracted"

        raw_dir.mkdir(
            parents=True,
            exist_ok=True,
        )

        extracted_dir.mkdir(
            parents=True,
            exist_ok=True,
        )

        generated_files: Dict[str, str] = {}

        if self.save_raw_response:
            raw_file = (
                raw_dir
                / "azure_analysis.json"
            )

            self._write_json(
                raw_file,
                raw_response,
            )

            generated_files[
                "raw_azure_response"
            ] = str(raw_file)

        if self.save_markdown:
            markdown_file = (
                extracted_dir
                / "document.md"
            )

            self._write_text(
                markdown_file,
                result.get(
                    "content",
                    {},
                ).get(
                    "markdown",
                    "",
                ),
            )

            generated_files[
                "markdown"
            ] = str(markdown_file)

        if self.save_text:
            text_file = (
                extracted_dir
                / "document.txt"
            )

            self._write_text(
                text_file,
                result.get(
                    "content",
                    {},
                ).get(
                    "text",
                    "",
                ),
            )

            generated_files[
                "text"
            ] = str(text_file)

        if self.save_tables:
            tables_file = (
                extracted_dir
                / "tables.json"
            )

            tables_payload = {
                "document_id": (
                    result.get(
                        "document",
                        {},
                    ).get(
                        "document_id"
                    )
                ),
                "total_tables": len(
                    result.get(
                        "structure",
                        {},
                    ).get(
                        "tables",
                        [],
                    )
                ),
                "tables": (
                    result.get(
                        "structure",
                        {},
                    ).get(
                        "tables",
                        [],
                    )
                ),
            }

            self._write_json(
                tables_file,
                tables_payload,
            )

            generated_files[
                "tables"
            ] = str(tables_file)

        if self.save_structured_data:
            structured_file = (
                extracted_dir
                / "document_data.json"
            )

            serializable_result = copy.deepcopy(
                result
            )

            serializable_result[
                "generated_files"
            ] = {
                **generated_files,
                "document_data": str(
                    structured_file
                ),
            }

            self._write_json(
                structured_file,
                serializable_result,
            )

            generated_files[
                "document_data"
            ] = str(structured_file)

        return generated_files

    # ================================================================
    # Azure request handling
    # ================================================================

    def _build_analyze_url(self) -> str:
        """
        Build the Azure Document Intelligence analyze URL.
        """

        endpoint = self.endpoint.rstrip("/")

        return (
            f"{endpoint}"
            f"/documentintelligence"
            f"/documentModels"
            f"/{self.model_id}:analyze"
        )

    def _submit_document(
        self,
        analyze_url: str,
        pdf_bytes: bytes,
    ) -> str:
        """
        Submit PDF bytes to Azure and return the operation URL.
        """

        headers = {
            "Ocp-Apim-Subscription-Key": (
                self.api_key
            ),
            "Content-Type": (
                "application/octet-stream"
            ),
            "Accept": "application/json",
        }

        params = {
            "api-version": self.api_version,
            "outputContentFormat": (
                self.output_content_format
            ),
        }

        response = self._request_with_retry(
            method="POST",
            url=analyze_url,
            headers=headers,
            params=params,
            data=pdf_bytes,
        )

        if response.status_code not in {
            200,
            201,
            202,
        }:
            self._raise_azure_error(
                response=response,
                action="submit PDF",
            )

        operation_url = (
            response.headers.get(
                "Operation-Location"
            )
            or response.headers.get(
                "operation-location"
            )
        )

        if not operation_url:
            try:
                response_data = response.json()
            except ValueError:
                response_data = {}

            if (
                response.status_code == 200
                and response_data
            ):
                raise AzureDocumentExtractionError(
                    "Azure returned a synchronous response, but no "
                    "Operation-Location header was available. "
                    "The current extractor expects asynchronous "
                    "Document Intelligence analysis."
                )

            raise AzureDocumentExtractionError(
                "Azure accepted the PDF but did not return an "
                "Operation-Location header."
            )

        return self._normalize_operation_url(
            operation_url
        )

    def _poll_operation(
        self,
        operation_url: str,
    ) -> Dict[str, Any]:
        """
        Poll Azure until analysis succeeds or fails.
        """

        headers = {
            "Ocp-Apim-Subscription-Key": (
                self.api_key
            ),
            "Accept": "application/json",
        }

        started_at = time.monotonic()
        last_status = "notStarted"

        while True:
            elapsed = (
                time.monotonic()
                - started_at
            )

            if elapsed > self.polling_timeout:
                raise TimeoutError(
                    "Azure document analysis exceeded "
                    f"{self.polling_timeout} seconds. "
                    f"Last status: {last_status}"
                )

            response = self._request_with_retry(
                method="GET",
                url=operation_url,
                headers=headers,
            )

            if not response.ok:
                self._raise_azure_error(
                    response=response,
                    action=(
                        "retrieve document "
                        "analysis result"
                    ),
                )

            try:
                payload = response.json()
            except ValueError as error:
                raise (
                    AzureDocumentExtractionError(
                        "Azure returned a non-JSON "
                        "polling response."
                    )
                ) from error

            last_status = str(
                payload.get(
                    "status",
                    "",
                )
            ).strip()

            normalized_status = (
                last_status.lower()
            )

            if normalized_status == "succeeded":
                return payload

            if normalized_status in {
                "failed",
                "canceled",
                "cancelled",
            }:
                error_data = payload.get(
                    "error",
                    {}
                )

                error_message = (
                    error_data.get(
                        "message"
                    )
                    if isinstance(
                        error_data,
                        dict,
                    )
                    else str(
                        error_data
                    )
                )

                raise (
                    AzureDocumentExtractionError(
                        "Azure document analysis "
                        f"{normalized_status}. "
                        f"{error_message or ''}"
                    )
                )

            time.sleep(
                self.polling_interval
            )

    def _request_with_retry(
        self,
        method: str,
        url: str,
        **kwargs: Any,
    ) -> requests.Response:
        """
        Execute an HTTP request with retry handling.
        """

        last_exception: Optional[
            requests.RequestException
        ] = None

        for attempt in range(
            self.max_retries + 1
        ):
            try:
                response = (
                    self.session.request(
                        method=method,
                        url=url,
                        timeout=(
                            self.request_timeout
                        ),
                        **kwargs,
                    )
                )

                if (
                    response.status_code
                    not in self.RETRYABLE_STATUS_CODES
                ):
                    return response

                if attempt >= self.max_retries:
                    return response

                retry_after = (
                    response.headers.get(
                        "Retry-After"
                    )
                )

                delay = self._get_retry_delay(
                    attempt=attempt,
                    retry_after=retry_after,
                )

                time.sleep(delay)

            except (
                requests.Timeout,
                requests.ConnectionError,
            ) as error:
                last_exception = error

                if attempt >= self.max_retries:
                    break

                delay = self._get_retry_delay(
                    attempt=attempt,
                    retry_after=None,
                )

                time.sleep(delay)

        if last_exception is not None:
            raise (
                AzureDocumentExtractionError(
                    "Unable to communicate with "
                    "Azure Document Intelligence: "
                    f"{last_exception}"
                )
            ) from last_exception

        raise AzureDocumentExtractionError(
            "Azure request failed after all "
            "retry attempts."
        )

    # ================================================================
    # Result construction
    # ================================================================

    def _build_result(
        self,
        raw_response: Dict[str, Any],
        filename: str,
        document_id: str,
        source_url: Optional[str],
        source_title: Optional[str],
        operation_url: str,
    ) -> Dict[str, Any]:
        """
        Convert Azure's response into the project's document schema.
        """

        analyze_result = raw_response.get(
            "analyzeResult",
            {}
        )

        if not isinstance(
            analyze_result,
            dict,
        ):
            analyze_result = {}

        markdown = str(
            analyze_result.get(
                "content",
                "",
            )
            or ""
        )

        plain_text = (
            self._markdown_to_text(
                markdown
            )
        )

        pages = self._extract_pages(
            analyze_result
        )

        paragraphs = (
            self._extract_paragraphs(
                analyze_result
            )
        )

        sections = self._extract_sections(
            analyze_result=analyze_result,
            markdown=markdown,
        )

        tables = self._extract_tables(
            analyze_result
        )

        figures = self._extract_figures(
            analyze_result
        )

        languages = self._extract_languages(
            analyze_result
        )

        styles = self._extract_styles(
            analyze_result
        )

        page_count = len(pages)

        if page_count == 0:
            page_count = self._infer_page_count(
                analyze_result
            )

        result = {
            "source": {
                "provider": (
                    "Azure AI Document Intelligence"
                ),
                "source_type": "pdf",
                "source_url": (
                    source_url or ""
                ),
                "source_title": (
                    source_title
                    or Path(
                        filename
                    ).stem
                ),
                "filename": filename,
            },
            "document": {
                "document_id": (
                    document_id
                ),
                "filename": filename,
                "file_type": "pdf",
                "page_count": page_count,
            },
            "content": {
                "format": (
                    self.output_content_format
                ),
                "markdown": markdown,
                "text": plain_text,
                "character_count": len(
                    markdown
                ),
                "text_character_count": len(
                    plain_text
                ),
                "word_count": (
                    self._count_words(
                        plain_text
                    )
                ),
            },
            "structure": {
                "pages": pages,
                "paragraphs": paragraphs,
                "sections": sections,
                "tables": tables,
                "figures": figures,
                "languages": languages,
                "styles": styles,
            },
            "statistics": {
                "pages": page_count,
                "paragraphs": len(
                    paragraphs
                ),
                "sections": len(
                    sections
                ),
                "tables": len(
                    tables
                ),
                "table_cells": sum(
                    table.get(
                        "cell_count",
                        0,
                    )
                    for table in tables
                ),
                "figures": len(
                    figures
                ),
                "languages": len(
                    languages
                ),
                "styles": len(
                    styles
                ),
            },
            "azure": {
                "model_id": (
                    analyze_result.get(
                        "modelId"
                    )
                    or self.model_id
                ),
                "api_version": (
                    analyze_result.get(
                        "apiVersion"
                    )
                    or self.api_version
                ),
                "content_format": (
                    analyze_result.get(
                        "contentFormat"
                    )
                    or (
                        self.output_content_format
                    )
                ),
                "string_index_type": (
                    analyze_result.get(
                        "stringIndexType"
                    )
                ),
                "operation_url": (
                    operation_url
                ),
            },
            "extraction": {
                "status": "success",
                "extracted_at": (
                    datetime.now(
                        timezone.utc
                    ).isoformat()
                ),
                "loaded_from_cache": False,
            },
        }

        return result

    # ================================================================
    # Azure structure parsing
    # ================================================================

    def _extract_pages(
        self,
        analyze_result: Dict[str, Any],
    ) -> List[Dict[str, Any]]:
        """
        Extract page-level metadata and lines.
        """

        output: List[
            Dict[str, Any]
        ] = []

        raw_pages = analyze_result.get(
            "pages",
            []
        )

        if not isinstance(
            raw_pages,
            list,
        ):
            return output

        for page_index, page in enumerate(
            raw_pages,
            start=1,
        ):
            if not isinstance(
                page,
                dict,
            ):
                continue

            lines = []

            for line in page.get(
                "lines",
                [],
            ):
                if not isinstance(
                    line,
                    dict,
                ):
                    continue

                lines.append(
                    {
                        "content": (
                            line.get(
                                "content",
                                "",
                            )
                        ),
                        "polygon": (
                            line.get(
                                "polygon",
                                [],
                            )
                        ),
                        "spans": (
                            line.get(
                                "spans",
                                [],
                            )
                        ),
                    }
                )

            words = []

            for word in page.get(
                "words",
                [],
            ):
                if not isinstance(
                    word,
                    dict,
                ):
                    continue

                words.append(
                    {
                        "content": (
                            word.get(
                                "content",
                                "",
                            )
                        ),
                        "confidence": (
                            word.get(
                                "confidence"
                            )
                        ),
                        "polygon": (
                            word.get(
                                "polygon",
                                [],
                            )
                        ),
                        "span": (
                            word.get(
                                "span",
                                {}
                            )
                        ),
                    }
                )

            output.append(
                {
                    "page_number": (
                        page.get(
                            "pageNumber",
                            page_index,
                        )
                    ),
                    "width": (
                        page.get(
                            "width"
                        )
                    ),
                    "height": (
                        page.get(
                            "height"
                        )
                    ),
                    "unit": (
                        page.get(
                            "unit"
                        )
                    ),
                    "angle": (
                        page.get(
                            "angle"
                        )
                    ),
                    "line_count": len(
                        lines
                    ),
                    "word_count": len(
                        words
                    ),
                    "lines": lines,
                    "words": words,
                    "spans": (
                        page.get(
                            "spans",
                            [],
                        )
                    ),
                }
            )

        return output

    def _extract_paragraphs(
        self,
        analyze_result: Dict[str, Any],
    ) -> List[Dict[str, Any]]:
        """
        Extract document paragraphs.
        """

        output: List[
            Dict[str, Any]
        ] = []

        raw_paragraphs = (
            analyze_result.get(
                "paragraphs",
                [],
            )
        )

        if not isinstance(
            raw_paragraphs,
            list,
        ):
            return output

        for index, paragraph in enumerate(
            raw_paragraphs,
            start=1,
        ):
            if not isinstance(
                paragraph,
                dict,
            ):
                continue

            output.append(
                {
                    "paragraph_id": (
                        f"paragraph_{index:04d}"
                    ),
                    "role": (
                        paragraph.get(
                            "role"
                        )
                    ),
                    "content": (
                        paragraph.get(
                            "content",
                            "",
                        )
                    ),
                    "bounding_regions": (
                        paragraph.get(
                            "boundingRegions",
                            [],
                        )
                    ),
                    "spans": (
                        paragraph.get(
                            "spans",
                            [],
                        )
                    ),
                }
            )

        return output

    def _extract_sections(
        self,
        analyze_result: Dict[str, Any],
        markdown: str,
    ) -> List[Dict[str, Any]]:
        """
        Extract Azure sections when available.

        If Azure does not return section objects, Markdown headings are
        used as a lightweight fallback.
        """

        output: List[
            Dict[str, Any]
        ] = []

        raw_sections = analyze_result.get(
            "sections",
            [],
        )

        if isinstance(
            raw_sections,
            list,
        ):
            for index, section in enumerate(
                raw_sections,
                start=1,
            ):
                if not isinstance(
                    section,
                    dict,
                ):
                    continue

                output.append(
                    {
                        "section_id": (
                            f"section_{index:04d}"
                        ),
                        "elements": (
                            section.get(
                                "elements",
                                [],
                            )
                        ),
                        "spans": (
                            section.get(
                                "spans",
                                [],
                            )
                        ),
                    }
                )

        if output:
            return output

        return self._extract_markdown_sections(
            markdown
        )

    def _extract_markdown_sections(
        self,
        markdown: str,
    ) -> List[Dict[str, Any]]:
        """
        Create basic section records from Markdown headings.
        """

        if not markdown.strip():
            return []

        heading_pattern = re.compile(
            r"^(#{1,6})\s+(.+?)\s*$",
            flags=re.MULTILINE,
        )

        matches = list(
            heading_pattern.finditer(
                markdown
            )
        )

        sections = []

        for index, match in enumerate(
            matches,
            start=1,
        ):
            content_start = match.end()

            content_end = (
                matches[index].start()
                if index < len(matches)
                else len(markdown)
            )

            section_content = (
                markdown[
                    content_start:
                    content_end
                ].strip()
            )

            sections.append(
                {
                    "section_id": (
                        f"section_{index:04d}"
                    ),
                    "level": len(
                        match.group(1)
                    ),
                    "title": (
                        match.group(2).strip()
                    ),
                    "content": (
                        section_content
                    ),
                    "source": (
                        "markdown_heading"
                    ),
                }
            )

        return sections

    def _extract_tables(
        self,
        analyze_result: Dict[str, Any],
    ) -> List[Dict[str, Any]]:
        """
        Convert Azure tables into structured rows and cells.
        """

        output: List[
            Dict[str, Any]
        ] = []

        raw_tables = analyze_result.get(
            "tables",
            [],
        )

        if not isinstance(
            raw_tables,
            list,
        ):
            return output

        for table_index, table in enumerate(
            raw_tables,
            start=1,
        ):
            if not isinstance(
                table,
                dict,
            ):
                continue

            row_count = self._safe_int(
                table.get(
                    "rowCount",
                    0,
                )
            )

            column_count = self._safe_int(
                table.get(
                    "columnCount",
                    0,
                )
            )

            cells = []

            for cell in table.get(
                "cells",
                [],
            ):
                if not isinstance(
                    cell,
                    dict,
                ):
                    continue

                cells.append(
                    {
                        "row_index": (
                            self._safe_int(
                                cell.get(
                                    "rowIndex",
                                    0,
                                )
                            )
                        ),
                        "column_index": (
                            self._safe_int(
                                cell.get(
                                    "columnIndex",
                                    0,
                                )
                            )
                        ),
                        "row_span": (
                            self._safe_int(
                                cell.get(
                                    "rowSpan",
                                    1,
                                )
                            )
                        ),
                        "column_span": (
                            self._safe_int(
                                cell.get(
                                    "columnSpan",
                                    1,
                                )
                            )
                        ),
                        "kind": (
                            cell.get(
                                "kind",
                                "content",
                            )
                        ),
                        "content": (
                            cell.get(
                                "content",
                                "",
                            )
                        ),
                        "bounding_regions": (
                            cell.get(
                                "boundingRegions",
                                [],
                            )
                        ),
                        "spans": (
                            cell.get(
                                "spans",
                                [],
                            )
                        ),
                    }
                )

            rows = self._build_table_rows(
                cells=cells,
                row_count=row_count,
                column_count=column_count,
            )

            headers = self._extract_table_headers(
                cells=cells,
                column_count=column_count,
            )

            output.append(
                {
                    "table_id": (
                        f"table_{table_index:04d}"
                    ),
                    "row_count": row_count,
                    "column_count": (
                        column_count
                    ),
                    "cell_count": len(
                        cells
                    ),
                    "headers": headers,
                    "rows": rows,
                    "cells": cells,
                    "bounding_regions": (
                        table.get(
                            "boundingRegions",
                            [],
                        )
                    ),
                    "spans": (
                        table.get(
                            "spans",
                            [],
                        )
                    ),
                }
            )

        return output

    def _build_table_rows(
        self,
        cells: List[Dict[str, Any]],
        row_count: int,
        column_count: int,
    ) -> List[List[str]]:
        """
        Build a rectangular table matrix.
        """

        if (
            row_count <= 0
            or column_count <= 0
        ):
            return []

        rows = [
            [
                ""
                for _ in range(
                    column_count
                )
            ]
            for _ in range(
                row_count
            )
        ]

        for cell in cells:
            row_index = self._safe_int(
                cell.get(
                    "row_index",
                    0,
                )
            )

            column_index = self._safe_int(
                cell.get(
                    "column_index",
                    0,
                )
            )

            if (
                0 <= row_index < row_count
                and (
                    0
                    <= column_index
                    < column_count
                )
            ):
                rows[
                    row_index
                ][
                    column_index
                ] = str(
                    cell.get(
                        "content",
                        "",
                    )
                )

        return rows

    def _extract_table_headers(
        self,
        cells: List[Dict[str, Any]],
        column_count: int,
    ) -> List[str]:
        """
        Extract table column headers when Azure identifies them.
        """

        if column_count <= 0:
            return []

        headers = [
            ""
            for _ in range(
                column_count
            )
        ]

        for cell in cells:
            kind = str(
                cell.get(
                    "kind",
                    "",
                )
            ).lower()

            if kind not in {
                "columnheader",
                "stubhead",
            }:
                continue

            column_index = self._safe_int(
                cell.get(
                    "column_index",
                    0,
                )
            )

            if (
                0
                <= column_index
                < column_count
            ):
                headers[
                    column_index
                ] = str(
                    cell.get(
                        "content",
                        "",
                    )
                )

        if not any(
            header.strip()
            for header in headers
        ):
            return []

        return headers

    def _extract_figures(
        self,
        analyze_result: Dict[str, Any],
    ) -> List[Dict[str, Any]]:
        """
        Extract figure metadata.
        """

        output = []

        raw_figures = analyze_result.get(
            "figures",
            [],
        )

        if not isinstance(
            raw_figures,
            list,
        ):
            return output

        for index, figure in enumerate(
            raw_figures,
            start=1,
        ):
            if not isinstance(
                figure,
                dict,
            ):
                continue

            output.append(
                {
                    "figure_id": (
                        figure.get(
                            "id"
                        )
                        or (
                            f"figure_{index:04d}"
                        )
                    ),
                    "elements": (
                        figure.get(
                            "elements",
                            [],
                        )
                    ),
                    "caption": (
                        figure.get(
                            "caption"
                        )
                    ),
                    "bounding_regions": (
                        figure.get(
                            "boundingRegions",
                            [],
                        )
                    ),
                    "spans": (
                        figure.get(
                            "spans",
                            [],
                        )
                    ),
                }
            )

        return output

    def _extract_languages(
        self,
        analyze_result: Dict[str, Any],
    ) -> List[Dict[str, Any]]:
        """
        Extract detected language information.
        """

        output = []

        raw_languages = (
            analyze_result.get(
                "languages",
                [],
            )
        )

        if not isinstance(
            raw_languages,
            list,
        ):
            return output

        for language in raw_languages:
            if not isinstance(
                language,
                dict,
            ):
                continue

            output.append(
                {
                    "locale": (
                        language.get(
                            "locale"
                        )
                    ),
                    "confidence": (
                        language.get(
                            "confidence"
                        )
                    ),
                    "spans": (
                        language.get(
                            "spans",
                            [],
                        )
                    ),
                }
            )

        return output

    def _extract_styles(
        self,
        analyze_result: Dict[str, Any],
    ) -> List[Dict[str, Any]]:
        """
        Extract detected document style information.
        """

        output = []

        raw_styles = analyze_result.get(
            "styles",
            [],
        )

        if not isinstance(
            raw_styles,
            list,
        ):
            return output

        for style in raw_styles:
            if not isinstance(
                style,
                dict,
            ):
                continue

            output.append(
                {
                    "is_handwritten": (
                        style.get(
                            "isHandwritten"
                        )
                    ),
                    "similar_font_family": (
                        style.get(
                            "similarFontFamily"
                        )
                    ),
                    "font_style": (
                        style.get(
                            "fontStyle"
                        )
                    ),
                    "font_weight": (
                        style.get(
                            "fontWeight"
                        )
                    ),
                    "color": (
                        style.get(
                            "color"
                        )
                    ),
                    "background_color": (
                        style.get(
                            "backgroundColor"
                        )
                    ),
                    "confidence": (
                        style.get(
                            "confidence"
                        )
                    ),
                    "spans": (
                        style.get(
                            "spans",
                            [],
                        )
                    ),
                }
            )

        return output

    # ================================================================
    # Utility methods
    # ================================================================

    def _validate_configuration(
        self,
    ) -> None:
        """
        Validate Azure configuration.
        """

        if not self.endpoint:
            raise ValueError(
                "Azure PDF endpoint is missing. "
                "Set AZURE_PDF_ENDPOINT in .env "
                "and expose it through Config."
            )

        if not self.api_key:
            raise ValueError(
                "Azure PDF key is missing. "
                "Set AZURE_PDF_KEY in .env "
                "and expose it through Config."
            )

        if not self.endpoint.startswith(
            (
                "https://",
                "http://",
            )
        ):
            raise ValueError(
                "AZURE_PDF_ENDPOINT must be a "
                "complete HTTP or HTTPS URL."
            )

        if not self.api_version:
            raise ValueError(
                "Azure API version cannot be empty."
            )

        if not self.model_id:
            raise ValueError(
                "Azure model ID cannot be empty."
            )

        if self.output_content_format not in {
            "markdown",
            "text",
        }:
            raise ValueError(
                "output_content_format must be "
                "'markdown' or 'text'."
            )

    def _normalize_operation_url(
        self,
        operation_url: str,
    ) -> str:
        """
        Normalize absolute or relative Azure operation URLs.
        """

        operation_url = (
            operation_url.strip()
        )

        if operation_url.startswith(
            (
                "https://",
                "http://",
            )
        ):
            return operation_url

        return urljoin(
            f"{self.endpoint}/",
            operation_url.lstrip("/"),
        )

    def _get_retry_delay(
        self,
        attempt: int,
        retry_after: Optional[str],
    ) -> float:
        """
        Calculate retry delay.
        """

        if retry_after:
            try:
                return max(
                    0.5,
                    float(
                        retry_after
                    ),
                )
            except (
                TypeError,
                ValueError,
            ):
                pass

        return (
            self.retry_delay
            * (
                2 ** attempt
            )
        )

    def _raise_azure_error(
        self,
        response: requests.Response,
        action: str,
    ) -> None:
        """
        Raise a readable Azure API error.
        """

        error_message = ""

        try:
            payload = response.json()

            if isinstance(
                payload,
                dict,
            ):
                error_data = payload.get(
                    "error",
                    payload,
                )

                if isinstance(
                    error_data,
                    dict,
                ):
                    error_message = str(
                        error_data.get(
                            "message",
                            "",
                        )
                    )
                else:
                    error_message = str(
                        error_data
                    )

        except ValueError:
            error_message = (
                response.text[:1000]
            )

        if response.status_code in {
            401,
            403,
        }:
            extra_message = (
                "Check AZURE_PDF_ENDPOINT and "
                "AZURE_PDF_KEY. Ensure that the "
                "key belongs to the same Azure "
                "resource as the endpoint."
            )
        elif response.status_code == 404:
            extra_message = (
                "Check the Azure endpoint, model "
                "path, and API version."
            )
        elif response.status_code == 429:
            extra_message = (
                "Azure rate limit or quota was "
                "reached. Retry later."
            )
        else:
            extra_message = ""

        message_parts = [
            (
                f"Unable to {action}. "
                f"Azure returned HTTP "
                f"{response.status_code}."
            )
        ]

        if error_message:
            message_parts.append(
                error_message
            )

        if extra_message:
            message_parts.append(
                extra_message
            )

        raise AzureDocumentExtractionError(
            " ".join(
                message_parts
            )
        )

    def _markdown_to_text(
        self,
        markdown: str,
    ) -> str:
        """
        Convert extracted Markdown into readable plain text.

        This intentionally performs lightweight cleanup only. The
        original Markdown remains the authoritative structured content.
        """

        if not markdown:
            return ""

        text = markdown

        text = re.sub(
            r"<!--.*?-->",
            "",
            text,
            flags=re.DOTALL,
        )

        text = re.sub(
            r"!\[([^\]]*)\]\([^)]+\)",
            r"\1",
            text,
        )

        text = re.sub(
            r"\[([^\]]+)\]\([^)]+\)",
            r"\1",
            text,
        )

        text = re.sub(
            r"^\s{0,3}#{1,6}\s*",
            "",
            text,
            flags=re.MULTILINE,
        )

        text = re.sub(
            r"^\s*[-*+]\s+",
            "",
            text,
            flags=re.MULTILINE,
        )

        text = re.sub(
            r"^\s*\d+[.)]\s+",
            "",
            text,
            flags=re.MULTILINE,
        )

        text = re.sub(
            r"</?[^>]+>",
            " ",
            text,
        )

        text = text.replace(
            "|",
            " "
        )

        text = re.sub(
            r"[*_~`]+",
            "",
            text,
        )

        text = re.sub(
            r"[ \t]+",
            " ",
            text,
        )

        text = re.sub(
            r"\n[ \t]+",
            "\n",
            text,
        )

        text = re.sub(
            r"\n{3,}",
            "\n\n",
            text,
        )

        return text.strip()

    def _create_document_id(
        self,
        filename: str,
    ) -> str:
        """
        Create a stable filesystem-safe document ID.
        """

        stem = Path(
            filename
        ).stem.lower()

        slug = re.sub(
            r"[^a-z0-9]+",
            "_",
            stem,
        )

        slug = slug.strip("_")

        return (
            slug
            or "document"
        )

    def _count_words(
        self,
        text: str,
    ) -> int:
        """
        Count text words.
        """

        return len(
            re.findall(
                r"\b[\w'-]+\b",
                text,
                flags=re.UNICODE,
            )
        )

    def _safe_int(
        self,
        value: Any,
    ) -> int:
        """
        Convert a value to an integer safely.
        """

        try:
            return int(
                value
            )
        except (
            TypeError,
            ValueError,
        ):
            return 0

    def _infer_page_count(
        self,
        analyze_result: Dict[str, Any],
    ) -> int:
        """
        Infer page count from bounding regions if page objects are absent.
        """

        page_numbers = set()

        collections = [
            analyze_result.get(
                "paragraphs",
                [],
            ),
            analyze_result.get(
                "tables",
                [],
            ),
            analyze_result.get(
                "figures",
                [],
            ),
        ]

        for collection in collections:
            if not isinstance(
                collection,
                list,
            ):
                continue

            for item in collection:
                if not isinstance(
                    item,
                    dict,
                ):
                    continue

                for region in item.get(
                    "boundingRegions",
                    [],
                ):
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

                    if page_number:
                        page_numbers.add(
                            self._safe_int(
                                page_number
                            )
                        )

        return max(
            page_numbers,
            default=0,
        )

    def _load_cached_result(
        self,
        output_dir: Path,
    ) -> Optional[Dict[str, Any]]:
        """
        Load an existing document_data.json.
        """

        structured_file = (
            output_dir
            / "extracted"
            / "document_data.json"
        )

        if not structured_file.exists():
            return None

        try:
            with structured_file.open(
                "r",
                encoding="utf-8",
            ) as file:
                payload = json.load(
                    file
                )

            if isinstance(
                payload,
                dict,
            ):
                return payload

        except (
            OSError,
            json.JSONDecodeError,
        ):
            return None

        return None

    def _write_json(
        self,
        path: Path,
        payload: Any,
    ) -> None:
        """
        Write formatted UTF-8 JSON.
        """

        path.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        with path.open(
            "w",
            encoding="utf-8",
        ) as file:
            json.dump(
                payload,
                file,
                ensure_ascii=False,
                indent=2,
            )

    def _write_text(
        self,
        path: Path,
        content: str,
    ) -> None:
        """
        Write UTF-8 text.
        """

        path.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        path.write_text(
            content or "",
            encoding="utf-8",
        )