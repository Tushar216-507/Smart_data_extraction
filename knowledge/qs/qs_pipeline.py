"""
knowledge/qs/qs_pipeline.py

Orchestrator for the complete QS data extraction pipeline.

Coordinates:
    QSProfileExtractor  → profile_data.json  (intermediate)
    QSRankingExtractor   → rankings_data.json (intermediate)
    QSOutputBuilder      → qs_data.json       (final output)

Usage (from UniversityPipeline):

    qs_pipeline = QSPipeline()
    result = qs_pipeline.run(
        qs_profile_url="https://www.topuniversities.com/universities/...",
        output_directory=workspace.university_root / "final",
    )

This class does NOT contain extraction logic — it delegates
to existing QS modules and passes data between stages.
"""

from __future__ import annotations

import json
import traceback
from pathlib import Path
from typing import Any, Dict, Optional


class QSPipeline:
    """
    Orchestrates the complete QS data extraction pipeline.

    Responsibilities:
        - Run profile extraction
        - Run ranking extraction
        - Run output building
        - Handle errors gracefully
        - Optionally save intermediate files for debugging

    This class does NOT contain QS parsing logic.
    It only coordinates existing QS components.
    """

    def run(
        self,
        qs_profile_url: str,
        output_directory: str | Path,
        qs_data_directory: Optional[str | Path] = None,
        save_intermediates: bool = False,
        verbose: bool = False,
    ) -> Dict[str, Any]:
        """
        Execute the complete QS extraction pipeline.

        Args:
            qs_profile_url:
                Full QS TopUniversities profile URL.
                Example: https://www.topuniversities.com/universities/eth-zurich

            output_directory:
                Directory where the final qs_data.json will be written.
                Typically the university-level final/ directory.

            qs_data_directory:
                Optional root directory for QS working data.
                If omitted, uses a temporary directory structure.
                When save_intermediates is True, intermediate files
                (profile_data.json, rankings_data.json) are saved here.

            save_intermediates:
                If True, preserve profile_data.json and rankings_data.json
                for debugging. If False, only qs_data.json is persisted.

            verbose:
                If True, print extra debug information.

        Returns:
            Result dict with status, output file path, and summary.
        """

        from knowledge.qs.qs_profile_extractor import QSProfileExtractor
        from knowledge.qs.qs_ranking_extractor import QSRankingExtractor
        from knowledge.qs.qs_output_builder import QSOutputBuilder

        output_directory = Path(output_directory)
        output_directory.mkdir(parents=True, exist_ok=True)

        # Resolve QS working directory for intermediate files
        if qs_data_directory:
            qs_root = Path(qs_data_directory)
        else:
            qs_root = output_directory / ".qs_working"

        if save_intermediates:
            qs_root.mkdir(parents=True, exist_ok=True)

        # ----------------------------------------------------------
        # Stage 1: Profile Extraction
        # ----------------------------------------------------------

        print("    ── QS Profile Extraction")

        profile_extractor = QSProfileExtractor(
            output_directory=qs_root,
        )

        profile_result = profile_extractor.extract(
            profile_url=qs_profile_url,
        )

        university_slug = profile_result.get(
            "source", {}
        ).get("university_slug", "unknown")

        print(f"    ✓ QS profile extracted: {university_slug}")

        if verbose:
            university_name = profile_result.get(
                "university", {}
            ).get("name", "Unknown")
            print(f"      University: {university_name}")

        # ----------------------------------------------------------
        # Stage 2: Ranking Extraction
        # ----------------------------------------------------------

        print("    ── QS Ranking Extraction")

        ranking_extractor = QSRankingExtractor(
            output_directory=qs_root,
        )

        # The ranking extractor reads endpoints discovered
        # by the profile extractor.
        rankings_result = ranking_extractor.extract(
            profile_data=profile_result,
        )

        if save_intermediates:
            ranking_extractor.save_json(
                data=rankings_result,
                university_slug=university_slug,
            )

        ranking_count = len(
            rankings_result.get("rankings", [])
        )

        print(f"    ✓ {ranking_count} QS rankings extracted")

        # ----------------------------------------------------------
        # Stage 3: Output Building
        # ----------------------------------------------------------

        print("    ── QS Output Building")

        output_builder = QSOutputBuilder(
            qs_directory=qs_root,
        )

        qs_data = output_builder.build_data(
            university_slug=university_slug,
            profile_data=profile_result,
            rankings_data=rankings_result,
        )

        # Write the final merged QS data
        output_file = output_directory / "qs_data.json"

        with open(output_file, "w", encoding="utf-8") as f:
            json.dump(qs_data, f, indent=2, ensure_ascii=False)

        print(f"    ✓ QS data saved: {output_file.name}")

        # ----------------------------------------------------------
        # Clean up working directory if intermediates not needed
        # ----------------------------------------------------------

        if not save_intermediates and (output_directory / ".qs_working").exists():
            import shutil
            try:
                shutil.rmtree(output_directory / ".qs_working")
            except Exception:
                pass  # Non-critical cleanup

        return {
            "status": "success",
            "university_slug": university_slug,
            "output_file": str(output_file),
            "rankings_count": ranking_count,
            "data": qs_data,
        }
