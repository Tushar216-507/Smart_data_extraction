"""
pipelines/program_metadata.py

Typed representation of a discovered programme.

Every pipeline stage accepts ProgramMetadata instead of
raw dictionaries, which removes dict-key typo bugs and
gives IDE autocompletion.
"""

from __future__ import annotations

from dataclasses import dataclass, field, asdict
from typing import Dict, Any


@dataclass
class ProgramMetadata:
    """
    One discovered university programme.

    Created during Stage 1 (Programme Discovery) and
    passed through every downstream stage.
    """

    url: str
    title: str
    h1: str = ""
    status: int = 200

    title_original: str = ""
    h1_original: str = ""
    title_en: str = ""
    h1_en: str = ""

    # ----------------------------------------------------------
    # Helpers
    # ----------------------------------------------------------

    @property
    def display_name(self) -> str:
        """Best human-readable programme name available."""
        return self.h1_en or self.title_en or self.h1 or self.title

    def to_dict(self) -> Dict[str, Any]:
        """Serialize for JSON or for modules still expecting dicts."""
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> ProgramMetadata:
        """Construct from a dictionary (e.g. main.py output)."""
        return cls(
            url=data.get("url", ""),
            title=data.get("title", ""),
            h1=data.get("h1", ""),
            status=data.get("status", 200),
            title_original=data.get("title_original", ""),
            h1_original=data.get("h1_original", ""),
            title_en=data.get("title_en", ""),
            h1_en=data.get("h1_en", ""),
        )
