from knowledge.evidence_pack_builder import (
    EvidencePackBuilder
)

builder = EvidencePackBuilder()

pack = builder.build(
    "data/0001"
)

print()

print("University :", pack.university)

print("Program    :", pack.program_name)

print("Pages      :", len(pack.pages))

print("PDFs       :", len(pack.pdfs))

print()

for page in pack.pages:

    print(
        page.category,
        "-",
        page.title
    )

print()

for pdf in pack.pdfs:

    print(
        pdf.category,
        "-",
        pdf.title
    )