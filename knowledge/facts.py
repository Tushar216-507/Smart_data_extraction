from dataclasses import dataclass, field
from typing import Any, Dict, List

@dataclass
class ExtractedFact:
    category: str         # 'university' or 'programme'
    subcategory: str      # 'admission', 'curriculum', 'fees', etc.
    field: str            
    value: Any
    confidence: float = 1.0
    source_url: str = ""
    source_type: str = "" # program, webpage, pdf
    programme_association: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)

@dataclass
class FactCollection:
    facts: List[ExtractedFact] = field(default_factory=list)

    def add(self, fact: ExtractedFact):
        self.facts.append(fact)

    def by_category(self, category: str):
        return [f for f in self.facts if f.category == category]
        
    def by_subcategory(self, subcategory: str):
        return [f for f in self.facts if f.subcategory == subcategory]

    def by_field(self, field: str):
        return [f for f in self.facts if f.field == field]
