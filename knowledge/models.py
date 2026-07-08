from dataclasses import dataclass, field
from typing import List, Dict, Any


@dataclass
class EvidencePage:
    id: str
    title: str
    category: str
    type: str
    markdown: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class PdfEvidence:
    id: str
    title: str
    category: str
    pdf_path: str
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class EvidencePack:
    university: str
    program_name: str
    program_markdown: str

    program_metadata: Dict[str, Any]

    pages: List[EvidencePage] = field(default_factory=list)

    pdfs: List[PdfEvidence] = field(default_factory=list)

    crawl_manifest: Dict[str, Any] = field(default_factory=dict)

    links: Dict[str, Any] = field(default_factory=dict)