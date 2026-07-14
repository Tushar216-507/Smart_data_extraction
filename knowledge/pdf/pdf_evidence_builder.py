"""
PDF Evidence Builder
====================

Converts Azure Document Intelligence output into structured,
LLM-ready evidence chunks.

Pipeline:

Azure document_data.json
        ↓
Load Markdown and document structure
        ↓
Clean repeated document noise
        ↓
Detect headings and logical sections
        ↓
Preserve Markdown/HTML tables
        ↓
Split oversized sections safely
        ↓
Attach source and page metadata
        ↓
Save pdf_evidence_chunks.json

The builder is intentionally country-independent. It does not depend
on German-specific curriculum terminology. Document structure,
headings, paragraphs, tables, and content boundaries are the primary
signals.

Typical usage:

    from pathlib import Path

    from knowledge.pdf.pdf_evidence_builder import (
        PDFEvidenceBuilder,
    )

    builder = PDFEvidenceBuilder()

    result = builder.build(
        document_data_path=Path(
            "data/0001/pdf/0002/source/"
            "extracted/document_data.json"
        ),
        output_dir=Path(
            "data/0001/pdf/0002/source/evidence"
        ),
        program_id="0001",
        page_id="0002",
    )
"""

from __future__ import annotations

import hashlib
import html
import json
import re

from collections import Counter
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple


# ====================================================================
# Exceptions
# ====================================================================


class PDFEvidenceBuilderError(
    RuntimeError
):
    """
    Raised when PDF evidence generation cannot be completed.
    """


# ====================================================================
# Internal data models
# ====================================================================


@dataclass
class ContentBlock:
    """
    Internal representation of one logical Markdown block.
    """

    block_type: str
    content: str

    heading_level: Optional[int] = None
    heading_text: Optional[str] = None

    start_offset: Optional[int] = None
    end_offset: Optional[int] = None

    page_numbers: Tuple[int, ...] = ()


@dataclass
class EvidenceSection:
    """
    Internal representation of one document section.
    """

    title: str
    heading_level: Optional[int]

    blocks: List[ContentBlock]

    section_index: int = 0

    heading_path: Tuple[str, ...] = ()

    parent_section_title: Optional[str] = None

    previous_section_title: Optional[str] = None

    next_section_title: Optional[str] = None


# ====================================================================
# PDF evidence builder
# ====================================================================


