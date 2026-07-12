import os
from dotenv import load_dotenv
from config import Config

from knowledge.evidence_pack_builder import (
    EvidencePackBuilder
)

from knowledge.llm.client import (
    LLMClient
)

from knowledge.llm.openai_provider import (
    OpenAIProvider
)

from knowledge.extractors.program_extractor import (
    ProgramExtractor
)

from knowledge.storage.fact_repository import (
    FactRepository
)


load_dotenv()


builder = EvidencePackBuilder()

pack = builder.build(
    "data/0001"
)


provider = OpenAIProvider(

    api_key="",
    model="gpt-4.1"
)


client = LLMClient(
    provider
)


extractor = ProgramExtractor(
    client
)


facts = extractor.extract(
    pack.program
)

repository = FactRepository()

output_path = repository.save(
    facts=facts.facts,
    output_path=(
        "data/0001/knowledge/"
        "raw_program_facts.json"
    ),
)

print()

print(
    f"✓ Raw facts saved to: "
    f"{output_path}"
)


print()

print("=" * 80)

print(f"Extracted {len(facts.facts)} facts")

print("=" * 80)

print()


for fact in facts.facts:

    print(

        f"[{fact.category}] "

        f"{fact.field} "

        f"= "

        f"{fact.value}"

    )