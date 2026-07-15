"""
PDF Fact Extractor
==================

Extracts structured university-program facts from PDF evidence chunks.

Input:
    data/{program_id}/pdf/{page_id}/{document_id}/evidence/
        pdf_evidence_chunks.json

Output:
    data/{program_id}/pdf/{page_id}/{document_id}/facts/
        pdf_program_facts.json

Pipeline:
    AzureDocumentExtractor
        -> PDFEvidenceBuilder
        -> PDFFactExtractor
        -> PDF enrichment layer
        -> Final output builder

Design goals:
    - Extract facts from every PDF evidence chunk independently.
    - Maximize factual recall.
    - Remain country-independent.
    - Preserve original-language information.
    - Add normalized English values when useful.
    - Preserve complete source provenance.
    - Keep module and course relationships.
    - Avoid silently dropping valid facts.
    - Remove only exact duplicate facts.
    - Continue processing when an individual chunk fails.
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import re
import time
from copy import deepcopy
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Iterable, Optional

try:
    from openai import OpenAI
except ImportError:  # pragma: no cover
    OpenAI = None


LOGGER = logging.getLogger(__name__)

# =============================================================================
# LLM PROVIDER PRICING
# =============================================================================

# Prices are in USD per 1 million tokens.
#
# OpenAI:
#   Model: GPT-4.1
#   Input:  $2.00 / 1M tokens
#   Output: $8.00 / 1M tokens
#
# Groq:
#   Input:  $0.15 / 1M tokens
#   Output: $0.60 / 1M tokens
#
# NVIDIA NIM hosted:
#   Currently treated as free for this project.
#   Token usage is still recorded.
#
# Azure Document Intelligence is intentionally excluded because it is not
# part of this LLM token-pricing tracker.

PROVIDER_PRICING = {
    "openai": {
        "input_price_per_million": 2.00,
        "output_price_per_million": 8.00,
        "billing_type": "token_based",
    },

    "groq": {
        "input_price_per_million": 0.15,
        "output_price_per_million": 0.60,
        "billing_type": "token_based",
    },

    "nvidia": {
        "input_price_per_million": 0.00,
        "output_price_per_million": 0.00,
        "billing_type": "free_hosted",
    },
}

# =============================================================================
# EXTRACTION PROMPT
# =============================================================================

PDF_PROGRAM_EXTRACTION_PROMPT = """
You are extracting structured university-program facts from evidence obtained
from an official university PDF document.

Your goal is MAXIMUM FACTUAL RECALL.

Extract every useful fact explicitly supported by the supplied evidence.
Do not summarize the document. Do not omit details merely because they are
specific, repetitive, administrative, curriculum-related, or written in a
language other than English.

The extraction must remain country-independent. Do not assume that the program
uses German, American, British, Canadian, European, or any other country-specific
academic terminology.

IMPORTANT RULES

1. Use only the supplied evidence.
2. Never invent, infer, estimate, calculate, or complete missing information.
3. A fact must be directly supported by the evidence.
4. Preserve the original meaning.
5. Always preserve the exact source-language information in "original_value".
6. "value" must contain a faithful English representation whenever the source information is not already English.
7. Translation is required for meaningful non-English text. Do not copy
   non-English text unchanged into "value" unless it is:
   - a proper name
   - an official program title
   - an institution name
   - a module or course code
   - an abbreviation
   - a value that should not be translated
8. Keep distinct facts separate.
9. Do not merge unrelated modules, courses, requirements, assessments, or hours.
10. Preserve identifiers such as:
    - module codes
    - course codes
    - unit codes
    - requirement codes
    - qualification names
11. Preserve relationships using "entity" and "parent_entity".
12. Do not convert hours, credits, grades, currencies, dates, semesters, terms,
    or academic periods unless the evidence explicitly provides the conversion.
13. Do not assume that CP, ECTS, credits, credit hours, units, points, or similar
    systems are equivalent.
14. Do not treat an example as a mandatory requirement.
15. Do not treat a recommendation as a requirement.
16. Do not treat an elective as compulsory.
17. Do not treat a module component as a complete module.
18. Preserve optional, compulsory, elective, conditional, alternative, and
    recommended statuses.
19. Extract repeated facts when they belong to different modules or courses.
20. Return valid JSON only.
21. Translate meanings, not academic systems. Do not convert one credit system,
   qualification system, grade system, semester system, or academic concept
   into another.
22. Preserve official names in "original_value". A translated name may be placed
   in "value", but do not replace or lose the official source-language name.

23. Normalize common descriptive values into clear English when directly
    supported. Examples:

    "Deutsch" -> "German"
    "Englisch" -> "English"
    "Wintersemester" -> "Winter semester"
    "Sommersemester" -> "Summer semester"
    "Pflichtmodul" -> "Compulsory module"
    "Wahlpflichtmodul" -> "Compulsory elective module"
    "benotet" -> "Graded"
    "unbenotet" -> "Ungraded"
    "Hausarbeit" -> "Term paper"
    "Klausur" -> "Written examination"
    "mündliche Prüfung" -> "Oral examination"
    "Vorlesung" -> "Lecture"
    "Seminar" -> "Seminar"
    "Übung" -> "Tutorial or practical class"

FACT CATEGORIES

Use the most appropriate category:

- identity
- overview
- qualification
- academic_structure
- curriculum
- module
- course
- module_component
- credits
- workload
- teaching
- assessment
- learning_outcomes
- admission
- eligibility
- application
- language
- duration
- study_mode
- attendance
- schedule
- semester
- academic_calendar
- fees
- funding
- scholarship
- career
- accreditation
- regulation
- progression
- graduation
- thesis
- dissertation
- project
- internship
- placement
- exchange
- contact
- campus
- facilities
- student_support
- other

COMMON FIELDS

Examples of useful field names include:

Program identity:
- program_name
- official_program_name
- translated_program_name
- qualification
- qualification_level
- award
- degree
- degree_abbreviation
- program_code
- faculty
- school
- department
- institution
- university

Program structure:
- total_credits
- credit_system
- duration
- standard_duration
- study_mode
- attendance_mode
- language_of_instruction
- start_term
- academic_year
- curriculum_version
- regulation_date
- document_effective_date
- document_updated_date

Modules and courses:
- module_code
- module_name
- module_type
- module_status
- module_credits
- module_total_hours
- course_code
- course_name
- course_type
- course_status
- course_credits
- teaching_format
- delivery_period
- semester_offered
- term_offered
- contact_hours
- self_study_hours
- workload_hours
- weekly_contact_hours
- weekly_hours
- assessment
- assessment_type
- examination
- learning_outcomes
- prerequisites
- required_selection
- elective_selection
- minimum_credits
- maximum_credits

Final requirements:
- thesis
- thesis_credits
- dissertation
- final_project
- final_examination
- defense
- viva
- graduation_requirement

Use a different clear snake_case field when the evidence contains useful
information not represented above.

FIELD CLASSIFICATION RULES

A field must describe the meaning of the value. Do not select a field merely
because nearby text contains a related academic word.

Module identity:

- A value such as "P 5", "WP 1", "M01", or "MOD-101" is normally a
  "module_code", not a "module_name".

- A descriptive module title is "module_name".

- Never place a module code in "module_name".

Course identity:

- A value such as "P 5.1", "C101", or "COURSE-02" is normally a
  "course_code", not a "course_name".

- Never place a course code in "course_name".

Assessment:

- "assessment_type" describes the assessment method or deliverable.

Examples:
    Hausarbeit -> assessment_type: "Term paper"
    Klausur -> assessment_type: "Written examination"
    Referat -> assessment_type: "Presentation"
    mündliche Prüfung -> assessment_type: "Oral examination"

- Whether an assessment is graded or ungraded is not an assessment type.

Use:
    field: "grading_status"
    value: "Graded"

for:
    benotet

Use:
    field: "grading_status"
    value: "Ungraded"

for:
    unbenotet

Do not classify "benotet" as "assessment_type".

Credits:

Use fields according to the entity being described:

- program entity -> total_credits
- module entity -> module_credits
- course entity -> course_credits
- module component entity -> component_credits

Do not create dynamic field names containing module codes, semester numbers,
course codes, indexes, or values.

Incorrect:
    module_6th_semester_p8_1_title
    semester_4_mandatory_module_p5_1

Correct:
    field: course_name
    entity.id: P 8.1
    qualifiers.semester: 6

Correct:
    field: module_name
    entity.id: P 5
    qualifiers.semester: 4

Entity identifiers, semesters, terms, indexes, and statuses belong in
"entity", "parent_entity", or "qualifiers", not inside field names.

ENTITY RULES

Use "entity" for the item that the fact directly describes.

Examples:

{
  "entity": {
    "type": "program",
    "id": null,
    "name": "Bachelor of Arts in History"
  }
}

{
  "entity": {
    "type": "module",
    "id": "P 4",
    "name": "Religion"
  }
}

{
  "entity": {
    "type": "course",
    "id": "P 4.1",
    "name": "Egyptian Religion"
  },
  "parent_entity": {
    "type": "module",
    "id": "P 4",
    "name": "Religion"
  }
}

For facts describing the whole program, use:

{
  "type": "program",
  "id": null,
  "name": null
}

If the entity is not clear, use null values rather than guessing.

VALUE RULES

"value" must contain the useful English-normalized representation.

Use:
- string for text
- number for a single numeric value
- boolean only when explicitly supported
- list for a genuine multi-value fact
- object when the value naturally contains related subfields

Examples:

{
  "value": 180,
  "original_value": "180 ECTS-Punkte",
  "unit": "ECTS"
}

{
  "value": "Winter semester",
  "original_value": "WiSe",
  "unit": null
}

{
  "value": {
    "hours": 60,
    "weekly_hours": 4
  },
  "original_value": "60 h (4 SWS)",
  "unit": "hours"
}

Do not split a meaningful structured value into unrelated facts if doing so
would lose context. However, preserve independently useful facts separately
when appropriate.

CONFIDENCE

Use:
- 1.0 when the fact is explicitly and unambiguously stated
- 0.95 when directly stated but requires simple formatting or translation
- 0.90 when directly supported but table structure or OCR introduces minor
  uncertainty
- below 0.90 only when the evidence remains usable but contains visible
  extraction ambiguity

Do not include unsupported low-confidence guesses.

OUTPUT FORMAT

Return exactly one JSON object:

{
  "facts": [
    {
      "category": "module",
      "field": "module_name",
      "value": "Religion",
      "original_value": "Religion",
      "unit": null,
      "entity": {
        "type": "module",
        "id": "P 4",
        "name": "Religion"
      },
      "parent_entity": {
        "type": "program",
        "id": null,
        "name": null
      },
      "qualifiers": {
        "status": null,
        "requirement_type": null,
        "semester": null,
        "term": null,
        "academic_year": null
      },
      "confidence": 1.0
    }
  ]
}

