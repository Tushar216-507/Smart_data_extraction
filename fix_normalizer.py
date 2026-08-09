import re
from pathlib import Path

sn_path = Path("knowledge/normalization/semantic_normalizer.py")
sn_content = sn_path.read_text(encoding="utf-8")

# Find the start of _dict_to_fact
start_idx = sn_content.find("    @staticmethod\n    def _dict_to_fact")
if start_idx == -1:
    print("Could not find _dict_to_fact")
    exit(1)

new_dict_to_fact = """    @staticmethod
    def _dict_to_fact(
        data: dict[str, Any],
    ) -> ExtractedFact:
        \"\"\"
        Convert one normalized JSON object into an
        ExtractedFact.
        \"\"\"

        if not isinstance(data, dict):
            raise TypeError("Normalized fact must be a JSON object.")

        category = data.get("category", "")
        subcategory = data.get("subcategory", "")
        field = data.get("field", "")

        if not isinstance(category, str) or not category.strip():
            raise ValueError("Missing or invalid category.")

        if not isinstance(subcategory, str) or not subcategory.strip():
            raise ValueError("Missing or invalid subcategory.")

        if not isinstance(field, str) or not field.strip():
            raise ValueError("Missing or invalid field.")

        if "value" not in data:
            raise ValueError("Missing value.")

        confidence = data.get("confidence", 1.0)
        try:
            confidence = float(confidence)
        except (TypeError, ValueError) as error:
            raise ValueError("Confidence must be numeric.") from error
            
        confidence = max(0.0, min(confidence, 1.0))

        metadata = data.get("metadata", {})
        if metadata is None:
            metadata = {}

        if not isinstance(metadata, dict):
            raise ValueError("Metadata must be an object.")

        return ExtractedFact(
            category=category.strip().lower(),
            subcategory=subcategory.strip().lower(),
            field=field.strip().lower(),
            value=data["value"],
            confidence=confidence,
            source_url=data.get("source_url", ""),
            source_type=data.get("source_type", ""),
            programme_association=data.get("programme_association", ""),
            metadata=metadata,
        )
"""

# Replace everything from start_idx to the end of the file
new_content = sn_content[:start_idx] + new_dict_to_fact
sn_path.write_text(new_content, encoding="utf-8")
print("Replaced _dict_to_fact successfully")
