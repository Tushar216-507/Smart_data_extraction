import re
from pathlib import Path

# 1. Update normalization_chunker.py
nc_path = Path("knowledge/normalization/normalization_chunker.py")
nc_content = nc_path.read_text(encoding="utf-8")

# Group facts according to their current category -> subcategory
nc_content = nc_content.replace(
    '            category = self._get_category(\n                fact\n            )',
    '            category = self._get_subcategory(\n                fact\n            )'
)

# Rename _get_category to _get_subcategory
nc_content = nc_content.replace('def _get_category(', 'def _get_subcategory(')
nc_content = nc_content.replace(
    'category = getattr(\n            fact,\n            "category",\n            "",\n        )',
    'category = getattr(\n            fact,\n            "subcategory",\n            "",\n        )'
)

# Update _fact_to_dict to include both category and subcategory, plus new fields
dict_replacement = """    def _fact_to_dict(
        self,
        fact: Any,
    ) -> dict[str, Any]:
        \"\"\"
        Convert a Fact to a minimal dictionary for the prompt.
        \"\"\"
        return {
            "category": getattr(
                fact,
                "category",
                "",
            ),
            "subcategory": getattr(
                fact,
                "subcategory",
                "",
            ),
            "field": getattr(
                fact,
                "field",
                "",
            ),
            "value": getattr(
                fact,
                "value",
                "",
            ),
            "source_url": getattr(
                fact,
                "source_url",
                "",
            ),
            "source_type": getattr(
                fact,
                "source_type",
                "",
            ),
            "programme_association": getattr(
                fact,
                "programme_association",
                "",
            ),
        }"""
nc_content = re.sub(r'    def _fact_to_dict\([\s\S]*?        }', dict_replacement, nc_content)
nc_path.write_text(nc_content, encoding="utf-8")

# 2. Update semantic_normalizer.py
sn_path = Path("knowledge/normalization/semantic_normalizer.py")
sn_content = sn_path.read_text(encoding="utf-8")

sn_replacement = """        category = data.get("category", "")
        subcategory = data.get("subcategory", "")

        if not isinstance(category, str) or not category.strip():
            raise ValueError("Missing or invalid category.")
            
        if not isinstance(subcategory, str) or not subcategory.strip():
            raise ValueError("Missing or invalid subcategory.")

        field = data.get("field")"""

sn_content = re.sub(r'        category = data\.get\([\s\S]*?field = data\.get\(', sn_replacement + '\n        field = data.get(', sn_content)

sn_instantiate = """        return ExtractedFact(
            category=category,
            subcategory=subcategory,
            field=field,
            value=value,
            confidence=1.0,
            source_url=data.get("source_url", ""),
            source_type=data.get("source_type", ""),
            programme_association=data.get("programme_association", ""),
        )"""

sn_content = re.sub(r'        return ExtractedFact\([\s\S]*?\)', sn_instantiate, sn_content)
sn_path.write_text(sn_content, encoding="utf-8")

print("Updated normalizers successfully")
