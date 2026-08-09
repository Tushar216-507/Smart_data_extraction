import re
from pathlib import Path

# 1. Update knowledge/facts.py
facts_path = Path("knowledge/facts.py")
facts_content = facts_path.read_text(encoding="utf-8")

facts_replacement = """from dataclasses import dataclass, field
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
"""
facts_path.write_text(facts_replacement, encoding="utf-8")

# 2. Update knowledge/storage/fact_repository.py
repo_path = Path("knowledge/storage/fact_repository.py")
repo_content = repo_path.read_text(encoding="utf-8")

# Remove SourceReference import
repo_content = repo_content.replace("    SourceReference,\n", "")

dict_to_fact_replacement = """
    @staticmethod
    def _fact_to_dict(fact: ExtractedFact) -> dict[str, Any]:
        metadata = fact.metadata
        if not isinstance(metadata, dict):
            metadata = {}

        return {
            "category": fact.category,
            "subcategory": fact.subcategory,
            "field": fact.field,
            "value": fact.value,
            "confidence": fact.confidence,
            "source_url": fact.source_url,
            "source_type": fact.source_type,
            "programme_association": fact.programme_association,
            "metadata": metadata,
        }

    @staticmethod
    def _dict_to_fact(data: dict[str, Any]) -> ExtractedFact:
        # Backwards compatibility for old data format
        category = data.get("category", "programme")
        subcategory = data.get("subcategory", data.get("category", "other"))
        if "source" in data and isinstance(data["source"], dict):
            source_url = data["source"].get("url", "")
            source_type = data["source"].get("source_type", "")
        else:
            source_url = data.get("source_url", "")
            source_type = data.get("source_type", "")

        metadata = data.get("metadata", {})
        if not isinstance(metadata, dict):
            metadata = {}

        return ExtractedFact(
            category=category,
            subcategory=subcategory,
            field=data.get("field", ""),
            value=data.get("value"),
            confidence=data.get("confidence", 1.0),
            source_url=source_url,
            source_type=source_type,
            programme_association=data.get("programme_association", ""),
            metadata=metadata
        )
"""
repo_content = re.sub(r"    @staticmethod\n    def _fact_to_dict\([\s\S]*?return ExtractedFact\(.*?\)\n", dict_to_fact_replacement, repo_content)
repo_path.write_text(repo_content, encoding="utf-8")

# 3. Update knowledge/extractors/program_extractor.py
pe_path = Path("knowledge/extractors/program_extractor.py")
pe_content = pe_path.read_text(encoding="utf-8")
pe_content = pe_content.replace("    SourceReference,\n", "")

pe_replacement = """                    collection.add(
                        ExtractedFact(
                            category=item.get("category", "programme"),
                            subcategory=item.get("subcategory", item.get("category", "other")),
                            field=item["field"],
                            value=item["value"],
                            confidence=item.get("confidence", 1.0),
                            source_url=pack.program.metadata.get("url", ""),
                            source_type=chunk.source_type,
                            programme_association=item.get("programme_association", ""),
                            metadata=fact_metadata,
                        )
                    )"""

pe_content = re.sub(r"                    collection.add\(\n                        ExtractedFact\([\s\S]*?,\n                        \)\n                    \)", pe_replacement, pe_content)
pe_path.write_text(pe_content, encoding="utf-8")


# 4. Update knowledge/pdf/pdf_fact_extractor.py
pdf_path = Path("knowledge/pdf/pdf_fact_extractor.py")
pdf_content = pdf_path.read_text(encoding="utf-8")
pdf_content = pdf_content.replace("    SourceReference,\n", "")

pdf_replacement = """                    collection.add(
                        ExtractedFact(
                            category=item.get("category", "university"),
                            subcategory=item.get("subcategory", item.get("category", "other")),
                            field=item["field"],
                            value=item["value"],
                            confidence=item.get("confidence", 1.0),
                            source_url=pack.program.metadata.get("url", "") if pack else "",
                            source_type="pdf",
                            programme_association=item.get("programme_association", ""),
                            metadata=fact_metadata,
                        )
                    )"""

pdf_content = re.sub(r"                    collection.add\(\n                        ExtractedFact\([\s\S]*?,\n                        \)\n                    \)", pdf_replacement, pdf_content)
pdf_path.write_text(pdf_content, encoding="utf-8")

# 5. Update prompts.py
prompts_path = Path("knowledge/prompts.py")
prompts_content = prompts_path.read_text(encoding="utf-8")

# Update JSON formats in PROGRAM_EXTRACTION_PROMPT and FACT_NORMALIZATION_PROMPT
prompts_content = re.sub(
r"""\{
  "facts": \[
    \{
      "category": "\.\.\.",
      "field": "\.\.\.",
      "value": "\.\.\.",
      "confidence": 1\.0,
      "metadata": \{\}
    \}
  \]
\}""",
r"""{
  "facts": [
    {
      "category": "university or programme",
      "subcategory": "...",
      "field": "...",
      "value": "...",
      "confidence": 1.0,
      "programme_association": "..."
    }
  ]
}""", prompts_content)

prompts_path.write_text(prompts_content, encoding="utf-8")
print("Updated all schema files")
