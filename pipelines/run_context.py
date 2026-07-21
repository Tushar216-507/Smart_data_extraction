from dataclasses import dataclass, field
from discovery.models import DiscoveryResult
from pipelines.program_metadata import ProgramMetadata
from knowledge.models import EvidencePack
from knowledge.extractors.program_extractor import (
    ProgramExtractor
)
from knowledge.normalization.semantic_normalizer import SemanticNormalizer

@dataclass
class RunContext:
    university: str
    country: str = ""

    discovery: DiscoveryResult | None = None
    program: ProgramMetadata | None = None

    metrics: dict = field(default_factory=dict)
    evidence_pack: EvidencePack | None = None
    raw_facts: ProgramExtractor | None = None
    normalized_facts: SemanticNormalizer | None = None
    final_output: dict | None = None