from __future__ import annotations

import json
from copy import deepcopy
from dataclasses import asdict, is_dataclass
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Set, Union


class FinalOutputBuilder:
    """
    Builds final JSON files from normalized university programme facts.

    This builder is intentionally deterministic.

    Responsibilities:
    - Load normalized facts from JSON or accept facts directly.
    - Group facts into final output files.
    - Preserve every normalized fact.
    - Remove exact duplicate facts only.
    - Track handled and unhandled facts.
    - Write final JSON files.
    - Generate a build summary.

    This class does not:
    - Call an LLM.
    - Infer missing information.
    - Rename normalized fields.
    - Merge semantically similar values.
    - Reconstruct curriculum relationships.
    - Drop unsupported categories silently.
    """

    # Final output file names.
    OUTPUT_FILES: Dict[str, str] = {
        "program": "program_data.json",
        "admission": "admission_data.json",
        "curriculum": "curriculum_data.json",
        "career": "career_data.json",
        "fees": "fees_data.json",
        "scholarships": "scholarships_data.json",
        "contacts": "contacts_data.json",
        "student_life": "student_life_data.json",
        "research": "research_data.json",
        "housing": "housing_data.json",
        "visa": "visa_data.json",
        "documents": "documents_data.json",
        "statistics": "statistics_data.json",
        "other": "other_data.json",
        "unhandled": "unhandled_data.json",
        "summary": "build_summary.json",
    }

    # Maps normalized fact categories to final output sections.
    #
    # Identity and overview belong to program_data.
    # Language is grouped with admission because language requirements and
    # language of instruction are commonly required during programme discovery.
    # Curriculum and modules belong to curriculum_data.
    CATEGORY_TO_SECTION: Dict[str, str] = {
        "identity": "program",
        "overview": "program",

        "admission": "admission",
        "language": "admission",

        "curriculum": "curriculum",
        "modules": "curriculum",

        "career": "career",

        "fees": "fees",
        "scholarships": "scholarships",

        "contacts": "contacts",
        "student_life": "student_life",
        "research": "research",

        "housing": "housing",
        "visa": "visa",

        "documents": "documents",
        "statistics": "statistics",

        "faculty": "program",
        "other": "other",
    }

    def __init__(
        self,
        output_directory: Union[str, Path] = "final",
        write_empty_files: bool = False,
        indent: int = 2,
    ) -> None:
        """
        Args:
            output_directory:
                Directory where final JSON files will be written.

            write_empty_files:
                If True, create JSON files even when a section has no facts.
                If False, write only sections containing data.

            indent:
                Number of spaces used for JSON indentation.
        """

        self.output_directory = Path(output_directory)
        self.write_empty_files = write_empty_files
        self.indent = indent

    def build_from_file(
        self,
        input_file: Union[str, Path],
        program_id: Optional[str] = None,
        program_name: Optional[str] = None,
        write_files: bool = True,
    ) -> Dict[str, Any]:
        """
        Load normalized facts from a JSON file and build final output.

        Supported input shapes:

        1. Object containing a facts array:

            {
                "facts": [
                    {
                        "category": "identity",
                        "field": "program_name",
                        "value": "Egyptology and Coptology"
                    }
                ]
            }

        2. Direct list of facts:

            [
                {
                    "category": "identity",
                    "field": "program_name",
                    "value": "Egyptology and Coptology"
                }
            ]

        Args:
            input_file:
                Path to normalized facts JSON.

            program_id:
                Optional programme identifier.

            program_name:
                Optional programme name. If omitted, the builder attempts
                to find it from identity facts.

            write_files:
                Whether final JSON files should be written.

        Returns:
            Complete in-memory build result.
        """

        input_path = Path(input_file)

        if not input_path.exists():
            raise FileNotFoundError(
                f"Normalized facts file was not found: {input_path}"
            )

        with input_path.open(
            "r",
            encoding="utf-8",
        ) as file:
            payload = json.load(file)

        facts = self._extract_facts_from_payload(payload)

        return self.build(
            facts=facts,
            program_id=program_id,
            program_name=program_name,
            source_file=str(input_path),
            write_files=write_files,
        )

    def build(
        self,
        facts: Iterable[Any],
        program_id: Optional[str] = None,
        program_name: Optional[str] = None,
        source_file: Optional[str] = None,
        write_files: bool = True,
    ) -> Dict[str, Any]:
        """
        Build final output from normalized facts.

        Args:
            facts:
                Iterable containing dictionaries or ExtractedFact objects.

            program_id:
                Optional programme identifier.

            program_name:
                Optional programme name.

            source_file:
                Optional path of the normalized source file.

            write_files:
                Whether output JSON files should be written.

        Returns:
            Dictionary containing:
            - generated section data;
            - build summary;
            - output file paths.
        """

        normalized_facts = [
            self._fact_to_dictionary(fact)
            for fact in facts
        ]

        input_fact_count = len(normalized_facts)

        unique_facts, duplicate_count = self._remove_exact_duplicates(
            normalized_facts
        )

        resolved_program_name = (
            program_name
            or self._find_program_name(unique_facts)
        )

        grouped_facts: Dict[str, List[Dict[str, Any]]] = {
            section: []
            for section in self.OUTPUT_FILES
            if section not in {
                "summary",
                "unhandled",
            }
        }

        unhandled_facts: List[Dict[str, Any]] = []

        handled_fact_count = 0

        for fact in unique_facts:
            subcategory = fact.get("subcategory", "")
            section = self.CATEGORY_TO_SECTION.get(subcategory)

            if section is None:
                unhandled_facts.append(
                    deepcopy(fact)
                )
                continue

            grouped_facts[section].append(
                deepcopy(fact)
            )

            handled_fact_count += 1

        section_outputs = self._build_section_outputs(
            grouped_facts=grouped_facts,
            program_id=program_id,
            program_name=resolved_program_name,
        )

        output_file_paths: Dict[str, str] = {}

        if write_files:
            self.output_directory.mkdir(
                parents=True,
                exist_ok=True,
            )

            output_file_paths = self._write_section_files(
                section_outputs
            )

            if unhandled_facts:
                unhandled_output = {
                    "program_id": program_id,
                    "program_name": resolved_program_name,
                    "facts": unhandled_facts,
                }

                unhandled_path = self._write_json(
                    self.OUTPUT_FILES["unhandled"],
                    unhandled_output,
                )

                output_file_paths["unhandled"] = str(
                    unhandled_path
                )

        written_fact_count = (
            handled_fact_count
            + len(unhandled_facts)
        )

        dropped_fact_count = (
            len(unique_facts)
            - written_fact_count
        )

        summary = {
            "status": (
                "success"
                if dropped_fact_count == 0
                else "warning"
            ),
            "program_id": program_id,
            "program_name": resolved_program_name,
            "source_file": source_file,
            "output_directory": str(
                self.output_directory
            ),
            "input_fact_count": input_fact_count,
            "unique_fact_count": len(unique_facts),
            "exact_duplicate_count": duplicate_count,
            "handled_fact_count": handled_fact_count,
            "unhandled_fact_count": len(
                unhandled_facts
            ),
            "written_fact_count": written_fact_count,
            "dropped_fact_count": dropped_fact_count,
            "section_fact_counts": {
                section: len(facts_in_section)
                for section, facts_in_section
                in grouped_facts.items()
            },
            "generated_files": {},
        }

        if write_files:
            summary_path = (
                self.output_directory
                / self.OUTPUT_FILES["summary"]
            )

            # Include the summary path before writing the summary.
            output_file_paths["summary"] = str(
                summary_path
            )

            summary["generated_files"] = (
                output_file_paths
            )

            self._write_json(
                self.OUTPUT_FILES["summary"],
                summary,
            )

        return {
            "sections": section_outputs,
            "unhandled_facts": unhandled_facts,
            "summary": summary,
            "output_files": output_file_paths,
        }

    def _extract_facts_from_payload(
        self,
        payload: Any,
    ) -> List[Any]:
        """
        Extract a fact list from supported JSON structures.
        """

        if isinstance(payload, list):
            return payload

        if isinstance(payload, dict):
            facts = payload.get("facts")

            if isinstance(facts, list):
                return facts

        raise ValueError(
            "Invalid normalized facts JSON. Expected either "
            "a list of facts or an object containing a "
            "'facts' list."
        )

    def _fact_to_dictionary(
        self,
        fact: Any,
    ) -> Dict[str, Any]:
        """
        Convert an ExtractedFact dataclass or dictionary into a
        validated dictionary.
        """

        if is_dataclass(fact):
            fact = asdict(fact)

        if not isinstance(fact, dict):
            raise TypeError(
                "Every fact must be a dictionary or dataclass. "
                f"Received: {type(fact).__name__}"
            )

        category = fact.get("category")
        subcategory = fact.get("subcategory")
        
        # Backwards compatibility
        if category not in ["university", "programme"]:
            subcategory = subcategory or category
            category = "programme"
            
        field = fact.get("field")

        if not isinstance(category, str) or not category.strip():
            raise ValueError("Fact category cannot be empty.")

        if not isinstance(field, str) or not field.strip():
            raise ValueError("Fact field cannot be empty.")

        if "value" not in fact:
            raise ValueError("Every fact must contain a 'value' property.")

        metadata = fact.get("metadata", {})
        if not isinstance(metadata, dict):
            metadata = {"original_metadata": metadata}

        normalized_fact = {
            "category": category.strip().lower(),
            "subcategory": subcategory.strip().lower() if subcategory else "other",
            "field": field.strip().lower(),
            "value": deepcopy(fact.get("value")),
            "confidence": fact.get("confidence", 1.0),
            "source_url": fact.get("source_url", ""),
            "source_type": fact.get("source_type", ""),
            "programme_association": fact.get("programme_association", ""),
            "metadata": deepcopy(metadata),
        }

        # Backwards compatibility for 'source' dict
        if fact.get("source") is not None:
            normalized_fact["source"] = deepcopy(fact["source"])

        return normalized_fact

    def _remove_exact_duplicates(
        self,
        facts: List[Dict[str, Any]],
    ) -> tuple[List[Dict[str, Any]], int]:
        """
        Remove exact duplicate facts.

        A duplicate must have the same:
        - category;
        - field;
        - value;
        - confidence;
        - metadata;
        - source.

        Facts with the same field but different values are preserved.
        """

        unique_facts: List[Dict[str, Any]] = []
        seen: Set[str] = set()

        duplicate_count = 0

        for fact in facts:
            signature = json.dumps(
                fact,
                ensure_ascii=False,
                sort_keys=True,
                default=str,
            )

            if signature in seen:
                duplicate_count += 1
                continue

            seen.add(signature)

            unique_facts.append(
                deepcopy(fact)
            )

        return unique_facts, duplicate_count

    def _find_program_name(
        self,
        facts: List[Dict[str, Any]],
    ) -> Optional[str]:
        """
        Attempt to find the programme name from normalized facts.
        """

        preferred_fields = (
            "program_name",
            "programme_name",
            "name",
        )

        preferred_categories = (
            "identity",
            "overview",
        )

        for category in preferred_categories:
            for preferred_field in preferred_fields:
                for fact in facts:
                    if (
                        fact.get("subcategory") == category
                        and fact.get("field") == preferred_field
                    ):
                        value = fact.get("value")

                        if isinstance(value, str):
                            return value

        return None

    def _build_section_outputs(
        self,
        grouped_facts: Dict[
            str,
            List[Dict[str, Any]]
        ],
        program_id: Optional[str],
        program_name: Optional[str],
    ) -> Dict[str, Dict[str, Any]]:
        """
        Build final JSON objects for each output section.
        """

        outputs: Dict[str, Dict[str, Any]] = {}

        for section, facts in grouped_facts.items():
            u_facts = [f for f in facts if f.get("category") == "university"]
            p_facts = [f for f in facts if f.get("category") == "programme"]
            
            outputs[section] = {
                "program_id": program_id,
                "program_name": program_name,
                "fact_count": len(facts),
                "university_facts": u_facts,
                "programme_facts": p_facts,
            }

        return outputs

    def _write_section_files(
        self,
        section_outputs: Dict[
            str,
            Dict[str, Any]
        ],
    ) -> Dict[str, str]:
        """
        Write populated section outputs to JSON files.
        """

        output_paths: Dict[str, str] = {}

        for section, output in section_outputs.items():
            u_facts = output.get("university_facts", [])
            p_facts = output.get("programme_facts", [])

            if (
                not u_facts and not p_facts
                and not self.write_empty_files
            ):
                continue

            file_name = self.OUTPUT_FILES[section]

            output_path = self._write_json(
                file_name,
                output,
            )

            output_paths[section] = str(
                output_path
            )

        return output_paths

    def _write_json(
        self,
        file_name: str,
        payload: Dict[str, Any],
    ) -> Path:
        """
        Write JSON safely using UTF-8 encoding.
        """

        output_path = (
            self.output_directory
            / file_name
        )

        with output_path.open(
            "w",
            encoding="utf-8",
        ) as file:
            json.dump(
                payload,
                file,
                ensure_ascii=False,
                indent=self.indent,
                default=str,
            )

            file.write("\n")

        return output_path