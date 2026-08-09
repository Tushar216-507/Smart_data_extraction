import re
from pathlib import Path

path = Path("knowledge/output/final_output_builder.py")
content = path.read_text(encoding="utf-8")

replacement = """    def _fact_to_dictionary(
        self,
        fact: Any,
    ) -> Dict[str, Any]:
        \"\"\"
        Convert an ExtractedFact dataclass or dictionary into a
        validated dictionary.
        \"\"\"

        if is_dataclass(fact):
            fact = asdict(fact)

        if not isinstance(fact, dict):
            raise TypeError(
                "Every fact must be a dictionary or dataclass. "
                f"Received: {type(fact).__name__}"
            )

        category = fact.get("category")
        field = fact.get("field")

        if not isinstance(category, str) or not category.strip():
            raise ValueError("Fact category cannot be empty.")

        if not isinstance(field, str) or not field.strip():
            raise ValueError("Fact field cannot be empty.")

        if "value" not in fact:
            raise ValueError("Every fact must contain a 'value' property.")

        metadata = fact.get("metadata", {})
        if not isinstance(metadata, dict):
            metadata = {"original_metadata": metadata}

        normalized_fact = {
            "category": category.strip().lower(),
            "subcategory": fact.get("subcategory", "").strip().lower(),
            "field": field.strip().lower(),
            "value": deepcopy(fact.get("value")),
            "confidence": fact.get("confidence", 1.0),
            "source_url": fact.get("source_url", ""),
            "source_type": fact.get("source_type", ""),
            "programme_association": fact.get("programme_association", ""),
            "metadata": deepcopy(metadata),
        }

        # Backwards compatibility for 'source' dict
        if fact.get("source") is not None:
            normalized_fact["source"] = deepcopy(fact["source"])

        return normalized_fact"""

content = re.sub(r'    def _fact_to_dictionary\([\s\S]*?        return normalized_fact', replacement, content)
path.write_text(content, encoding="utf-8")
print("Fixed FinalOutputBuilder._fact_to_dictionary")
