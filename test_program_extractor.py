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

from knowledge.billing.usage_tracker import UsageTracker


load_dotenv()


builder = EvidencePackBuilder()

program_path = "data/0001"

pack = builder.build(program_path)

program_id = program_path.split("/")[-1]


provider = OpenAIProvider(
    api_key="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",
    model="gpt-4.1"
)

tracker = UsageTracker()



client = LLMClient(
    provider=provider,
    usage_tracker=tracker,
    stage="Program Extraction",
    program_id=program_id,
)


extractor = ProgramExtractor(
    client
)


facts = extractor.extract(
    pack.program
)

tracker.print_summary()

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