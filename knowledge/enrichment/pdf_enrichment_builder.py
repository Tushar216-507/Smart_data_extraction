"""
PDF Enrichment Builder
======================

Combines normalized webpage facts with extracted PDF facts.

Input:

    Web normalized facts:
        data/<program_id>/knowledge/
            normalized_program_facts.json

    PDF extracted facts:
        data/<program_id>/pdf/<page_id>/<document_id>/facts/
            pdf_program_facts.json

Output:

    data/<program_id>/knowledge/enriched/
        enriched_program_facts.json
        pdf_enrichment_summary.json


Enrichment strategy
-------------------

1. Preserve every normalized webpage fact.

2. Canonicalize field names only for matching.

   Examples:

       total_ects
       total_credits
       ects_credits

   become:

       total_credits

3. Match facts using:

       entity type
       entity ID/code
       normalized entity name
       canonical field

4. If webpage and PDF values agree:

       confirm the existing fact
       attach PDF supporting evidence

5. If the webpage value is incomplete and the PDF value is richer:

       enrich the existing fact
       preserve the original webpage value
       preserve both sources

6. If values conflict:

       keep the webpage value as the primary value
       preserve the PDF value as a conflict candidate
       do not silently overwrite data

7. If no existing fact matches:

       add the PDF fact as a new enriched fact

8. Remove semantic duplicates created by field aliases.

No LLM call is required.
"""

from __future__ import annotations

import copy
import hashlib
import json
import re
import unicodedata

from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable


# =============================================================================
# CONSTANTS
# =============================================================================

DEFAULT_WEB_FACTS_FILENAME = (
    "normalized_program_facts.json"
)

DEFAULT_PDF_FACTS_FILENAME = (
    "pdf_program_facts.json"
)

DEFAULT_OUTPUT_FILENAME = (
    "enriched_program_facts.json"
)

DEFAULT_SUMMARY_FILENAME = (
    "pdf_enrichment_summary.json"
)


# =============================================================================
# FIELD ALIASES
# =============================================================================

FIELD_ALIASES: dict[str, str] = {

    # -------------------------------------------------------------------------
    # Identity
    # -------------------------------------------------------------------------

    "name": "name",

    "program": "program_name",
    "programme": "program_name",
    "program_title": "program_name",
    "programme_title": "program_name",
    "degree_program": "program_name",
    "degree_program_name": "program_name",
    "degree_programme": "program_name",
    "degree_programme_name": "program_name",
    "study_program": "program_name",
    "study_program_name": "program_name",
    "study_programme": "program_name",
    "study_programme_name": "program_name",
    "program_name": "program_name",

    "translated_name": "translated_program_name",
    "english_name": "translated_program_name",
    "english_program_name": "translated_program_name",
    "translated_program_name": "translated_program_name",

    "program_code": "program_code",
    "programme_code": "program_code",
    "degree_program_code": "program_code",
    "degree_programme_code": "program_code",

    "university": "university_name",
    "institution": "university_name",
    "institution_name": "university_name",
    "university_name": "university_name",

    # -------------------------------------------------------------------------
    # Qualification
    # -------------------------------------------------------------------------

    "award": "qualification",
    "award_name": "qualification",
    "degree": "qualification",
    "degree_name": "qualification",
    "degree_title": "qualification",
    "qualification": "qualification",
    "qualification_awarded": "qualification",

    "abbreviation": "degree_abbreviation",
    "award_abbreviation": "degree_abbreviation",
    "degree_abbreviation": "degree_abbreviation",
    "qualification_abbreviation": "degree_abbreviation",

    # -------------------------------------------------------------------------
    # Credits
    # -------------------------------------------------------------------------

    "credit": "credits",
    "credit_points": "credits",
    "credits": "credits",
    "ects": "credits",
    "ects_credit": "credits",
    "ects_credits": "credits",

    "total_credit": "total_credits",
    "total_credit_points": "total_credits",
    "total_credits": "total_credits",
    "total_ects": "total_credits",
    "total_ects_credits": "total_credits",
    "program_credits": "total_credits",
    "program_total_credits": "total_credits",
    "programme_credits": "total_credits",
    "programme_total_credits": "total_credits",

    "module_credit": "module_credits",
    "module_credits": "module_credits",
    "module_ects": "module_credits",
    "module_ects_credit": "module_credits",
    "module_ects_credits": "module_credits",
    "module_total_credit": "module_credits",
    "module_total_credits": "module_credits",
    "module_total_ects": "module_credits",

    "course_credit": "course_credits",
    "course_credits": "course_credits",
    "course_ects": "course_credits",
    "course_ects_credit": "course_credits",
    "course_ects_credits": "course_credits",

    "elective_credit": "elective_credits",
    "elective_credits": "elective_credits",
    "elective_ects": "elective_credits",

    # -------------------------------------------------------------------------
    # Duration
    # -------------------------------------------------------------------------

    "duration": "duration",
    "program_duration": "duration",
    "programme_duration": "duration",

    "duration_in_semesters": "duration_semesters",
    "duration_semester": "duration_semesters",
    "duration_semesters": "duration_semesters",
    "number_of_semesters": "duration_semesters",
    "program_duration_semesters": "duration_semesters",
    "programme_duration_semesters": "duration_semesters",

    "module_duration": "module_duration",
    "module_duration_semester": "module_duration_semesters",
    "module_duration_semesters": "module_duration_semesters",

    # -------------------------------------------------------------------------
    # Language
    # -------------------------------------------------------------------------

    "instruction_language": "language_of_instruction",
    "instruction_languages": "language_of_instruction",
    "language": "language_of_instruction",
    "language_of_instruction": "language_of_instruction",
    "language_of_teaching": "language_of_instruction",
    "teaching_language": "language_of_instruction",
    "teaching_languages": "language_of_instruction",

    "module_instruction_language": (
        "module_language_of_instruction"
    ),
    "module_language": (
        "module_language_of_instruction"
    ),
    "module_language_of_instruction": (
        "module_language_of_instruction"
    ),
    "module_teaching_language": (
        "module_language_of_instruction"
    ),

    # -------------------------------------------------------------------------
    # Module
    # -------------------------------------------------------------------------

    "module": "module_name",
    "module_title": "module_name",
    "module_name": "module_name",

    "module_identifier": "module_code",
    "module_id": "module_code",
    "module_number": "module_code",
    "module_code": "module_code",

    "module_category": "module_type",
    "module_status": "module_type",
    "module_type": "module_type",

    "module_coordinator": "module_responsible",
    "module_coordinator_name": "module_responsible",
    "module_leader": "module_responsible",
    "module_responsible": "module_responsible",
    "responsible_person": "module_responsible",
    "responsible_personnel": "module_responsible",
    "responsible_staff": "module_responsible",

    # -------------------------------------------------------------------------
    # Course
    # -------------------------------------------------------------------------

    "course": "course_name",
    "course_title": "course_name",
    "course_name": "course_name",

    "course_identifier": "course_code",
    "course_id": "course_code",
    "course_number": "course_code",
    "course_code": "course_code",

    # -------------------------------------------------------------------------
    # Semester and schedule
    # -------------------------------------------------------------------------

    "semester": "semester_offered",
    "offered_in_semester": "semester_offered",
    "semester_available": "semester_offered",
    "semester_offered": "semester_offered",
    "term": "semester_offered",
    "term_offered": "semester_offered",

    "recommended_semester": "recommended_semesters",
    "recommended_semesters": "recommended_semesters",
    "recommended_study_semester": "recommended_semesters",
    "recommended_study_semesters": "recommended_semesters",

    "recommended_start": "recommended_start_semester",
    "recommended_start_semester": "recommended_start_semester",

    # -------------------------------------------------------------------------
    # Teaching
    # -------------------------------------------------------------------------

    "delivery_method": "teaching_format",
    "delivery_mode": "teaching_format",
    "instruction_format": "teaching_format",
    "teaching_form": "teaching_format",
    "teaching_format": "teaching_format",
    "teaching_method": "teaching_format",
    "teaching_mode": "teaching_format",

    # -------------------------------------------------------------------------
    # Assessment
    # -------------------------------------------------------------------------

    "assessment": "assessment",
    "assessment_details": "assessment",
    "assessment_form": "assessment_type",
    "assessment_method": "assessment_type",
    "assessment_mode": "assessment_type",
    "assessment_type": "assessment_type",
    "exam_type": "assessment_type",
    "examination": "assessment_type",
    "examination_type": "assessment_type",

    "module_assessment": "module_assessment",
    "module_assessment_form": "module_assessment_type",
    "module_assessment_method": "module_assessment_type",
    "module_assessment_type": "module_assessment_type",

    "grade": "grading",
    "grading": "grading",
    "grading_method": "grading",

    "graded": "graded",
    "is_graded": "graded",
    "module_graded": "graded",

    "exam_repeat_limit": "exam_repeat_limit",
    "examination_repeat_limit": "exam_repeat_limit",

    # -------------------------------------------------------------------------
    # Workload
    # -------------------------------------------------------------------------

    "workload": "total_workload_hours",
    "workload_hours": "total_workload_hours",
    "total_hours": "total_workload_hours",
    "total_workload": "total_workload_hours",
    "total_workload_hours": "total_workload_hours",

    "module_workload": "module_total_workload_hours",
    "module_workload_hours": "module_total_workload_hours",
    "module_total_hours": "module_total_workload_hours",
    "module_total_workload": "module_total_workload_hours",
    "module_total_workload_hours": "module_total_workload_hours",

    "self_study": "self_study_hours",
    "self_study_hours": "self_study_hours",
    "self_study_time": "self_study_hours",
    "independent_study_hours": "self_study_hours",

    "contact_hours": "contact_hours",
    "contact_time": "contact_hours",
    "presence_hours": "contact_hours",
    "presence_time": "contact_hours",

    "contact_hours_total": "contact_hours_total",
    "total_contact_hours": "contact_hours_total",
    "total_presence_hours": "contact_hours_total",

    "contact_hours_per_week": "weekly_contact_hours",
    "presence_hours_per_week": "weekly_contact_hours",
    "presence_weekly_hours": "weekly_contact_hours",
    "weekly_contact_hours": "weekly_contact_hours",

    "module_contact_hours_per_week": (
        "module_weekly_contact_hours"
    ),
    "module_weekly_contact_hours": (
        "module_weekly_contact_hours"
    ),

    # -------------------------------------------------------------------------
    # Eligibility and prerequisites
    # -------------------------------------------------------------------------

    "admission_requirements": "eligibility",
    "eligibility": "eligibility",
    "entry_requirements": "eligibility",

    "prerequisite": "prerequisites",
    "prerequisite_course": "prerequisites",
    "prerequisite_courses": "prerequisites",
    "prerequisites": "prerequisites",

    "module_prerequisite": "module_prerequisites",
    "module_prerequisites": "module_prerequisites",

    # -------------------------------------------------------------------------
    # Learning outcomes and content
    # -------------------------------------------------------------------------

    "learning_outcome": "learning_outcomes",
    "learning_outcomes": "learning_outcomes",
    "qualification_goal": "learning_outcomes",
    "qualification_goals": "learning_outcomes",

    "module_learning_outcome": "module_learning_outcomes",
    "module_learning_outcomes": "module_learning_outcomes",
    "module_qualification_goal": "module_learning_outcomes",
    "module_qualification_goals": "module_learning_outcomes",

    "content": "content",
    "course_content": "content",

    "module_content": "module_content",

    # -------------------------------------------------------------------------
    # Electives
    # -------------------------------------------------------------------------

    "elective_rule": "elective_rules",
    "elective_rules": "elective_rules",
    "elective_regulation": "elective_rules",
    "elective_regulations": "elective_rules",
    "elective_selection_rule": "elective_rules",

    "module_elective_rule": "module_elective_rules",
    "module_elective_rules": "module_elective_rules",

    # -------------------------------------------------------------------------
    # Reusability
    # -------------------------------------------------------------------------

    "applicable_in_other_programs": (
        "usable_in_other_programs"
    ),
    "applicable_programs": (
        "usable_in_other_programs"
    ),
    "applicability_other_programs": (
        "usable_in_other_programs"
    ),
    "usable_in_other_programs": (
        "usable_in_other_programs"
    ),
    "usability_in_other_programs": (
        "usable_in_other_programs"
    ),

    "module_applicable_in_other_programs": (
        "module_usable_in_other_programs"
    ),
    "module_usable_in_other_programs": (
        "module_usable_in_other_programs"
    ),

    # -------------------------------------------------------------------------
    # Contact
    # -------------------------------------------------------------------------

    "email": "email",
    "email_address": "email",

    "phone": "phone",
    "phone_number": "phone",
    "telephone": "phone",

    "website": "website",
    "website_url": "website",

    # -------------------------------------------------------------------------
    # Dates
    # -------------------------------------------------------------------------

    "effective_date": "document_effective_date",
    "document_date": "document_effective_date",
    "document_effective_date": "document_effective_date",

    "regulation_date": "regulation_date",
}


