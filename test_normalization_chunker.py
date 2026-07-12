from knowledge.storage.fact_repository import (
    FactRepository,
)

from knowledge.normalization.normalization_chunker import (
    NormalizationChunker,
)


# ============================================================
# 1. Load previously extracted raw facts
# ============================================================

repository = FactRepository()

raw_facts = repository.load(
    "data/0001/knowledge/raw_program_facts.json"
)


print(
    f"\nLoaded {len(raw_facts)} "
    f"raw facts from JSON."
)


# ============================================================
# 2. Create normalization chunks
# ============================================================

chunker = NormalizationChunker(
    max_facts_per_chunk=30,
    max_characters_per_chunk=10_000,
)

chunks = chunker.chunk(
    raw_facts
)


# ============================================================
# 3. Display normalization chunks
# ============================================================

print("\n" + "=" * 80)

print(
    f"Generated {len(chunks)} "
    f"normalization chunks"
)

print("=" * 80)


total_chunked_facts = 0


for chunk in chunks:

    fact_count = len(
        chunk.facts
    )

    total_chunked_facts += (
        fact_count
    )

    print(
        f"\n"
        f"Chunk ID   : {chunk.chunk_id}\n"
        f"Group      : {chunk.group}\n"
        f"Order      : {chunk.order}\n"
        f"Facts      : {fact_count}\n"
        f"Characters : {chunk.character_count}"
    )

    print("-" * 80)

    for fact in chunk.facts:

        value = str(
            fact.value
        )

        if len(value) > 150:
            value = (
                value[:150]
                + "..."
            )

        print(
            f"[{fact.category}] "
            f"{fact.field} = "
            f"{value}"
        )

    print("=" * 80)


# ============================================================
# 4. Verify that no facts were lost
# ============================================================

print(
    "\nNORMALIZATION CHUNK VERIFICATION"
)

print("-" * 80)

print(
    f"Loaded raw facts : "
    f"{len(raw_facts)}"
)

print(
    f"Chunked facts    : "
    f"{total_chunked_facts}"
)

print(
    f"Difference       : "
    f"{len(raw_facts) - total_chunked_facts}"
)


if (
    len(raw_facts)
    == total_chunked_facts
):

    print(
        "\n✓ All saved facts were included "
        "in normalization chunks."
    )

else:

    print(
        "\n✗ Some facts were lost or "
        "duplicated during chunking."
    )