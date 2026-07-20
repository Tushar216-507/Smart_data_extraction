from __future__ import annotations

import json
import re
from datetime import datetime
from pathlib import Path


class WorkspaceManager:
    """
    Manages the project workspace for a university.

    Responsibilities:
    - Create folder structure
    - Return paths
    - Create metadata.json
    - Keep all filesystem logic in one place
    """

    WORKSPACE_VERSION = "1.0"

    def __init__(
        self,
        country: str,
        university: str,
        root_dir: str | Path = "data",
    ):
        self.country = self._slugify(country)
        self.university = self._slugify(university)

        self.root_dir = Path(root_dir)
        self.university_root = (
            self.root_dir
            / self.country
            / self.university
        )

        self.programs_root = self.university_root / "programs"

    # ------------------------------------------------------------------
    # Initialization
    # ------------------------------------------------------------------

    def initialize(self) -> None:
        """Create university workspace."""

        self.programs_root.mkdir(parents=True, exist_ok=True)

        self._write_metadata()

    # ------------------------------------------------------------------
    # Metadata
    # ------------------------------------------------------------------

    def _write_metadata(self) -> None:

        metadata = {
            "country": self.country,
            "university": self.university,
            "workspace_version": self.WORKSPACE_VERSION,
            "created_at": datetime.utcnow().isoformat(),
        }

        metadata_path = self.university_root / "metadata.json"

        if not metadata_path.exists():
            metadata_path.write_text(
                json.dumps(metadata, indent=4),
                encoding="utf-8",
            )

    # ------------------------------------------------------------------
    # Program
    # ------------------------------------------------------------------

    def create_program(self, program_id: str) -> Path:
        """
        Creates complete program folder structure.

        Example:
            create_program("0001")
        """

        root = self.program_root(program_id)

        folders = [
            "webpage",
            "pages",
            "pdf",
            "evidence",
            "facts",
            "merged",
            "final",
        ]

        for folder in folders:
            (root / folder).mkdir(
                parents=True,
                exist_ok=True,
            )

        return root

    # ------------------------------------------------------------------
    # Path helpers
    # ------------------------------------------------------------------

    def program_root(self, program_id: str) -> Path:
        return self.programs_root / program_id

    def webpage_dir(self, program_id: str) -> Path:
        return self.program_root(program_id) / "webpage"

    def pages_dir(self, program_id: str) -> Path:
        return self.program_root(program_id) / "pages"

    def pdf_dir(self, program_id: str) -> Path:
        return self.program_root(program_id) / "pdf"

    def evidence_dir(self, program_id: str) -> Path:
        return self.program_root(program_id) / "evidence"

    def facts_dir(self, program_id: str) -> Path:
        return self.program_root(program_id) / "facts"

    def merged_dir(self, program_id: str) -> Path:
        return self.program_root(program_id) / "merged"

    def final_dir(self, program_id: str) -> Path:
        return self.program_root(program_id) / "final"

    # ------------------------------------------------------------------
    # Files
    # ------------------------------------------------------------------

    def final_json(self, program_id: str) -> Path:
        return self.final_dir(program_id) / "program.json"

    def metadata_file(self) -> Path:
        return self.university_root / "metadata.json"

    # ------------------------------------------------------------------
    # Utils
    # ------------------------------------------------------------------

    @staticmethod
    def _slugify(value: str) -> str:
        value = value.strip().lower()
        value = re.sub(r"[^\w\s-]", "", value)
        value = re.sub(r"[\s-]+", "_", value)
        return value