# =============================================================================
# CATEGORY ALIASES
# =============================================================================

CATEGORY_ALIASES: dict[str, str] = {
    "programme": "program",
    "program": "program",

    "identity": "identity",

    "admissions": "admission",
    "admission": "admission",

    "eligibility": "eligibility",

    "qualification": "qualification",

    "credit": "credits",
    "credits": "credits",

    "curriculum": "curriculum",

    "module": "module",
    "modules": "module",

    "course": "course",
    "courses": "course",

    "assessment": "assessment",
    "assessments": "assessment",

    "workload": "workload",

    "duration": "duration",

    "language": "language",

    "schedule": "schedule",

    "semester": "semester",

    "teaching": "teaching",

    "learning_outcome": "learning_outcomes",
    "learning_outcomes": "learning_outcomes",

    "contact": "contact",
    "contacts": "contact",

    "regulation": "regulation",

    "other": "other",
}


# =============================================================================
# ENTITY TYPE ALIASES
# =============================================================================

ENTITY_TYPE_ALIASES: dict[str, str] = {
    "programme": "program",
    "program": "program",

    "degree_program": "program",
    "degree_programme": "program",

    "module": "module",

    "course": "course",

    "subject": "course",

    "university": "university",
    "institution": "university",

    "document": "document",
}


# =============================================================================
# VALUE NORMALIZATION
# =============================================================================

BOOLEAN_TRUE_VALUES = {
    "1",
    "true",
    "yes",
    "y",
    "required",
    "graded",
}

BOOLEAN_FALSE_VALUES = {
    "0",
    "false",
    "no",
    "n",
    "not required",
    "ungraded",
}


# =============================================================================
# BUILDER
# =============================================================================

