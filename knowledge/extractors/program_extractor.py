import json

from knowledge.models import ProgramEvidence
from knowledge.facts import (
    FactCollection,
    ExtractedFact,
    SourceReference
)
from knowledge.llm.client import LLMClient
from knowledge.prompts import PROGRAM_EXTRACTION_PROMPT


class ProgramExtractor:

    def __init__(
        self,
        client: LLMClient
    ):

        self.client = client

    def build_user_prompt(
        self,
        program: ProgramEvidence
    ) -> str:

        return f"""
PROGRAM METADATA

{json.dumps(program.metadata, indent=2, ensure_ascii=False)}

------------------------------------------------------------

PROGRAM MARKDOWN

{program.markdown}

------------------------------------------------------------

IMPORTANT

- The source language may be German, French, Spanish, Japanese or any other language.

- Translate EVERYTHING into English.

- Never keep translated values in the original language unless they are official names.

- Extract EVERY meaningful fact.

- Never summarize.

- Never omit information because it is not in today's schema.

- Return ONLY valid JSON.
"""

    def extract(
        self,
        program: ProgramEvidence
    ) -> FactCollection:

        response = self.client.extract(

            system_prompt=PROGRAM_EXTRACTION_PROMPT,

            user_prompt=self.build_user_prompt(
                program
            )
        )

        if isinstance(response, str):
            response = json.loads(response)

        collection = FactCollection()

        for item in response.get(
            "facts",
            []
        ):

            collection.add(

                ExtractedFact(

                    category=item["category"],

                    field=item["field"],

                    value=item["value"],

                    confidence=item.get(
                        "confidence",
                        1.0
                    ),

                    source=SourceReference(

                        source_type="program",

                        source_id="program",

                        title=program.metadata.get(
                            "title",
                            ""
                        ),

                        url=program.metadata.get(
                            "url",
                            ""
                        )
                    ),

                    metadata=item.get(
                        "metadata",
                        {}
                    )
                )
            )

        return collection