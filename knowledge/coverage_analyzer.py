from knowledge.facts import FactCollection

class CoverageAnalyzer:
    """
    Analyzes a FactCollection to determine if critical fields are missing.
    """

    CRITICAL_FIELDS = [
        "tuition_fee",
        "application_deadline",
        "duration",
        "language_requirements"
    ]

    def analyze(self, facts: FactCollection) -> dict:
        """
        Returns a dictionary with:
        - coverage_score: float (0.0 to 1.0)
        - missing_fields: list of strings
        - found_fields: list of strings
        """
        found = set()
        for fact in facts.facts:
            # Check for exact matches or partial matches in the fact's field name
            field_lower = fact.field.lower()
            if "tuition" in field_lower or "fee" in field_lower:
                found.add("tuition_fee")
            if "deadline" in field_lower or "application" in field_lower:
                found.add("application_deadline")
            if "duration" in field_lower or "length" in field_lower:
                found.add("duration")
            if "language" in field_lower or "english" in field_lower or "german" in field_lower:
                found.add("language_requirements")

        missing = [f for f in self.CRITICAL_FIELDS if f not in found]
        
        return {
            "coverage_score": len(found) / len(self.CRITICAL_FIELDS),
            "missing_fields": missing,
            "found_fields": list(found)
        }
