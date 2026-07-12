from dataclasses import dataclass, field
from typing import Any, Dict, List


@dataclass
class SourceReference:
    source_type: str      # program, webpage, pdf
    source_id: str        # 0001, 0002, etc.
    title: str
    url: str = ""


@dataclass
class ExtractedFact:
    category: str         # admission, curriculum, fees
    field: str            # duration, ects, tuition
    value: Any

    confidence: float = 1.0

    source: SourceReference = None

    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class FactCollection:

    facts: List[ExtractedFact] = field(default_factory=list)

    def add(self, fact: ExtractedFact):

        self.facts.append(fact)

    def by_category(self, category: str):

        return [
            f
            for f in self.facts
            if f.category == category
        ]

    def by_field(self, field: str):

        return [
            f
            for f in self.facts
            if f.field == field
        ]