from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

from knowledge.facts import ExtractedFact


@dataclass
class NormalizationChunk:
    """
    A group of related extracted facts prepared for
    semantic normalization.

    Attributes:
        chunk_id:
            Stable identifier for the normalization chunk.

        group:
            Logical normalization group, such as
            identity_overview or admission_language.

        facts:
            Raw extracted facts assigned to this chunk.

        order:
            Original order of the normalization chunk.

        character_count:
            Approximate serialized JSON size of the facts.
    """

    chunk_id: str
    group: str
    facts: list[ExtractedFact]
    order: int
    character_count: int


class NormalizationChunker:
    """
    Groups extracted facts by semantic category and then
    splits oversized groups into safe normalization chunks.

    This prevents sending the complete extraction result to
    the normalization model in one large request.
    """

    CATEGORY_GROUPS = {
        "identity": "identity_overview",
        "overview": "identity_overview",
        "statistics": "identity_overview",

        "admission": "admission_language",
        "language": "admission_language",
        "required_language_skills": (
            "admission_language"
        ),
        "visa": "admission_language",

        "career": "career_research",
        "skills_developed": "career_research",
        "research": "career_research",

        "fees": "fees_student_support",
        "scholarships": "fees_student_support",
        "housing": "fees_student_support",
        "student_life": "fees_student_support",

        "faculty": "institution_contacts",
        "contacts": "institution_contacts",
        "documents": "institution_contacts",
        "other": "institution_contacts",

        "curriculum": "curriculum",
        "modules": "curriculum",
    }

    GROUP_ORDER = [
        "identity_overview",
        "admission_language",
        "career_research",
        "fees_student_support",
        "institution_contacts",
        "curriculum",
        "uncategorized",
    ]

    def __init__(
        self,
        max_facts_per_chunk: int = 30,
        max_characters_per_chunk: int = 10_000,
    ):
        if max_facts_per_chunk <= 0:
            raise ValueError(
                "max_facts_per_chunk must be "
                "greater than zero."
            )

        if max_characters_per_chunk <= 0:
            raise ValueError(
                "max_characters_per_chunk must be "
                "greater than zero."
            )

        self.max_facts_per_chunk = (
            max_facts_per_chunk
        )

        self.max_characters_per_chunk = (
            max_characters_per_chunk
        )

    def chunk(
        self,
        facts: list[ExtractedFact],
    ) -> list[NormalizationChunk]:
        """
        Group facts semantically and split large groups.

        Args:
            facts:
                Extracted facts produced by the extraction
                pipeline.

        Returns:
            Ordered normalization chunks.
        """

        if not isinstance(facts, list):
            raise TypeError(
                "facts must be a list."
            )

        grouped_facts = self._group_facts(
            facts
        )

        chunks: list[NormalizationChunk] = []

        for group in self.GROUP_ORDER:

            group_facts = grouped_facts.get(
                group,
                [],
            )

            if not group_facts:
                continue

            group_chunks = self._split_group(
                group=group,
                facts=group_facts,
            )

            chunks.extend(
                group_chunks
            )

        for index, chunk in enumerate(
            chunks,
            start=1,
        ):
            chunk.chunk_id = (
                f"normalization_{index:04d}"
            )

            chunk.order = index - 1

        return chunks

    def _group_facts(
        self,
        facts: list[ExtractedFact],
    ) -> dict[str, list[ExtractedFact]]:
        """
        Group facts according to their current category.

        Known invalid categories produced by the extraction
        model are mapped to their intended semantic groups.
        """

        grouped: dict[
            str,
            list[ExtractedFact],
        ] = {
            group: []
            for group in self.GROUP_ORDER
        }

        for fact in facts:

            category = self._get_subcategory(
                fact
            )

            group = self.CATEGORY_GROUPS.get(
                category,
                "uncategorized",
            )

            grouped[group].append(
                fact
            )

        return grouped

    def _split_group(
        self,
        group: str,
        facts: list[ExtractedFact],
    ) -> list[NormalizationChunk]:
        """
        Split one semantic group using both fact-count and
        serialized-character limits.
        """

        chunks: list[NormalizationChunk] = []

        current_facts: list[
            ExtractedFact
        ] = []

        current_character_count = 0

        for fact in facts:

            fact_character_count = (
                self._fact_character_count(
                    fact
                )
            )

            exceeds_fact_limit = (
                len(current_facts)
                >= self.max_facts_per_chunk
            )

            exceeds_character_limit = (
                current_facts
                and (
                    current_character_count
                    + fact_character_count
                    > self.max_characters_per_chunk
                )
            )

            if (
                exceeds_fact_limit
                or exceeds_character_limit
            ):
                chunks.append(
                    self._create_chunk(
                        group=group,
                        facts=current_facts,
                        order=len(chunks),
                    )
                )

                current_facts = []
                current_character_count = 0

            current_facts.append(
                fact
            )

            current_character_count += (
                fact_character_count
            )

        if current_facts:
            chunks.append(
                self._create_chunk(
                    group=group,
                    facts=current_facts,
                    order=len(chunks),
                )
            )

        return chunks

    def _create_chunk(
        self,
        group: str,
        facts: list[ExtractedFact],
        order: int,
    ) -> NormalizationChunk:
        """
        Create one normalization chunk.
        """

        character_count = sum(
            self._fact_character_count(
                fact
            )
            for fact in facts
        )

        return NormalizationChunk(
            chunk_id="",
            group=group,
            facts=list(facts),
            order=order,
            character_count=character_count,
        )

    def _get_subcategory(
        self,
        fact: ExtractedFact,
    ) -> str:
        """
        Return a normalized category value.
        """

        category = getattr(
            fact,
            "subcategory",
            "",
        )

        if not isinstance(
            category,
            str,
        ):
            return ""

        return (
            category
            .strip()
            .lower()
        )

    def _fact_character_count(
        self,
        fact: ExtractedFact,
    ) -> int:
        """
        Estimate the serialized size of one fact.
        """

        serialized_fact = (
            self.fact_to_dict(
                fact
            )
        )

        return len(
            json.dumps(
                serialized_fact,
                ensure_ascii=False,
                sort_keys=True,
                default=str,
            )
        )

    @staticmethod
    def fact_to_dict(
        fact: ExtractedFact,
    ) -> dict[str, Any]:
        """
        Convert an ExtractedFact into a JSON-safe dictionary.

        Source metadata is retained because it may help the
        normalizer preserve traceability.
        """

        source = getattr(
            fact,
            "source",
            None,
        )

        source_data = None

        if source is not None:

            source_data = {
                "source_type": getattr(
                    source,
                    "source_type",
                    None,
                ),
                "source_id": getattr(
                    source,
                    "source_id",
                    None,
                ),
                "title": getattr(
                    source,
                    "title",
                    None,
                ),
                "url": getattr(
                    source,
                    "url",
                    None,
                ),
            }

        metadata = getattr(
            fact,
            "metadata",
            {},
        )

        if not isinstance(
            metadata,
            dict,
        ):
            metadata = {}

        return {
            "category": getattr(
                fact,
                "category",
                "",
            ),
            "field": getattr(
                fact,
                "field",
                "",
            ),
            "value": getattr(
                fact,
                "value",
                None,
            ),
            "confidence": getattr(
                fact,
                "confidence",
                1.0,
            ),
            "source": source_data,
            "metadata": metadata,
        }

    @staticmethod
    def chunk_to_dict(
        chunk: NormalizationChunk,
    ) -> dict[str, Any]:
        """
        Convert a complete normalization chunk into a
        JSON-safe dictionary.
        """

        return {
            "chunk_id": chunk.chunk_id,
            "group": chunk.group,
            "order": chunk.order,
            "character_count": (
                chunk.character_count
            ),
            "facts": [
                NormalizationChunker.fact_to_dict(
                    fact
                )
                for fact in chunk.facts
            ],
        }