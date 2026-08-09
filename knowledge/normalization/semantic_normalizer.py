from __future__ import annotations

import json
from typing import Any

from knowledge.facts import (
    ExtractedFact,
    FactCollection,
)

from knowledge.llm.client import (
    LLMClient,
)

from knowledge.prompts import (
    FACT_NORMALIZATION_PROMPT,
)

from knowledge.normalization.normalization_chunker import (
    NormalizationChunk,
    NormalizationChunker,
)


class SemanticNormalizer:
    """
    Normalizes extracted university facts using an LLM.

    Each normalization chunk is processed independently.
    The normalized responses are converted back into
    ExtractedFact objects and returned as one collection.
    """

    def __init__(
        self,
        client: LLMClient,
    ):
        self.client = client

    def normalize(
        self,
        chunks: list[NormalizationChunk],
    ) -> FactCollection:
        """
        Normalize all supplied chunks.

        Args:
            chunks:
                Semantic normalization chunks created by
                NormalizationChunker.

        Returns:
            One FactCollection containing all normalized
            facts from every chunk.
        """

        if not isinstance(
            chunks,
            list,
        ):
            raise TypeError(
                "chunks must be a list."
            )

        normalized_collection = (
            FactCollection()
        )

        total_chunks = len(chunks)

        print(
            f"\nNormalizing "
            f"{total_chunks} chunks..."
        )

        for index, chunk in enumerate(
            chunks,
            start=1,
        ):
            print(
                f"\n[{index}/{total_chunks}] "
                f"{chunk.chunk_id} "
                f"({chunk.group})"
            )

            normalized_facts = (
                self.normalize_chunk(
                    chunk
                )
            )

            for fact in normalized_facts:
                normalized_collection.add(
                    fact
                )

            print(
                f"✓ Normalized "
                f"{len(normalized_facts)} facts"
            )

        return normalized_collection

    def normalize_chunk(
        self,
        chunk: NormalizationChunk,
    ) -> list[ExtractedFact]:
        """
        Normalize one chunk through the configured
        LLM provider.
        """

        if not isinstance(
            chunk,
            NormalizationChunk,
        ):
            raise TypeError(
                "chunk must be a "
                "NormalizationChunk."
            )

        user_prompt = (
            self._build_user_prompt(
                chunk
            )
        )

        response = self.client.extract(
            system_prompt=(
                FACT_NORMALIZATION_PROMPT
            ),
            user_prompt=user_prompt,
            response_schema={
                "type": "json_object"
            },
            temperature=0.0,
        )

        raw_facts = response.get(
            "facts",
            [],
        )

        if not isinstance(
            raw_facts,
            list,
        ):
            raise ValueError(
                "Normalized response field "
                "'facts' must be a list."
            )

        normalized_facts = []

        for index, fact_data in enumerate(
            raw_facts,
            start=1,
        ):
            try:
                fact = self._dict_to_fact(
                    fact_data
                )

            except (
                TypeError,
                ValueError,
            ) as error:
                raise ValueError(
                    "Invalid normalized fact "
                    f"at position {index} in "
                    f"{chunk.chunk_id}: {error}"
                ) from error

            normalized_facts.append(
                fact
            )

        if (
            chunk.facts
            and not normalized_facts
        ):
            raise ValueError(
                "The normalizer returned no facts "
                f"for non-empty chunk "
                f"{chunk.chunk_id}."
            )

        return normalized_facts

    @staticmethod
    def _build_user_prompt(
        chunk: NormalizationChunk,
    ) -> str:
        """
        Serialize one normalization chunk for the model.
        """

        chunk_data = (
            NormalizationChunker
            .chunk_to_dict(
                chunk
            )
        )

        serialized_chunk = json.dumps(
            chunk_data,
            ensure_ascii=False,
            indent=2,
            default=str,
        )

        return (
            "Normalize the following extracted "
            "university programme fact chunk.\n\n"
            "Important:\n"
            "- Normalize only the supplied facts.\n"
            "- Preserve all meaningful information.\n"
            "- Preserve source and metadata.\n"
            "- Return only valid JSON with a "
            "top-level 'facts' array.\n\n"
            "INPUT CHUNK:\n\n"
            f"{serialized_chunk}"
        )

    @staticmethod
    def _dict_to_fact(
        data: dict[str, Any],
    ) -> ExtractedFact:
        """
        Convert one normalized JSON object into an
        ExtractedFact.
        """

        if not isinstance(data, dict):
            raise TypeError("Normalized fact must be a JSON object.")

        category = data.get("category", "")
        subcategory = data.get("subcategory", "")
        field = data.get("field", "")

        if not isinstance(category, str) or not category.strip():
            raise ValueError("Missing or invalid category.")

        if not isinstance(subcategory, str) or not subcategory.strip():
            raise ValueError("Missing or invalid subcategory.")

        if not isinstance(field, str) or not field.strip():
            raise ValueError("Missing or invalid field.")

        if "value" not in data:
            raise ValueError("Missing value.")

        confidence = data.get("confidence", 1.0)
        try:
            confidence = float(confidence)
        except (TypeError, ValueError) as error:
            raise ValueError("Confidence must be numeric.") from error
            
        confidence = max(0.0, min(confidence, 1.0))

        metadata = data.get("metadata", {})
        if metadata is None:
            metadata = {}

        if not isinstance(metadata, dict):
            raise ValueError("Metadata must be an object.")

        return ExtractedFact(
            category=category.strip().lower(),
            subcategory=subcategory.strip().lower(),
            field=field.strip().lower(),
            value=data["value"],
            confidence=confidence,
            source_url=data.get("source_url", ""),
            source_type=data.get("source_type", ""),
            programme_association=data.get("programme_association", ""),
            metadata=metadata,
        )
