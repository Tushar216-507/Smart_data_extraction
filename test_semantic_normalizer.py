from dotenv import load_dotenv

from config import Config

from knowledge.llm.client import (
    LLMClient,
)

from knowledge.llm.groq_provider import (
    GroqProvider,
)

from knowledge.normalization.normalization_chunker import (
    NormalizationChunker,
)

from knowledge.normalization.semantic_normalizer import (
    SemanticNormalizer,
)

from knowledge.storage.fact_repository import (
    FactRepository,
)

from knowledge.llm.nvidia_provider import (
    NvidiaProvider,
)

from knowledge.llm.fallback_provider import (
    FallbackProvider,
)


# ============================================================
# 1. Load environment variables
# ============================================================

load_dotenv()


# ============================================================
# 2. File paths
# ============================================================

RAW_FACTS_PATH = (
    "data/0001/knowledge/"
    "raw_program_facts.json"
)

NORMALIZED_FACTS_PATH = (
    "data/0001/knowledge/"
    "normalized_program_facts.json"
)


# ============================================================
# 3. Load previously extracted GPT-4.1 facts
# ============================================================

repository = FactRepository()

raw_facts = repository.load(
    RAW_FACTS_PATH
)


print()

print("=" * 80)

print(
    f"Loaded {len(raw_facts)} "
    f"raw facts"
)

print("=" * 80)


# ============================================================
# 4. Create safe normalization chunks
# ============================================================

chunker = NormalizationChunker(
    max_facts_per_chunk=30,
    max_characters_per_chunk=6_000,
)

chunks = chunker.chunk(
    raw_facts
)


print()

print(
    f"Generated {len(chunks)} "
    f"normalization chunks"
)


for chunk in chunks:

    print(
        f"- {chunk.chunk_id}"
        f" | group={chunk.group}"
        f" | facts={len(chunk.facts)}"
        f" | characters="
        f"{chunk.character_count}"
    )


# ============================================================
# 5. Configure Groq
# ============================================================

groq_provider = GroqProvider(
    api_key=Config.GROQ_API_KEY,
    model=Config.GROQ_MODEL,
)


nvidia_provider = NvidiaProvider(
    api_key=Config.NVIDIA_API_KEY,
    model=Config.NVIDIA_MODEL,
    max_tokens=4096,
)


provider = FallbackProvider(
    primary_provider=groq_provider,
    fallback_provider=nvidia_provider,
)


client = LLMClient(
    provider
)


# ============================================================
# 6. Create semantic normalizer
# ============================================================

normalizer = SemanticNormalizer(
    client
)


# ============================================================
# 7. Normalize all chunks
# ============================================================

normalized_facts = normalizer.normalize(
    chunks
)


# ============================================================
# 8. Save normalized facts
# ============================================================

output_path = repository.save(
    facts=normalized_facts.facts,
    output_path=NORMALIZED_FACTS_PATH,
)


# ============================================================
# 9. Display summary
# ============================================================

print()

print("=" * 80)

print("NORMALIZATION COMPLETED")

print("=" * 80)

print(
    f"Raw facts        : "
    f"{len(raw_facts)}"
)

print(
    f"Normalized facts : "
    f"{len(normalized_facts.facts)}"
)

print(
    f"Difference       : "
    f"{(
        len(normalized_facts.facts)
        - len(raw_facts)
    )}"
)

print(
    f"Output file      : "
    f"{output_path}"
)


# ============================================================
# 10. Display normalized facts
# ============================================================

print()

print("=" * 80)

print("NORMALIZED FACTS")

print("=" * 80)


for fact in normalized_facts.facts:

    value = str(
        fact.value
    )

    if len(value) > 300:

        value = (
            value[:300]
            + "..."
        )

    print()

    print(
        f"[{fact.category}] "
        f"{fact.field} "
        f"= "
        f"{value}"
    )

    print(
        f"Confidence: "
        f"{fact.confidence}"
    )

    if fact.source is not None:

        print(
            f"Source: "
            f"{fact.source.source_type}"
            f"/"
            f"{fact.source.source_id}"
        )