from dataclasses import dataclass, field
from typing import List, Dict, Any


@dataclass
class EvidencePage:

    id: str

    title: str

    category: str

    type: str

    source: str = ""

    markdown: str = ""

    clean_html: str = ""

    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class PdfEvidence:

    id: str

    title: str

    category: str

    source: str = ""

    document_type: str = ""

    pdf_path: str = ""

    metadata: Dict[str, Any] = field(default_factory=dict)

@dataclass
class ProgramEvidence:

    markdown: str

    metadata: Dict[str, Any]

    raw_html: str = ""

    clean_html: str = ""

@dataclass
class CrawlStatistics:

    html_pages: int = 0

    pdfs: int = 0

    failed_pages: int = 0

    max_depth: int = 0
    
@dataclass
class EvidencePack:

    program: ProgramEvidence

    pages: List[EvidencePage] = field(default_factory=list)

    pdfs: List[PdfEvidence] = field(default_factory=list)

    statistics: CrawlStatistics = field(
        default_factory=CrawlStatistics
    )

    crawl_manifest: Dict[str, Any] = field(default_factory=dict)

    links: Dict[str, Any] = field(default_factory=dict)