Return:

{
  "facts": []
}

when the evidence contains no extractable university-program facts.

Do not include Markdown.
Do not include explanations.
Do not wrap the JSON in a code block.
"""


# =============================================================================
# DATA CLASSES
# =============================================================================

@dataclass
class ChunkExtractionResult:
    """Internal result for one evidence chunk."""

    chunk_id: str
    status: str
    facts: list[dict[str, Any]]
    attempts: int = 0
    error: Optional[str] = None
    response_text: Optional[str] = None
    usage: Optional[dict[str, Any]] = None


# =============================================================================
# PDF FACT EXTRACTOR
# =============================================================================

class PDFFactExtractor:
    """
    Extract structured program facts from PDF evidence chunks.

    The extractor accepts either:

    1. A configured OpenAI-compatible client.
    2. A custom callable through ``llm_callable``.

    A custom callable is useful for NVIDIA, Groq, Azure OpenAI, local models,
    tests, or any future provider.

    The callable may use either signature:

        llm_callable(system_prompt, user_prompt)

    or:

        llm_callable(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            model=model,
            temperature=temperature,
            max_tokens=max_tokens,
        )

    The callable should return one of:

        - JSON string
        - dictionary
        - OpenAI-style response object
    """

    DEFAULT_INPUT_FILENAME = "pdf_evidence_chunks.json"
    DEFAULT_OUTPUT_FILENAME = "pdf_program_facts.json"

    ALLOWED_CATEGORIES = {
        "identity",
        "overview",
        "qualification",
        "program",
        "requirement",
        "academic_structure",
        "curriculum",
        "module",
        "course",
        "module_component",
        "credits",
        "workload",
        "teaching",
        "assessment",
        "learning_outcomes",
        "admission",
        "eligibility",
        "application",
        "language",
        "duration",
        "study_mode",
        "attendance",
        "schedule",
        "semester",
        "academic_calendar",
        "fees",
        "funding",
        "scholarship",
        "career",
        "accreditation",
        "regulation",
        "progression",
        "graduation",
        "thesis",
        "dissertation",
        "project",
        "internship",
        "placement",
        "exchange",
        "contact",
        "campus",
        "facilities",
        "student_support",
        "other",
    }

    CANONICAL_FIELD_ALIASES = {
        # -------------------------------------------------------------
        # Program credits
        # -------------------------------------------------------------
        "credits": "credits",
        "credit": "credits",
        "ects": "credits",
        "ects_credits": "credits",
        "credit_points": "credits",

        "program_credits": "total_credits",
        "program_total_credits": "total_credits",
        "total_ects": "total_credits",
        "total_credit_points": "total_credits",

        # -------------------------------------------------------------
        # Module credits
        # -------------------------------------------------------------
        "module_credit": "module_credits",
        "module_ects": "module_credits",
        "module_ects_credits": "module_credits",
        "module_total_credits": "module_credits",
        "module_total_ects": "module_credits",
        "module_credit_points": "module_credits",

        # -------------------------------------------------------------
        # Course credits
        # -------------------------------------------------------------
        "course_credit": "course_credits",
        "course_ects": "course_credits",
        "course_ects_credits": "course_credits",
        "course_total_credits": "course_credits",
        "course_total_ects": "course_credits",

        # -------------------------------------------------------------
        # Module component credits
        # -------------------------------------------------------------
        "submodule_credits": "component_credits",
        "submodule_ects": "component_credits",
        "component_ects": "component_credits",
        "module_component_credits": "component_credits",

        # -------------------------------------------------------------
        # Teaching
        # -------------------------------------------------------------
        "teaching_form": "teaching_format",
        "instruction_format": "teaching_format",
        "instructional_format": "teaching_format",
        "delivery_format": "teaching_format",
        "class_format": "teaching_format",

        # -------------------------------------------------------------
        # Contact time
        # -------------------------------------------------------------
        "contact_time": "contact_hours",
        "presence_hours": "contact_hours",
        "presence_time": "contact_hours",
        "contact_hours_total": "contact_hours",
        "total_contact_hours": "contact_hours",

        "contact_hours_per_week": "weekly_contact_hours",
        "presence_hours_per_week": "weekly_contact_hours",
        "weekly_presence_hours": "weekly_contact_hours",

        # -------------------------------------------------------------
        # Workload
        # -------------------------------------------------------------
        "total_workload": "workload_hours",
        "total_workload_hours": "workload_hours",
        "student_workload": "workload_hours",
        "student_workload_hours": "workload_hours",

        "self_study": "self_study_hours",
        "self_study_time": "self_study_hours",
        "independent_study_hours": "self_study_hours",

        # -------------------------------------------------------------
        # Assessment
        # -------------------------------------------------------------
        "assessment_form": "assessment_type",
        "assessment_method": "assessment_type",
        "examination_form": "assessment_type",
        "examination_type": "assessment_type",
        "exam_type": "assessment_type",

        "grading": "grading_status",
        "graded_status": "grading_status",
        "assessment_grading": "grading_status",

        # -------------------------------------------------------------
        # Language
        # -------------------------------------------------------------
        "instruction_language": "language_of_instruction",
        "teaching_language": "language_of_instruction",
        "language_of_teaching": "language_of_instruction",

        # -------------------------------------------------------------
        # Identity
        # -------------------------------------------------------------
        "module_title": "module_name",
        "course_title": "course_name",
        "program_title": "program_name",
        "programme_name": "program_name",
        "programme_title": "program_name",
    }

    DETERMINISTIC_VALUE_TRANSLATIONS = {
        # Languages
        "deutsch": "German",
        "englisch": "English",
        "französisch": "French",
        "franzoesisch": "French",
        "spanisch": "Spanish",
        "italienisch": "Italian",

        # Academic periods
        "wintersemester": "Winter semester",
        "sommersemester": "Summer semester",
        "wise": "Winter semester",
        "sose": "Summer semester",

        # Requirement status
        "pflicht": "Compulsory",
        "verpflichtend": "Compulsory",
        "pflichtmodul": "Compulsory module",
        "wahlmodul": "Elective module",
        "wahlpflichtmodul": "Compulsory elective module",
        "optional": "Optional",

        # Grading status
        "benotet": "Graded",
        "unbenotet": "Ungraded",
        "bestanden/nicht bestanden": "Pass/fail",

        # Assessment types
        "hausarbeit": "Term paper",
        "klausur": "Written examination",
        "schriftliche prüfung": "Written examination",
        "schriftliche pruefung": "Written examination",
        "mündliche prüfung": "Oral examination",
        "muendliche pruefung": "Oral examination",
        "referat": "Presentation",
        "präsentation": "Presentation",
        "praesentation": "Presentation",
        "portfolio": "Portfolio",

        # Teaching formats
        "vorlesung": "Lecture",
        "seminar": "Seminar",
        "übung": "Tutorial or practical class",
        "uebung": "Tutorial or practical class",
        "praktikum": "Practical course",
        "kolloquium": "Colloquium",
    }

    GRADING_STATUS_VALUES = {
        "graded",
        "ungraded",
        "pass/fail",
        "benotet",
        "unbenotet",
        "bestanden/nicht bestanden",
    }

    ENTITY_CODE_PATTERN = re.compile(
        r"^[A-Za-zÄÖÜäöü]{0,8}"
        r"(?:[- ]?[A-Za-z]{0,4})?"
        r"[- ]?\d+"
        r"(?:[.\-]\d+)*"
        r"(?:[A-Za-z])?$",
        flags=re.IGNORECASE,
    )

    def __init__(
        self,
        client: Any = None,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        model: Optional[str] = None,
        llm_callable: Optional[Callable[..., Any]] = None,
        system_prompt: str = PDF_PROGRAM_EXTRACTION_PROMPT,
        temperature: float = 0.0,
        max_tokens: int = 12000,
        request_timeout: float = 180.0,
        max_retries: int = 3,
        retry_delay: float = 2.0,
        overwrite: bool = True,
        continue_on_error: bool = True,
        remove_exact_duplicates: bool = True,
        save_raw_responses: bool = True,
        logger: Optional[logging.Logger] = None,
    ) -> None:
        self.model = (
            model
            or os.getenv("PDF_EXTRACTION_MODEL")
            or os.getenv("OPENAI_MODEL")
            or "gpt-4.1-mini"
        )

        self.llm_callable = llm_callable
        self.system_prompt = system_prompt.strip()
        self.temperature = float(temperature)
        self.max_tokens = int(max_tokens)
        self.request_timeout = float(request_timeout)
        self.max_retries = max(1, int(max_retries))
        self.retry_delay = max(0.0, float(retry_delay))

        self.overwrite = bool(overwrite)
        self.continue_on_error = bool(continue_on_error)
        self.remove_exact_duplicates = bool(remove_exact_duplicates)
        self.save_raw_responses = bool(save_raw_responses)

        self.logger = logger or LOGGER

        self.client = client

        resolved_api_key = (
            api_key
            or os.getenv("OPENAI_API_KEY")
            or os.getenv("GROQ_API_KEY")
            or os.getenv("NVIDIA_API_KEY")
        )

        resolved_base_url = (
            base_url
            or os.getenv("OPENAI_BASE_URL")
            or os.getenv("GROQ_BASE_URL")
            or os.getenv("NVIDIA_BASE_URL")
        )

        # Store the base URL for provider detection.
        self.base_url = resolved_base_url

        if self.client is None and self.llm_callable is None:
            if resolved_api_key:
                if OpenAI is None:
                    raise ImportError(
                        "The 'openai' package is required when no custom "
                        "llm_callable is supplied. Install it using:\n"
                        "pip install openai"
                    )

                client_kwargs: dict[str, Any] = {
                    "api_key": resolved_api_key,
                    "timeout": self.request_timeout,
                }

                if resolved_base_url:
                    client_kwargs["base_url"] = (
                        resolved_base_url
                    )

                self.client = OpenAI(
                    **client_kwargs
                )

    # =========================================================================
    # PUBLIC API
    # =========================================================================

    def _detect_provider(
        self,
    ) -> str:
        """
        Detect the configured LLM provider.

        Supported providers:

        - OpenAI
        - Groq
        - NVIDIA NIM

        Provider detection primarily uses the configured base URL.
        """

        base_url = str(
            self.base_url
            or ""
        ).casefold()

        model = str(
            self.model
            or ""
        ).casefold()

        if (
            "api.groq.com" in base_url
            or "groq" in base_url
        ):
            return "groq"

        if (
            "integrate.api.nvidia.com" in base_url
            or "nvidia" in base_url
            or model.startswith("nvidia/")
        ):
            return "nvidia"

        if (
            "api.openai.com" in base_url
            or model.startswith("gpt-")
            or model.startswith("openai/")
        ):
            return "openai"

        return "unknown"
    
    def _get_provider_pricing(
        self,
    ) -> dict[str, Any]:
        """
        Return pricing information for the configured provider.
        """

        provider = self._detect_provider()

        pricing = PROVIDER_PRICING.get(
            provider
        )

        if pricing is None:
            return {
                "provider": provider,
                "currency": "USD",
                "input_price_per_million": None,
                "output_price_per_million": None,
                "billing_type": "unknown",
            }

        return {
            "provider": provider,
            "currency": "USD",

            "input_price_per_million": (
                pricing[
                    "input_price_per_million"
                ]
            ),

            "output_price_per_million": (
                pricing[
                    "output_price_per_million"
                ]
            ),

            "billing_type": (
                pricing["billing_type"]
            ),
        }

    def extract(
        self,
        evidence_path: str | Path,
        output_dir: Optional[str | Path] = None,
        program_id: Optional[str] = None,
        page_id: Optional[str] = None,
        document_id: Optional[str] = None,
        university_name: Optional[str] = None,
        program_name: Optional[str] = None,
        overwrite: Optional[bool] = None,
    ) -> dict[str, Any]:
        """
        Extract facts from a PDF evidence JSON file.

        Args:
            evidence_path:
                Path to ``pdf_evidence_chunks.json``.

            output_dir:
                Output directory. When omitted, a sibling ``facts`` directory
                is created beside the evidence directory.

            program_id:
                Optional program ID override.

            page_id:
                Optional source-page ID override.

            document_id:
                Optional document ID override.

            university_name:
                Optional university identity supplied to the model.

            program_name:
                Optional program identity supplied to the model.

            overwrite:
                Optional per-call overwrite override.

        Returns:
            Complete PDF fact extraction result.
        """

        evidence_path = Path(evidence_path)

        if not evidence_path.exists():
            raise FileNotFoundError(
                f"PDF evidence file was not found: {evidence_path}"
            )

        if not evidence_path.is_file():
            raise ValueError(
                f"PDF evidence path is not a file: {evidence_path}"
            )

        evidence_data = self._load_json(evidence_path)

        return self.extract_data(
            evidence_data=evidence_data,
            evidence_path=evidence_path,
            output_dir=output_dir,
            program_id=program_id,
            page_id=page_id,
            document_id=document_id,
            university_name=university_name,
            program_name=program_name,
            overwrite=overwrite,
        )

    def extract_data(
        self,
        evidence_data: dict[str, Any],
        evidence_path: Optional[str | Path] = None,
        output_dir: Optional[str | Path] = None,
        program_id: Optional[str] = None,
        page_id: Optional[str] = None,
        document_id: Optional[str] = None,
        university_name: Optional[str] = None,
        program_name: Optional[str] = None,
        overwrite: Optional[bool] = None,
    ) -> dict[str, Any]:
        """
        Extract facts from an already loaded evidence dictionary.
        """

        self._validate_evidence_data(evidence_data)

        evidence_path_obj = (
            Path(evidence_path)
            if evidence_path is not None
            else None
        )

        resolved_output_dir = self._resolve_output_dir(
            evidence_path=evidence_path_obj,
            output_dir=output_dir,
        )

        resolved_output_dir.mkdir(
            parents=True,
            exist_ok=True,
        )

        output_path = (
            resolved_output_dir
            / self.DEFAULT_OUTPUT_FILENAME
        )

        should_overwrite = (
            self.overwrite
            if overwrite is None
            else bool(overwrite)
        )

        if output_path.exists() and not should_overwrite:
            return self._load_json(output_path)

        metadata = self._extract_document_metadata(
            evidence_data=evidence_data,
            program_id=program_id,
            page_id=page_id,
            document_id=document_id,
            university_name=university_name,
            program_name=program_name,
        )

        chunks = evidence_data.get("chunks", [])

        extracted_facts: list[dict[str, Any]] = []
        chunk_results: list[dict[str, Any]] = []
        failed_chunks: list[dict[str, Any]] = []

        raw_response_dir = resolved_output_dir / "raw_responses"

        if self.save_raw_responses:
            raw_response_dir.mkdir(
                parents=True,
                exist_ok=True,
            )

        for chunk_index, chunk in enumerate(chunks, start=1):
            chunk_result = self._extract_chunk_with_retry(
                chunk=chunk,
                chunk_index=chunk_index,
                total_chunks=len(chunks),
                metadata=metadata,
            )

            chunk_summary = {
                "chunk_id": chunk_result.chunk_id,
                "status": chunk_result.status,
                "attempts": chunk_result.attempts,
                "facts_extracted": len(
                    chunk_result.facts
                ),
                "error": chunk_result.error,
                "usage": (
                    chunk_result.usage
                    or self._empty_usage()
                ),
            }

            chunk_results.append(chunk_summary)

            if (
                self.save_raw_responses
                and chunk_result.response_text is not None
            ):
                self._save_raw_response(
                    raw_response_dir=raw_response_dir,
                    chunk_id=chunk_result.chunk_id,
                    response_text=chunk_result.response_text,
                )

            if chunk_result.status == "success":
                for fact_index, raw_fact in enumerate(
                    chunk_result.facts,
                    start=1,
                ):
                    prepared_fact = self._prepare_fact(
                        raw_fact=raw_fact,
                        chunk=chunk,
                        metadata=metadata,
                        fact_index=fact_index,
                    )

                    if prepared_fact is not None:
                        extracted_facts.append(prepared_fact)

            else:
                failed_chunks.append(chunk_summary)

                if not self.continue_on_error:
                    raise RuntimeError(
                        "PDF fact extraction failed for chunk "
                        f"{chunk_result.chunk_id}: "
                        f"{chunk_result.error}"
                    )

        facts_before_deduplication = len(extracted_facts)

        if self.remove_exact_duplicates:
            (
                unique_facts,
                duplicate_count,
            ) = self._remove_exact_duplicates(
                extracted_facts
            )
        else:
            unique_facts = extracted_facts
            duplicate_count = 0

        unique_facts = self._assign_fact_ids(
            facts=unique_facts,
            document_id=metadata["document_id"],
        )

        result = self._build_result(
            metadata=metadata,
            evidence_data=evidence_data,
            evidence_path=evidence_path_obj,
            output_path=output_path,
            facts=unique_facts,
            chunk_results=chunk_results,
            failed_chunks=failed_chunks,
            facts_before_deduplication=facts_before_deduplication,
            exact_duplicates_removed=duplicate_count,
        )

        self.save_json(
            data=result,
            output_path=output_path,
        )

        return result

    def extract_from_document_directory(
        self,
        document_dir: str | Path,
        program_id: Optional[str] = None,
        page_id: Optional[str] = None,
        document_id: Optional[str] = None,
        university_name: Optional[str] = None,
        program_name: Optional[str] = None,
        overwrite: Optional[bool] = None,
    ) -> dict[str, Any]:
        """
        Convenience method for the standard PDF document directory.

        Expected structure:

            document_dir/
                evidence/
                    pdf_evidence_chunks.json

        Output:

            document_dir/
                facts/
                    pdf_program_facts.json
        """

        document_dir = Path(document_dir)

        evidence_path = (
            document_dir
            / "evidence"
            / self.DEFAULT_INPUT_FILENAME
        )

        output_dir = document_dir / "facts"

        return self.extract(
            evidence_path=evidence_path,
            output_dir=output_dir,
            program_id=program_id,
            page_id=page_id,
            document_id=document_id,
            university_name=university_name,
            program_name=program_name,
            overwrite=overwrite,
        )

    def save_json(
        self,
        data: dict[str, Any],
        output_path: str | Path,
    ) -> Path:
        """
        Save JSON atomically.
        """

        output_path = Path(output_path)

        output_path.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        temporary_path = output_path.with_suffix(
            output_path.suffix + ".tmp"
        )

        with temporary_path.open(
            "w",
            encoding="utf-8",
        ) as file:
            json.dump(
                data,
                file,
                ensure_ascii=False,
                indent=2,
            )

        temporary_path.replace(output_path)

        return output_path

    # =========================================================================
    # CHUNK EXTRACTION
    # =========================================================================

    def _extract_chunk_with_retry(
        self,
        chunk: dict[str, Any],
        chunk_index: int,
        total_chunks: int,
        metadata: dict[str, Any],
    ) -> ChunkExtractionResult:
        """
        Extract one chunk with retry support.
        """

        chunk_id = str(
            chunk.get("chunk_id")
            or f"chunk_{chunk_index:04d}"
        )

        last_error: Optional[Exception] = None
        last_response_text: Optional[str] = None

        for attempt in range(1, self.max_retries + 1):
            try:
                user_prompt = self._build_chunk_prompt(
                    chunk=chunk,
                    chunk_index=chunk_index,
                    total_chunks=total_chunks,
                    metadata=metadata,
                )

                response = self._call_llm(
                    system_prompt=self.system_prompt,
                    user_prompt=user_prompt,
                )

                usage = self._extract_response_usage(
                    response
                )

                response_text = self._response_to_text(
                    response
                )

                last_response_text = response_text

                parsed_response = self._parse_json_response(
                    response
                )

                facts = parsed_response.get("facts", [])

                if not isinstance(facts, list):
                    raise ValueError(
                        "The LLM response field 'facts' must be a list."
                    )

                return ChunkExtractionResult(
                    chunk_id=chunk_id,
                    status="success",
                    facts=facts,
                    attempts=attempt,
                    response_text=response_text,
                    usage=usage
                )

            except Exception as exc:
                last_error = exc

                self.logger.warning(
                    "PDF fact extraction failed for chunk %s "
                    "on attempt %s/%s: %s",
                    chunk_id,
                    attempt,
                    self.max_retries,
                    exc,
                )

                if attempt < self.max_retries:
                    delay = self.retry_delay * attempt

                    if delay > 0:
                        time.sleep(delay)

        return ChunkExtractionResult(
            chunk_id=chunk_id,
            status="failed",
            facts=[],
            attempts=self.max_retries,
            error=str(last_error),
            response_text=last_response_text,
        )

    def _build_chunk_prompt(
        self,
        chunk: dict[str, Any],
        chunk_index: int,
        total_chunks: int,
        metadata: dict[str, Any],
    ) -> str:
        """
        Build a self-contained extraction request for one chunk.
        """

        chunk_id = (
            chunk.get("chunk_id")
            or f"chunk_{chunk_index:04d}"
        )

        section = chunk.get("section")

        if not isinstance(section, dict):
            section = {}

        section_title = (
            section.get("title")
            or chunk.get("section_title")
            or chunk.get("title")
            or "Unknown section"
        )

        section_type = (
            section.get("type")
            or chunk.get("section_type")
            or "other"
        )

        pages = self._extract_page_numbers(chunk)

        content = (
            chunk.get("content")
            or chunk.get("text")
            or ""
        )

        document_context = {
            "university_name": metadata.get(
                "university_name"
            ),
            "program_name": metadata.get(
                "program_name"
            ),
            "program_id": metadata.get(
                "program_id"
            ),
            "page_id": metadata.get(
                "page_id"
            ),
            "document_id": metadata.get(
                "document_id"
            ),
            "source_filename": metadata.get(
                "source_filename"
            ),
        }

        chunk_statistics = (
            chunk.get("statistics")
            or chunk.get("content_statistics")
            or {}
        )

        if not isinstance(
            chunk_statistics,
            dict,
        ):
            chunk_statistics = {}

        chunk_context = {
            "chunk_number": chunk_index,
            "total_chunks": total_chunks,
            "chunk_id": chunk_id,
            "section_title": section_title,
            "section_type": section_type,
            "pages": pages,
            "heading_path": (
                chunk.get("heading_path")
                or chunk.get("section_path")
                or []
            ),
            "parent_section_title": (
                chunk.get(
                    "parent_section_title"
                )
            ),
            "previous_section_title": (
                chunk.get(
                    "previous_section_title"
                )
            ),
            "next_section_title": (
                chunk.get(
                    "next_section_title"
                )
            ),
            "contains_table": bool(
                chunk_statistics.get(
                    "contains_table",
                    chunk.get(
                        "contains_table",
                        False,
                    ),
                )
            ),
            "table_count": self._safe_int(
                chunk_statistics.get(
                    "table_count",
                    chunk.get(
                        "table_count",
                        0,
                    ),
                ),
                default=0,
            ),
        }

        return (
            "DOCUMENT CONTEXT\n"
            f"{json.dumps(document_context, ensure_ascii=False, indent=2)}\n\n"
            "EVIDENCE CHUNK CONTEXT\n"
            f"{json.dumps(chunk_context, ensure_ascii=False, indent=2)}\n\n"
            "EVIDENCE\n"
            "----- BEGIN PDF EVIDENCE -----\n"
            f"{content.strip()}\n"
            "----- END PDF EVIDENCE -----\n\n"
            "Extract every directly supported university-program fact from "
            "this evidence. Preserve module, course, component, credit, "
            "workload, teaching, assessment, semester, requirement, thesis, "
            "and program relationships. Return valid JSON only."
        )

    # =========================================================================
    # LLM
    # =========================================================================

    @staticmethod
    def _calculate_token_expense(
        *,
        token_count: int,
        price_per_million: Optional[float],
    ) -> Optional[float]:
        """
        Calculate token expense in USD.
        """

        if price_per_million is None:
            return None

        expense = (
            float(token_count)
            / 1_000_000
        ) * float(
            price_per_million
        )

        return round(
            expense,
            12,
        )

    def _empty_usage(
        self,
    ) -> dict[str, Any]:
        """
        Return an empty provider-aware usage record.
        """

        pricing = self._get_provider_pricing()

        input_price = pricing.get(
            "input_price_per_million"
        )

        output_price = pricing.get(
            "output_price_per_million"
        )

        return {
            "provider": pricing["provider"],
            "model": self.model,

            "input_tokens": 0,
            "output_tokens": 0,
            "total_tokens": 0,

            "pricing": {
                "input_usd_per_million_tokens": (
                    input_price
                ),

                "output_usd_per_million_tokens": (
                    output_price
                ),

                "billing_type": (
                    pricing["billing_type"]
                ),

                "currency": "USD",
            },

            "expense": {
                "input_tokens_expense": (
                    0.0
                    if input_price is not None
                    else None
                ),

                "output_tokens_expense": (
                    0.0
                    if output_price is not None
                    else None
                ),

                "total_tokens_expense": (
                    0.0
                    if (
                        input_price is not None
                        and output_price is not None
                    )
                    else None
                ),

                "currency": "USD",
            },
        }
    
    def _aggregate_usage(
        self,
        chunk_results: list[dict[str, Any]],
    ) -> dict[str, Any]:
        """
        Aggregate token usage and provider-specific expenses
        across all completed LLM requests.
        """

        pricing = self._get_provider_pricing()

        input_price = pricing.get(
            "input_price_per_million"
        )

        output_price = pricing.get(
            "output_price_per_million"
        )

        total_input_tokens = 0
        total_output_tokens = 0
        total_tokens = 0

        request_count = 0

        for chunk_result in chunk_results:
            usage = (
                chunk_result.get("usage")
                or {}
            )

            if usage:
                request_count += 1

            total_input_tokens += self._safe_int(
                usage.get("input_tokens"),
                default=0,
            )

            total_output_tokens += self._safe_int(
                usage.get("output_tokens"),
                default=0,
            )

            total_tokens += self._safe_int(
                usage.get("total_tokens"),
                default=0,
            )

        if total_tokens <= 0:
            total_tokens = (
                total_input_tokens
                + total_output_tokens
            )

        input_token_expense = (
            self._calculate_token_expense(
                token_count=total_input_tokens,
                price_per_million=input_price,
            )
        )

        output_token_expense = (
            self._calculate_token_expense(
                token_count=total_output_tokens,
                price_per_million=output_price,
            )
        )

        if (
            input_token_expense is not None
            and output_token_expense is not None
        ):
            total_token_expense = round(
                input_token_expense
                + output_token_expense,
                12,
            )

        else:
            total_token_expense = None

        return {
            "provider": pricing["provider"],
            "model": self.model,

            "requests": request_count,

            "input_tokens": (
                total_input_tokens
            ),

            "output_tokens": (
                total_output_tokens
            ),

            "total_tokens": (
                total_tokens
            ),

            "pricing": {
                "input_usd_per_million_tokens": (
                    input_price
                ),

                "output_usd_per_million_tokens": (
                    output_price
                ),

                "billing_type": (
                    pricing["billing_type"]
                ),

                "currency": "USD",
            },

            "expense": {
                "input_tokens_expense": (
                    input_token_expense
                ),

                "output_tokens_expense": (
                    output_token_expense
                ),

                "total_tokens_expense": (
                    total_token_expense
                ),

                "currency": "USD",
            },
        }
    
    def _call_llm(
        self,
        system_prompt: str,
        user_prompt: str,
    ) -> Any:
        """
        Call either a custom provider function or an OpenAI-compatible client.
        """

        if self.llm_callable is not None:
            return self._call_custom_llm(
                system_prompt=system_prompt,
                user_prompt=user_prompt,
            )

        if self.client is None:
            raise RuntimeError(
                "No LLM provider is configured. Supply one of:\n"
                "- client\n"
                "- api_key\n"
                "- OPENAI_API_KEY\n"
                "- NVIDIA_API_KEY\n"
                "- llm_callable"
            )

        request_kwargs: dict[str, Any] = {
            "model": self.model,
            "messages": [
                {
                    "role": "system",
                    "content": system_prompt,
                },
                {
                    "role": "user",
                    "content": user_prompt,
                },
            ],
            "temperature": self.temperature,
            "max_tokens": self.max_tokens,
        }

        try:
            return self.client.chat.completions.create(
                **request_kwargs,
                response_format={
                    "type": "json_object",
                },
            )

        except Exception as structured_error:
            self.logger.debug(
                "Structured JSON response mode was unavailable. "
                "Retrying without response_format. Error: %s",
                structured_error,
            )

            return self.client.chat.completions.create(
                **request_kwargs
            )

    def _call_custom_llm(
        self,
        system_prompt: str,
        user_prompt: str,
    ) -> Any:
        """
        Call a custom LLM provider while supporting simple and keyword APIs.
        """

        try:
            return self.llm_callable(
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                model=self.model,
                temperature=self.temperature,
                max_tokens=self.max_tokens,
            )

        except TypeError:
            return self.llm_callable(
                system_prompt,
                user_prompt,
            )
        
    def _extract_response_usage(
        self,
        response: Any,
    ) -> dict[str, Any]:
        """
        Extract token usage and calculate provider-specific expense.

        Supports OpenAI-compatible responses from:

        - OpenAI
        - Groq
        - NVIDIA NIM

        OpenAI-compatible APIs commonly expose:

            prompt_tokens
            completion_tokens
            total_tokens

        Some APIs may instead expose:

            input_tokens
            output_tokens
            total_tokens
        """

        usage_object = None

        if isinstance(
            response,
            dict,
        ):
            usage_object = response.get(
                "usage"
            )

        else:
            usage_object = getattr(
                response,
                "usage",
                None,
            )

        input_tokens = 0
        output_tokens = 0
        total_tokens = 0

        if usage_object is not None:
            input_tokens = self._read_usage_integer(
                usage_object,
                "prompt_tokens",
                "input_tokens",
            )

            output_tokens = self._read_usage_integer(
                usage_object,
                "completion_tokens",
                "output_tokens",
            )

            total_tokens = self._read_usage_integer(
                usage_object,
                "total_tokens",
            )

        if total_tokens <= 0:
            total_tokens = (
                input_tokens
                + output_tokens
            )

        pricing = self._get_provider_pricing()

        input_price = pricing.get(
            "input_price_per_million"
        )

        output_price = pricing.get(
            "output_price_per_million"
        )

        input_token_expense = (
            self._calculate_token_expense(
                token_count=input_tokens,
                price_per_million=input_price,
            )
        )

        output_token_expense = (
            self._calculate_token_expense(
                token_count=output_tokens,
                price_per_million=output_price,
            )
        )

        if (
            input_token_expense is not None
            and output_token_expense is not None
        ):
            total_token_expense = round(
                input_token_expense
                + output_token_expense,
                12,
            )

        else:
            total_token_expense = None

        return {
            "provider": pricing["provider"],
            "model": self.model,

            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "total_tokens": total_tokens,

            "pricing": {
                "input_usd_per_million_tokens": (
                    input_price
                ),

                "output_usd_per_million_tokens": (
                    output_price
                ),

                "billing_type": (
                    pricing["billing_type"]
                ),

                "currency": "USD",
            },

            "expense": {
                "input_tokens_expense": (
                    input_token_expense
                ),

                "output_tokens_expense": (
                    output_token_expense
                ),

                "total_tokens_expense": (
                    total_token_expense
                ),

                "currency": "USD",
            },
        }

    @staticmethod
    def _read_usage_integer(
        usage_object: Any,
        *field_names: str,
    ) -> int:
        """
        Read a token count from dictionary-style or
        object-style OpenAI-compatible usage metadata.

        Supported examples:

            response.usage.prompt_tokens
            response.usage.completion_tokens
            response.usage.total_tokens

        and:

            {
                "prompt_tokens": 100,
                "completion_tokens": 200,
                "total_tokens": 300
            }
        """

        for field_name in field_names:
            value = None

            if isinstance(
                usage_object,
                dict,
            ):
                value = usage_object.get(
                    field_name
                )

            else:
                value = getattr(
                    usage_object,
                    field_name,
                    None,
                )

            if value is None:
                continue

            try:
                return max(
                    0,
                    int(value),
                )

            except (
                TypeError,
                ValueError,
            ):
                continue

        return 0
    # =========================================================================
    # RESPONSE PARSING
    # =========================================================================

    def _response_to_text(
        self,
        response: Any,
    ) -> str:
        """
        Convert common LLM response types to text.
        """

        if response is None:
            return ""

        if isinstance(response, str):
            return response

        if isinstance(response, dict):
            return json.dumps(
                response,
                ensure_ascii=False,
            )

        choices = getattr(
            response,
            "choices",
            None,
        )

        if choices:
            first_choice = choices[0]

            message = getattr(
                first_choice,
                "message",
                None,
            )

            if message is not None:
                content = getattr(
                    message,
                    "content",
                    None,
                )

                if content is not None:
                    return self._flatten_message_content(
                        content
                    )

            text = getattr(
                first_choice,
                "text",
                None,
            )

            if text is not None:
                return str(text)

        output_text = getattr(
            response,
            "output_text",
            None,
        )

        if output_text is not None:
            return str(output_text)

        content = getattr(
            response,
            "content",
            None,
        )

        if content is not None:
            return self._flatten_message_content(
                content
            )

        return str(response)

    @staticmethod
    def _flatten_message_content(
        content: Any,
    ) -> str:
        """
        Flatten string or multi-part message content.
        """

        if isinstance(content, str):
            return content

        if isinstance(content, list):
            parts: list[str] = []

            for item in content:
                if isinstance(item, str):
                    parts.append(item)

                elif isinstance(item, dict):
                    text = (
                        item.get("text")
                        or item.get("content")
                    )

                    if text is not None:
                        parts.append(str(text))

                else:
                    text = getattr(
                        item,
                        "text",
                        None,
                    )

                    if text is not None:
                        parts.append(str(text))

            return "\n".join(parts)

        return str(content)

    def _parse_json_response(
        self,
        response: Any,
    ) -> dict[str, Any]:
        """
        Parse a JSON object from an LLM response.
        """

        if isinstance(response, dict):
            parsed = deepcopy(response)

        else:
            response_text = self._response_to_text(
                response
            )

            cleaned_text = self._strip_code_fence(
                response_text
            )

            try:
                parsed = json.loads(cleaned_text)

            except json.JSONDecodeError:
                json_object = self._find_first_json_object(
                    cleaned_text
                )

                if json_object is None:
                    raise ValueError(
                        "The LLM response did not contain a valid "
                        "JSON object."
                    )

                parsed = json.loads(json_object)

        if isinstance(parsed, list):
            parsed = {
                "facts": parsed,
            }

        if not isinstance(parsed, dict):
            raise ValueError(
                "The parsed LLM response must be a JSON object."
            )

        if "facts" not in parsed:
            parsed["facts"] = []

        return parsed

    @staticmethod
    def _strip_code_fence(
        text: str,
    ) -> str:
        """
        Remove a surrounding Markdown code fence.
        """

        text = text.strip()

        pattern = re.compile(
            r"^```(?:json)?\s*(.*?)\s*```$",
            flags=re.IGNORECASE | re.DOTALL,
        )

        match = pattern.match(text)

        if match:
            return match.group(1).strip()

        return text

    @staticmethod
    def _find_first_json_object(
        text: str,
    ) -> Optional[str]:
        """
        Find the first balanced JSON object in arbitrary text.
        """

        start_index = text.find("{")

        if start_index < 0:
            return None

        depth = 0
        in_string = False
        escaped = False

        for index in range(
            start_index,
            len(text),
        ):
            character = text[index]

            if in_string:
                if escaped:
                    escaped = False

                elif character == "\\":
                    escaped = True

                elif character == '"':
                    in_string = False

                continue

            if character == '"':
                in_string = True

            elif character == "{":
                depth += 1

            elif character == "}":
                depth -= 1

                if depth == 0:
                    return text[
                        start_index:index + 1
                    ]

        return None

    # =========================================================================
    # FACT PREPARATION
    # =========================================================================

    def _prepare_fact(
        self,
        raw_fact: Any,
        chunk: dict[str, Any],
        metadata: dict[str, Any],
        fact_index: int,
    ) -> Optional[dict[str, Any]]:
        """
        Validate and enrich one extracted fact.
        """

        if not isinstance(raw_fact, dict):
            return None

        category = self._normalize_category(
            raw_fact.get("category")
        )

        field = self._normalize_field_name(
            raw_fact.get("field")
        )

        value = raw_fact.get("value")

        original_value = raw_fact.get(
            "original_value"
        )

        if self._is_empty_value(value):
            if not self._is_empty_value(
                original_value
            ):
                value = deepcopy(original_value)

        if self._is_empty_value(value):
            return None

        if self._is_empty_value(
            original_value
        ):
            original_value = deepcopy(value)

        unit = self._clean_optional_string(
            raw_fact.get("unit")
        )

        entity = self._normalize_entity(
            raw_fact.get("entity"),
            default_type=self._default_entity_type(
                category
            ),
        )

        parent_entity = self._normalize_entity(
            raw_fact.get("parent_entity"),
            default_type=None,
            allow_none=True,
        )

        qualifiers = self._normalize_qualifiers(
            raw_fact.get("qualifiers")
        )

        confidence = self._normalize_confidence(
            raw_fact.get("confidence")
        )

        source = self._build_fact_source(
            chunk=chunk,
            metadata=metadata,
        )

        evidence_text = self._build_evidence_text(
            raw_fact=raw_fact,
            chunk=chunk,
        )

        fact = {
            "fact_id": None,
            "category": category,
            "field": field,
            "value": self._clean_json_value(
                value
            ),
            "original_value": self._clean_json_value(
                original_value
            ),
            "unit": unit,
            "entity": entity,
            "parent_entity": parent_entity,
            "qualifiers": qualifiers,
            "confidence": confidence,
            "source": source,
            "evidence": {
                "text": evidence_text,
                "chunk_id": source["chunk_id"],
                "section_title": source[
                    "section_title"
                ],
                "section_type": source[
                    "section_type"
                ],
                "pages": source["pages"],
                "content_sha256": source[
                    "content_sha256"
                ],
            },
            "extraction": {
                "extractor": self.__class__.__name__,
                "model": self.model,
                "fact_index_in_chunk": fact_index,
            },
        }

        fact = self._normalize_prepared_fact(
            fact
        )

        if fact is None:
            return None

        return fact
    
    def _normalize_prepared_fact(
        self,
        fact: dict[str, Any],
    ) -> Optional[dict[str, Any]]:
        """
        Apply deterministic corrections after LLM extraction.

        The LLM remains responsible for broad multilingual translation and
        high-recall extraction. This method only applies conservative,
        high-confidence corrections that prevent schema fragmentation and
        obvious semantic misclassification.
        """

        normalized = deepcopy(
            fact
        )

        normalized["field"] = (
            self._canonicalize_field_for_entity(
                field=normalized.get("field"),
                entity=normalized.get("entity"),
            )
        )

        normalized["value"] = (
            self._normalize_translated_value(
                value=normalized.get("value"),
                original_value=normalized.get(
                    "original_value"
                ),
            )
        )

        normalized = (
            self._normalize_dynamic_field(
                normalized
            )
        )

        normalized = (
            self._correct_assessment_semantics(
                normalized
            )
        )

        normalized = (
            self._correct_identity_field(
                normalized
            )
        )

        normalized = (
            self._synchronize_entity_identity(
                normalized
            )
        )

        return normalized

    def _canonicalize_field_for_entity(
        self,
        field: Any,
        entity: Any,
    ) -> str:
        """
        Resolve generic credit fields according to entity type.
        """

        normalized_field = (
            self._normalize_field_name(
                field
            )
        )

        entity_type = ""

        if isinstance(
            entity,
            dict,
        ):
            entity_type = str(
                entity.get("type")
                or ""
            ).casefold()

        if normalized_field == "credits":
            credit_field_by_entity = {
                "program": "total_credits",
                "programme": "total_credits",
                "module": "module_credits",
                "course": "course_credits",
                "module_component": (
                    "component_credits"
                ),
                "component": "component_credits",
            }

            return credit_field_by_entity.get(
                entity_type,
                "credits",
            )

        return normalized_field

    def _normalize_translated_value(
        self,
        value: Any,
        original_value: Any,
    ) -> Any:
        """
        Apply deterministic translations for common scalar values.

        Complex translation remains the LLM's responsibility.
        """

        if isinstance(
            value,
            list,
        ):
            return [
                self._normalize_translated_value(
                    item,
                    item,
                )
                for item in value
            ]

        if not isinstance(
            value,
            str,
        ):
            return value

        cleaned_value = value.strip()

        original_text = (
            original_value.strip()
            if isinstance(
                original_value,
                str,
            )
            else ""
        )

        candidates = [
            cleaned_value,
            original_text,
        ]

        for candidate in candidates:
            lookup_key = (
                self._normalize_translation_key(
                    candidate
                )
            )

            translated = (
                self.DETERMINISTIC_VALUE_TRANSLATIONS.get(
                    lookup_key
                )
            )

            if translated:
                return translated

        return cleaned_value

    @staticmethod
    def _normalize_translation_key(
        value: str,
    ) -> str:
        """
        Normalize a scalar value for deterministic translation lookup.
        """

        normalized = value.casefold().strip()

        normalized = re.sub(
            r"\s+",
            " ",
            normalized,
        )

        normalized = normalized.strip(
            " .,:;()[]{}"
        )

        return normalized

    def _correct_assessment_semantics(
        self,
        fact: dict[str, Any],
    ) -> dict[str, Any]:
        """
        Separate grading status from assessment method.
        """

        field = str(
            fact.get("field")
            or ""
        )

        value = fact.get(
            "value"
        )

        original_value = fact.get(
            "original_value"
        )

        candidate_values = [
            value,
            original_value,
        ]

        normalized_candidates = {
            self._normalize_translation_key(
                candidate
            )
            for candidate in candidate_values
            if isinstance(
                candidate,
                str,
            )
        }

        if (
            field
            in {
                "assessment",
                "assessment_type",
                "examination",
            }
            and normalized_candidates
            & self.GRADING_STATUS_VALUES
        ):
            fact["field"] = (
                "grading_status"
            )

            fact["category"] = (
                "assessment"
            )

            fact["value"] = (
                self._normalize_translated_value(
                    value=value,
                    original_value=original_value,
                )
            )

        return fact

    def _correct_identity_field(
        self,
        fact: dict[str, Any],
    ) -> dict[str, Any]:
        """
        Correct obvious cases where an entity code was emitted as a name.
        """

        field = str(
            fact.get("field")
            or ""
        )

        value = fact.get(
            "value"
        )

        if not isinstance(
            value,
            str,
        ):
            return fact

        cleaned_value = value.strip()

        if not self._looks_like_entity_code(
            cleaned_value
        ):
            return fact

        if field == "module_name":
            fact["field"] = "module_code"

        elif field == "course_name":
            fact["field"] = "course_code"

        return fact

    def _synchronize_entity_identity(
        self,
        fact: dict[str, Any],
    ) -> dict[str, Any]:
        """
        Copy explicit code/name facts into the entity object when missing.
        """

        entity = fact.get(
            "entity"
        )

        if not isinstance(
            entity,
            dict,
        ):
            return fact

        field = fact.get(
            "field"
        )

        value = fact.get(
            "value"
        )

        if not isinstance(
            value,
            str,
        ):
            return fact

        cleaned_value = value.strip()

        if not cleaned_value:
            return fact

        if field in {
            "module_code",
            "course_code",
        }:
            if not entity.get(
                "id"
            ):
                entity["id"] = (
                    cleaned_value
                )

        elif field in {
            "module_name",
            "course_name",
        }:
            if not entity.get(
                "name"
            ):
                entity["name"] = (
                    cleaned_value
                )

        fact["entity"] = entity

        return fact

    def _looks_like_entity_code(
        self,
        value: str,
    ) -> bool:
        """
        Detect short structured identifiers such as P 5, WP 1, or P 5.1.
        """

        cleaned = value.strip()

        if not cleaned:
            return False

        if len(
            cleaned
        ) > 30:
            return False

        if len(
            cleaned.split()
        ) > 4:
            return False

        return bool(
            self.ENTITY_CODE_PATTERN.fullmatch(
                cleaned
            )
        )
    
    def _normalize_dynamic_field(
        self,
        fact: dict[str, Any],
    ) -> dict[str, Any]:
        """
        Convert common dynamic curriculum field names into stable fields.

        This is intentionally conservative. Unknown fields are preserved
        instead of being guessed.
        """

        field = str(
            fact.get("field")
            or ""
        )

        entity = fact.get(
            "entity"
        )

        qualifiers = fact.get(
            "qualifiers"
        )

        if not isinstance(
            entity,
            dict,
        ):
            entity = {
                "type": None,
                "id": None,
                "name": None,
            }

        if not isinstance(
            qualifiers,
            dict,
        ):
            qualifiers = {}

        semester_match = re.search(
            r"(?:semester|sem)_?(\d+)",
            field,
            flags=re.IGNORECASE,
        )

        if semester_match and not qualifiers.get(
            "semester"
        ):
            qualifiers["semester"] = int(
                semester_match.group(1)
            )

        code_match = re.search(
            r"\b((?:wp|p|m|mod|module|course)"
            r"_?\d+(?:_\d+)*)\b",
            field,
            flags=re.IGNORECASE,
        )

        extracted_code = None

        if code_match:
            extracted_code = (
                code_match.group(1)
                .replace("_", ".")
                .upper()
            )

            extracted_code = re.sub(
                r"^(WP|P|M|MOD|MODULE|COURSE)\.",
                r"\1 ",
                extracted_code,
            )

        entity_type = str(
            entity.get("type")
            or ""
        ).casefold()

        if field.endswith(
            (
                "_title",
                "_name",
            )
        ):
            # Preserve already valid canonical identity fields.
            if field in {
                "program_name",
                "module_name",
                "course_name",
            }:
                pass

            elif entity_type in {
                "program",
                "programme",
            }:
                fact["field"] = "program_name"

            elif entity_type == "course":
                fact["field"] = "course_name"

            elif entity_type in {
                "module",
                "module_component",
                "component",
            }:
                fact["field"] = "module_name"

            elif (
                "course" in field
                or (
                    extracted_code
                    and "." in extracted_code
                )
            ):
                fact["field"] = "course_name"

                if not entity.get("type"):
                    entity["type"] = "course"

            else:
                # Unknown descriptive fields are preserved.
                # Do not automatically convert every *_name or
                # *_title field into module_name.
                fact["field"] = field

        elif field.endswith(
            (
                "_ects",
                "_credits",
                "_credit",
            )
        ):
            # Preserve valid canonical credit fields.
            if field in {
                "total_credits",
                "module_credits",
                "course_credits",
                "component_credits",
            }:
                pass

            elif entity_type in {
                "program",
                "programme",
            }:
                fact["field"] = "total_credits"

            elif entity_type == "course":
                fact["field"] = "course_credits"

            elif entity_type in {
                "module_component",
                "component",
            }:
                fact["field"] = "component_credits"

            elif entity_type == "module":
                fact["field"] = "module_credits"

            elif (
                "course" in field
                or (
                    extracted_code
                    and "." in extracted_code
                )
            ):
                fact["field"] = "course_credits"

            else:
                fact["field"] = field

        elif field.endswith(
            (
                "_format",
                "_teaching_form",
                "_teaching_format",
            )
        ):
            fact["field"] = (
                "teaching_format"
            )

        if (
            extracted_code
            and not entity.get("id")
        ):
            entity["id"] = (
                extracted_code
            )

        fact["entity"] = entity
        fact["qualifiers"] = qualifiers

        return fact

    def _build_fact_source(
        self,
        chunk: dict[str, Any],
        metadata: dict[str, Any],
    ) -> dict[str, Any]:
        """
        Build complete PDF provenance for one fact.
        """

        section = chunk.get("section")

        if not isinstance(section, dict):
            section = {}

        chunk_statistics = (
            chunk.get("statistics")
            or chunk.get("content_statistics")
            or {}
        )

        if not isinstance(
            chunk_statistics,
            dict,
        ):
            chunk_statistics = {}

        chunk_content = str(
            chunk.get("content")
            or chunk.get("text")
            or ""
        )

        content_hash = (
            chunk.get("content_sha256")
            or chunk.get("sha256")
            or hashlib.sha256(
                chunk_content.encode("utf-8")
            ).hexdigest()
        )

        return {
            "source_type": "pdf",
            "provider": metadata.get(
                "provider"
            ),
            "program_id": metadata.get(
                "program_id"
            ),
            "page_id": metadata.get(
                "page_id"
            ),
            "document_id": metadata.get(
                "document_id"
            ),
            "source_filename": metadata.get(
                "source_filename"
            ),
            "source_pdf": metadata.get(
                "source_pdf"
            ),
            "document_data": metadata.get(
                "document_data"
            ),
            "chunk_id": (
                chunk.get("chunk_id")
                or chunk.get("id")
            ),
            "section_title": (
                section.get("title")
                or chunk.get("section_title")
                or chunk.get("title")
            ),
            "section_type": (
                section.get("type")
                or chunk.get("section_type")
                or "other"
            ),
            "pages": self._extract_page_numbers(
                chunk
            ),
            "contains_table": bool(
                chunk_statistics.get(
                    "contains_table",
                    chunk.get(
                        "contains_table",
                        False,
                    ),
                )
            ),
            "table_count": self._safe_int(
                chunk_statistics.get(
                    "table_count",
                    chunk.get(
                        "table_count",
                        0,
                    ),
                ),
                default=0,
            ),
            "content_sha256": str(
                content_hash
            ),
        }

    @staticmethod
    def _build_evidence_text(
        raw_fact: dict[str, Any],
        chunk: dict[str, Any],
    ) -> str:
        """
        Use model-supplied evidence when available; otherwise preserve the
        complete source chunk so no traceability is lost.
        """

        candidate = (
            raw_fact.get("evidence_text")
            or raw_fact.get("evidence")
        )

        if isinstance(candidate, dict):
            candidate = (
                candidate.get("text")
                or candidate.get("quote")
            )

        if isinstance(candidate, str):
            candidate = candidate.strip()

            if candidate:
                return candidate

        return str(
            chunk.get("content")
            or chunk.get("text")
            or ""
        ).strip()

    # =========================================================================
    # NORMALIZATION
    # =========================================================================

    def _normalize_category(
        self,
        category: Any,
    ) -> str:
        """
        Normalize categories without losing unknown valid information.
        """

        normalized = self._normalize_field_name(
            category
        )

        if normalized in self.ALLOWED_CATEGORIES:
            return normalized

        return "other"

    def _normalize_field_name(
        self,
        value: Any,
    ) -> str:
        """
        Normalize an extracted field to stable snake_case and apply
        conservative canonical aliases.

        Dynamic information such as semester numbers and entity codes should
        remain in entity metadata or qualifiers rather than field names.
        """

        cleaned = self._clean_optional_string(
            value
        )

        if not cleaned:
            return "other"

        normalized = cleaned.casefold()

        normalized = re.sub(
            r"[^a-z0-9]+",
            "_",
            normalized,
        )

        normalized = re.sub(
            r"_+",
            "_",
            normalized,
        ).strip("_")

        if not normalized:
            return "other"

        canonical = self.CANONICAL_FIELD_ALIASES.get(
            normalized,
            normalized,
        )

        return canonical

    def _normalize_entity(
        self,
        entity: Any,
        default_type: Optional[str],
        allow_none: bool = False,
    ) -> Optional[dict[str, Any]]:
        """
        Normalize an entity reference.
        """

        if entity is None:
            if allow_none:
                return None

            return {
                "type": default_type or "program",
                "id": None,
                "name": None,
            }

        if isinstance(entity, str):
            cleaned_name = entity.strip()

            return {
                "type": default_type or "other",
                "id": None,
                "name": cleaned_name or None,
            }

        if not isinstance(entity, dict):
            if allow_none:
                return None

            return {
                "type": default_type or "program",
                "id": None,
                "name": None,
            }

        entity_type = self._normalize_field_name(
            entity.get("type")
            or default_type
            or "other"
        )

        entity_id = self._clean_optional_string(
            entity.get("id")
            or entity.get("code")
        )

        entity_name = self._clean_optional_string(
            entity.get("name")
            or entity.get("title")
        )

        if (
            allow_none
            and entity_id is None
            and entity_name is None
            and entity.get("type") is None
        ):
            return None

        return {
            "type": entity_type,
            "id": entity_id,
            "name": entity_name,
        }

    def _normalize_qualifiers(
        self,
        qualifiers: Any,
    ) -> dict[str, Any]:
        """
        Preserve standard and provider-specific qualifiers.
        """

        normalized: dict[str, Any] = {
            "status": None,
            "requirement_type": None,
            "semester": None,
            "term": None,
            "academic_year": None,
        }

        if isinstance(qualifiers, dict):
            for key, value in qualifiers.items():
                normalized_key = self._normalize_field_name(
                    key
                )

                normalized[normalized_key] = (
                    self._clean_json_value(value)
                )

        return normalized

    @staticmethod
    def _normalize_confidence(
        confidence: Any,
    ) -> float:
        """
        Normalize confidence to the inclusive range 0.0-1.0.
        """

        try:
            value = float(confidence)

        except (TypeError, ValueError):
            value = 0.95

        return round(
            min(1.0, max(0.0, value)),
            4,
        )

    @staticmethod
    def _default_entity_type(
        category: str,
    ) -> str:
        """
        Select a conservative entity type from the fact category.
        """

        mapping = {
            "module": "module",
            "course": "course",
            "module_component": "module_component",
            "thesis": "program",
            "dissertation": "program",
            "project": "program",
            "identity": "program",
            "overview": "program",
            "qualification": "program",
            "curriculum": "program",
            "credits": "program",
            "duration": "program",
            "study_mode": "program",
            "admission": "program",
            "fees": "program",
        }

        return mapping.get(
            category,
            "program",
        )

    def _clean_json_value(
        self,
        value: Any,
    ) -> Any:
        """
        Recursively clean JSON-compatible values.
        """

        if isinstance(value, str):
            return self._clean_text(value)

        if isinstance(value, list):
            return [
                self._clean_json_value(item)
                for item in value
            ]

        if isinstance(value, tuple):
            return [
                self._clean_json_value(item)
                for item in value
            ]

        if isinstance(value, dict):
            return {
                str(key): self._clean_json_value(
                    item
                )
                for key, item in value.items()
            }

        return value

    @staticmethod
    def _clean_text(
        value: str,
    ) -> str:
        """
        Normalize unnecessary whitespace without altering meaning.
        """

        value = value.replace(
            "\u00a0",
            " ",
        )

        value = re.sub(
            r"[ \t]+",
            " ",
            value,
        )

        value = re.sub(
            r"\n{3,}",
            "\n\n",
            value,
        )

        return value.strip()

    @staticmethod
    def _clean_optional_string(
        value: Any,
    ) -> Optional[str]:
        """
        Normalize an optional string.
        """

        if value is None:
            return None

        value = str(value).strip()

        return value or None

    @staticmethod
    def _is_empty_value(
        value: Any,
    ) -> bool:
        """
        Determine whether a value contains no useful information.
        """

        if value is None:
            return True

        if isinstance(value, str):
            return not value.strip()

        if isinstance(value, (list, tuple, dict)):
            return len(value) == 0

        return False

    # =========================================================================
    # DEDUPLICATION
    # =========================================================================

    def _remove_exact_duplicates(
        self,
        facts: Iterable[dict[str, Any]],
    ) -> tuple[list[dict[str, Any]], int]:
        """
        Remove exact semantic duplicates.

        Source metadata is intentionally excluded from the duplicate key so
        the same fact repeated in overlapping evidence chunks is not written
        multiple times.

        This is conservative. Facts attached to different entities remain
        separate.
        """

        unique_facts: list[dict[str, Any]] = []
        seen: set[str] = set()
        duplicate_count = 0

        for fact in facts:
            duplicate_payload = {
                "category": fact.get("category"),
                "field": fact.get("field"),
                "value": fact.get("value"),
                "original_value": fact.get(
                    "original_value"
                ),
                "unit": fact.get("unit"),
                "entity": fact.get("entity"),
                "parent_entity": fact.get(
                    "parent_entity"
                ),
                "qualifiers": fact.get(
                    "qualifiers"
                ),
            }

            duplicate_key = self._stable_json_hash(
                duplicate_payload
            )

            if duplicate_key in seen:
                duplicate_count += 1
                continue

            seen.add(duplicate_key)
            unique_facts.append(fact)

        return unique_facts, duplicate_count

    def _assign_fact_ids(
        self,
        facts: list[dict[str, Any]],
        document_id: str,
    ) -> list[dict[str, Any]]:
        """
        Assign deterministic fact IDs.
        """

        safe_document_id = self._safe_identifier(
            document_id
        )

        for index, fact in enumerate(
            facts,
            start=1,
        ):
            semantic_hash = self._stable_json_hash(
                {
                    "category": fact.get(
                        "category"
                    ),
                    "field": fact.get("field"),
                    "value": fact.get("value"),
                    "entity": fact.get("entity"),
                    "parent_entity": fact.get(
                        "parent_entity"
                    ),
                    "source": {
                        "chunk_id": (
                            fact.get("source", {})
                            .get("chunk_id")
                        ),
                        "pages": (
                            fact.get("source", {})
                            .get("pages")
                        ),
                    },
                }
            )[:12]

            fact["fact_id"] = (
                f"pdf_{safe_document_id}_"
                f"{index:04d}_{semantic_hash}"
            )

        return facts

    # =========================================================================
    # RESULT BUILDING
    # =========================================================================

    def _build_result(
        self,
        metadata: dict[str, Any],
        evidence_data: dict[str, Any],
        evidence_path: Optional[Path],
        output_path: Path,
        facts: list[dict[str, Any]],
        chunk_results: list[dict[str, Any]],
        failed_chunks: list[dict[str, Any]],
        facts_before_deduplication: int,
        exact_duplicates_removed: int,
    ) -> dict[str, Any]:
        """
        Build the final extraction result.
        """

        category_counts = self._count_values(
            fact.get("category", "other")
            for fact in facts
        )

        field_counts = self._count_values(
            fact.get(
                "field",
                "unspecified_fact",
            )
            for fact in facts
        )

        entity_type_counts = self._count_values(
            (
                fact.get("entity") or {}
            ).get("type", "unknown")
            for fact in facts
        )

        chunks = evidence_data.get(
            "chunks",
            [],
        )

        successful_chunks = sum(
            1
            for item in chunk_results
            if item.get("status") == "success"
        )

        chunks_with_facts = sum(
            1
            for item in chunk_results
            if item.get("facts_extracted", 0) > 0
        )

        total_pages = sorted(
            {
                page
                for fact in facts
                for page in (
                    fact.get("source", {})
                    .get("pages", [])
                )
                if isinstance(page, int)
            }
        )

        result = {
            "schema_version": "1.0",
            "source": {
                "type": "pdf",
                "provider": metadata.get(
                    "provider"
                ),
                "program_id": metadata.get(
                    "program_id"
                ),
                "page_id": metadata.get(
                    "page_id"
                ),
                "document_id": metadata.get(
                    "document_id"
                ),
                "source_filename": metadata.get(
                    "source_filename"
                ),
                "source_pdf": metadata.get(
                    "source_pdf"
                ),
                "document_data": metadata.get(
                    "document_data"
                ),
                "evidence_file": (
                    str(evidence_path)
                    if evidence_path
                    else None
                ),
            },
            "identity": {
                "university_name": metadata.get(
                    "university_name"
                ),
                "program_name": metadata.get(
                    "program_name"
                ),
            },
            "extraction": {
                "extractor": self.__class__.__name__,
                "model": self.model,
                "temperature": self.temperature,
                "max_tokens": self.max_tokens,
                "generated_at": self._utc_now(),
                "output_file": str(output_path),
            },
            "summary": {
                "evidence_chunks_available": len(
                    chunks
                ),
                "evidence_chunks_processed": len(
                    chunk_results
                ),
                "successful_chunks": successful_chunks,
                "failed_chunks": len(
                    failed_chunks
                ),
                "chunks_with_facts": chunks_with_facts,
                "facts_before_deduplication": (
                    facts_before_deduplication
                ),
                "exact_duplicates_removed": (
                    exact_duplicates_removed
                ),
                "facts_written": len(facts),
                "unique_pages_referenced": len(
                    total_pages
                ),
                "page_numbers": total_pages,
                "usage": self._aggregate_usage(
                    chunk_results
                ),
            },
            "distribution": {
                "by_category": category_counts,
                "by_field": field_counts,
                "by_entity_type": (
                    entity_type_counts
                ),
            },
            "facts": facts,
            "chunk_results": chunk_results,
            "failed_chunks": failed_chunks,
            "quality": {
                "all_facts_have_ids": all(
                    bool(fact.get("fact_id"))
                    for fact in facts
                ),
                "all_facts_have_values": all(
                    not self._is_empty_value(
                        fact.get("value")
                    )
                    for fact in facts
                ),
                "all_facts_have_sources": all(
                    isinstance(
                        fact.get("source"),
                        dict,
                    )
                    for fact in facts
                ),
                "all_facts_have_chunk_ids": all(
                    bool(
                        fact.get(
                            "source",
                            {},
                        ).get("chunk_id")
                    )
                    for fact in facts
                ),
                "all_facts_have_content_hashes": all(
                    bool(
                        fact.get(
                            "source",
                            {},
                        ).get(
                            "content_sha256"
                        )
                    )
                    for fact in facts
                ),
                "page_traceability_available": (
                    any(
                        bool(
                            fact.get(
                                "source",
                                {},
                            ).get("pages")
                        )
                        for fact in facts
                    )
                ),
                "partial_extraction": bool(
                    failed_chunks
                ),
            },
        }

        return result

    # =========================================================================
    # EVIDENCE METADATA
    # =========================================================================

    def _extract_document_metadata(
        self,
        evidence_data: dict[str, Any],
        program_id: Optional[str],
        page_id: Optional[str],
        document_id: Optional[str],
        university_name: Optional[str],
        program_name: Optional[str],
    ) -> dict[str, Any]:
        """
        Resolve metadata across the evidence builder's possible structures.
        """

        source = self._first_dict(
            evidence_data.get("source"),
            evidence_data.get(
                "document_source"
            ),
        )

        identity = self._first_dict(
            evidence_data.get("identity"),
            evidence_data.get(
                "document_identity"
            ),
        )

        metadata = self._first_dict(
            evidence_data.get("metadata"),
            evidence_data.get(
                "document_metadata"
            ),
        )

        resolved_program_id = (
            program_id
            or source.get("program_id")
            or identity.get("program_id")
            or metadata.get("program_id")
            or "unknown"
        )

        resolved_page_id = (
            page_id
            or source.get("page_id")
            or identity.get("page_id")
            or metadata.get("page_id")
            or "unknown"
        )

        resolved_document_id = (
            document_id
            or source.get("document_id")
            or identity.get("document_id")
            or metadata.get("document_id")
            or "document"
        )

        resolved_university_name = (
            university_name
            or identity.get("university_name")
            or identity.get("university")
            or metadata.get("university_name")
            or metadata.get("university")
        )

        resolved_program_name = (
            program_name
            or identity.get("program_name")
            or identity.get("program")
            or metadata.get("program_name")
            or metadata.get("program")
        )

        source_filename = (
            source.get("source_filename")
            or source.get("filename")
            or metadata.get("source_filename")
            or metadata.get("filename")
        )

        source_pdf = (
            source.get("source_pdf")
            or source.get("pdf_path")
            or metadata.get("source_pdf")
            or metadata.get("pdf_path")
        )

        document_data = (
            source.get("document_data")
            or source.get(
                "document_data_path"
            )
            or metadata.get("document_data")
            or metadata.get(
                "document_data_path"
            )
        )

        provider = (
            source.get("provider")
            or metadata.get("provider")
            or "Azure AI Document Intelligence"
        )

        return {
            "program_id": str(
                resolved_program_id
            ),
            "page_id": str(
                resolved_page_id
            ),
            "document_id": str(
                resolved_document_id
            ),
            "university_name": (
                self._clean_optional_string(
                    resolved_university_name
                )
            ),
            "program_name": (
                self._clean_optional_string(
                    resolved_program_name
                )
            ),
            "source_filename": (
                self._clean_optional_string(
                    source_filename
                )
            ),
            "source_pdf": (
                self._clean_optional_string(
                    source_pdf
                )
            ),
            "document_data": (
                self._clean_optional_string(
                    document_data
                )
            ),
            "provider": str(provider),
        }

    @staticmethod
    def _first_dict(
        *values: Any,
    ) -> dict[str, Any]:
        """
        Return the first dictionary supplied.
        """

        for value in values:
            if isinstance(value, dict):
                return value

        return {}

    # =========================================================================
    # PAGE HANDLING
    # =========================================================================

    def _extract_page_numbers(
        self,
        chunk: dict[str, Any],
    ) -> list[int]:
        """
        Extract page numbers from both the current nested evidence schema
        and older flat chunk schemas.
        """

        location = chunk.get("location")

        if not isinstance(location, dict):
            location = {}

        page_candidates = (
            location.get("page_numbers")
            or chunk.get("page_numbers")
            or chunk.get("pages")
            or []
        )

        if isinstance(page_candidates, dict):
            start_page = (
                page_candidates.get("start")
                or page_candidates.get("start_page")
            )

            end_page = (
                page_candidates.get("end")
                or page_candidates.get("end_page")
                or start_page
            )

            if start_page is not None:
                try:
                    start_page = int(start_page)
                    end_page = int(end_page)

                    return list(
                        range(
                            start_page,
                            end_page + 1,
                        )
                    )

                except (
                    TypeError,
                    ValueError,
                ):
                    return []

        if not isinstance(
            page_candidates,
            (list, tuple, set),
        ):
            page_candidates = [
                page_candidates
            ]

        page_numbers: list[int] = []

        for page_number in page_candidates:
            try:
                normalized_page = int(
                    page_number
                )

            except (
                TypeError,
                ValueError,
            ):
                continue

            if normalized_page not in page_numbers:
                page_numbers.append(
                    normalized_page
                )

        return sorted(
            page_numbers
        )

    def _collect_page_numbers(
        self,
        value: Any,
        output: set[int],
    ) -> None:
        """
        Recursively collect page numbers.
        """

        if value is None:
            return

        if self._is_integer_like(value):
            output.add(int(value))
            return

        if isinstance(value, str):
            ranges = re.findall(
                r"\d+\s*-\s*\d+|\d+",
                value,
            )

            for item in ranges:
                if "-" in item:
                    start_text, end_text = re.split(
                        r"\s*-\s*",
                        item,
                        maxsplit=1,
                    )

                    start = int(start_text)
                    end = int(end_text)

                    if (
                        end >= start
                        and end - start <= 500
                    ):
                        output.update(
                            range(start, end + 1)
                        )

                else:
                    output.add(int(item))

            return

        if isinstance(value, dict):
            start = (
                value.get("start")
                or value.get("start_page")
                or value.get("page_start")
            )

            end = (
                value.get("end")
                or value.get("end_page")
                or value.get("page_end")
            )

            if (
                self._is_integer_like(start)
                and self._is_integer_like(end)
            ):
                start_number = int(start)
                end_number = int(end)

                if (
                    end_number >= start_number
                    and end_number - start_number <= 500
                ):
                    output.update(
                        range(
                            start_number,
                            end_number + 1,
                        )
                    )

            else:
                for nested_value in value.values():
                    self._collect_page_numbers(
                        nested_value,
                        output,
                    )

            return

        if isinstance(value, (list, tuple, set)):
            for item in value:
                self._collect_page_numbers(
                    item,
                    output,
                )

    @staticmethod
    def _is_integer_like(
        value: Any,
    ) -> bool:
        """
        Check whether a value safely represents an integer.
        """

        if isinstance(value, bool):
            return False

        if isinstance(value, int):
            return True

        if isinstance(value, float):
            return value.is_integer()

        if isinstance(value, str):
            return bool(
                re.fullmatch(
                    r"\d+",
                    value.strip(),
                )
            )

        return False

    # =========================================================================
    # VALIDATION
    # =========================================================================

    @staticmethod
    def _validate_evidence_data(
        evidence_data: Any,
    ) -> None:
        """
        Validate the minimum evidence contract.
        """

        if not isinstance(
            evidence_data,
            dict,
        ):
            raise ValueError(
                "PDF evidence data must be a JSON object."
            )

        chunks = evidence_data.get("chunks")

        if not isinstance(chunks, list):
            raise ValueError(
                "PDF evidence data must contain a 'chunks' list."
            )

        if not chunks:
            raise ValueError(
                "PDF evidence data contains no evidence chunks."
            )

        for index, chunk in enumerate(
            chunks,
            start=1,
        ):
            if not isinstance(chunk, dict):
                raise ValueError(
                    f"Evidence chunk {index} is not an object."
                )

            content = (
                chunk.get("content")
                or chunk.get("text")
            )

            if not isinstance(content, str):
                raise ValueError(
                    f"Evidence chunk {index} has no text content."
                )

            if not content.strip():
                raise ValueError(
                    f"Evidence chunk {index} is empty."
                )

    # =========================================================================
    # FILE HELPERS
    # =========================================================================

    @staticmethod
    def _load_json(
        path: str | Path,
    ) -> dict[str, Any]:
        """
        Load a UTF-8 JSON file.
        """

        path = Path(path)

        with path.open(
            "r",
            encoding="utf-8",
        ) as file:
            data = json.load(file)

        if not isinstance(data, dict):
            raise ValueError(
                f"Expected a JSON object in: {path}"
            )

        return data

    @staticmethod
    def _resolve_output_dir(
        evidence_path: Optional[Path],
        output_dir: Optional[str | Path],
    ) -> Path:
        """
        Resolve the standard facts output directory.
        """

        if output_dir is not None:
            return Path(output_dir)

        if evidence_path is None:
            raise ValueError(
                "output_dir is required when evidence_path "
                "is not supplied."
            )

        evidence_directory = evidence_path.parent

        if (
            evidence_directory.name.lower()
            == "evidence"
        ):
            return (
                evidence_directory.parent
                / "facts"
            )

        return evidence_directory / "facts"

    def _save_raw_response(
        self,
        raw_response_dir: Path,
        chunk_id: str,
        response_text: str,
    ) -> Path:
        """
        Preserve the raw model response for debugging and auditing.
        """

        safe_chunk_id = self._safe_identifier(
            chunk_id
        )

        output_path = (
            raw_response_dir
            / f"{safe_chunk_id}.json"
        )

        payload = {
            "chunk_id": chunk_id,
            "model": self.model,
            "response": response_text,
        }

        self.save_json(
            data=payload,
            output_path=output_path,
        )

        return output_path

    # =========================================================================
    # GENERAL HELPERS
    # =========================================================================

    @staticmethod
    def _count_values(
        values: Iterable[Any],
    ) -> dict[str, int]:
        """
        Count values and return deterministic descending output.
        """

        counts: dict[str, int] = {}

        for value in values:
            key = str(
                value
                if value is not None
                else "unknown"
            )

            counts[key] = (
                counts.get(key, 0) + 1
            )

        return dict(
            sorted(
                counts.items(),
                key=lambda item: (
                    -item[1],
                    item[0],
                ),
            )
        )

    @staticmethod
    def _stable_json_hash(
        value: Any,
    ) -> str:
        """
        Create a deterministic SHA-256 hash from JSON-compatible data.
        """

        serialized = json.dumps(
            value,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        )

        return hashlib.sha256(
            serialized.encode("utf-8")
        ).hexdigest()

    @staticmethod
    def _safe_identifier(
        value: Any,
    ) -> str:
        """
        Convert arbitrary text into a safe filename/identifier component.
        """

        value = str(
            value
            if value is not None
            else "unknown"
        )

        value = re.sub(
            r"[^a-zA-Z0-9_-]+",
            "_",
            value,
        )

        value = re.sub(
            r"_+",
            "_",
            value,
        )

        return (
            value.strip("_").lower()
            or "unknown"
        )

    @staticmethod
    def _safe_int(
        value: Any,
        default: int = 0,
    ) -> int:
        """
        Safely convert a value to an integer.
        """

        try:
            return int(value)

        except (TypeError, ValueError):
            return default

    @staticmethod
    def _utc_now() -> str:
        """
        Return an ISO-8601 UTC timestamp.
        """

        return (
            datetime.now(timezone.utc)
            .replace(microsecond=0)
            .isoformat()
            .replace("+00:00", "Z")
        )


# =============================================================================
# OPTIONAL COMMAND-LINE ENTRY POINT
# =============================================================================

def main() -> None:
    """
    Minimal command-line execution for the current test document.

    The dedicated test file should still be used for complete validation.
    """

    evidence_path = Path(
        "data/0001/pdf/0002/source/"
        "evidence/pdf_evidence_chunks.json"
    )

    extractor = PDFFactExtractor()

    result = extractor.extract(
        evidence_path=evidence_path,
        program_id="0001",
        page_id="0002",
        document_id="source",
    )

    print(
        json.dumps(
            result["summary"],
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()