from dataclasses import dataclass, field
from typing import Dict, List


@dataclass
class CandidateURL:
    url: str
    source: str
    score: int = 0
    metadata: Dict = field(default_factory=dict)


@dataclass
class DiscoveryResult:
    candidates: List[CandidateURL] = field(default_factory=list)
    strategy_stats: Dict[str, Dict] = field(default_factory=dict)

    def add(self, candidate):
        self.candidates.append(candidate)