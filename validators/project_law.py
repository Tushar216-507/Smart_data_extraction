"""
project_law.py
--------------
Non-negotiable assertions enforced on every fact before it ships.

These are the project's hard rules — violations are code bugs, not data issues.

Rules:
  1. No value without a source URL.
  2. No estimation ever — absence is a typed gap, not silence.
  3. Rankings from official files only.
  4. Every shipped value must be non-empty and non-placeholder.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


# ── Typed Gap ────────────────────────────────────────────────────
# Instead of omitting a field or shipping an empty string, we
# use a typed gap object. This makes absence explicit and machine-
# readable.

def typed_gap(reason: str = "not_found") -> dict:
    """
    Create a typed gap value for missing data.

    Instead of empty strings or None, every missing field gets
    a gap object with a reason code.
    """
    return {
        "gap": True,
        "gap_reason": reason,
    }


GAP_REASONS = {
    "not_found": "Field not present in any evidence source.",
    "not_available": "Information exists but is not publicly available.",
    "redacted": "Information was intentionally removed by the source.",
    "budget_exhausted": "LLM budget was exhausted before this field could be extracted.",
    "extraction_failed": "LLM extraction attempted but returned no usable value.",
    "low_confidence": "Value was extracted but below confidence threshold.",
    "page_type_rejected": "Source page was classified as non-programme content.",
}


# ── Placeholder Detection ────────────────────────────────────────

PLACEHOLDER_PATTERNS = [
    r"(?i)^n/?a$",
    r"(?i)^not available$",
    r"(?i)^tbd$",
    r"(?i)^tba$",
    r"(?i)^coming soon$",
    r"(?i)^lorem ipsum",
    r"(?i)^placeholder",
    r"(?i)^test\s*$",
    r"(?i)^null$",
    r"(?i)^none$",
    r"(?i)^undefined$",
    r"(?i)^\.\.\.$",
    r"(?i)^---$",
    r"(?i)^\[.*\]$",  # [placeholder], [TBD], etc.
]


def is_placeholder(value: Any) -> bool:
    """Check if a value is a placeholder or non-meaningful string."""
    if value is None:
        return True
    if isinstance(value, str):
        v = value.strip()
        if not v:
            return True
        for pattern in PLACEHOLDER_PATTERNS:
            if re.match(pattern, v):
                return True
    return False


# ── Assertion Functions ──────────────────────────────────────────

@dataclass
class LawViolation:
    """A single violation of the project law."""
    rule: str
    field: str
    value: Any
    detail: str


def assert_has_source(fact: dict) -> Optional[LawViolation]:
    """
    Rule 1: No value without a source URL.
    Every shipped fact MUST carry the URL of its evidence source.
    """
    source_url = fact.get("source_url", "")
    if not source_url or not isinstance(source_url, str) or not source_url.strip():
        # Check metadata for chunk_id as fallback
        metadata = fact.get("metadata", {})
        chunk_id = metadata.get("chunk_id", "")
        if not chunk_id:
            return LawViolation(
                rule="NO_VALUE_WITHOUT_SOURCE",
                field=fact.get("field", "unknown"),
                value=fact.get("value"),
                detail="Fact has no source_url and no chunk_id in metadata.",
            )
    return None


def assert_no_estimation(fact: dict) -> Optional[LawViolation]:
    """
    Rule 2: No estimation ever.
    If confidence is below the threshold, the value must not ship.
    """
    confidence = fact.get("confidence", 1.0)
    if isinstance(confidence, (int, float)) and confidence < 0.3:
        return LawViolation(
            rule="NO_ESTIMATION",
            field=fact.get("field", "unknown"),
            value=fact.get("value"),
            detail=f"Confidence {confidence} is below minimum threshold 0.3.",
        )
    return None


def assert_valid_value(fact: dict) -> Optional[LawViolation]:
    """
    Rule 3: Every shipped value must be non-empty and non-placeholder.
    If the value is a gap object, it passes (gap is explicit absence).
    """
    value = fact.get("value")

    # Typed gaps are valid — they represent explicit absence
    if isinstance(value, dict) and value.get("gap") is True:
        return None

    if is_placeholder(value):
        return LawViolation(
            rule="INVALID_VALUE",
            field=fact.get("field", "unknown"),
            value=value,
            detail="Value is empty, None, or a placeholder.",
        )
    return None


def assert_rankings_official(fact: dict) -> Optional[LawViolation]:
    """
    Rule 4: Rankings from official files only.
    Any fact in the 'statistics' subcategory with a ranking field
    must have a known provenance (EXTERNAL_LOADER or official source).
    """
    subcategory = fact.get("subcategory", "")
    field_name = fact.get("field", "")

    ranking_fields = {"ranking", "world_ranking", "national_ranking", "subject_ranking"}

    if subcategory == "statistics" and field_name in ranking_fields:
        metadata = fact.get("metadata", {})
        provenance = metadata.get("provenance", "")
        if provenance not in ("EXTERNAL_LOADER", "official_file", "qs_official"):
            return LawViolation(
                rule="RANKINGS_OFFICIAL_ONLY",
                field=field_name,
                value=fact.get("value"),
                detail=f"Ranking fact has provenance '{provenance}' — must be from official files.",
            )
    return None


# ── Enforcement ──────────────────────────────────────────────────

ALL_RULES = [
    assert_has_source,
    assert_no_estimation,
    assert_valid_value,
    assert_rankings_official,
]


def enforce_project_law(fact: dict) -> List[LawViolation]:
    """
    Run all project law assertions against a single fact.
    Returns a list of violations (empty list = fact is clean).
    """
    violations = []
    for rule_fn in ALL_RULES:
        violation = rule_fn(fact)
        if violation is not None:
            violations.append(violation)
    return violations


def enforce_on_collection(facts: list) -> tuple:
    """
    Enforce project law on a list of facts.

    Returns:
        (clean_facts, rejected_facts_with_reasons)
    """
    clean = []
    rejected = []

    for fact in facts:
        violations = enforce_project_law(fact)
        if violations:
            rejected.append({
                "fact": fact,
                "violations": [
                    {
                        "rule": v.rule,
                        "field": v.field,
                        "detail": v.detail,
                    }
                    for v in violations
                ],
            })
        else:
            clean.append(fact)

    return clean, rejected