class PDFEvidenceBuilder:
    """
    Build structured evidence chunks from Azure PDF extraction output.

    The builder uses Markdown as the canonical extraction source because
    Azure preserves headings and tables more effectively in Markdown
    than in plain text.

    The output is intended for:

        PDF evidence
            ↓
        PDF fact extraction
            ↓
        Semantic normalization
            ↓
        Website + PDF enrichment

    No LLM request is made by this component.
    """

    DEFAULT_OUTPUT_FILENAME = (
        "pdf_evidence_chunks.json"
    )

    SCHEMA_VERSION = "1.0"

    # ---------------------------------------------------------------
    # Generic document-section vocabulary
    # ---------------------------------------------------------------

    SECTION_KEYWORDS: Dict[str, Tuple[str, ...]] = {
        "identity_overview": (
            "overview",
            "programme overview",
            "program overview",
            "course overview",
            "programme information",
            "program information",
            "general information",
            "introduction",
            "about the programme",
            "about the program",
            "qualification",
            "degree",
            "award",
            "programme title",
            "program title",
            "study programme",
            "study program",
            "studiengang",
            "studienprogramm",
            "allgemeine informationen",
            "übersicht",
        ),
        "curriculum": (
            "curriculum",
            "programme structure",
            "program structure",
            "course structure",
            "degree structure",
            "study structure",
            "study plan",
            "study programme",
            "study program",
            "module",
            "modules",
            "module catalogue",
            "module catalog",
            "module handbook",
            "course catalogue",
            "course catalog",
            "course description",
            "course descriptions",
            "unit",
            "units",
            "subject",
            "subjects",
            "syllabus",
            "study content",
            "programme content",
            "program content",
            "course content",
            "credit",
            "credits",
            "credit hours",
            "ects",
            "learning outcomes",
            "learning objectives",
            "qualification objectives",
            "modul",
            "module",
            "modulhandbuch",
            "modulkatalog",
            "studienverlaufsplan",
            "studieninhalte",
            "lernergebnisse",
            "qualifikationsziele",
            "lehrveranstaltung",
        ),
        "admission": (
            "admission",
            "admissions",
            "entry requirements",
            "admission requirements",
            "eligibility",
            "application",
            "applications",
            "application requirements",
            "application process",
            "selection",
            "selection process",
            "enrolment",
            "enrollment",
            "registration",
            "admission criteria",
            "zugang",
            "zulassung",
            "zulassungsvoraussetzungen",
            "bewerbung",
            "einschreibung",
        ),
        "language": (
            "language",
            "language requirements",
            "language requirement",
            "language of instruction",
            "teaching language",
            "english requirements",
            "english language requirements",
            "language proficiency",
            "ielts",
            "toefl",
            "duolingo",
            "sprachkenntnisse",
            "unterrichtssprache",
            "lehrsprache",
        ),
        "assessment": (
            "assessment",
            "assessments",
            "examination",
            "examinations",
            "exam",
            "exams",
            "grading",
            "evaluation",
            "assessment methods",
            "assessment method",
            "examination methods",
            "prüfung",
            "prüfungen",
            "prüfungsform",
            "prüfungsformen",
            "leistungsnachweis",
        ),
        "fees_funding": (
            "tuition",
            "tuition fees",
            "fees",
            "cost",
            "costs",
            "funding",
            "scholarship",
            "scholarships",
            "financial aid",
            "financial support",
            "study costs",
            "semester fee",
            "semester contribution",
            "studiengebühren",
            "gebühren",
            "kosten",
            "finanzierung",
            "stipendium",
            "stipendien",
        ),
        "career": (
            "career",
            "careers",
            "career prospects",
            "career opportunities",
            "employment",
            "employability",
            "professional opportunities",
            "professional prospects",
            "graduate outcomes",
            "job opportunities",
            "beruf",
            "berufsfelder",
            "berufsperspektiven",
            "karriere",
        ),
        "research": (
            "research",
            "research areas",
            "research opportunities",
            "research focus",
            "thesis",
            "dissertation",
            "project",
            "projects",
            "forschung",
            "forschungsschwerpunkte",
            "abschlussarbeit",
        ),
        "student_support": (
            "student support",
            "support services",
            "academic support",
            "student services",
            "student life",
            "facilities",
            "resources",
            "accommodation",
            "housing",
            "international students",
            "student counselling",
            "student counseling",
            "beratung",
            "studierendenservice",
        ),
        "contacts": (
            "contact",
            "contacts",
            "contact information",
            "programme contact",
            "program contact",
            "course contact",
            "coordinator",
            "programme coordinator",
            "program coordinator",
            "module coordinator",
            "faculty",
            "department",
            "school",
            "institute",
            "ansprechpartner",
            "kontakt",
            "koordination",
            "modulverantwortliche",
        ),
        "regulations": (
            "regulation",
            "regulations",
            "academic regulations",
            "programme regulations",
            "program regulations",
            "examination regulations",
            "rules",
            "policy",
            "policies",
            "statute",
            "ordinance",
            "ordnung",
            "prüfungsordnung",
            "studienordnung",
            "satzung",
        ),
    }

    # ---------------------------------------------------------------
    # Generic section importance
    # ---------------------------------------------------------------

    IMPORTANT_SECTION_TYPES = {
        "identity_overview",
        "curriculum",
        "admission",
        "language",
        "assessment",
        "fees_funding",
        "career",
        "research",
        "student_support",
        "contacts",
        "regulations",
    }

    # ---------------------------------------------------------------
    # Markdown parsing expressions
    # ---------------------------------------------------------------

    MARKDOWN_HEADING_PATTERN = re.compile(
        r"^(?P<marks>#{1,6})[ \t]+"
        r"(?P<title>.+?)[ \t]*#*[ \t]*$"
    )

    SETEXT_H1_PATTERN = re.compile(
        r"^[ \t]*=+[ \t]*$"
    )

    SETEXT_H2_PATTERN = re.compile(
        r"^[ \t]*-+[ \t]*$"
    )

    HTML_TABLE_START_PATTERN = re.compile(
        r"<table\b",
        flags=re.IGNORECASE,
    )

    HTML_TABLE_END_PATTERN = re.compile(
        r"</table>",
        flags=re.IGNORECASE,
    )

    HTML_TAG_PATTERN = re.compile(
        r"<[^>]+>"
    )

    MARKDOWN_LINK_PATTERN = re.compile(
        r"\[([^\]]+)\]\([^)]+\)"
    )

    MARKDOWN_IMAGE_PATTERN = re.compile(
        r"!\[([^\]]*)\]\([^)]+\)"
    )

    WHITESPACE_PATTERN = re.compile(
        r"[ \t]+"
    )

    MULTIPLE_NEWLINES_PATTERN = re.compile(
        r"\n{3,}"
    )

    PAGE_NUMBER_ONLY_PATTERN = re.compile(
        r"^\s*(?:page|seite)?\s*"
        r"\d{1,4}"
        r"(?:\s*(?:of|von)\s*\d{1,4})?"
        r"\s*$",
        flags=re.IGNORECASE,
    )

    PAGE_LABEL_PATTERN = re.compile(
        r"^\s*(?:page|seite)\s+"
        r"\d{1,4}"
        r"(?:\s*(?:of|von)\s*\d{1,4})?"
        r"\s*$",
        flags=re.IGNORECASE,
    )

    MARKDOWN_TABLE_SEPARATOR_PATTERN = re.compile(
        r"^\s*\|?"
        r"(?:\s*:?-{3,}:?\s*\|)+"
        r"\s*:?-{3,}:?\s*\|?"
        r"\s*$"
    )

    BULLET_PATTERN = re.compile(
        r"^\s*(?:[-*+]|\d+[.)])\s+"
    )

    # ---------------------------------------------------------------
    # Constructor
    # ---------------------------------------------------------------

    def __init__(
        self,
        *,
        target_chunk_characters: int = 6500,
        max_chunk_characters: int = 9000,
        min_chunk_characters: int = 250,
        overlap_characters: int = 350,
        remove_repeated_noise: bool = True,
        repeated_line_min_pages: int = 3,
        repeated_line_ratio: float = 0.35,
        preserve_tables: bool = True,
        include_empty_sections: bool = False,
        output_filename: str = DEFAULT_OUTPUT_FILENAME,
    ) -> None:
        """
        Initialize the evidence builder.

        Args:
            target_chunk_characters:
                Preferred maximum size before a section is split.

            max_chunk_characters:
                Hard chunk-size target. A single indivisible table may
                exceed this value because table preservation is preferred.

            min_chunk_characters:
                Very small adjacent sections may be merged when safe.

            overlap_characters:
                Context copied between oversized text fragments.

            remove_repeated_noise:
                Remove repeated page headers, footers, and page labels
                conservatively.

            repeated_line_min_pages:
                Minimum number of pages on which a short line must appear
                before it can be considered repeated document noise.

            repeated_line_ratio:
                Minimum ratio of document pages containing a repeated line.

            preserve_tables:
                Keep complete Markdown and HTML tables together whenever
                possible.

            include_empty_sections:
                Whether empty detected sections should be written.

            output_filename:
                Name of the generated evidence JSON file.
        """

        if target_chunk_characters < 500:
            raise ValueError(
                "target_chunk_characters must be at least 500."
            )

        if max_chunk_characters < target_chunk_characters:
            raise ValueError(
                "max_chunk_characters must be greater than or "
                "equal to target_chunk_characters."
            )

        if min_chunk_characters < 0:
            raise ValueError(
                "min_chunk_characters cannot be negative."
            )

        if overlap_characters < 0:
            raise ValueError(
                "overlap_characters cannot be negative."
            )

        if overlap_characters >= target_chunk_characters:
            raise ValueError(
                "overlap_characters must be smaller than "
                "target_chunk_characters."
            )

        if repeated_line_min_pages < 2:
            raise ValueError(
                "repeated_line_min_pages must be at least 2."
            )

        if not 0.0 <= repeated_line_ratio <= 1.0:
            raise ValueError(
                "repeated_line_ratio must be between 0 and 1."
            )

        self.target_chunk_characters = (
            int(
                target_chunk_characters
            )
        )

        self.max_chunk_characters = (
            int(
                max_chunk_characters
            )
        )

        self.min_chunk_characters = (
            int(
                min_chunk_characters
            )
        )

        self.overlap_characters = (
            int(
                overlap_characters
            )
        )

        self.remove_repeated_noise = (
            bool(
                remove_repeated_noise
            )
        )

        self.repeated_line_min_pages = (
            int(
                repeated_line_min_pages
            )
        )

        self.repeated_line_ratio = (
            float(
                repeated_line_ratio
            )
        )

        self.preserve_tables = (
            bool(
                preserve_tables
            )
        )

        self.include_empty_sections = (
            bool(
                include_empty_sections
            )
        )

        self.output_filename = (
            str(
                output_filename
            ).strip()
            or self.DEFAULT_OUTPUT_FILENAME
        )

    # =================================================================
    # Public API
    # =================================================================

    def build(
        self,
        *,
        document_data_path: str | Path,
        output_dir: str | Path,
        program_id: Optional[str] = None,
        page_id: Optional[str] = None,
        document_id: Optional[str] = None,
        source_pdf_path: Optional[str | Path] = None,
        source_url: Optional[str] = None,
        university_name: Optional[str] = None,
        program_name: Optional[str] = None,
        overwrite: bool = True,
    ) -> Dict[str, Any]:
        """
        Build evidence chunks from Azure document data.

        Args:
            document_data_path:
                Path to Azure-generated document_data.json.

            output_dir:
                Directory in which pdf_evidence_chunks.json is saved.

            program_id:
                Program identifier, for example "0001".

            page_id:
                Crawled page identifier, for example "0002".

            document_id:
                Optional explicit document identifier.

            source_pdf_path:
                Optional original PDF path.

            source_url:
                Optional original PDF URL.

            university_name:
                Optional university name.

            program_name:
                Optional program name.

            overwrite:
                Replace an existing output file.

        Returns:
            Complete evidence payload.
        """

        document_path = Path(
            document_data_path
        )

        output_directory = Path(
            output_dir
        )

        if not document_path.exists():
            raise FileNotFoundError(
                "Azure document data does not exist: "
                f"{document_path}"
            )

        if not document_path.is_file():
            raise PDFEvidenceBuilderError(
                "Azure document-data path is not a file: "
                f"{document_path}"
            )

        document_data = self._load_json(
            document_path
        )

        resolved_document_id = (
            self._clean_optional_string(
                document_id
            )
            or self._clean_optional_string(
                self._get_nested(
                    document_data,
                    "document",
                    "document_id",
                )
            )
            or document_path.parent.parent.name
            or document_path.stem
        )

        resolved_program_id = (
            self._clean_optional_string(
                program_id
            )
        )

        resolved_page_id = (
            self._clean_optional_string(
                page_id
            )
        )

        output_file = (
            output_directory
            / self.output_filename
        )

        if (
            output_file.exists()
            and not overwrite
        ):
            return self._load_json(
                output_file
            )

        markdown = self._resolve_markdown(
            document_data=document_data,
            document_data_path=document_path,
        )

        if not markdown.strip():
            raise PDFEvidenceBuilderError(
                "No Markdown content was found in "
                f"{document_path}."
            )

        original_character_count = len(
            markdown
        )

        page_ranges = self._build_page_ranges(
            document_data
        )

        repeated_noise = (
            self._detect_repeated_page_noise(
                document_data
            )
            if self.remove_repeated_noise
            else set()
        )

        cleaned_markdown = self._clean_markdown(
            markdown=markdown,
            repeated_noise=repeated_noise,
        )

        blocks = self._parse_markdown_blocks(
            cleaned_markdown
        )

        blocks = self._attach_pages_to_blocks(
            blocks=blocks,
            original_markdown=markdown,
            page_ranges=page_ranges,
        )

        sections = self._build_sections(
            blocks
        )

        chunk_candidates = (
            self._build_chunk_candidates(
                sections
            )
        )

        chunk_candidates = (
            self._merge_small_chunks(
                chunk_candidates
            )
        )

        chunks = self._finalize_chunks(
            chunk_candidates=chunk_candidates,
            program_id=resolved_program_id,
            page_id=resolved_page_id,
            document_id=resolved_document_id,
            source_pdf_path=source_pdf_path,
            source_url=source_url,
        )

        payload = self._build_output_payload(
            document_data=document_data,
            document_data_path=document_path,
            output_file=output_file,
            chunks=chunks,
            program_id=resolved_program_id,
            page_id=resolved_page_id,
            document_id=resolved_document_id,
            source_pdf_path=source_pdf_path,
            source_url=source_url,
            university_name=university_name,
            program_name=program_name,
            original_character_count=(
                original_character_count
            ),
            cleaned_character_count=len(
                cleaned_markdown
            ),
            repeated_noise=repeated_noise,
            sections=sections,
        )

        output_directory.mkdir(
            parents=True,
            exist_ok=True,
        )

        self._write_json(
            output_file,
            payload,
        )

        return payload

    def build_from_directory(
        self,
        *,
        extracted_dir: str | Path,
        output_dir: Optional[str | Path] = None,
        program_id: Optional[str] = None,
        page_id: Optional[str] = None,
        document_id: Optional[str] = None,
        source_pdf_path: Optional[str | Path] = None,
        source_url: Optional[str] = None,
        university_name: Optional[str] = None,
        program_name: Optional[str] = None,
        overwrite: bool = True,
    ) -> Dict[str, Any]:
        """
        Build evidence from an Azure extracted-output directory.

        Expected input:

            extracted/
            ├── document.md
            ├── document.txt
            ├── document_data.json
            └── tables.json

        Default output:

            ../evidence/pdf_evidence_chunks.json
        """

        extracted_directory = Path(
            extracted_dir
        )

        document_data_path = (
            extracted_directory
            / "document_data.json"
        )

        if output_dir is None:
            resolved_output_dir = (
                extracted_directory.parent
                / "evidence"
            )
        else:
            resolved_output_dir = Path(
                output_dir
            )

        return self.build(
            document_data_path=(
                document_data_path
            ),
            output_dir=(
                resolved_output_dir
            ),
            program_id=program_id,
            page_id=page_id,
            document_id=document_id,
            source_pdf_path=source_pdf_path,
            source_url=source_url,
            university_name=university_name,
            program_name=program_name,
            overwrite=overwrite,
        )

    # =================================================================
    # Input loading
    # =================================================================

    def _load_json(
        self,
        file_path: Path,
    ) -> Dict[str, Any]:
        """
        Load and validate a JSON object.
        """

        try:
            with file_path.open(
                "r",
                encoding="utf-8",
            ) as file:
                payload = json.load(
                    file
                )

        except json.JSONDecodeError as error:
            raise PDFEvidenceBuilderError(
                "Invalid JSON in "
                f"{file_path}: {error}"
            ) from error

        except OSError as error:
            raise PDFEvidenceBuilderError(
                "Unable to read "
                f"{file_path}: {error}"
            ) from error

        if not isinstance(
            payload,
            dict,
        ):
            raise PDFEvidenceBuilderError(
                "Expected a JSON object in "
                f"{file_path}."
            )

        return payload

    def _resolve_markdown(
        self,
        *,
        document_data: Dict[str, Any],
        document_data_path: Path,
    ) -> str:
        """
        Resolve Markdown from document_data.json or document.md.
        """

        candidates = [
            self._get_nested(
                document_data,
                "content",
                "markdown",
            ),
            document_data.get(
                "markdown"
            ),
            self._get_nested(
                document_data,
                "document",
                "markdown",
            ),
        ]

        for candidate in candidates:
            if (
                isinstance(
                    candidate,
                    str,
                )
                and candidate.strip()
            ):
                return self._normalize_newlines(
                    candidate
                )

        generated_markdown = (
            self._get_nested(
                document_data,
                "generated_files",
                "markdown",
            )
        )

        candidate_paths: List[Path] = []

        if isinstance(
            generated_markdown,
            str,
        ):
            generated_path = Path(
                generated_markdown
            )

            candidate_paths.append(
                generated_path
            )

            if not generated_path.is_absolute():
                candidate_paths.append(
                    document_data_path.parent
                    / generated_path.name
                )

        candidate_paths.extend(
            [
                (
                    document_data_path.parent
                    / "document.md"
                ),
                (
                    document_data_path.parent
                    / "content.md"
                ),
                (
                    document_data_path.parent
                    / "extracted.md"
                ),
            ]
        )

        visited = set()

        for candidate_path in candidate_paths:
            normalized_path = str(
                candidate_path
            )

            if normalized_path in visited:
                continue

            visited.add(
                normalized_path
            )

            if (
                candidate_path.exists()
                and candidate_path.is_file()
            ):
                try:
                    content = (
                        candidate_path.read_text(
                            encoding="utf-8"
                        )
                    )

                except OSError:
                    continue

                if content.strip():
                    return self._normalize_newlines(
                        content
                    )

        return ""

    # =================================================================
    # Page mapping
    # =================================================================

    def _build_page_ranges(
        self,
        document_data: Dict[str, Any],
    ) -> List[Dict[str, int]]:
        """
        Build content-offset ranges for extracted PDF pages.

        Azure may expose page spans using different key styles. This
        method accepts both snake_case and Azure camelCase structures.
        """

        pages = self._get_nested(
            document_data,
            "structure",
            "pages",
            default=[],
        )

        if not isinstance(
            pages,
            list,
        ):
            return []

        ranges: List[Dict[str, int]] = []

        for index, page in enumerate(
            pages,
            start=1,
        ):
            if not isinstance(
                page,
                dict,
            ):
                continue

            page_number = self._first_integer(
                page.get(
                    "page_number"
                ),
                page.get(
                    "pageNumber"
                ),
                index,
            )

            spans = page.get(
                "spans",
                []
            )

            if not isinstance(
                spans,
                list,
            ):
                spans = []

            for span in spans:
                if not isinstance(
                    span,
                    dict,
                ):
                    continue

                offset = self._first_integer(
                    span.get(
                        "offset"
                    ),
                    span.get(
                        "start_offset"
                    ),
                )

                length = self._first_integer(
                    span.get(
                        "length"
                    ),
                )

                if (
                    offset is None
                    or length is None
                    or length <= 0
                ):
                    continue

                ranges.append(
                    {
                        "page_number": (
                            page_number
                        ),
                        "start": offset,
                        "end": (
                            offset
                            + length
                        ),
                    }
                )

        ranges.sort(
            key=lambda item: (
                item["start"],
                item["end"],
                item["page_number"],
            )
        )

        return ranges

    def _attach_pages_to_blocks(
        self,
        *,
        blocks: List[ContentBlock],
        original_markdown: str,
        page_ranges: List[Dict[str, int]],
    ) -> List[ContentBlock]:
        """
        Attach best-effort page references to Markdown blocks.

        The cleaned Markdown may differ from Azure's original content,
        so blocks are located sequentially in the original Markdown.
        """

        if not page_ranges:
            return blocks

        search_cursor = 0

        for block in blocks:
            search_text = (
                block.content.strip()
            )

            if not search_text:
                continue

            position = original_markdown.find(
                search_text,
                search_cursor,
            )

            if position < 0:
                compact_search = (
                    self._normalize_for_matching(
                        search_text
                    )
                )

                if len(
                    compact_search
                ) >= 30:
                    position = self._find_fuzzy_offset(
                        original_markdown=(
                            original_markdown
                        ),
                        block_content=(
                            search_text
                        ),
                        start_offset=(
                            search_cursor
                        ),
                    )

            if position < 0:
                continue

            end_position = (
                position
                + len(
                    search_text
                )
            )

            page_numbers = (
                self._pages_for_range(
                    start_offset=position,
                    end_offset=end_position,
                    page_ranges=page_ranges,
                )
            )

            block.start_offset = position
            block.end_offset = end_position
            block.page_numbers = tuple(
                page_numbers
            )

            search_cursor = max(
                search_cursor,
                end_position,
            )

        return blocks

    def _find_fuzzy_offset(
        self,
        *,
        original_markdown: str,
        block_content: str,
        start_offset: int,
    ) -> int:
        """
        Locate a block using a stable content prefix.
        """

        plain_content = (
            self._content_to_plain_text(
                block_content
            )
        )

        words = plain_content.split()

        if len(
            words
        ) < 6:
            return -1

        prefix = " ".join(
            words[:12]
        )

        if len(
            prefix
        ) < 30:
            return -1

        direct_position = (
            original_markdown.find(
                prefix,
                start_offset,
            )
        )

        return direct_position

    def _pages_for_range(
        self,
        *,
        start_offset: int,
        end_offset: int,
        page_ranges: List[Dict[str, int]],
    ) -> List[int]:
        """
        Return page numbers intersecting a content range.
        """

        pages = set()

        for page_range in page_ranges:
            if (
                start_offset
                < page_range["end"]
                and end_offset
                > page_range["start"]
            ):
                pages.add(
                    page_range[
                        "page_number"
                    ]
                )

        return sorted(
            pages
        )

    # =================================================================
    # Repeated page-noise detection
    # =================================================================

    def _detect_repeated_page_noise(
        self,
        document_data: Dict[str, Any],
    ) -> set[str]:
        """
        Detect likely repeated headers, footers, and page labels.

        Removal is intentionally conservative. Long repeated content is
        preserved because it may represent legitimate table headings or
        curriculum information.
        """

        pages = self._get_nested(
            document_data,
            "structure",
            "pages",
            default=[],
        )

        if not isinstance(
            pages,
            list,
        ):
            return set()

        total_pages = len(
            pages
        )

        if total_pages < 3:
            return set()

        per_page_lines: List[set[str]] = []

        for page in pages:
            if not isinstance(
                page,
                dict,
            ):
                continue

            page_lines = (
                self._extract_page_lines(
                    page
                )
            )

            normalized_lines = set()

            for line in page_lines:
                normalized = (
                    self._normalize_noise_line(
                        line
                    )
                )

                if normalized:
                    normalized_lines.add(
                        normalized
                    )

            if normalized_lines:
                per_page_lines.append(
                    normalized_lines
                )

        if len(
            per_page_lines
        ) < 3:
            return set()

        counter: Counter[str] = Counter()

        for page_lines in per_page_lines:
            counter.update(
                page_lines
            )

        minimum_by_ratio = max(
            1,
            int(
                len(
                    per_page_lines
                )
                * self.repeated_line_ratio
            ),
        )

        minimum_occurrences = max(
            self.repeated_line_min_pages,
            minimum_by_ratio,
        )

        repeated_noise = set()

        for normalized_line, count in (
            counter.items()
        ):
            if count < minimum_occurrences:
                continue

            if self._is_safe_repeated_noise(
                normalized_line
            ):
                repeated_noise.add(
                    normalized_line
                )

        return repeated_noise

    def _extract_page_lines(
        self,
        page: Dict[str, Any],
    ) -> List[str]:
        """
        Extract line content from a page object.
        """

        raw_lines = page.get(
            "lines",
            []
        )

        if not isinstance(
            raw_lines,
            list,
        ):
            return []

        lines: List[str] = []

        for raw_line in raw_lines:
            if isinstance(
                raw_line,
                str,
            ):
                content = raw_line

            elif isinstance(
                raw_line,
                dict,
            ):
                content = (
                    raw_line.get(
                        "content"
                    )
                    or raw_line.get(
                        "text"
                    )
                    or ""
                )

            else:
                continue

            content = str(
                content
            ).strip()

            if content:
                lines.append(
                    content
                )

        return lines

    def _is_safe_repeated_noise(
        self,
        normalized_line: str,
    ) -> bool:
        """
        Decide whether a repeated line is safe to remove.
        """

        if not normalized_line:
            return False

        if len(
            normalized_line
        ) > 120:
            return False

        if self.PAGE_NUMBER_ONLY_PATTERN.fullmatch(
            normalized_line
        ):
            return True

        word_count = len(
            normalized_line.split()
        )

        if word_count > 14:
            return False

        lowered = normalized_line.casefold()

        noise_markers = (
            "page ",
            "seite ",
            "copyright",
            "all rights reserved",
            "confidential",
            "www.",
            "http://",
            "https://",
            "module handbook",
            "module catalogue",
            "module catalog",
            "programme handbook",
            "program handbook",
            "course catalogue",
            "course catalog",
            "modulhandbuch",
            "modulkatalog",
        )

        return any(
            marker in lowered
            for marker in noise_markers
        )

    # =================================================================
    # Markdown cleaning
    # =================================================================

    def _clean_markdown(
        self,
        *,
        markdown: str,
        repeated_noise: set[str],
    ) -> str:
        """
        Clean Markdown without destroying document structure.
        """

        markdown = self._normalize_newlines(
            markdown
        )

        markdown = markdown.replace(
            "\x00",
            ""
        )

        lines = markdown.split(
            "\n"
        )

        cleaned_lines: List[str] = []

        inside_fenced_code = False
        inside_html_table = False

        for line in lines:
            stripped = line.strip()

            if stripped.startswith(
                "```"
            ):
                inside_fenced_code = (
                    not inside_fenced_code
                )

                cleaned_lines.append(
                    line.rstrip()
                )

                continue

            if self.HTML_TABLE_START_PATTERN.search(
                line
            ):
                inside_html_table = True

            if (
                not inside_fenced_code
                and not inside_html_table
            ):
                normalized_line = (
                    self._normalize_noise_line(
                        stripped
                    )
                )

                if (
                    normalized_line
                    and normalized_line
                    in repeated_noise
                ):
                    continue

                if self._is_standalone_page_label(
                    stripped
                ):
                    continue

            cleaned_lines.append(
                line.rstrip()
            )

            if self.HTML_TABLE_END_PATTERN.search(
                line
            ):
                inside_html_table = False

        cleaned = "\n".join(
            cleaned_lines
        )

        cleaned = (
            self.MULTIPLE_NEWLINES_PATTERN.sub(
                "\n\n",
                cleaned,
            )
        )

        return cleaned.strip()

    def _is_standalone_page_label(
        self,
        line: str,
    ) -> bool:
        """
        Detect standalone page-number labels.
        """

        if not line:
            return False

        return bool(
            self.PAGE_LABEL_PATTERN.fullmatch(
                line
            )
        )

    # =================================================================
    # Markdown block parsing
    # =================================================================

    def _parse_markdown_blocks(
        self,
        markdown: str,
    ) -> List[ContentBlock]:
        """
        Parse Markdown into headings, tables, and text blocks.
        """

        lines = markdown.split(
            "\n"
        )

        blocks: List[ContentBlock] = []

        text_buffer: List[str] = []

        index = 0

        def flush_text_buffer() -> None:
            if not text_buffer:
                return

            content = "\n".join(
                text_buffer
            ).strip()

            text_buffer.clear()

            if not content:
                return

            blocks.append(
                ContentBlock(
                    block_type="text",
                    content=content,
                )
            )

        while index < len(
            lines
        ):
            line = lines[
                index
            ]

            stripped = line.strip()

            # -------------------------------------------------------
            # ATX Markdown heading
            # -------------------------------------------------------

            heading_match = (
                self.MARKDOWN_HEADING_PATTERN.match(
                    line
                )
            )

            if heading_match:
                flush_text_buffer()

                heading_level = len(
                    heading_match.group(
                        "marks"
                    )
                )

                heading_text = (
                    self._clean_heading_text(
                        heading_match.group(
                            "title"
                        )
                    )
                )

                blocks.append(
                    ContentBlock(
                        block_type="heading",
                        content=(
                            "#"
                            * heading_level
                            + " "
                            + heading_text
                        ),
                        heading_level=(
                            heading_level
                        ),
                        heading_text=(
                            heading_text
                        ),
                    )
                )

                index += 1
                continue

            # -------------------------------------------------------
            # Setext Markdown heading
            # -------------------------------------------------------

            if (
                stripped
                and index + 1
                < len(
                    lines
                )
            ):
                next_line = lines[
                    index + 1
                ]

                if self.SETEXT_H1_PATTERN.fullmatch(
                    next_line
                ):
                    flush_text_buffer()

                    heading_text = (
                        self._clean_heading_text(
                            stripped
                        )
                    )

                    blocks.append(
                        ContentBlock(
                            block_type="heading",
                            content=(
                                "# "
                                + heading_text
                            ),
                            heading_level=1,
                            heading_text=(
                                heading_text
                            ),
                        )
                    )

                    index += 2
                    continue

                if self.SETEXT_H2_PATTERN.fullmatch(
                    next_line
                ):
                    flush_text_buffer()

                    heading_text = (
                        self._clean_heading_text(
                            stripped
                        )
                    )

                    blocks.append(
                        ContentBlock(
                            block_type="heading",
                            content=(
                                "## "
                                + heading_text
                            ),
                            heading_level=2,
                            heading_text=(
                                heading_text
                            ),
                        )
                    )

                    index += 2
                    continue

            # -------------------------------------------------------
            # HTML table
            # -------------------------------------------------------

            if self.HTML_TABLE_START_PATTERN.search(
                line
            ):
                flush_text_buffer()

                table_lines = [
                    line
                ]

                table_depth = (
                    len(
                        self.HTML_TABLE_START_PATTERN.findall(
                            line
                        )
                    )
                    - len(
                        self.HTML_TABLE_END_PATTERN.findall(
                            line
                        )
                    )
                )

                index += 1

                while (
                    index
                    < len(
                        lines
                    )
                    and table_depth > 0
                ):
                    table_line = (
                        lines[
                            index
                        ]
                    )

                    table_lines.append(
                        table_line
                    )

                    table_depth += (
                        len(
                            self.HTML_TABLE_START_PATTERN.findall(
                                table_line
                            )
                        )
                        - len(
                            self.HTML_TABLE_END_PATTERN.findall(
                                table_line
                            )
                        )
                    )

                    index += 1

                blocks.append(
                    ContentBlock(
                        block_type="table",
                        content=(
                            "\n".join(
                                table_lines
                            ).strip()
                        ),
                    )
                )

                continue

            # -------------------------------------------------------
            # Markdown pipe table
            # -------------------------------------------------------

            if self._is_markdown_table_start(
                lines=lines,
                index=index,
            ):
                flush_text_buffer()

                table_lines = [
                    line,
                    lines[
                        index + 1
                    ],
                ]

                index += 2

                while index < len(
                    lines
                ):
                    candidate = (
                        lines[
                            index
                        ]
                    )

                    if not self._is_markdown_table_row(
                        candidate
                    ):
                        break

                    table_lines.append(
                        candidate
                    )

                    index += 1

                blocks.append(
                    ContentBlock(
                        block_type="table",
                        content=(
                            "\n".join(
                                table_lines
                            ).strip()
                        ),
                    )
                )

                continue

            # -------------------------------------------------------
            # Paragraph/list content
            # -------------------------------------------------------

            if not stripped:
                if text_buffer:
                    text_buffer.append(
                        ""
                    )

                index += 1
                continue

            text_buffer.append(
                line
            )

            index += 1

        flush_text_buffer()

        return blocks

    def _is_markdown_table_start(
        self,
        *,
        lines: Sequence[str],
        index: int,
    ) -> bool:
        """
        Detect the first line of a Markdown pipe table.
        """

        if (
            index + 1
            >= len(
                lines
            )
        ):
            return False

        current_line = (
            lines[
                index
            ]
        )

        separator_line = (
            lines[
                index + 1
            ]
        )

        if "|" not in current_line:
            return False

        return bool(
            self.MARKDOWN_TABLE_SEPARATOR_PATTERN.match(
                separator_line
            )
        )

    def _is_markdown_table_row(
        self,
        line: str,
    ) -> bool:
        """
        Return whether a line is likely part of a Markdown table.
        """

        stripped = line.strip()

        if not stripped:
            return False

        return "|" in stripped

    # =================================================================
    # Section construction
    # =================================================================

    def _build_sections(
        self,
        blocks: List[ContentBlock],
    ) -> List[EvidenceSection]:
        """
        Build logical document sections from heading boundaries.
        """

        if not blocks:
            return []

        sections: List[EvidenceSection] = []

        current_title = (
            "Document overview"
        )

        current_heading_level: Optional[int] = (
            None
        )

        current_blocks: List[ContentBlock] = []

        section_index = 1

        for block in blocks:
            if block.block_type == "heading":
                if current_blocks:
                    sections.append(
                        EvidenceSection(
                            title=(
                                current_title
                            ),
                            heading_level=(
                                current_heading_level
                            ),
                            blocks=(
                                current_blocks
                            ),
                            section_index=(
                                section_index
                            ),
                        )
                    )

                    section_index += 1

                current_title = (
                    block.heading_text
                    or "Untitled section"
                )

                current_heading_level = (
                    block.heading_level
                )

                current_blocks = [
                    block
                ]

                continue

            current_blocks.append(
                block
            )

        if (
            current_blocks
            or self.include_empty_sections
        ):
            sections.append(
                EvidenceSection(
                    title=current_title,
                    heading_level=(
                        current_heading_level
                    ),
                    blocks=current_blocks,
                    section_index=(
                        section_index
                    ),
                )
            )

        return [
            section
            for section in sections
            if (
                self.include_empty_sections
                or self._section_has_content(
                    section
                )
            )
        ]

    def _section_has_content(
        self,
        section: EvidenceSection,
    ) -> bool:
        """
        Return whether a section contains meaningful content.
        """

        for block in section.blocks:
            if (
                block.block_type
                != "heading"
                and self._content_to_plain_text(
                    block.content
                ).strip()
            ):
                return True

        return any(
            block.content.strip()
            for block in section.blocks
        )

    # =================================================================
    # Chunk construction
    # =================================================================

    def _build_chunk_candidates(
        self,
        sections: List[EvidenceSection],
    ) -> List[Dict[str, Any]]:
        """
        Convert sections into size-safe chunk candidates.
        """

        candidates: List[
            Dict[str, Any]
        ] = []

        for section in sections:
            section_chunks = (
                self._split_section(
                    section
                )
            )

            candidates.extend(
                section_chunks
            )

        return candidates

    def _split_section(
        self,
        section: EvidenceSection,
    ) -> List[Dict[str, Any]]:
        """
        Split one section while preserving tables and headings.
        """

        section_type = (
            self._classify_section(
                section.title,
                self._section_content(
                    section
                ),
            )
        )

        section_heading = (
            self._section_heading_block(
                section
            )
        )

        content_blocks = [
            block
            for block in section.blocks
            if block.block_type
            != "heading"
        ]

        if not content_blocks:
            if not self.include_empty_sections:
                return []

            content = (
                section_heading
                or section.title
            )

            return [
                self._create_chunk_candidate(
                    section=section,
                    section_type=(
                        section_type
                    ),
                    content=content,
                    blocks=(
                        section.blocks
                    ),
                    part_number=1,
                    part_count=1,
                )
            ]

        prepared_blocks: List[
            ContentBlock
        ] = []

        for block in content_blocks:
            prepared_blocks.extend(
                self._split_oversized_block(
                    block=block,
                    heading_context=(
                        section_heading
                    ),
                )
            )

        chunk_groups: List[
            List[ContentBlock]
        ] = []

        current_group: List[
            ContentBlock
        ] = []

        current_length = len(
            section_heading
        )

        for block in prepared_blocks:
            block_length = len(
                block.content
            )

            separator_length = (
                2
                if current_group
                else 0
            )

            proposed_length = (
                current_length
                + separator_length
                + block_length
            )

            should_flush = (
                bool(
                    current_group
                )
                and proposed_length
                > self.target_chunk_characters
            )

            if should_flush:
                chunk_groups.append(
                    current_group
                )

                current_group = []
                current_length = len(
                    section_heading
                )

            current_group.append(
                block
            )

            current_length += (
                (
                    2
                    if len(
                        current_group
                    ) > 1
                    else 0
                )
                + block_length
            )

        if current_group:
            chunk_groups.append(
                current_group
            )

        if not chunk_groups:
            return []

        part_count = len(
            chunk_groups
        )

        candidates = []

        for part_index, group in enumerate(
            chunk_groups,
            start=1,
        ):
            content_parts = []

            if section_heading:
                content_parts.append(
                    section_heading
                )

            content_parts.extend(
                block.content.strip()
                for block in group
                if block.content.strip()
            )

            content = "\n\n".join(
                content_parts
            ).strip()

            candidates.append(
                self._create_chunk_candidate(
                    section=section,
                    section_type=(
                        section_type
                    ),
                    content=content,
                    blocks=group,
                    part_number=(
                        part_index
                    ),
                    part_count=(
                        part_count
                    ),
                )
            )

        return candidates

    def _split_oversized_block(
        self,
        *,
        block: ContentBlock,
        heading_context: str,
    ) -> List[ContentBlock]:
        """
        Split an oversized text block.

        Complete tables are preserved unless they are extremely large.
        """

        if (
            len(
                block.content
            )
            <= self.max_chunk_characters
        ):
            return [
                block
            ]

        if (
            block.block_type
            == "table"
            and self.preserve_tables
        ):
            return [
                block
            ]

        fragments = (
            self._split_text_content(
                block.content
            )
        )

        split_blocks = []

        for fragment in fragments:
            split_blocks.append(
                ContentBlock(
                    block_type=(
                        block.block_type
                    ),
                    content=fragment,
                    heading_level=(
                        block.heading_level
                    ),
                    heading_text=(
                        block.heading_text
                    ),
                    page_numbers=(
                        block.page_numbers
                    ),
                )
            )

        return split_blocks

    def _split_text_content(
        self,
        content: str,
    ) -> List[str]:
        """
        Split text using paragraph, list, sentence, and character
        boundaries in that order.
        """

        content = content.strip()

        if (
            len(
                content
            )
            <= self.max_chunk_characters
        ):
            return [
                content
            ]

        paragraphs = [
            paragraph.strip()
            for paragraph in re.split(
                r"\n\s*\n",
                content,
            )
            if paragraph.strip()
        ]

        if len(
            paragraphs
        ) <= 1:
            paragraphs = (
                self._split_by_lines(
                    content
                )
            )

        fragments: List[str] = []

        current_parts: List[str] = []
        current_length = 0

        for paragraph in paragraphs:
            paragraph_parts = (
                self._split_oversized_paragraph(
                    paragraph
                )
            )

            for paragraph_part in (
                paragraph_parts
            ):
                separator_length = (
                    2
                    if current_parts
                    else 0
                )

                proposed_length = (
                    current_length
                    + separator_length
                    + len(
                        paragraph_part
                    )
                )

                if (
                    current_parts
                    and proposed_length
                    > self.target_chunk_characters
                ):
                    fragment = "\n\n".join(
                        current_parts
                    ).strip()

                    if fragment:
                        fragments.append(
                            fragment
                        )

                    overlap = (
                        self._build_overlap(
                            fragment
                        )
                    )

                    current_parts = (
                        [overlap]
                        if overlap
                        else []
                    )

                    current_length = len(
                        overlap
                    )

                current_parts.append(
                    paragraph_part
                )

                current_length += (
                    (
                        2
                        if len(
                            current_parts
                        ) > 1
                        else 0
                    )
                    + len(
                        paragraph_part
                    )
                )

        if current_parts:
            fragment = "\n\n".join(
                current_parts
            ).strip()

            if fragment:
                fragments.append(
                    fragment
                )

        return self._deduplicate_adjacent_strings(
            fragments
        )

    def _split_by_lines(
        self,
        content: str,
    ) -> List[str]:
        """
        Split content into logical line groups.
        """

        lines = [
            line.rstrip()
            for line in content.split(
                "\n"
            )
        ]

        groups: List[str] = []

        current: List[str] = []

        for line in lines:
            if not line.strip():
                if current:
                    groups.append(
                        "\n".join(
                            current
                        ).strip()
                    )

                    current = []

                continue

            if (
                current
                and self.BULLET_PATTERN.match(
                    line
                )
                and not self.BULLET_PATTERN.match(
                    current[-1]
                )
            ):
                groups.append(
                    "\n".join(
                        current
                    ).strip()
                )

                current = [
                    line
                ]

                continue

            current.append(
                line
            )

        if current:
            groups.append(
                "\n".join(
                    current
                ).strip()
            )

        return [
            group
            for group in groups
            if group
        ]

    def _split_oversized_paragraph(
        self,
        paragraph: str,
    ) -> List[str]:
        """
        Split a large paragraph by sentence boundaries.
        """

        if (
            len(
                paragraph
            )
            <= self.max_chunk_characters
        ):
            return [
                paragraph
            ]

        sentences = re.split(
            r"(?<=[.!?])"
            r"\s+(?=[A-ZÀ-ÖØ-Þ0-9])",
            paragraph,
        )

        if len(
            sentences
        ) <= 1:
            return self._hard_split_text(
                paragraph
            )

        parts: List[str] = []

        current: List[str] = []
        current_length = 0

        for sentence in sentences:
            sentence = sentence.strip()

            if not sentence:
                continue

            if (
                len(
                    sentence
                )
                > self.max_chunk_characters
            ):
                if current:
                    parts.append(
                        " ".join(
                            current
                        ).strip()
                    )

                    current = []
                    current_length = 0

                parts.extend(
                    self._hard_split_text(
                        sentence
                    )
                )

                continue

            proposed_length = (
                current_length
                + (
                    1
                    if current
                    else 0
                )
                + len(
                    sentence
                )
            )

            if (
                current
                and proposed_length
                > self.target_chunk_characters
            ):
                parts.append(
                    " ".join(
                        current
                    ).strip()
                )

                current = []
                current_length = 0

            current.append(
                sentence
            )

            current_length += (
                (
                    1
                    if len(
                        current
                    ) > 1
                    else 0
                )
                + len(
                    sentence
                )
            )

        if current:
            parts.append(
                " ".join(
                    current
                ).strip()
            )

        return [
            part
            for part in parts
            if part
        ]

    def _hard_split_text(
        self,
        content: str,
    ) -> List[str]:
        """
        Last-resort character splitting with word-safe boundaries.
        """

        parts: List[str] = []

        cursor = 0
        content_length = len(
            content
        )

        while cursor < content_length:
            end = min(
                cursor
                + self.target_chunk_characters,
                content_length,
            )

            if end < content_length:
                boundary = content.rfind(
                    " ",
                    cursor,
                    end,
                )

                if (
                    boundary
                    > cursor
                    + (
                        self.target_chunk_characters
                        // 2
                    )
                ):
                    end = boundary

            part = content[
                cursor:end
            ].strip()

            if part:
                parts.append(
                    part
                )

            if end >= content_length:
                break

            next_cursor = max(
                end
                - self.overlap_characters,
                cursor + 1,
            )

            cursor = next_cursor

        return parts

    def _build_overlap(
        self,
        content: str,
    ) -> str:
        """
        Build a word-safe overlap fragment.
        """

        if (
            self.overlap_characters <= 0
            or not content
        ):
            return ""

        overlap = content[
            -self.overlap_characters:
        ]

        first_space = overlap.find(
            " "
        )

        if first_space >= 0:
            overlap = overlap[
                first_space + 1:
            ]

        return overlap.strip()

    def _create_chunk_candidate(
        self,
        *,
        section: EvidenceSection,
        section_type: str,
        content: str,
        blocks: Sequence[ContentBlock],
        part_number: int,
        part_count: int,
    ) -> Dict[str, Any]:
        """
        Create an internal chunk candidate.
        """

        page_numbers = sorted(
            {
                page_number
                for block in blocks
                for page_number
                in block.page_numbers
            }
        )

        table_count = sum(
            1
            for block in blocks
            if block.block_type
            == "table"
        )

        plain_text = (
            self._content_to_plain_text(
                content
            )
        )

        return {
            "section_index": (
                section.section_index
            ),
            "section_title": (
                section.title
            ),
            "section_type": (
                section_type
            ),
            "heading_level": (
                section.heading_level
            ),
            "part_number": (
                part_number
            ),
            "part_count": (
                part_count
            ),
            "content": (
                content.strip()
            ),
            "page_numbers": (
                page_numbers
            ),
            "table_count": (
                table_count
            ),
            "contains_table": (
                table_count > 0
            ),
            "character_count": len(
                content
            ),
            "word_count": (
                self._count_words(
                    plain_text
                )
            ),
        }

    def _merge_small_chunks(
        self,
        chunks: List[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        """
        Merge very small adjacent chunks when semantically safe.

        Chunks from different classified sections are not merged.
        """

        if (
            self.min_chunk_characters <= 0
            or len(
                chunks
            ) <= 1
        ):
            return chunks

        merged: List[
            Dict[str, Any]
        ] = []

        for chunk in chunks:
            if not merged:
                merged.append(
                    chunk
                )

                continue

            previous = merged[
                -1
            ]

            can_merge = (
                chunk[
                    "character_count"
                ]
                < self.min_chunk_characters
                and previous[
                    "section_type"
                ]
                == chunk[
                    "section_type"
                ]
                and (
                    previous[
                        "character_count"
                    ]
                    + 2
                    + chunk[
                        "character_count"
                    ]
                )
                <= self.target_chunk_characters
                and not (
                    previous[
                        "contains_table"
                    ]
                    and chunk[
                        "contains_table"
                    ]
                )
            )

            if not can_merge:
                merged.append(
                    chunk
                )

                continue

            previous[
                "content"
            ] = (
                previous[
                    "content"
                ].rstrip()
                + "\n\n"
                + chunk[
                    "content"
                ].lstrip()
            )

            previous[
                "page_numbers"
            ] = sorted(
                set(
                    previous[
                        "page_numbers"
                    ]
                )
                | set(
                    chunk[
                        "page_numbers"
                    ]
                )
            )

            previous[
                "table_count"
            ] += chunk[
                "table_count"
            ]

            previous[
                "contains_table"
            ] = (
                previous[
                    "table_count"
                ] > 0
            )

            previous[
                "character_count"
            ] = len(
                previous[
                    "content"
                ]
            )

            previous[
                "word_count"
            ] = self._count_words(
                self._content_to_plain_text(
                    previous[
                        "content"
                    ]
                )
            )

        return merged

    # =================================================================
    # Final chunk schema
    # =================================================================

    def _finalize_chunks(
        self,
        *,
        chunk_candidates: List[Dict[str, Any]],
        program_id: Optional[str],
        page_id: Optional[str],
        document_id: str,
        source_pdf_path: Optional[str | Path],
        source_url: Optional[str],
    ) -> List[Dict[str, Any]]:
        """
        Add stable IDs, source metadata, and extraction metadata.
        """

        chunks: List[
            Dict[str, Any]
        ] = []

        total_chunks = len(
            chunk_candidates
        )

        source_pdf = (
            str(
                source_pdf_path
            )
            if source_pdf_path
            is not None
            else None
        )

        for index, candidate in enumerate(
            chunk_candidates,
            start=1,
        ):
            chunk_id = (
                f"pdf_{document_id}_"
                f"{index:04d}"
            )

            content = candidate[
                "content"
            ]

            content_hash = (
                hashlib.sha256(
                    content.encode(
                        "utf-8"
                    )
                ).hexdigest()
            )

            page_numbers = (
                candidate[
                    "page_numbers"
                ]
            )

            chunks.append(
                {
                    "chunk_id": (
                        chunk_id
                    ),
                    "chunk_index": (
                        index
                    ),
                    "total_chunks": (
                        total_chunks
                    ),
                    "source_type": (
                        "pdf"
                    ),
                    "document_id": (
                        document_id
                    ),
                    "program_id": (
                        program_id
                    ),
                    "page_id": (
                        page_id
                    ),
                    "section": {
                        "index": (
                            candidate[
                                "section_index"
                            ]
                        ),
                        "title": (
                            candidate[
                                "section_title"
                            ]
                        ),
                        "type": (
                            candidate[
                                "section_type"
                            ]
                        ),
                        "heading_level": (
                            candidate[
                                "heading_level"
                            ]
                        ),
                        "part_number": (
                            candidate[
                                "part_number"
                            ]
                        ),
                        "part_count": (
                            candidate[
                                "part_count"
                            ]
                        ),
                    },
                    "location": {
                        "page_numbers": (
                            page_numbers
                        ),
                        "page_start": (
                            min(
                                page_numbers
                            )
                            if page_numbers
                            else None
                        ),
                        "page_end": (
                            max(
                                page_numbers
                            )
                            if page_numbers
                            else None
                        ),
                    },
                    "content": (
                        content
                    ),
                    "content_format": (
                        "markdown"
                    ),
                    "statistics": {
                        "character_count": (
                            candidate[
                                "character_count"
                            ]
                        ),
                        "word_count": (
                            candidate[
                                "word_count"
                            ]
                        ),
                        "contains_table": (
                            candidate[
                                "contains_table"
                            ]
                        ),
                        "table_count": (
                            candidate[
                                "table_count"
                            ]
                        ),
                    },
                    "source": {
                        "source_type": (
                            "pdf"
                        ),
                        "pdf_path": (
                            source_pdf
                        ),
                        "source_url": (
                            self._clean_optional_string(
                                source_url
                            )
                        ),
                        "document_id": (
                            document_id
                        ),
                        "program_id": (
                            program_id
                        ),
                        "page_id": (
                            page_id
                        ),
                        "page_numbers": (
                            page_numbers
                        ),
                    },
                    "traceability": {
                        "content_sha256": (
                            content_hash
                        ),
                        "evidence_preserved": (
                            True
                        ),
                    },
                }
            )

        return chunks

    # =================================================================
    # Output payload
    # =================================================================

    def _build_output_payload(
        self,
        *,
        document_data: Dict[str, Any],
        document_data_path: Path,
        output_file: Path,
        chunks: List[Dict[str, Any]],
        program_id: Optional[str],
        page_id: Optional[str],
        document_id: str,
        source_pdf_path: Optional[str | Path],
        source_url: Optional[str],
        university_name: Optional[str],
        program_name: Optional[str],
        original_character_count: int,
        cleaned_character_count: int,
        repeated_noise: set[str],
        sections: List[EvidenceSection],
    ) -> Dict[str, Any]:
        """
        Build the final evidence-file schema.
        """

        page_count = self._first_integer(
            self._get_nested(
                document_data,
                "document",
                "page_count",
            ),
            self._get_nested(
                document_data,
                "statistics",
                "pages",
            ),
            0,
        )

        source_filename = (
            self._clean_optional_string(
                self._get_nested(
                    document_data,
                    "document",
                    "filename",
                )
            )
        )

        if (
            source_filename is None
            and source_pdf_path
            is not None
        ):
            source_filename = Path(
                source_pdf_path
            ).name

        total_characters = sum(
            chunk[
                "statistics"
            ][
                "character_count"
            ]
            for chunk in chunks
        )

        total_words = sum(
            chunk[
                "statistics"
            ][
                "word_count"
            ]
            for chunk in chunks
        )

        chunks_with_pages = sum(
            1
            for chunk in chunks
            if chunk[
                "location"
            ][
                "page_numbers"
            ]
        )

        chunks_with_tables = sum(
            1
            for chunk in chunks
            if chunk[
                "statistics"
            ][
                "contains_table"
            ]
        )

        section_type_counts = Counter(
            chunk[
                "section"
            ][
                "type"
            ]
            for chunk in chunks
        )

        return {
            "schema_version": (
                self.SCHEMA_VERSION
            ),
            "builder": {
                "name": (
                    self.__class__.__name__
                ),
                "built_at": (
                    datetime.now(
                        timezone.utc
                    ).isoformat()
                ),
                "strategy": (
                    "structure_aware_markdown_chunking"
                ),
                "country_specific": (
                    False
                ),
                "llm_used": (
                    False
                ),
            },
            "identity": {
                "university_name": (
                    self._clean_optional_string(
                        university_name
                    )
                ),
                "program_name": (
                    self._clean_optional_string(
                        program_name
                    )
                ),
                "program_id": (
                    program_id
                ),
                "page_id": (
                    page_id
                ),
                "document_id": (
                    document_id
                ),
            },
            "source": {
                "source_type": (
                    "pdf"
                ),
                "provider": (
                    self._clean_optional_string(
                        self._get_nested(
                            document_data,
                            "source",
                            "provider",
                        )
                    )
                    or (
                        "Azure Document "
                        "Intelligence"
                    )
                ),
                "filename": (
                    source_filename
                ),
                "pdf_path": (
                    str(
                        source_pdf_path
                    )
                    if source_pdf_path
                    is not None
                    else None
                ),
                "source_url": (
                    self._clean_optional_string(
                        source_url
                    )
                ),
                "document_data_path": (
                    str(
                        document_data_path
                    )
                ),
                "page_count": (
                    page_count
                ),
            },
            "configuration": {
                "target_chunk_characters": (
                    self.target_chunk_characters
                ),
                "max_chunk_characters": (
                    self.max_chunk_characters
                ),
                "min_chunk_characters": (
                    self.min_chunk_characters
                ),
                "overlap_characters": (
                    self.overlap_characters
                ),
                "preserve_tables": (
                    self.preserve_tables
                ),
                "remove_repeated_noise": (
                    self.remove_repeated_noise
                ),
            },
            "statistics": {
                "original_character_count": (
                    original_character_count
                ),
                "cleaned_character_count": (
                    cleaned_character_count
                ),
                "characters_removed": max(
                    0,
                    (
                        original_character_count
                        - cleaned_character_count
                    ),
                ),
                "sections_detected": len(
                    sections
                ),
                "chunks_created": len(
                    chunks
                ),
                "total_chunk_characters": (
                    total_characters
                ),
                "total_chunk_words": (
                    total_words
                ),
                "chunks_with_page_references": (
                    chunks_with_pages
                ),
                "chunks_without_page_references": (
                    len(
                        chunks
                    )
                    - chunks_with_pages
                ),
                "chunks_containing_tables": (
                    chunks_with_tables
                ),
                "repeated_noise_lines_removed": (
                    len(
                        repeated_noise
                    )
                ),
                "section_type_counts": dict(
                    sorted(
                        section_type_counts.items()
                    )
                ),
            },
            "quality": {
                "all_chunks_have_content": (
                    all(
                        bool(
                            chunk[
                                "content"
                            ].strip()
                        )
                        for chunk in chunks
                    )
                ),
                "all_chunks_have_hashes": (
                    all(
                        bool(
                            chunk[
                                "traceability"
                            ][
                                "content_sha256"
                            ]
                        )
                        for chunk in chunks
                    )
                ),
                "page_mapping_available": (
                    chunks_with_pages > 0
                ),
                "tables_preserved": (
                    self.preserve_tables
                ),
            },
            "generated_files": {
                "evidence_chunks": (
                    str(
                        output_file
                    )
                ),
            },
            "chunks": (
                chunks
            ),
        }

    # =================================================================
    # Section classification
    # =================================================================

    def _classify_section(
        self,
        title: str,
        content: str,
    ) -> str:
        """
        Classify a section using generic multilingual signals.

        Classification is only metadata. It does not determine whether
        content is preserved.
        """

        normalized_title = (
            self._normalize_for_matching(
                title
            )
        )

        normalized_content = (
            self._normalize_for_matching(
                self._content_to_plain_text(
                    content
                )[:2500]
            )
        )

        scores: Dict[
            str,
            float
        ] = {}

        for section_type, keywords in (
            self.SECTION_KEYWORDS.items()
        ):
            score = 0.0

            for keyword in keywords:
                normalized_keyword = (
                    self._normalize_for_matching(
                        keyword
                    )
                )

                if not normalized_keyword:
                    continue

                if normalized_keyword in (
                    normalized_title
                ):
                    score += 4.0

                if normalized_keyword in (
                    normalized_content
                ):
                    score += 1.0

            if score > 0:
                scores[
                    section_type
                ] = score

        if not scores:
            return "general"

        return max(
            scores,
            key=scores.get,
        )

    # =================================================================
    # Content helpers
    # =================================================================

    def _section_heading_block(
        self,
        section: EvidenceSection,
    ) -> str:
        """
        Return a Markdown heading for a section.
        """

        for block in section.blocks:
            if block.block_type == "heading":
                return block.content.strip()

        if not section.title:
            return ""

        return (
            "## "
            + section.title.strip()
        )

    def _section_content(
        self,
        section: EvidenceSection,
    ) -> str:
        """
        Join all section blocks.
        """

        return "\n\n".join(
            block.content.strip()
            for block in section.blocks
            if block.content.strip()
        )

    def _content_to_plain_text(
        self,
        content: str,
    ) -> str:
        """
        Convert Markdown/HTML evidence to approximate plain text.
        """

        value = self.MARKDOWN_IMAGE_PATTERN.sub(
            r"\1",
            content,
        )

        value = self.MARKDOWN_LINK_PATTERN.sub(
            r"\1",
            value,
        )

        value = self.HTML_TAG_PATTERN.sub(
            " ",
            value,
        )

        value = re.sub(
            r"^\s*#{1,6}\s+",
            "",
            value,
            flags=re.MULTILINE,
        )

        value = value.replace(
            "|",
            " ",
        )

        value = value.replace(
            "`",
            "",
        )

        value = html.unescape(
            value
        )

        value = self.WHITESPACE_PATTERN.sub(
            " ",
            value,
        )

        value = re.sub(
            r"\n\s*\n+",
            "\n",
            value,
        )

        return value.strip()

    def _clean_heading_text(
        self,
        value: str,
    ) -> str:
        """
        Normalize heading text.
        """

        value = html.unescape(
            value
        )

        value = self.MARKDOWN_LINK_PATTERN.sub(
            r"\1",
            value,
        )

        value = value.strip(
            " \t#"
        )

        value = self.WHITESPACE_PATTERN.sub(
            " ",
            value,
        )

        return value.strip()

    def _normalize_noise_line(
        self,
        value: str,
    ) -> str:
        """
        Normalize a line for repeated-noise comparison.
        """

        value = self._content_to_plain_text(
            value
        )

        value = value.casefold()

        value = re.sub(
            r"\s+",
            " ",
            value,
        )

        return value.strip()

    def _normalize_for_matching(
        self,
        value: str,
    ) -> str:
        """
        Normalize text for keyword matching.
        """

        value = html.unescape(
            str(
                value
            )
        )

        value = value.casefold()

        value = re.sub(
            r"[^\wÀ-ÖØ-öø-ÿ]+",
            " ",
            value,
            flags=re.UNICODE,
        )

        value = re.sub(
            r"\s+",
            " ",
            value,
        )

        return value.strip()

    def _normalize_newlines(
        self,
        value: str,
    ) -> str:
        """
        Normalize CRLF and CR newlines.
        """

        return (
            value.replace(
                "\r\n",
                "\n",
            )
            .replace(
                "\r",
                "\n",
            )
        )

    def _count_words(
        self,
        value: str,
    ) -> int:
        """
        Count Unicode word-like tokens.
        """

        return len(
            re.findall(
                r"\b[\wÀ-ÖØ-öø-ÿ]+\b",
                value,
                flags=re.UNICODE,
            )
        )

    def _deduplicate_adjacent_strings(
        self,
        values: Iterable[str],
    ) -> List[str]:
        """
        Remove only adjacent exact duplicate strings.
        """

        result: List[str] = []

        previous: Optional[str] = (
            None
        )

        for value in values:
            cleaned = value.strip()

            if not cleaned:
                continue

            if cleaned == previous:
                continue

            result.append(
                cleaned
            )

            previous = cleaned

        return result

    # =================================================================
    # Generic helpers
    # =================================================================

    def _get_nested(
        self,
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

    def _first_integer(
        self,
        *values: Any,
    ) -> Optional[int]:
        """
        Return the first value that can be converted to an integer.
        """

        for value in values:
            if value is None:
                continue

            try:
                return int(
                    value
                )

            except (
                TypeError,
                ValueError,
            ):
                continue

        return None

    def _clean_optional_string(
        self,
        value: Any,
    ) -> Optional[str]:
        """
        Convert a value to a stripped optional string.
        """

        if value is None:
            return None

        cleaned = str(
            value
        ).strip()

        return (
            cleaned
            if cleaned
            else None
        )

    def _write_json(
        self,
        file_path: Path,
        payload: Dict[str, Any],
    ) -> None:
        """
        Write UTF-8 JSON atomically.
        """

        file_path.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        temporary_path = (
            file_path.with_suffix(
                file_path.suffix
                + ".tmp"
            )
        )

        try:
            with temporary_path.open(
                "w",
                encoding="utf-8",
            ) as file:
                json.dump(
                    payload,
                    file,
                    ensure_ascii=False,
                    indent=2,
                )

                file.write(
                    "\n"
                )

            temporary_path.replace(
                file_path
            )

        except OSError as error:
            try:
                if temporary_path.exists():
                    temporary_path.unlink()

            except OSError:
                pass

            raise PDFEvidenceBuilderError(
                "Unable to save PDF evidence to "
                f"{file_path}: {error}"
            ) from error