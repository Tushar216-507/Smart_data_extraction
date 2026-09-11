"""
TISCA Canonical Schema Mapping
"""

from typing import Dict

# Maps LLM-chosen field names into the TISCA canonical schema.
# Any field not in this registry will be preserved as-is, but
# registering fields ensures consistent outputs across universities.
FIELD_REGISTRY: Dict[str, Dict[str, str]] = {
    # ── Identity ────────────────────────────────────────────────
    "programme_name": {"canonical": "programme_name", "domain": "identity"},
    "program_name": {"canonical": "programme_name", "domain": "identity"},
    "degree_type": {"canonical": "degree_type", "domain": "identity"},
    "academic_degree": {"canonical": "degree_type", "domain": "identity"},
    "duration": {"canonical": "duration_months", "domain": "identity"},
    "study_duration": {"canonical": "duration_months", "domain": "identity"},
    "start_term": {"canonical": "start_term", "domain": "identity"},
    "study_mode": {"canonical": "study_mode", "domain": "identity"},
    "faculty": {"canonical": "faculty", "domain": "identity"},
    "department": {"canonical": "department", "domain": "identity"},

    # ── Fees ────────────────────────────────────────────────────
    "tuition_fee": {"canonical": "tuition_fee_amount", "domain": "fees"},
    "total_course_fee": {"canonical": "tuition_fee_amount", "domain": "fees"},
    "tuition_amount": {"canonical": "tuition_fee_amount", "domain": "fees"},
    "tuition_currency": {"canonical": "tuition_fee_currency", "domain": "fees"},
    "semester_contribution": {"canonical": "semester_contribution", "domain": "fees"},

    # ── Admission ───────────────────────────────────────────────
    "ielts_score": {"canonical": "english_requirement_ielts", "domain": "admission"},
    "toefl_score": {"canonical": "english_requirement_toefl", "domain": "admission"},
    "application_deadline": {"canonical": "application_deadline", "domain": "admission"},
    "formal_requirements": {"canonical": "entry_requirements", "domain": "admission"},
    "entry_requirements": {"canonical": "entry_requirements", "domain": "admission"},

    # ── Curriculum ──────────────────────────────────────────────
    "module_name": {"canonical": "module_name", "domain": "curriculum"},
    "course_name": {"canonical": "module_name", "domain": "curriculum"},
    "ects_credits": {"canonical": "module_ects", "domain": "curriculum"},
    "module_ects": {"canonical": "module_ects", "domain": "curriculum"},
    
    # ── Career ──────────────────────────────────────────────────
    "skills_developed": {"canonical": "skills_developed", "domain": "career"},
    "career_prospects": {"canonical": "career_opportunities", "domain": "career"},
    "employment_opportunities": {"canonical": "career_opportunities", "domain": "career"},
    
    # ── Contacts ────────────────────────────────────────────────
    "email": {"canonical": "contact_email", "domain": "contacts"},
    "contact_email": {"canonical": "contact_email", "domain": "contacts"},
    "phone": {"canonical": "contact_phone", "domain": "contacts"},
    "office_hours": {"canonical": "office_hours", "domain": "contacts"},
}

def canonicalize_field(field_name: str, category: str = None) -> tuple[str, str]:
    """
    Returns (canonical_field_name, domain).
    If the field is not in the registry, returns (field_name, category or "other").
    """
    field_lower = field_name.lower().strip()
    if field_lower in FIELD_REGISTRY:
        entry = FIELD_REGISTRY[field_lower]
        return entry["canonical"], entry["domain"]
    return field_name, category or "other"
