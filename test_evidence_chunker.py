from knowledge.chunking.evidence_chunker import (
    EvidenceChunker,
)
from knowledge.evidence_pack_builder import (
    EvidencePackBuilder,
)


builder = EvidencePackBuilder()

pack = builder.build(
    "data/0001"
)

chunker = EvidenceChunker(
    max_characters=14_000,
    minimum_chunk_characters=500,
)

chunks = chunker.chunk(
    content=pack.program.markdown,
    source_type="program",
)


print("\n" + "=" * 80)
print(
    f"Generated {len(chunks)} chunks"
)
print("=" * 80)


for chunk in chunks:

    print(
        f"\n"
        f"Chunk ID : {chunk.chunk_id}\n"
        f"Title    : {chunk.title}\n"
        f"Order    : {chunk.order}\n"
        f"Characters: {len(chunk.content)}"
    )

    print("-" * 80)

    preview = chunk.content[:500]

    print(preview)

    if len(chunk.content) > 500:
        print("\n...")

    print("=" * 80)