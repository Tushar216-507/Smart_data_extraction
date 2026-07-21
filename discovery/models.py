from dataclasses import dataclass, field
from typing import Dict, List, Any


@dataclass
class CandidateURL:
    url: str
    source: str
    score: int = 0
    page_type: str = "Unknown"
    metadata: Dict = field(default_factory=dict)
    evidence: Dict[str, Any] = field(default_factory=dict)
    reasons: List[str] = field(default_factory=list)

    def add_evidence(self, key: str, value: Any, reason: str = None):
        self.evidence[key] = value
        if reason:
            self.reasons.append(reason)


@dataclass
class DiscoveryResult:
    candidates: List[CandidateURL] = field(default_factory=list)
    strategy_stats: Dict[str, Dict] = field(default_factory=dict)

    def add(self, candidate):
        self.candidates.append(candidate)