class PDFEnrichmentBuilder:
    """
    Enrich normalized webpage facts using PDF-extracted facts.

    The builder is deterministic and does not call an LLM.
    """

    def __init__(
        self,
        *,
        field_aliases: dict[str, str] | None = None,
        category_aliases: dict[str, str] | None = None,
        entity_type_aliases: dict[str, str] | None = None,
        preserve_web_value_on_conflict: bool = True,
        add_unmatched_pdf_facts: bool = True,
        enrich_empty_values: bool = True,
        attach_confirming_sources: bool = True,
        remove_semantic_duplicates: bool = True,
        minimum_fuzzy_entity_similarity: float = 0.92,
        overwrite: bool = False,
    ) -> None:
        """
        Initialize the enrichment builder.
        """

        self.field_aliases = {
            **FIELD_ALIASES,
            **(
                field_aliases
                or {}
            ),
        }

        self.category_aliases = {
            **CATEGORY_ALIASES,
            **(
                category_aliases
                or {}
            ),
        }

        self.entity_type_aliases = {
            **ENTITY_TYPE_ALIASES,
            **(
                entity_type_aliases
                or {}
            ),
        }

        self.preserve_web_value_on_conflict = (
            preserve_web_value_on_conflict
        )

        self.add_unmatched_pdf_facts = (
            add_unmatched_pdf_facts
        )

        self.enrich_empty_values = (
            enrich_empty_values
        )

        self.attach_confirming_sources = (
            attach_confirming_sources
        )

        self.remove_semantic_duplicates = (
            remove_semantic_duplicates
        )

        self.minimum_fuzzy_entity_similarity = (
            minimum_fuzzy_entity_similarity
        )

        self.overwrite = overwrite

        self._reset_statistics()

    # =========================================================================
    # PUBLIC API
    # =========================================================================

    def build(
        self,
        *,
        program_id: str,
        page_id: str = "0002",
        document_id: str = "source",
        data_directory: str | Path = "data",
        web_facts_path: str | Path | None = None,
        pdf_facts_path: str | Path | None = None,
        output_directory: str | Path | None = None,
        output_path: str | Path | None = None,
        summary_path: str | Path | None = None,
        overwrite: bool | None = None,
    ) -> dict[str, Any]:
        """
        Build enriched program facts.

        Returns the complete enriched output object.
        """

        self._reset_statistics()

        resolved_overwrite = (
            self.overwrite
            if overwrite is None
            else overwrite
        )

        paths = self._resolve_paths(
            program_id=program_id,
            page_id=page_id,
            document_id=document_id,
            data_directory=data_directory,
            web_facts_path=web_facts_path,
            pdf_facts_path=pdf_facts_path,
            output_directory=output_directory,
            output_path=output_path,
            summary_path=summary_path,
        )

        self._validate_input_file(
            paths["web_facts_path"],
            label=(
                "Normalized webpage facts"
            ),
        )

        self._validate_input_file(
            paths["pdf_facts_path"],
            label=(
                "PDF program facts"
            ),
        )

        self._validate_output_paths(
            output_path=paths["output_path"],
            summary_path=paths["summary_path"],
            overwrite=resolved_overwrite,
        )

        web_document = self._load_json(
            paths["web_facts_path"]
        )

        pdf_document = self._load_json(
            paths["pdf_facts_path"]
        )

        web_facts = self._extract_facts(
            web_document,
            source_name="normalized webpage",
        )

        pdf_facts = self._extract_facts(
            pdf_document,
            source_name="PDF",
        )

        self.statistics[
            "web_facts_loaded"
        ] = len(web_facts)

        self.statistics[
            "pdf_facts_loaded"
        ] = len(pdf_facts)

        prepared_web_facts = [
            self._prepare_web_fact(
                fact=fact,
                index=index,
            )
            for index, fact in enumerate(
                web_facts,
                start=1,
            )
        ]

        prepared_pdf_facts = [
            self._prepare_pdf_fact(
                fact=fact,
                index=index,
            )
            for index, fact in enumerate(
                pdf_facts,
                start=1,
            )
        ]

        (
            prepared_pdf_facts,
            pdf_duplicates_removed,
        ) = self._deduplicate_pdf_facts(
            prepared_pdf_facts
        )

        self.statistics[
            "pdf_semantic_duplicates_removed"
        ] = pdf_duplicates_removed

        enriched_facts = copy.deepcopy(
            prepared_web_facts
        )

        web_index = self._build_fact_index(
            enriched_facts
        )

        unmatched_pdf_facts: list[
            dict[str, Any]
        ] = []

        for pdf_fact in prepared_pdf_facts:
            match = self._find_best_match(
                pdf_fact=pdf_fact,
                enriched_facts=enriched_facts,
                fact_index=web_index,
            )

            if match is None:
                unmatched_pdf_facts.append(
                    pdf_fact
                )

                if (
                    self.add_unmatched_pdf_facts
                ):
                    new_fact = (
                        self._create_new_pdf_fact(
                            pdf_fact
                        )
                    )

                    enriched_facts.append(
                        new_fact
                    )

                    self._add_fact_to_index(
                        fact_index=web_index,
                        fact=new_fact,
                        index=(
                            len(
                                enriched_facts
                            )
                            - 1
                        ),
                    )

                    self.statistics[
                        "new_pdf_facts_added"
                    ] += 1

                else:
                    self.statistics[
                        "unmatched_pdf_facts_skipped"
                    ] += 1

                continue

            matched_index = match[
                "index"
            ]

            existing_fact = (
                enriched_facts[
                    matched_index
                ]
            )

            outcome = (
                self._merge_matched_fact(
                    existing_fact=existing_fact,
                    pdf_fact=pdf_fact,
                    match=match,
                )
            )

            self.statistics[
                "matched_pdf_facts"
            ] += 1

            self.statistics[
                outcome
            ] += 1

            self._refresh_index_for_fact(
                fact_index=web_index,
                fact=existing_fact,
                index=matched_index,
            )

        if self.remove_semantic_duplicates:
            (
                enriched_facts,
                final_duplicates_removed,
            ) = self._deduplicate_final_facts(
                enriched_facts
            )

        else:
            final_duplicates_removed = 0

        self.statistics[
            "final_semantic_duplicates_removed"
        ] = final_duplicates_removed

        self.statistics[
            "unmatched_pdf_facts"
        ] = len(
            unmatched_pdf_facts
        )

        self.statistics[
            "final_facts_written"
        ] = len(
            enriched_facts
        )

        distributions = (
            self._build_distributions(
                enriched_facts
            )
        )

        conflicts = (
            self._collect_conflicts(
                enriched_facts
            )
        )

        enrichments = (
            self._collect_enrichments(
                enriched_facts
            )
        )

        generated_at = (
            self._utc_now()
        )

        result = {
            "schema_version": "1.0",

            "program_id": str(
                program_id
            ),

            "source": {
                "normalized_web_facts": (
                    str(
                        paths[
                            "web_facts_path"
                        ]
                    )
                ),

                "pdf_facts": (
                    str(
                        paths[
                            "pdf_facts_path"
                        ]
                    )
                ),

                "page_id": str(
                    page_id
                ),

                "document_id": str(
                    document_id
                ),
            },

            "enrichment": {
                "strategy": (
                    "web_primary_pdf_enrichment"
                ),

                "web_value_preserved_on_conflict": (
                    self
                    .preserve_web_value_on_conflict
                ),

                "unmatched_pdf_facts_added": (
                    self
                    .add_unmatched_pdf_facts
                ),

                "semantic_deduplication_enabled": (
                    self
                    .remove_semantic_duplicates
                ),

                "generated_at": (
                    generated_at
                ),
            },

            "summary": (
                copy.deepcopy(
                    self.statistics
                )
            ),

            "distribution": (
                distributions
            ),

            "conflicts": (
                conflicts
            ),

            "enrichments": (
                enrichments
            ),

            "facts": (
                enriched_facts
            ),
        }

        summary = {
            "schema_version": "1.0",

            "program_id": str(
                program_id
            ),

            "generated_at": (
                generated_at
            ),

            "input": {
                "normalized_web_facts": (
                    str(
                        paths[
                            "web_facts_path"
                        ]
                    )
                ),

                "pdf_facts": (
                    str(
                        paths[
                            "pdf_facts_path"
                        ]
                    )
                ),
            },

            "output": {
                "enriched_facts": (
                    str(
                        paths[
                            "output_path"
                        ]
                    )
                ),

                "enrichment_summary": (
                    str(
                        paths[
                            "summary_path"
                        ]
                    )
                ),
            },

            "summary": (
                copy.deepcopy(
                    self.statistics
                )
            ),

            "distribution": (
                distributions
            ),

            "conflict_count": len(
                conflicts
            ),

            "enrichment_count": len(
                enrichments
            ),
        }

        self._save_json(
            file_path=paths[
                "output_path"
            ],
            data=result,
        )

        self._save_json(
            file_path=paths[
                "summary_path"
            ],
            data=summary,
        )

        return result

    def enrich(
        self,
        **kwargs: Any,
    ) -> dict[str, Any]:
        """
        Alias for build().
        """

        return self.build(
            **kwargs
        )

    def build_from_files(
        self,
        *,
        web_facts_path: str | Path,
        pdf_facts_path: str | Path,
        output_directory: str | Path,
        program_id: str,
        page_id: str = "0002",
        document_id: str = "source",
        overwrite: bool | None = None,
    ) -> dict[str, Any]:
        """
        Build enrichment using explicit file paths.
        """

        return self.build(
            program_id=program_id,
            page_id=page_id,
            document_id=document_id,
            web_facts_path=(
                web_facts_path
            ),
            pdf_facts_path=(
                pdf_facts_path
            ),
            output_directory=(
                output_directory
            ),
            overwrite=overwrite,
        )

    # =========================================================================
    # PATHS
    # =========================================================================

    def _resolve_paths(
        self,
        *,
        program_id: str,
        page_id: str,
        document_id: str,
        data_directory: str | Path,
        web_facts_path: str | Path | None,
        pdf_facts_path: str | Path | None,
        output_directory: str | Path | None,
        output_path: str | Path | None,
        summary_path: str | Path | None,
    ) -> dict[str, Path]:
        """
        Resolve default and explicit input/output paths.
        """

        data_root = Path(
            data_directory
        )

        program_directory = (
            data_root
            / str(program_id)
        )

        resolved_web_path = Path(
            web_facts_path
        ) if web_facts_path else (
            program_directory
            / "knowledge"
            / DEFAULT_WEB_FACTS_FILENAME
        )

        resolved_pdf_path = Path(
            pdf_facts_path
        ) if pdf_facts_path else (
            program_directory
            / "pdf"
            / str(page_id)
            / str(document_id)
            / "facts"
            / DEFAULT_PDF_FACTS_FILENAME
        )

        resolved_output_directory = Path(
            output_directory
        ) if output_directory else (
            program_directory
            / "knowledge"
            / "enriched"
        )

        resolved_output_path = Path(
            output_path
        ) if output_path else (
            resolved_output_directory
            / DEFAULT_OUTPUT_FILENAME
        )

        resolved_summary_path = Path(
            summary_path
        ) if summary_path else (
            resolved_output_directory
            / DEFAULT_SUMMARY_FILENAME
        )

        return {
            "web_facts_path": (
                resolved_web_path
            ),

            "pdf_facts_path": (
                resolved_pdf_path
            ),

            "output_directory": (
                resolved_output_directory
            ),

            "output_path": (
                resolved_output_path
            ),

            "summary_path": (
                resolved_summary_path
            ),
        }

    # =========================================================================
    # INPUT AND OUTPUT
    # =========================================================================

    @staticmethod
    def _validate_input_file(
        file_path: Path,
        *,
        label: str,
    ) -> None:
        """
        Validate one required input file.
        """

        if not file_path.exists():
            raise FileNotFoundError(
                f"{label} file was not found:\n"
                f"{file_path}"
            )

        if not file_path.is_file():
            raise ValueError(
                f"{label} path is not a file:\n"
                f"{file_path}"
            )

    @staticmethod
    def _validate_output_paths(
        *,
        output_path: Path,
        summary_path: Path,
        overwrite: bool,
    ) -> None:
        """
        Prevent accidental output replacement.
        """

        existing_files = [
            file_path
            for file_path in (
                output_path,
                summary_path,
            )
            if file_path.exists()
        ]

        if (
            existing_files
            and not overwrite
        ):
            formatted_paths = "\n".join(
                str(file_path)
                for file_path
                in existing_files
            )

            raise FileExistsError(
                "Enrichment output already exists.\n"
                "Enable overwrite or remove:\n"
                f"{formatted_paths}"
            )

    @staticmethod
    def _load_json(
        file_path: Path,
    ) -> Any:
        """
        Load UTF-8 JSON.
        """

        try:
            with file_path.open(
                "r",
                encoding="utf-8",
            ) as file:
                return json.load(
                    file
                )

        except json.JSONDecodeError as error:
            raise ValueError(
                "Invalid JSON file:\n"
                f"{file_path}\n\n"
                f"{error}"
            ) from error

    @staticmethod
    def _save_json(
        *,
        file_path: Path,
        data: Any,
    ) -> None:
        """
        Save formatted UTF-8 JSON.
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

            file.write("\n")

        temporary_path.replace(
            file_path
        )

    # =========================================================================
    # FACT EXTRACTION
    # =========================================================================

    def _extract_facts(
        self,
        document: Any,
        *,
        source_name: str,
    ) -> list[dict[str, Any]]:
        """
        Extract facts from supported document structures.
        """

        if isinstance(document, list):
            facts = document

        elif isinstance(document, dict):
            facts = self._find_fact_list(
                document
            )

        else:
            raise ValueError(
                f"The {source_name} document "
                "must contain a JSON object "
                "or JSON list."
            )

        if facts is None:
            raise ValueError(
                f"No facts list was found in "
                f"the {source_name} document."
            )

        valid_facts: list[
            dict[str, Any]
        ] = []

        for index, fact in enumerate(
            facts,
            start=1,
        ):
            if not isinstance(
                fact,
                dict,
            ):
                raise ValueError(
                    f"{source_name.capitalize()} "
                    f"fact {index} is not "
                    "a JSON object."
                )

            valid_facts.append(
                copy.deepcopy(
                    fact
                )
            )

        return valid_facts

    def _find_fact_list(
        self,
        document: dict[str, Any],
    ) -> list[Any] | None:
        """
        Find a fact list in common output structures.
        """

        direct_keys = (
            "facts",
            "normalized_facts",
            "program_facts",
            "extracted_facts",
            "items",
        )

        for key in direct_keys:
            value = document.get(
                key
            )

            if (
                isinstance(value, list)
                and self._looks_like_fact_list(
                    value
                )
            ):
                return value

        nested_keys = (
            "data",
            "result",
            "output",
            "knowledge",
            "extraction",
        )

        for key in nested_keys:
            nested = document.get(
                key
            )

            if isinstance(
                nested,
                dict,
            ):
                found = (
                    self._find_fact_list(
                        nested
                    )
                )

                if found is not None:
                    return found

        for value in document.values():
            if isinstance(
                value,
                list,
            ) and self._looks_like_fact_list(
                value
            ):
                return value

        return None

    @staticmethod
    def _looks_like_fact_list(
        values: list[Any],
    ) -> bool:
        """
        Determine whether a list resembles facts.
        """

        if not values:
            return True

        sample = values[
            : min(
                len(values),
                10,
            )
        ]

        object_values = [
            value
            for value in sample
            if isinstance(
                value,
                dict,
            )
        ]

        if not object_values:
            return False

        fact_like_count = sum(
            1
            for value in object_values
            if (
                "field" in value
                or "value" in value
                or "fact_id" in value
            )
        )

        return (
            fact_like_count
            >= max(
                1,
                len(
                    object_values
                )
                // 2,
            )
        )

    # =========================================================================
    # FACT PREPARATION
    # =========================================================================

    def _prepare_web_fact(
        self,
        *,
        fact: dict[str, Any],
        index: int,
    ) -> dict[str, Any]:
        """
        Prepare one normalized webpage fact.
        """

        prepared = copy.deepcopy(
            fact
        )

        prepared.setdefault(
            "fact_id",
            self._generate_fact_id(
                prefix="web",
                fact=prepared,
                index=index,
            ),
        )

        prepared[
            "category"
        ] = self._canonical_category(
            prepared.get(
                "category"
            )
        )

        prepared[
            "canonical_field"
        ] = self._canonical_field(
            prepared.get(
                "field"
            )
        )

        prepared[
            "entity"
        ] = self._normalize_entity(
            prepared.get(
                "entity"
            ),
            fact=prepared,
        )

        parent_entity = (
            prepared.get(
                "parent_entity"
            )
        )

        if parent_entity:
            prepared[
                "parent_entity"
            ] = self._normalize_entity(
                parent_entity,
                fact=prepared,
            )

        prepared.setdefault(
            "enrichment",
            {
                "status": "original",
                "primary_source": "web",
                "supporting_sources": [],
                "changes": [],
                "conflicts": [],
            },
        )

        enrichment = prepared[
            "enrichment"
        ]

        enrichment.setdefault(
            "status",
            "original",
        )

        enrichment.setdefault(
            "primary_source",
            "web",
        )

        enrichment.setdefault(
            "supporting_sources",
            [],
        )

        enrichment.setdefault(
            "changes",
            [],
        )

        enrichment.setdefault(
            "conflicts",
            [],
        )

        return prepared

    def _prepare_pdf_fact(
        self,
        *,
        fact: dict[str, Any],
        index: int,
    ) -> dict[str, Any]:
        """
        Prepare one PDF fact.
        """

        prepared = copy.deepcopy(
            fact
        )

        prepared.setdefault(
            "fact_id",
            self._generate_fact_id(
                prefix="pdf",
                fact=prepared,
                index=index,
            ),
        )

        prepared[
            "category"
        ] = self._canonical_category(
            prepared.get(
                "category"
            )
        )

        prepared[
            "canonical_field"
        ] = self._canonical_field(
            prepared.get(
                "field"
            )
        )

        prepared[
            "entity"
        ] = self._normalize_entity(
            prepared.get(
                "entity"
            ),
            fact=prepared,
        )

        parent_entity = (
            prepared.get(
                "parent_entity"
            )
        )

        if parent_entity:
            prepared[
                "parent_entity"
            ] = self._normalize_entity(
                parent_entity,
                fact=prepared,
            )

        return prepared

    # =========================================================================
    # MATCHING
    # =========================================================================

    def _build_fact_index(
        self,
        facts: list[
            dict[str, Any]
        ],
    ) -> dict[
        tuple[str, str, str, str],
        list[int],
    ]:
        """
        Build an exact matching index.
        """

        index: dict[
            tuple[
                str,
                str,
                str,
                str,
            ],
            list[int],
        ] = {}

        for fact_index, fact in enumerate(
            facts
        ):
            self._add_fact_to_index(
                fact_index=index,
                fact=fact,
                index=fact_index,
            )

        return index

    def _add_fact_to_index(
        self,
        *,
        fact_index: dict[
            tuple[
                str,
                str,
                str,
                str,
            ],
            list[int],
        ],
        fact: dict[str, Any],
        index: int,
    ) -> None:
        """
        Add one fact to the exact index.
        """

        for key in self._fact_match_keys(
            fact
        ):
            fact_index.setdefault(
                key,
                [],
            )

            if index not in fact_index[
                key
            ]:
                fact_index[
                    key
                ].append(
                    index
                )

    def _refresh_index_for_fact(
        self,
        *,
        fact_index: dict[
            tuple[
                str,
                str,
                str,
                str,
            ],
            list[int],
        ],
        fact: dict[str, Any],
        index: int,
    ) -> None:
        """
        Refresh index keys after enrichment.
        """

        self._add_fact_to_index(
            fact_index=fact_index,
            fact=fact,
            index=index,
        )

    def _fact_match_keys(
        self,
        fact: dict[str, Any],
    ) -> set[
        tuple[
            str,
            str,
            str,
            str,
        ]
    ]:
        """
        Create exact matching keys for a fact.
        """

        entity = (
            fact.get("entity")
            or {}
        )

        entity_type = (
            self._canonical_entity_type(
                entity.get("type")
            )
        )

        canonical_field = (
            fact.get(
                "canonical_field"
            )
            or self._canonical_field(
                fact.get("field")
            )
        )

        identifiers = (
            self._entity_identifiers(
                fact
            )
        )

        keys: set[
            tuple[
                str,
                str,
                str,
                str,
            ]
        ] = set()

        for identifier_type, value in (
            identifiers
        ):
            if not value:
                continue

            keys.add(
                (
                    entity_type,
                    identifier_type,
                    value,
                    canonical_field,
                )
            )

        return keys

    def _find_best_match(
        self,
        *,
        pdf_fact: dict[str, Any],
        enriched_facts: list[
            dict[str, Any]
        ],
        fact_index: dict[
            tuple[
                str,
                str,
                str,
                str,
            ],
            list[int],
        ],
    ) -> dict[str, Any] | None:
        """
        Find the strongest existing match.
        """

        candidate_indexes: set[
            int
        ] = set()

        exact_keys = (
            self._fact_match_keys(
                pdf_fact
            )
        )

        for key in exact_keys:
            candidate_indexes.update(
                fact_index.get(
                    key,
                    [],
                )
            )

        best_match: (
            dict[str, Any]
            | None
        ) = None

        for candidate_index in (
            candidate_indexes
        ):
            candidate = (
                enriched_facts[
                    candidate_index
                ]
            )

            score, reasons = (
                self._calculate_match_score(
                    existing_fact=candidate,
                    pdf_fact=pdf_fact,
                )
            )

            if (
                best_match is None
                or score
                > best_match["score"]
            ):
                best_match = {
                    "index": (
                        candidate_index
                    ),

                    "score": score,

                    "reasons": (
                        reasons
                    ),

                    "method": (
                        "exact_entity_index"
                    ),
                }

        if (
            best_match is not None
            and best_match["score"]
            >= 70
        ):
            return best_match

        fuzzy_match = (
            self._find_fuzzy_match(
                pdf_fact=pdf_fact,
                enriched_facts=(
                    enriched_facts
                ),
            )
        )

        if (
            fuzzy_match is not None
            and (
                best_match is None
                or fuzzy_match["score"]
                > best_match["score"]
            )
        ):
            best_match = fuzzy_match

        if (
            best_match is not None
            and best_match["score"]
            >= 70
        ):
            return best_match

        return None

    def _find_fuzzy_match(
        self,
        *,
        pdf_fact: dict[str, Any],
        enriched_facts: list[
            dict[str, Any]
        ],
    ) -> dict[str, Any] | None:
        """
        Find a conservative fuzzy entity match.
        """

        pdf_entity = (
            pdf_fact.get("entity")
            or {}
        )

        pdf_entity_type = (
            self._canonical_entity_type(
                pdf_entity.get("type")
            )
        )

        pdf_field = (
            pdf_fact.get(
                "canonical_field"
            )
            or self._canonical_field(
                pdf_fact.get("field")
            )
        )

        pdf_name = (
            self._normalize_text(
                pdf_entity.get("name")
            )
        )

        if not pdf_name:
            return None

        best_match: (
            dict[str, Any]
            | None
        ) = None

        for index, existing_fact in (
            enumerate(
                enriched_facts
            )
        ):
            existing_entity = (
                existing_fact.get(
                    "entity"
                )
                or {}
            )

            existing_type = (
                self
                ._canonical_entity_type(
                    existing_entity.get(
                        "type"
                    )
                )
            )

            existing_field = (
                existing_fact.get(
                    "canonical_field"
                )
                or self._canonical_field(
                    existing_fact.get(
                        "field"
                    )
                )
            )

            if (
                existing_type
                != pdf_entity_type
            ):
                continue

            if (
                existing_field
                != pdf_field
            ):
                continue

            existing_name = (
                self._normalize_text(
                    existing_entity.get(
                        "name"
                    )
                )
            )

            if not existing_name:
                continue

            similarity = (
                self._text_similarity(
                    pdf_name,
                    existing_name,
                )
            )

            if (
                similarity
                < self
                .minimum_fuzzy_entity_similarity
            ):
                continue

            score = (
                70
                + (
                    similarity
                    * 20
                )
            )

            candidate = {
                "index": index,

                "score": score,

                "reasons": [
                    (
                        "canonical field "
                        "matched"
                    ),

                    (
                        "entity type "
                        "matched"
                    ),

                    (
                        "entity-name "
                        "similarity="
                        f"{similarity:.3f}"
                    ),
                ],

                "method": (
                    "fuzzy_entity_name"
                ),
            }

            if (
                best_match is None
                or candidate["score"]
                > best_match["score"]
            ):
                best_match = candidate

        return best_match

    def _calculate_match_score(
        self,
        *,
        existing_fact: dict[str, Any],
        pdf_fact: dict[str, Any],
    ) -> tuple[
        float,
        list[str],
    ]:
        """
        Score an existing fact against a PDF fact.
        """

        score = 0.0

        reasons: list[str] = []

        existing_field = (
            existing_fact.get(
                "canonical_field"
            )
            or self._canonical_field(
                existing_fact.get(
                    "field"
                )
            )
        )

        pdf_field = (
            pdf_fact.get(
                "canonical_field"
            )
            or self._canonical_field(
                pdf_fact.get(
                    "field"
                )
            )
        )

        if (
            existing_field
            != pdf_field
        ):
            return (
                0.0,
                [
                    (
                        "canonical fields "
                        "did not match"
                    )
                ],
            )

        score += 40

        reasons.append(
            "canonical field matched"
        )

        existing_entity = (
            existing_fact.get(
                "entity"
            )
            or {}
        )

        pdf_entity = (
            pdf_fact.get("entity")
            or {}
        )

        existing_type = (
            self._canonical_entity_type(
                existing_entity.get(
                    "type"
                )
            )
        )

        pdf_type = (
            self._canonical_entity_type(
                pdf_entity.get("type")
            )
        )

        if existing_type == pdf_type:
            score += 20

            reasons.append(
                "entity type matched"
            )

        else:
            return (
                0.0,
                [
                    (
                        "entity types "
                        "did not match"
                    )
                ],
            )

        existing_id = (
            self._normalize_identifier(
                existing_entity.get("id")
            )
        )

        pdf_id = (
            self._normalize_identifier(
                pdf_entity.get("id")
            )
        )

        if (
            existing_id
            and pdf_id
        ):
            if existing_id == pdf_id:
                score += 35

                reasons.append(
                    "entity ID matched"
                )

            else:
                score -= 35

                reasons.append(
                    "entity IDs conflicted"
                )

        existing_name = (
            self._normalize_text(
                existing_entity.get(
                    "name"
                )
            )
        )

        pdf_name = (
            self._normalize_text(
                pdf_entity.get("name")
            )
        )

        if (
            existing_name
            and pdf_name
        ):
            similarity = (
                self._text_similarity(
                    existing_name,
                    pdf_name,
                )
            )

            if similarity == 1.0:
                score += 25

                reasons.append(
                    "entity name matched"
                )

            elif (
                similarity
                >= self
                .minimum_fuzzy_entity_similarity
            ):
                score += (
                    similarity
                    * 20
                )

                reasons.append(
                    "entity names were "
                    "strongly similar"
                )

        existing_parent = (
            existing_fact.get(
                "parent_entity"
            )
            or {}
        )

        pdf_parent = (
            pdf_fact.get(
                "parent_entity"
            )
            or {}
        )

        existing_parent_id = (
            self._normalize_identifier(
                existing_parent.get("id")
            )
        )

        pdf_parent_id = (
            self._normalize_identifier(
                pdf_parent.get("id")
            )
        )

        if (
            existing_parent_id
            and pdf_parent_id
            and (
                existing_parent_id
                == pdf_parent_id
            )
        ):
            score += 10

            reasons.append(
                "parent entity ID matched"
            )

        existing_parent_name = (
            self._normalize_text(
                existing_parent.get(
                    "name"
                )
            )
        )

        pdf_parent_name = (
            self._normalize_text(
                pdf_parent.get(
                    "name"
                )
            )
        )

        if (
            existing_parent_name
            and pdf_parent_name
            and (
                existing_parent_name
                == pdf_parent_name
            )
        ):
            score += 5

            reasons.append(
                "parent entity name matched"
            )

        return (
            score,
            reasons,
        )

    # =========================================================================
    # MERGING
    # =========================================================================

    def _merge_matched_fact(
        self,
        *,
        existing_fact: dict[str, Any],
        pdf_fact: dict[str, Any],
        match: dict[str, Any],
    ) -> str:
        """
        Merge one matched PDF fact.

        Returns one statistics key:

            facts_confirmed
            facts_enriched
            conflicts_detected
            duplicate_pdf_facts_skipped
        """

        existing_value = (
            existing_fact.get("value")
        )

        pdf_value = (
            pdf_fact.get("value")
        )

        enrichment = (
            existing_fact.setdefault(
                "enrichment",
                {
                    "status": "original",
                    "primary_source": "web",
                    "supporting_sources": [],
                    "changes": [],
                    "conflicts": [],
                },
            )
        )

        if self._values_equal(
            existing_value,
            pdf_value,
        ):
            enrichment[
                "status"
            ] = self._merge_status(
                enrichment.get(
                    "status"
                ),
                "confirmed",
            )

            if (
                self
                .attach_confirming_sources
            ):
                self._append_unique(
                    enrichment[
                        "supporting_sources"
                    ],
                    self._build_pdf_support(
                        pdf_fact=pdf_fact,
                        relationship=(
                            "confirmation"
                        ),
                        match=match,
                    ),
                )

            return "facts_confirmed"

        if (
            self.enrich_empty_values
            and self._is_empty(
                existing_value
            )
            and not self._is_empty(
                pdf_value
            )
        ):
            previous_value = (
                copy.deepcopy(
                    existing_value
                )
            )

            existing_fact[
                "value"
            ] = copy.deepcopy(
                pdf_value
            )

            self._copy_richer_metadata(
                target=existing_fact,
                source=pdf_fact,
            )

            enrichment[
                "status"
            ] = "enriched"

            enrichment[
                "changes"
            ].append(
                {
                    "type": (
                        "filled_empty_value"
                    ),

                    "previous_value": (
                        previous_value
                    ),

                    "enriched_value": (
                        copy.deepcopy(
                            pdf_value
                        )
                    ),

                    "pdf_fact_id": (
                        pdf_fact.get(
                            "fact_id"
                        )
                    ),

                    "match_score": (
                        match.get(
                            "score"
                        )
                    ),

                    "match_method": (
                        match.get(
                            "method"
                        )
                    ),
                }
            )

            self._append_unique(
                enrichment[
                    "supporting_sources"
                ],
                self._build_pdf_support(
                    pdf_fact=pdf_fact,
                    relationship=(
                        "enrichment"
                    ),
                    match=match,
                ),
            )

            return "facts_enriched"

        if self._pdf_value_is_richer(
            existing_value=existing_value,
            pdf_value=pdf_value,
        ):
            previous_value = (
                copy.deepcopy(
                    existing_value
                )
            )

            existing_fact[
                "value"
            ] = copy.deepcopy(
                pdf_value
            )

            self._copy_richer_metadata(
                target=existing_fact,
                source=pdf_fact,
            )

            enrichment[
                "status"
            ] = "enriched"

            enrichment[
                "changes"
            ].append(
                {
                    "type": (
                        "replaced_with_richer_pdf_value"
                    ),

                    "previous_value": (
                        previous_value
                    ),

                    "enriched_value": (
                        copy.deepcopy(
                            pdf_value
                        )
                    ),

                    "pdf_fact_id": (
                        pdf_fact.get(
                            "fact_id"
                        )
                    ),

                    "match_score": (
                        match.get(
                            "score"
                        )
                    ),

                    "match_method": (
                        match.get(
                            "method"
                        )
                    ),
                }
            )

            self._append_unique(
                enrichment[
                    "supporting_sources"
                ],
                self._build_pdf_support(
                    pdf_fact=pdf_fact,
                    relationship=(
                        "richer_value"
                    ),
                    match=match,
                ),
            )

            return "facts_enriched"

        if self._values_compatible(
            existing_value=existing_value,
            pdf_value=pdf_value,
        ):
            enrichment[
                "status"
            ] = self._merge_status(
                enrichment.get(
                    "status"
                ),
                "confirmed",
            )

            self._append_unique(
                enrichment[
                    "supporting_sources"
                ],
                self._build_pdf_support(
                    pdf_fact=pdf_fact,
                    relationship=(
                        "compatible_value"
                    ),
                    match=match,
                ),
            )

            return "facts_confirmed"

        conflict = {
            "type": "value_conflict",

            "field": (
                existing_fact.get(
                    "field"
                )
            ),

            "canonical_field": (
                existing_fact.get(
                    "canonical_field"
                )
            ),

            "primary_value": (
                copy.deepcopy(
                    existing_value
                )
            ),

            "pdf_value": (
                copy.deepcopy(
                    pdf_value
                )
            ),

            "primary_fact_id": (
                existing_fact.get(
                    "fact_id"
                )
            ),

            "pdf_fact_id": (
                pdf_fact.get(
                    "fact_id"
                )
            ),

            "match_score": (
                match.get("score")
            ),

            "match_method": (
                match.get("method")
            ),

            "match_reasons": (
                copy.deepcopy(
                    match.get(
                        "reasons"
                    )
                    or []
                )
            ),

            "resolution": (
                "web_value_preserved"
                if self
                .preserve_web_value_on_conflict
                else (
                    "pdf_value_selected"
                )
            ),

            "pdf_source": (
                self._extract_source(
                    pdf_fact
                )
            ),
        }

        self._append_unique(
            enrichment[
                "conflicts"
            ],
            conflict,
        )

        enrichment[
            "status"
        ] = "conflict"

        if (
            not self
            .preserve_web_value_on_conflict
        ):
            existing_fact[
                "value"
            ] = copy.deepcopy(
                pdf_value
            )

            self._copy_richer_metadata(
                target=existing_fact,
                source=pdf_fact,
            )

        return "conflicts_detected"

    def _create_new_pdf_fact(
        self,
        pdf_fact: dict[str, Any],
    ) -> dict[str, Any]:
        """
        Create a new enriched fact from PDF.
        """

        new_fact = copy.deepcopy(
            pdf_fact
        )

        original_pdf_fact_id = (
            new_fact.get(
                "fact_id"
            )
        )

        new_fact[
            "fact_id"
        ] = self._generate_enriched_id(
            new_fact
        )

        new_fact[
            "enrichment"
        ] = {
            "status": "added_from_pdf",

            "primary_source": "pdf",

            "original_pdf_fact_id": (
                original_pdf_fact_id
            ),

            "supporting_sources": [
                self._build_pdf_support(
                    pdf_fact=pdf_fact,
                    relationship=(
                        "new_fact"
                    ),
                    match=None,
                )
            ],

            "changes": [],

            "conflicts": [],
        }

        return new_fact

    @staticmethod
    def _merge_status(
        current_status: Any,
        new_status: str,
    ) -> str:
        """
        Preserve stronger enrichment states.
        """

        priority = {
            "original": 0,
            "confirmed": 1,
            "enriched": 2,
            "added_from_pdf": 2,
            "conflict": 3,
        }

        current = str(
            current_status
            or "original"
        )

        if (
            priority.get(
                new_status,
                0,
            )
            > priority.get(
                current,
                0,
            )
        ):
            return new_status

        return current

    # =========================================================================
    # DEDUPLICATION
    # =========================================================================

    def _deduplicate_pdf_facts(
        self,
        facts: list[
            dict[str, Any]
        ],
    ) -> tuple[
        list[dict[str, Any]],
        int,
    ]:
        """
        Remove semantically identical PDF facts.
        """

        unique_facts: list[
            dict[str, Any]
        ] = []

        seen: dict[
            str,
            int,
        ] = {}

        removed = 0

        for fact in facts:
            signature = (
                self._semantic_signature(
                    fact
                )
            )

            if signature not in seen:
                seen[
                    signature
                ] = len(
                    unique_facts
                )

                unique_facts.append(
                    fact
                )

                continue

            existing_index = (
                seen[
                    signature
                ]
            )

            existing = (
                unique_facts[
                    existing_index
                ]
            )

            self._merge_pdf_duplicate(
                target=existing,
                duplicate=fact,
            )

            removed += 1

        return (
            unique_facts,
            removed,
        )

    def _deduplicate_final_facts(
        self,
        facts: list[
            dict[str, Any]
        ],
    ) -> tuple[
        list[dict[str, Any]],
        int,
    ]:
        """
        Remove final semantic duplicates.

        Web-origin facts are preferred over PDF-only facts.
        """

        unique_facts: list[
            dict[str, Any]
        ] = []

        seen: dict[
            str,
            int,
        ] = {}

        removed = 0

        for fact in facts:
            signature = (
                self._semantic_signature(
                    fact
                )
            )

            if signature not in seen:
                seen[
                    signature
                ] = len(
                    unique_facts
                )

                unique_facts.append(
                    fact
                )

                continue

            existing_index = (
                seen[
                    signature
                ]
            )

            existing = (
                unique_facts[
                    existing_index
                ]
            )

            existing_source = (
                (
                    existing.get(
                        "enrichment"
                    )
                    or {}
                ).get(
                    "primary_source"
                )
            )

            incoming_source = (
                (
                    fact.get(
                        "enrichment"
                    )
                    or {}
                ).get(
                    "primary_source"
                )
            )

            if (
                existing_source == "pdf"
                and incoming_source == "web"
            ):
                self._merge_fact_metadata(
                    target=fact,
                    duplicate=existing,
                )

                unique_facts[
                    existing_index
                ] = fact

            else:
                self._merge_fact_metadata(
                    target=existing,
                    duplicate=fact,
                )

            removed += 1

        return (
            unique_facts,
            removed,
        )

    def _merge_pdf_duplicate(
        self,
        *,
        target: dict[str, Any],
        duplicate: dict[str, Any],
    ) -> None:
        """
        Preserve provenance from a duplicate PDF fact.
        """

        target.setdefault(
            "duplicate_pdf_sources",
            [],
        )

        duplicate_record = {
            "fact_id": (
                duplicate.get(
                    "fact_id"
                )
            ),

            "source": (
                self._extract_source(
                    duplicate
                )
            ),

            "evidence": (
                copy.deepcopy(
                    duplicate.get(
                        "evidence"
                    )
                )
            ),
        }

        self._append_unique(
            target[
                "duplicate_pdf_sources"
            ],
            duplicate_record,
        )

    def _merge_fact_metadata(
        self,
        *,
        target: dict[str, Any],
        duplicate: dict[str, Any],
    ) -> None:
        """
        Merge enrichment metadata from duplicate facts.
        """

        target_enrichment = (
            target.setdefault(
                "enrichment",
                {
                    "status": "original",
                    "primary_source": "web",
                    "supporting_sources": [],
                    "changes": [],
                    "conflicts": [],
                },
            )
        )

        duplicate_enrichment = (
            duplicate.get(
                "enrichment"
            )
            or {}
        )

        for key in (
            "supporting_sources",
            "changes",
            "conflicts",
        ):
            target_enrichment.setdefault(
                key,
                [],
            )

            for item in (
                duplicate_enrichment.get(
                    key
                )
                or []
            ):
                self._append_unique(
                    target_enrichment[
                        key
                    ],
                    copy.deepcopy(
                        item
                    ),
                )

    # =========================================================================
    # CANONICALIZATION
    # =========================================================================

    def _canonical_field(
        self,
        value: Any,
    ) -> str:
        """
        Convert a field into a canonical field.
        """

        normalized = (
            self._normalize_key(
                value
            )
        )

        if not normalized:
            return "unknown"

        return self.field_aliases.get(
            normalized,
            normalized,
        )

    def _canonical_category(
        self,
        value: Any,
    ) -> str:
        """
        Convert a category into a canonical category.
        """

        normalized = (
            self._normalize_key(
                value
            )
        )

        if not normalized:
            return "other"

        return self.category_aliases.get(
            normalized,
            normalized,
        )

    def _canonical_entity_type(
        self,
        value: Any,
    ) -> str:
        """
        Convert an entity type into a canonical type.
        """

        normalized = (
            self._normalize_key(
                value
            )
        )

        if not normalized:
            return "program"

        return (
            self.entity_type_aliases.get(
                normalized,
                normalized,
            )
        )

    def _normalize_entity(
        self,
        entity: Any,
        *,
        fact: dict[str, Any],
    ) -> dict[str, Any]:
        """
        Normalize entity structure without removing data.
        """

        if isinstance(
            entity,
            dict,
        ):
            normalized_entity = (
                copy.deepcopy(
                    entity
                )
            )

        elif isinstance(
            entity,
            str,
        ):
            normalized_entity = {
                "type": (
                    self._infer_entity_type(
                        fact
                    )
                ),

                "name": entity,
            }

        else:
            normalized_entity = {
                "type": (
                    self._infer_entity_type(
                        fact
                    )
                )
            }

        normalized_entity[
            "type"
        ] = self._canonical_entity_type(
            normalized_entity.get(
                "type"
            )
        )

        entity_id = (
            normalized_entity.get(
                "id"
            )
        )

        entity_name = (
            normalized_entity.get(
                "name"
            )
        )

        if not entity_id:
            inferred_id = (
                self._infer_entity_id(
                    fact=fact,
                    entity_type=(
                        normalized_entity[
                            "type"
                        ]
                    ),
                )
            )

            if inferred_id:
                normalized_entity[
                    "id"
                ] = inferred_id

        if not entity_name:
            inferred_name = (
                self._infer_entity_name(
                    fact=fact,
                    entity_type=(
                        normalized_entity[
                            "type"
                        ]
                    ),
                )
            )

            if inferred_name:
                normalized_entity[
                    "name"
                ] = inferred_name

        return normalized_entity

    def _infer_entity_type(
        self,
        fact: dict[str, Any],
    ) -> str:
        """
        Infer entity type from category and field.
        """

        category = (
            self._canonical_category(
                fact.get(
                    "category"
                )
            )
        )

        field = (
            self._canonical_field(
                fact.get(
                    "field"
                )
            )
        )

        if (
            category == "module"
            or field.startswith(
                "module_"
            )
        ):
            return "module"

        if (
            category == "course"
            or field.startswith(
                "course_"
            )
        ):
            return "course"

        return "program"

    def _infer_entity_id(
        self,
        *,
        fact: dict[str, Any],
        entity_type: str,
    ) -> Any:
        """
        Infer an entity ID from known fact fields.
        """

        candidates: tuple[
            str,
            ...,
        ]

        if entity_type == "module":
            candidates = (
                "module_id",
                "module_code",
                "code",
            )

        elif entity_type == "course":
            candidates = (
                "course_id",
                "course_code",
                "code",
            )

        elif entity_type == "program":
            candidates = (
                "program_id",
                "programme_id",
                "program_code",
                "programme_code",
            )

        else:
            candidates = (
                "id",
                "code",
            )

        for key in candidates:
            value = fact.get(
                key
            )

            if not self._is_empty(
                value
            ):
                return value

        canonical_field = (
            self._canonical_field(
                fact.get("field")
            )
        )

        if (
            entity_type == "module"
            and canonical_field
            == "module_code"
        ):
            return fact.get(
                "value"
            )

        if (
            entity_type == "course"
            and canonical_field
            == "course_code"
        ):
            return fact.get(
                "value"
            )

        return None

    def _infer_entity_name(
        self,
        *,
        fact: dict[str, Any],
        entity_type: str,
    ) -> Any:
        """
        Infer an entity name from known fields.
        """

        candidates: tuple[
            str,
            ...,
        ]

        if entity_type == "module":
            candidates = (
                "module_name",
                "name",
            )

        elif entity_type == "course":
            candidates = (
                "course_name",
                "name",
            )

        elif entity_type == "program":
            candidates = (
                "program_name",
                "programme_name",
                "name",
            )

        else:
            candidates = (
                "name",
            )

        for key in candidates:
            value = fact.get(
                key
            )

            if not self._is_empty(
                value
            ):
                return value

        canonical_field = (
            self._canonical_field(
                fact.get("field")
            )
        )

        expected_name_field = {
            "module": "module_name",
            "course": "course_name",
            "program": "program_name",
        }.get(
            entity_type
        )

        if (
            expected_name_field
            and canonical_field
            == expected_name_field
        ):
            return fact.get(
                "value"
            )

        return None

    # =========================================================================
    # ENTITY IDENTIFIERS
    # =========================================================================

    def _entity_identifiers(
        self,
        fact: dict[str, Any],
    ) -> list[
        tuple[str, str]
    ]:
        """
        Return available normalized entity identifiers.
        """

        entity = (
            fact.get("entity")
            or {}
        )

        identifiers: list[
            tuple[str, str]
        ] = []

        entity_id = (
            self._normalize_identifier(
                entity.get("id")
            )
        )

        entity_name = (
            self._normalize_text(
                entity.get("name")
            )
        )

        if entity_id:
            identifiers.append(
                (
                    "id",
                    entity_id,
                )
            )

        if entity_name:
            identifiers.append(
                (
                    "name",
                    entity_name,
                )
            )

        if not identifiers:
            identifiers.append(
                (
                    "program_scope",
                    "program",
                )
            )

        return identifiers

    # =========================================================================
    # VALUE COMPARISON
    # =========================================================================

    def _values_equal(
        self,
        first: Any,
        second: Any,
    ) -> bool:
        """
        Compare values after normalization.
        """

        return (
            self._normalize_value(
                first
            )
            == self._normalize_value(
                second
            )
        )

    def _values_compatible(
        self,
        *,
        existing_value: Any,
        pdf_value: Any,
    ) -> bool:
        """
        Determine whether different values are compatible.
        """

        existing_normalized = (
            self._normalize_value(
                existing_value
            )
        )

        pdf_normalized = (
            self._normalize_value(
                pdf_value
            )
        )

        if (
            existing_normalized
            == pdf_normalized
        ):
            return True

        if isinstance(
            existing_normalized,
            list,
        ) and isinstance(
            pdf_normalized,
            list,
        ):
            existing_set = {
                self._stable_json(
                    value
                )
                for value
                in existing_normalized
            }

            pdf_set = {
                self._stable_json(
                    value
                )
                for value
                in pdf_normalized
            }

            if (
                existing_set
                and pdf_set
                and (
                    existing_set.issubset(
                        pdf_set
                    )
                    or pdf_set.issubset(
                        existing_set
                    )
                )
            ):
                return True

        if isinstance(
            existing_normalized,
            str,
        ) and isinstance(
            pdf_normalized,
            str,
        ):
            if (
                len(
                    existing_normalized
                )
                >= 4
                and len(
                    pdf_normalized
                )
                >= 4
            ):
                if (
                    existing_normalized
                    in pdf_normalized
                    or pdf_normalized
                    in existing_normalized
                ):
                    return True

        return False

    def _pdf_value_is_richer(
        self,
        *,
        existing_value: Any,
        pdf_value: Any,
    ) -> bool:
        """
        Determine whether PDF provides a richer compatible value.

        Conservative rules are used to avoid accidental replacement.
        """

        if self._is_empty(
            pdf_value
        ):
            return False

        if self._is_empty(
            existing_value
        ):
            return True

        existing_normalized = (
            self._normalize_value(
                existing_value
            )
        )

        pdf_normalized = (
            self._normalize_value(
                pdf_value
            )
        )

        if (
            existing_normalized
            == pdf_normalized
        ):
            return False

        if isinstance(
            existing_normalized,
            list,
        ) and isinstance(
            pdf_normalized,
            list,
        ):
            existing_set = {
                self._stable_json(
                    value
                )
                for value
                in existing_normalized
            }

            pdf_set = {
                self._stable_json(
                    value
                )
                for value
                in pdf_normalized
            }

            return (
                existing_set
                < pdf_set
            )

        if isinstance(
            existing_normalized,
            dict,
        ) and isinstance(
            pdf_normalized,
            dict,
        ):
            existing_keys = {
                key
                for key, value
                in existing_normalized.items()
                if not self._is_empty(
                    value
                )
            }

            pdf_keys = {
                key
                for key, value
                in pdf_normalized.items()
                if not self._is_empty(
                    value
                )
            }

            return (
                existing_keys
                < pdf_keys
            )

        if isinstance(
            existing_normalized,
            str,
        ) and isinstance(
            pdf_normalized,
            str,
        ):
            if (
                existing_normalized
                in pdf_normalized
                and (
                    len(
                        pdf_normalized
                    )
                    > len(
                        existing_normalized
                    )
                    * 1.15
                )
            ):
                return True

        return False

    def _normalize_value(
        self,
        value: Any,
    ) -> Any:
        """
        Normalize values for comparison.
        """

        if value is None:
            return None

        if isinstance(
            value,
            bool,
        ):
            return value

        if isinstance(
            value,
            (int, float),
        ):
            return self._normalize_number(
                value
            )

        if isinstance(
            value,
            str,
        ):
            stripped = value.strip()

            if not stripped:
                return ""

            normalized_text = (
                self._normalize_text(
                    stripped
                )
            )

            if (
                normalized_text
                in BOOLEAN_TRUE_VALUES
            ):
                return True

            if (
                normalized_text
                in BOOLEAN_FALSE_VALUES
            ):
                return False

            numeric = (
                self._parse_numeric_string(
                    stripped
                )
            )

            if numeric is not None:
                return numeric

            return normalized_text

        if isinstance(
            value,
            list,
        ):
            normalized_items = [
                self._normalize_value(
                    item
                )
                for item in value
            ]

            unique_items: list[
                Any
            ] = []

            seen: set[str] = set()

            for item in normalized_items:
                signature = (
                    self._stable_json(
                        item
                    )
                )

                if signature in seen:
                    continue

                seen.add(
                    signature
                )

                unique_items.append(
                    item
                )

            return sorted(
                unique_items,
                key=self._stable_json,
            )

        if isinstance(
            value,
            dict,
        ):
            return {
                self._normalize_key(
                    key
                ): self._normalize_value(
                    item
                )
                for key, item
                in sorted(
                    value.items(),
                    key=lambda pair: str(
                        pair[0]
                    ),
                )
            }

        return self._normalize_text(
            str(value)
        )

    @staticmethod
    def _normalize_number(
        value: int | float,
    ) -> int | float:
        """
        Normalize whole floats into integers.
        """

        if (
            isinstance(
                value,
                float,
            )
            and value.is_integer()
        ):
            return int(
                value
            )

        return value

    @staticmethod
    def _parse_numeric_string(
        value: str,
    ) -> int | float | None:
        """
        Parse a plain numeric value with an optional known unit.
        """

        normalized = (
            value.strip()
            .replace(",", ".")
        )

        pattern = (
            r"^"
            r"([-+]?\d+(?:\.\d+)?)"
            r"\s*"
            r"(?:"
            r"ects"
            r"|credits?"
            r"|credit\s*points?"
            r"|hours?"
            r"|hrs?"
            r"|semester"
            r"|semesters"
            r")?"
            r"$"
        )

        match = re.fullmatch(
            pattern,
            normalized,
            flags=re.IGNORECASE,
        )

        if not match:
            return None

        number = float(
            match.group(1)
        )

        if number.is_integer():
            return int(
                number
            )

        return number

    # =========================================================================
    # METADATA
    # =========================================================================

    def _copy_richer_metadata(
        self,
        *,
        target: dict[str, Any],
        source: dict[str, Any],
    ) -> None:
        """
        Copy missing metadata from a richer PDF fact.
        """

        copy_if_missing = (
            "unit",
            "original_value",
            "confidence",
        )

        for key in copy_if_missing:
            if (
                self._is_empty(
                    target.get(key)
                )
                and not self._is_empty(
                    source.get(key)
                )
            ):
                target[
                    key
                ] = copy.deepcopy(
                    source.get(key)
                )

        if (
            not target.get(
                "parent_entity"
            )
            and source.get(
                "parent_entity"
            )
        ):
            target[
                "parent_entity"
            ] = copy.deepcopy(
                source[
                    "parent_entity"
                ]
            )

    def _build_pdf_support(
        self,
        *,
        pdf_fact: dict[str, Any],
        relationship: str,
        match: dict[str, Any] | None,
    ) -> dict[str, Any]:
        """
        Build a compact PDF supporting-source record.
        """

        support = {
            "relationship": (
                relationship
            ),

            "fact_id": (
                pdf_fact.get(
                    "fact_id"
                )
            ),

            "field": (
                pdf_fact.get(
                    "field"
                )
            ),

            "canonical_field": (
                pdf_fact.get(
                    "canonical_field"
                )
            ),

            "value": (
                copy.deepcopy(
                    pdf_fact.get(
                        "value"
                    )
                )
            ),

            "original_value": (
                copy.deepcopy(
                    pdf_fact.get(
                        "original_value"
                    )
                )
            ),

            "confidence": (
                pdf_fact.get(
                    "confidence"
                )
            ),

            "source": (
                self._extract_source(
                    pdf_fact
                )
            ),

            "evidence": (
                copy.deepcopy(
                    pdf_fact.get(
                        "evidence"
                    )
                )
            ),
        }

        if match is not None:
            support[
                "match"
            ] = {
                "score": (
                    match.get(
                        "score"
                    )
                ),

                "method": (
                    match.get(
                        "method"
                    )
                ),

                "reasons": (
                    copy.deepcopy(
                        match.get(
                            "reasons"
                        )
                        or []
                    )
                ),
            }

        return support

    @staticmethod
    def _extract_source(
        fact: dict[str, Any],
    ) -> dict[str, Any]:
        """
        Return a copy of source provenance.
        """

        source = fact.get(
            "source"
        )

        if isinstance(
            source,
            dict,
        ):
            return copy.deepcopy(
                source
            )

        return {
            "source_type": "pdf"
        }

    # =========================================================================
    # SIGNATURES
    # =========================================================================

    def _semantic_signature(
        self,
        fact: dict[str, Any],
    ) -> str:
        """
        Build a semantic fact signature.
        """

        entity = (
            fact.get("entity")
            or {}
        )

        parent_entity = (
            fact.get(
                "parent_entity"
            )
            or {}
        )

        entity_type = (
            self._canonical_entity_type(
                entity.get("type")
            )
        )

        entity_id = (
            self._normalize_identifier(
                entity.get("id")
            )
        )

        entity_name = (
            self._normalize_text(
                entity.get("name")
            )
        )

        parent_type = (
            self._canonical_entity_type(
                parent_entity.get(
                    "type"
                )
            )
            if parent_entity
            else ""
        )

        parent_id = (
            self._normalize_identifier(
                parent_entity.get(
                    "id"
                )
            )
        )

        parent_name = (
            self._normalize_text(
                parent_entity.get(
                    "name"
                )
            )
        )

        canonical_field = (
            fact.get(
                "canonical_field"
            )
            or self._canonical_field(
                fact.get("field")
            )
        )

        normalized_value = (
            self._normalize_value(
                fact.get("value")
            )
        )

        payload = {
            "entity_type": (
                entity_type
            ),

            "entity_id": (
                entity_id
            ),

            "entity_name": (
                entity_name
            ),

            "parent_type": (
                parent_type
            ),

            "parent_id": (
                parent_id
            ),

            "parent_name": (
                parent_name
            ),

            "field": (
                canonical_field
            ),

            "value": (
                normalized_value
            ),
        }

        return self._sha256(
            self._stable_json(
                payload
            )
        )

    def _generate_fact_id(
        self,
        *,
        prefix: str,
        fact: dict[str, Any],
        index: int,
    ) -> str:
        """
        Generate a deterministic fallback fact ID.
        """

        payload = {
            "index": index,

            "category": (
                fact.get(
                    "category"
                )
            ),

            "field": (
                fact.get(
                    "field"
                )
            ),

            "value": (
                fact.get(
                    "value"
                )
            ),

            "entity": (
                fact.get(
                    "entity"
                )
            ),
        }

        digest = self._sha256(
            self._stable_json(
                payload
            )
        )[:16]

        return (
            f"{prefix}_{digest}"
        )

    def _generate_enriched_id(
        self,
        fact: dict[str, Any],
    ) -> str:
        """
        Generate an ID for a newly added PDF fact.
        """

        signature = (
            self._semantic_signature(
                fact
            )
        )

        return (
            "enriched_pdf_"
            f"{signature[:16]}"
        )

    # =========================================================================
    # DISTRIBUTIONS AND REPORTING
    # =========================================================================

    def _build_distributions(
        self,
        facts: list[
            dict[str, Any]
        ],
    ) -> dict[str, Any]:
        """
        Build output fact distributions.
        """

        by_category = Counter()

        by_entity_type = Counter()

        by_field = Counter()

        by_canonical_field = (
            Counter()
        )

        by_enrichment_status = (
            Counter()
        )

        for fact in facts:
            by_category[
                fact.get(
                    "category"
                )
                or "other"
            ] += 1

            entity = (
                fact.get("entity")
                or {}
            )

            by_entity_type[
                entity.get(
                    "type"
                )
                or "unknown"
            ] += 1

            by_field[
                fact.get(
                    "field"
                )
                or "unknown"
            ] += 1

            by_canonical_field[
                fact.get(
                    "canonical_field"
                )
                or "unknown"
            ] += 1

            enrichment = (
                fact.get(
                    "enrichment"
                )
                or {}
            )

            by_enrichment_status[
                enrichment.get(
                    "status"
                )
                or "unknown"
            ] += 1

        return {
            "by_category": (
                self._sorted_counter(
                    by_category
                )
            ),

            "by_entity_type": (
                self._sorted_counter(
                    by_entity_type
                )
            ),

            "by_field": (
                self._sorted_counter(
                    by_field
                )
            ),

            "by_canonical_field": (
                self._sorted_counter(
                    by_canonical_field
                )
            ),

            "by_enrichment_status": (
                self._sorted_counter(
                    by_enrichment_status
                )
            ),
        }

    @staticmethod
    def _sorted_counter(
        counter: Counter,
    ) -> dict[str, int]:
        """
        Sort counts by descending count and name.
        """

        return dict(
            sorted(
                counter.items(),
                key=lambda item: (
                    -item[1],
                    str(
                        item[0]
                    ),
                ),
            )
        )

    @staticmethod
    def _collect_conflicts(
        facts: list[
            dict[str, Any]
        ],
    ) -> list[
        dict[str, Any]
    ]:
        """
        Collect all fact conflicts.
        """

        conflicts: list[
            dict[str, Any]
        ] = []

        for fact in facts:
            enrichment = (
                fact.get(
                    "enrichment"
                )
                or {}
            )

            for conflict in (
                enrichment.get(
                    "conflicts"
                )
                or []
            ):
                conflicts.append(
                    {
                        "fact_id": (
                            fact.get(
                                "fact_id"
                            )
                        ),

                        "entity": (
                            copy.deepcopy(
                                fact.get(
                                    "entity"
                                )
                            )
                        ),

                        "field": (
                            fact.get(
                                "field"
                            )
                        ),

                        "canonical_field": (
                            fact.get(
                                "canonical_field"
                            )
                        ),

                        **copy.deepcopy(
                            conflict
                        ),
                    }
                )

        return conflicts

    @staticmethod
    def _collect_enrichments(
        facts: list[
            dict[str, Any]
        ],
    ) -> list[
        dict[str, Any]
    ]:
        """
        Collect enrichment changes.
        """

        changes: list[
            dict[str, Any]
        ] = []

        for fact in facts:
            enrichment = (
                fact.get(
                    "enrichment"
                )
                or {}
            )

            for change in (
                enrichment.get(
                    "changes"
                )
                or []
            ):
                changes.append(
                    {
                        "fact_id": (
                            fact.get(
                                "fact_id"
                            )
                        ),

                        "entity": (
                            copy.deepcopy(
                                fact.get(
                                    "entity"
                                )
                            )
                        ),

                        "field": (
                            fact.get(
                                "field"
                            )
                        ),

                        "canonical_field": (
                            fact.get(
                                "canonical_field"
                            )
                        ),

                        **copy.deepcopy(
                            change
                        ),
                    }
                )

        return changes

    # =========================================================================
    # GENERAL HELPERS
    # =========================================================================

    def _reset_statistics(
        self,
    ) -> None:
        """
        Reset build statistics.
        """

        self.statistics: dict[
            str,
            int,
        ] = {
            "web_facts_loaded": 0,

            "pdf_facts_loaded": 0,

            "pdf_semantic_duplicates_removed": 0,

            "matched_pdf_facts": 0,

            "facts_confirmed": 0,

            "facts_enriched": 0,

            "conflicts_detected": 0,

            "duplicate_pdf_facts_skipped": 0,

            "new_pdf_facts_added": 0,

            "unmatched_pdf_facts": 0,

            "unmatched_pdf_facts_skipped": 0,

            "final_semantic_duplicates_removed": 0,

            "final_facts_written": 0,
        }

    @staticmethod
    def _is_empty(
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
            (list, tuple, set, dict),
        ):
            return len(value) == 0

        return False

    @staticmethod
    def _normalize_key(
        value: Any,
    ) -> str:
        """
        Normalize a key into snake_case.
        """

        if value is None:
            return ""

        text = str(
            value
        ).strip()

        if not text:
            return ""

        text = unicodedata.normalize(
            "NFKC",
            text,
        )

        text = re.sub(
            r"([a-z0-9])([A-Z])",
            r"\1_\2",
            text,
        )

        text = text.casefold()

        text = re.sub(
            r"[^a-z0-9]+",
            "_",
            text,
        )

        text = re.sub(
            r"_+",
            "_",
            text,
        )

        return text.strip(
            "_"
        )

    @staticmethod
    def _normalize_text(
        value: Any,
    ) -> str:
        """
        Normalize human-readable text for matching.
        """

        if value is None:
            return ""

        text = unicodedata.normalize(
            "NFKC",
            str(value),
        )

        text = text.casefold()

        text = text.replace(
            "–",
            "-",
        )

        text = text.replace(
            "—",
            "-",
        )

        text = re.sub(
            r"\s+",
            " ",
            text,
        )

        text = re.sub(
            r"\s*([:/,;()])\s*",
            r"\1",
            text,
        )

        return text.strip()

    @staticmethod
    def _normalize_identifier(
        value: Any,
    ) -> str:
        """
        Normalize IDs and codes conservatively.
        """

        if value is None:
            return ""

        text = unicodedata.normalize(
            "NFKC",
            str(value),
        )

        text = text.casefold()

        text = re.sub(
            r"\s+",
            "",
            text,
        )

        return text.strip()

    @staticmethod
    def _text_similarity(
        first: str,
        second: str,
    ) -> float:
        """
        Calculate a lightweight sequence similarity.
        """

        if first == second:
            return 1.0

        if (
            not first
            or not second
        ):
            return 0.0

        first_tokens = set(
            re.findall(
                r"\w+",
                first,
                flags=re.UNICODE,
            )
        )

        second_tokens = set(
            re.findall(
                r"\w+",
                second,
                flags=re.UNICODE,
            )
        )

        if (
            not first_tokens
            or not second_tokens
        ):
            return 0.0

        intersection = len(
            first_tokens
            & second_tokens
        )

        union = len(
            first_tokens
            | second_tokens
        )

        jaccard = (
            intersection
            / union
        )

        containment = (
            intersection
            / min(
                len(
                    first_tokens
                ),
                len(
                    second_tokens
                ),
            )
        )

        length_ratio = (
            min(
                len(first),
                len(second),
            )
            / max(
                len(first),
                len(second),
            )
        )

        return (
            jaccard
            * 0.45
            + containment
            * 0.40
            + length_ratio
            * 0.15
        )

    @staticmethod
    def _stable_json(
        value: Any,
    ) -> str:
        """
        Serialize data deterministically.
        """

        return json.dumps(
            value,
            ensure_ascii=False,
            sort_keys=True,
            separators=(
                ",",
                ":",
            ),
            default=str,
        )

    @staticmethod
    def _sha256(
        value: str,
    ) -> str:
        """
        Generate SHA-256.
        """

        return hashlib.sha256(
            value.encode(
                "utf-8"
            )
        ).hexdigest()

    @staticmethod
    def _append_unique(
        values: list[Any],
        new_value: Any,
    ) -> None:
        """
        Append a JSON value only when not already present.
        """

        new_signature = (
            PDFEnrichmentBuilder
            ._stable_json(
                new_value
            )
        )

        existing_signatures = {
            (
                PDFEnrichmentBuilder
                ._stable_json(
                    value
                )
            )
            for value in values
        }

        if (
            new_signature
            not in existing_signatures
        ):
            values.append(
                copy.deepcopy(
                    new_value
                )
            )

    @staticmethod
    def _utc_now(
    ) -> str:
        """
        Return an ISO-8601 UTC timestamp.
        """

        return (
            datetime.now(
                timezone.utc
            )
            .replace(
                microsecond=0
            )
            .isoformat()
            .replace(
                "+00:00",
                "Z",
            )
        )


# =============================================================================
# OPTIONAL DIRECT EXECUTION
# =============================================================================

if __name__ == "__main__":
    builder = PDFEnrichmentBuilder(
        overwrite=True,
    )

    result = builder.build(
        program_id="0001",
        page_id="0002",
        document_id="source",
    )

    summary = result[
        "summary"
    ]

    print(
        "PDF enrichment completed."
    )

    print(
        "Web facts loaded:",
        summary[
            "web_facts_loaded"
        ],
    )

    print(
        "PDF facts loaded:",
        summary[
            "pdf_facts_loaded"
        ],
    )

    print(
        "Facts confirmed:",
        summary[
            "facts_confirmed"
        ],
    )

    print(
        "Facts enriched:",
        summary[
            "facts_enriched"
        ],
    )

    print(
        "New PDF facts added:",
        summary[
            "new_pdf_facts_added"
        ],
    )

    print(
        "Conflicts detected:",
        summary[
            "conflicts_detected"
        ],
    )

    print(
        "Final facts written:",
        summary[
            "final_facts_written"
        ],
    )