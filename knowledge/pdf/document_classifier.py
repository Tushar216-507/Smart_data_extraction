"""
PDF Document Classifier
=======================

Heuristic classifier that determines the type of a PDF document
from its title, filename, and first heading — without using an LLM.

Used by PDFFactExtractor to adjust extraction scope based on
document type. For example, a scholarship catalogue should not
produce hundreds of irrelevant programme facts.

Supported document types:
    programme_handbook
    module_catalogue
    curriculum
    academic_regulations
    examination_regulations
    scholarship_catalogue
    annual_report
    course_description
    study_guide
    general
    unknown
"""

from __future__ import annotations

import re
from typing import Optional


# ================================================================
# Document type keywords
# ================================================================

_DOCUMENT_TYPE_PATTERNS: dict[str, list[str]] = {
    "programme_handbook": [
        r"\bprogramme?\s*handbook\b",
        r"\bstudiengangs?\s*handbuch\b",
        r"\bprogram\s*guide\b",
        r"\bcourse\s*handbook\b",
        r"\bdegree\s*handbook\b",
    ],
    "module_catalogue": [
        r"\bmodule?\s*catalogue\b",
        r"\bmodule?\s*catalog\b",
        r"\bmodulhandbuch\b",
        r"\bmodulkatalog\b",
        r"\bmodule?\s*handbook\b",
        r"\bmodule?\s*guide\b",
        r"\bcourse\s*catalogue\b",
        r"\bcourse\s*catalog\b",
    ],
    "curriculum": [
        r"\bcurriculum\b",
        r"\bstudienverlaufsplan\b",
        r"\bstudy\s*plan\b",
        r"\bcourse\s*structure\b",
        r"\bprogramme?\s*structure\b",
        r"\bdegree\s*structure\b",
    ],
    "academic_regulations": [
        r"\bacademic\s*regulations?\b",
        r"\bstudy\s*regulations?\b",
        r"\bstudienordnung\b",
        r"\bstudien\s*und\s*prüfungsordnung\b",
        r"\bsatzung\b",
        r"\bregulations?\s*for\b",
    ],
    "examination_regulations": [
        r"\bexamination\s*regulations?\b",
        r"\bprüfungsordnung\b",
        r"\bprüfungs\s*und\s*studienordnung\b",
        r"\bexam\s*regulations?\b",
        r"\bassessment\s*regulations?\b",
    ],
    "scholarship_catalogue": [
        r"\bscholarship\s*catalogue\b",
        r"\bscholarship\s*catalog\b",
        r"\bscholarships?\s*guide\b",
        r"\bstipendien\b",
        r"\bbursary\b",
        r"\bbursaries\b",
        r"\bfinancial\s*aid\s*guide\b",
        r"\bfunding\s*guide\b",
    ],
    "annual_report": [
        r"\bannual\s*report\b",
        r"\bjahresbericht\b",
        r"\byearly\s*report\b",
        r"\btätigkeitsbericht\b",
    ],
    "course_description": [
        r"\bcourse\s*descriptions?\b",
        r"\bmodule?\s*descriptions?\b",
        r"\blehrveranstaltung\b",
        r"\bveranstaltungsverzeichnis\b",
    ],
    "study_guide": [
        r"\bstudy\s*guide\b",
        r"\bstudienführer\b",
        r"\bstudent\s*guide\b",
        r"\bstudent\s*handbook\b",
    ],
}


# ================================================================
# Public API
# ================================================================

def classify_document(
    *,
    title: Optional[str] = None,
    filename: Optional[str] = None,
    first_heading: Optional[str] = None,
) -> str:
    """
    Classify a PDF document type from available metadata.

    Args:
        title:
            Document title (from Azure extraction or page metadata).

        filename:
            Original PDF filename.

        first_heading:
            First heading found in the document content.

    Returns:
        One of the supported document type strings.
        Returns 'general' when the document appears to be an
        academic document but doesn't match a specific type.
        Returns 'unknown' when no classification can be made.
    """

    # Combine all available text for matching
    texts = []

    if title:
        texts.append(title.strip())

    if filename:
        # Convert filename separators to spaces for matching
        clean_filename = re.sub(
            r"[-_.]",
            " ",
            filename.strip(),
        )
        texts.append(clean_filename)

    if first_heading:
        texts.append(first_heading.strip())

    if not texts:
        return "unknown"

    combined = " ".join(texts).lower()

    # Check each document type
    for doc_type, patterns in _DOCUMENT_TYPE_PATTERNS.items():
        for pattern in patterns:
            if re.search(pattern, combined, flags=re.IGNORECASE):
                return doc_type

    # Check for general academic indicators
    academic_indicators = [
        r"\bprogramme?\b",
        r"\bdegree\b",
        r"\bstudien",
        r"\buniversity\b",
        r"\bfaculty\b",
        r"\bfakultät\b",
        r"\bmodule?\b",
        r"\bsemester\b",
    ]

    for pattern in academic_indicators:
        if re.search(pattern, combined, flags=re.IGNORECASE):
            return "general"

    return "unknown"


# ================================================================
# Extraction scope guidance
# ================================================================

# Maps document types to extraction scope hints.
# The PDFFactExtractor uses these to adjust its prompt.

DOCUMENT_EXTRACTION_SCOPE: dict[str, dict] = {
    "programme_handbook": {
        "scope": "programme",
        "extract_fully": True,
        "note": "Extract all programme and module information.",
    },
    "module_catalogue": {
        "scope": "programme",
        "extract_fully": True,
        "note": "Extract all module and course information.",
    },
    "curriculum": {
        "scope": "programme",
        "extract_fully": True,
        "note": "Extract all curriculum and semester structure.",
    },
    "academic_regulations": {
        "scope": "both",
        "extract_fully": True,
        "note": "Extract programme regulations and requirements.",
    },
    "examination_regulations": {
        "scope": "both",
        "extract_fully": True,
        "note": "Extract examination rules and assessment information.",
    },
    "scholarship_catalogue": {
        "scope": "university",
        "extract_fully": False,
        "note": (
            "Extract only scholarship names and eligibility. "
            "Do not extract every individual scholarship record."
        ),
    },
    "annual_report": {
        "scope": "university",
        "extract_fully": False,
        "note": (
            "Extract only university-level summary information. "
            "Do not extract every statistic or individual entry."
        ),
    },
    "course_description": {
        "scope": "programme",
        "extract_fully": True,
        "note": "Extract all course descriptions and details.",
    },
    "study_guide": {
        "scope": "both",
        "extract_fully": True,
        "note": "Extract all programme and study information.",
    },
    "general": {
        "scope": "both",
        "extract_fully": True,
        "note": "Extract all relevant university and programme facts.",
    },
    "unknown": {
        "scope": "both",
        "extract_fully": True,
        "note": "Extract all relevant university and programme facts.",
    },
}
