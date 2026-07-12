import json
from typing import Any

from knowledge.models import ProgramEvidence
from knowledge.facts import (
    FactCollection,
    ExtractedFact,
    SourceReference,
)
from knowledge.llm.client import LLMClient
from knowledge.prompts import PROGRAM_EXTRACTION_PROMPT
from knowledge.chunking.evidence_chunker import (
    EvidenceChunk,
    EvidenceChunker,
)


class ProgramExtractor:

    def __init__(
        self,
        client: LLMClient,
        chunker: EvidenceChunker | None = None,
    ):
        self.client = client

        self.chunker = (
            chunker
            if chunker is not None
            else EvidenceChunker(
                max_characters=14_000,
                minimum_chunk_characters=500,
            )
        )

    def build_user_prompt(
        self,
        program: ProgramEvidence,
        chunk: EvidenceChunk,
    ) -> str:

        return f"""
PROGRAM METADATA

{json.dumps(
    program.metadata,
    indent=2,
    ensure_ascii=False,
)}

------------------------------------------------------------

CURRENT EVIDENCE CHUNK

Chunk ID: {chunk.chunk_id}
Chunk title: {chunk.title}
Chunk position: {chunk.order + 1}

------------------------------------------------------------

PROGRAM SOURCE CONTENT

{chunk.content}

------------------------------------------------------------

IMPORTANT

- Extract facts only from the supplied evidence chunk.

- Use the programme metadata only as supporting source context.

- The source language may be German, French, Spanish,
  Japanese, or any other language.

- Translate every user-facing extracted value into English.

- Extract every meaningful fact from this chunk.

- Do not summarize.

- Do not omit information because it is not part of the
  current database schema.

- Do not invent information.

- Do not create a fact merely because it appears in the
  programme metadata.

- Return only valid JSON.
"""

    def extract(
        self,
        program: ProgramEvidence,
    ) -> FactCollection:

        chunks = self.chunker.chunk(
            content=program.markdown,
            source_type="program",
        )

        collection = FactCollection()

        seen_facts: set[str] = set()

        print(
            f"\nExtracting program data from "
            f"{len(chunks)} evidence chunks...\n"
        )

        for index, chunk in enumerate(
            chunks,
            start=1,
        ):
            print(
                f"[{index}/{len(chunks)}] "
                f"{chunk.title}"
            )

            try:
                response = self.client.extract(
                    system_prompt=(
                        PROGRAM_EXTRACTION_PROMPT
                    ),
                    user_prompt=self.build_user_prompt(
                        program=program,
                        chunk=chunk,
                    ),
                )

                response = self._parse_response(
                    response
                )

                facts = response.get(
                    "facts",
                    [],
                )

                if not isinstance(facts, list):
                    raise ValueError(
                        "The LLM response field "
                        "'facts' must be a list."
                    )

                added_count = 0

                for item in facts:

                    if not isinstance(item, dict):
                        continue

                    if not self._is_valid_fact(
                        item
                    ):
                        continue

                    fact_key = (
                        self._create_fact_key(
                            item
                        )
                    )

                    if fact_key in seen_facts:
                        continue

                    seen_facts.add(
                        fact_key
                    )

                    fact_metadata = dict(
                        item.get(
                            "metadata",
                            {}
                        )
                    )

                    fact_metadata.update(
                        {
                            "chunk_id": (
                                chunk.chunk_id
                            ),
                            "chunk_title": (
                                chunk.title
                            ),
                            "chunk_order": (
                                chunk.order
                            ),
                        }
                    )

                    collection.add(
                        ExtractedFact(
                            category=item[
                                "category"
                            ],
                            field=item[
                                "field"
                            ],
                            value=item[
                                "value"
                            ],
                            confidence=item.get(
                                "confidence",
                                1.0,
                            ),
                            source=(
                                SourceReference(
                                    source_type=(
                                        "program"
                                    ),
                                    source_id=(
                                        chunk.chunk_id
                                    ),
                                    title=(
                                        program.metadata.get(
                                            "title",
                                            "",
                                        )
                                    ),
                                    url=(
                                        program.metadata.get(
                                            "url",
                                            "",
                                        )
                                    ),
                                )
                            ),
                            metadata=(
                                fact_metadata
                            ),
                        )
                    )

                    added_count += 1

                print(
                    f"  Extracted: "
                    f"{len(facts)} facts"
                )

                print(
                    f"  Added: "
                    f"{added_count} unique facts"
                )

            except Exception as error:

                print(
                    f"  ERROR: "
                    f"{type(error).__name__}: "
                    f"{error}"
                )

        print(
            "\nProgram extraction completed."
        )

        return collection

    def _parse_response(
        self,
        response: Any,
    ) -> dict:

        if isinstance(
            response,
            str,
        ):
            response = json.loads(
                response
            )

        if not isinstance(
            response,
            dict,
        ):
            raise ValueError(
                "The LLM response must be "
                "a JSON object."
            )

        return response

    def _is_valid_fact(
        self,
        item: dict,
    ) -> bool:

        required_fields = (
            "category",
            "field",
            "value",
        )

        for required_field in (
            required_fields
        ):
            if required_field not in item:
                return False

        if not isinstance(
            item["category"],
            str,
        ):
            return False

        if not isinstance(
            item["field"],
            str,
        ):
            return False

        if not item[
            "category"
        ].strip():
            return False

        if not item[
            "field"
        ].strip():
            return False

        if item[
            "value"
        ] is None:
            return False

        return True

    def _create_fact_key(
        self,
        item: dict,
    ) -> str:

        normalized_value = json.dumps(
            item["value"],
            ensure_ascii=False,
            sort_keys=True,
            default=str,
        )

        return (
            f"{item['category'].strip().lower()}"
            f"|{item['field'].strip().lower()}"
            f"|{normalized_value}"
        )