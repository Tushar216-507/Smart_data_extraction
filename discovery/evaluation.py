import re
from discovery.models import CandidateURL

class CandidateEvaluator:
    """
    Evaluates CandidateURL objects using metadata, structured data, 
    and LLM-classified page types to heavily penalize hub pages 
    and reward actual degree programs.
    """

    DEGREE_INDICATORS = [
        r"\bbachelor", r"\bmaster", r"\bphd", r"\bdoctorate", 
        r"\bbsc\b", r"\bmsc\b", r"\bba\b", r"\bma\b"
    ]

    def evaluate(self, candidate: CandidateURL) -> CandidateURL:
        # Reset score but preserve existing evidence (like URL heuristics)
        # We'll just sum all evidence values to compute the new score.
        # But first, add new evidence based on metadata and classification.

        # 1. Classification Evidence (Phase 3)
        page_type = candidate.page_type
        if page_type == "Degree Programme":
            candidate.add_evidence("classification_degree", 50, "+ Classified as Degree Programme")
        elif page_type in ["Programme Hub", "Degree Catalogue", "Navigation"]:
            candidate.add_evidence("classification_hub", -100, f"- Classified as {page_type} (Not a leaf node)")
        elif page_type in ["Support", "Other", "Admissions", "Event", "News"]:
            candidate.add_evidence("classification_non_academic", -100, f"- Classified as {page_type}")

        # 2. Metadata Evidence (Phase 2)
        title = candidate.metadata.get("title_en", "").lower()
        h1 = candidate.metadata.get("h1_en", "").lower()
        combined_text = title + " " + h1

        has_degree_indicator = False
        for indicator in self.DEGREE_INDICATORS:
            if re.search(indicator, combined_text):
                has_degree_indicator = True
                break
        
        if has_degree_indicator:
            candidate.add_evidence("metadata_degree_indicator", 20, "+ Metadata contains specific degree indicator (e.g., Bachelor/Master)")
        else:
            candidate.add_evidence("metadata_missing_degree", -20, "- Metadata lacks specific degree indicators")

        # 3. Structured Data Evidence (Phase 2)
        structured_data = candidate.metadata.get("structured_data", [])
        has_educational_schema = False
        
        for item in structured_data:
            schema_type = item.get("@type", "")
            if isinstance(schema_type, str):
                schema_type = [schema_type]
            
            if any(t in ["Course", "EducationalOccupationalProgram"] for t in schema_type):
                has_educational_schema = True
                break

        if has_educational_schema:
            candidate.add_evidence("structured_data_schema", 30, "+ Found educational structured data (Course/EducationalOccupationalProgram)")

        # Re-calculate score by summing all evidence integer values
        total = sum(val for key, val in candidate.evidence.items() if isinstance(val, int))
        candidate.score = total

        return candidate
