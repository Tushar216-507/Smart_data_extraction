"""
pipelines/university_pipeline.py

Main orchestrator for the university data extraction pipeline.

This class coordinates all pipeline stages for a single
university. It does not contain business logic — it delegates
to existing modules and passes data between stages.

Usage (programmatic):

    pipeline = UniversityPipeline()

    pipeline.run(
        university_url="https://www.lmu.de/en/",
        program_limit=1,
    )

Usage (via run_pipeline.py):

    python run_pipeline.py --university "https://www.lmu.de/en/" --programs 1
"""

from __future__ import annotations

import time
from dataclasses import asdict
from pathlib import Path
from typing import List, Optional
from urllib.parse import urlparse

from pipelines.pipeline_context import PipelineContext
from pipelines.program_metadata import ProgramMetadata

from workspace.workspace_manager import WorkspaceManager

from knowledge.billing.usage_tracker import UsageTracker
from knowledge.llm.client import LLMClient
from knowledge.llm.provider import LLMProvider
from knowledge.llm.groq_provider import GroqProvider
from knowledge.llm.nvidia_provider import NvidiaProvider
from knowledge.llm.fallback_provider import FallbackProvider

from knowledge.evidence_pack_builder import EvidencePackBuilder
from knowledge.extractors.program_extractor import (
    ProgramExtractor as KnowledgeExtractor,
)
from knowledge.normalization.normalization_chunker import (
    NormalizationChunker,
)
from knowledge.normalization.semantic_normalizer import (
    SemanticNormalizer,
)
from knowledge.output.final_output_builder import FinalOutputBuilder
from knowledge.storage.fact_repository import FactRepository

from extractor.extractor import ProgramExtractor as EvidenceCollector


# ================================================================
# Country lookup from TLD
# ================================================================

TLD_COUNTRIES = {
    "de": "germany",
    "uk": "united_kingdom",
    "ac.uk": "united_kingdom",
    "at": "austria",
    "ch": "switzerland",
    "fr": "france",
    "nl": "netherlands",
    "jp": "japan",
    "au": "australia",
    "ca": "canada",
    "edu": "united_states",
    "it": "italy",
    "es": "spain",
    "se": "sweden",
    "dk": "denmark",
    "no": "norway",
    "fi": "finland",
    "be": "belgium",
    "ie": "ireland",
    "nz": "new_zealand",
    "sg": "singapore",
    "hk": "hong_kong",
    "kr": "south_korea",
    "cn": "china",
    "in": "india",
}


# ================================================================
# Pipeline
# ================================================================

class UniversityPipeline:
    """
    Orchestrates the complete university extraction pipeline.

    Responsibilities:
        - Execute each pipeline stage in the correct order
        - Pass outputs from one stage into the next
        - Handle per-programme errors
        - Display progress
        - Track LLM usage and cost

    This class does NOT contain extraction logic.
    It only coordinates existing components.
    """

    STAGES = [
        "Programme Discovery",
        "Evidence Collection",
        "Evidence Pack Building",
        "Fact Extraction",
        "Semantic Normalization",
        "Final Output",
    ]

    def __init__(self):
        self.fact_repository = FactRepository()
        self.evidence_pack_builder = EvidencePackBuilder()

    # ==============================================================
    # Public API
    # ==============================================================

    def run(
        self,
        university_url: str,
        program_limit: Optional[int] = None,
        country: Optional[str] = None,
        workspace_dir: str = "data",
        continue_on_error: bool = False,
        verbose: bool = False,
    ) -> dict:
        """
        Execute the complete pipeline for one university.

        Args:
            university_url:
                The university's base URL.

            program_limit:
                If set, only process the first N programmes.

            country:
                Country name for workspace organization.
                If omitted, inferred from the URL TLD.

            workspace_dir:
                Root directory for all output data.

            continue_on_error:
                If True, skip failed programmes and continue.
                If False, stop immediately on first error.

            verbose:
                If True, print extra debug information.

        Returns:
            Summary dict with pipeline results.
        """

        pipeline_start = time.time()

        # ----------------------------------------------------------
        # Resolve university identity from URL
        # ----------------------------------------------------------

        resolved_country = country or self._country_from_url(
            university_url
        )

        university_name = self._university_from_url(
            university_url
        )

        # ----------------------------------------------------------
        # Initialize shared resources
        # ----------------------------------------------------------

        workspace = WorkspaceManager(
            country=resolved_country,
            university=university_name,
            root_dir=workspace_dir,
        )

        usage_tracker = UsageTracker()

        llm_provider = self._create_llm_provider()

        context = PipelineContext(
            university_url=university_url,
            workspace=workspace,
            llm_provider=llm_provider,
            usage_tracker=usage_tracker,
            program_limit=program_limit,
            continue_on_error=continue_on_error,
            verbose=verbose,
        )

        workspace.initialize()

        total_stages = len(self.STAGES)

        self._print_header(university_url, workspace)

        # ----------------------------------------------------------
        # Stage 1: Programme Discovery
        # ----------------------------------------------------------

        self._print_stage(1, total_stages, self.STAGES[0])

        context.discovery = self._discover_programs(context)

        programs = context.discovery

        if not programs:
            self._print_error("No programmes found. Stopping.")
            return {"status": "error", "reason": "no_programs_found"}

        print(f"  Found {len(programs)} programmes")

        if program_limit:
            programs = programs[:program_limit]
            print(f"  Applying limit: {program_limit}")

        print()

        # ----------------------------------------------------------
        # Per-programme pipeline (Stages 2–6)
        # ----------------------------------------------------------

        succeeded = 0
        failed = 0
        failed_programs = []

        for index, program in enumerate(programs, start=1):

            context.program = program

            program_id = f"{index:04d}"

            self._print_program_header(
                index, len(programs), program
            )

            try:
                self._run_program_pipeline(
                    context=context,
                    program_id=program_id,
                    program_index=index,
                    total_programs=len(programs),
                    total_stages=total_stages,
                )
                succeeded += 1

            except Exception as error:

                failed += 1
                failed_programs.append(
                    (program_id, program.display_name, str(error))
                )

                self._print_error(
                    f"  ✗ Failed: {type(error).__name__}: {error}"
                )

                if not continue_on_error:
                    self._print_error(
                        "\n  Stopping pipeline. Use --continue-on-error "
                        "to skip failed programmes.\n"
                    )
                    raise

        # ----------------------------------------------------------
        # Summary
        # ----------------------------------------------------------

        elapsed = time.time() - pipeline_start

        usage_tracker.print_summary()

        self._print_footer(
            succeeded=succeeded,
            failed=failed,
            total=len(programs),
            elapsed=elapsed,
            failed_programs=failed_programs,
        )

        return {
            "status": "success" if failed == 0 else "partial",
            "programs_discovered": len(programs),
            "programs_succeeded": succeeded,
            "programs_failed": failed,
            "failed_programs": failed_programs,
            "elapsed_seconds": round(elapsed, 1),
            "workspace": str(workspace.university_root),
        }

    # ==============================================================
    # Per-programme pipeline
    # ==============================================================

    def _run_program_pipeline(
        self,
        context: PipelineContext,
        program_id: str,
        program_index: int,
        total_programs: int,
        total_stages: int,
    ) -> None:
        """Execute stages 2–6 for a single programme."""

        program = context.program

        if program is None:
            raise RuntimeError("No program is set in the pipeline context.")

        workspace = context.workspace

        # Stage 2: Evidence Collection
        self._print_stage(2, total_stages, self.STAGES[1])

        workspace.create_program(program_id)

        collector = EvidenceCollector(
            workspace=workspace,
            program_id=program_id,
        )

        collector.process_program(program.to_dict())

        print("  ✓ Evidence collected")

        # Stage 3: Evidence Pack Building
        self._print_stage(3, total_stages, self.STAGES[2])

        program_folder = workspace.program_root(program_id)

        context.evidence_pack = self.evidence_pack_builder.build(
            program_folder
        )

        evidence_pack = context.evidence_pack

        if evidence_pack is None:
            raise RuntimeError("Evidence pack was not created.")

        page_count = len(evidence_pack.pages)
        pdf_count = len(evidence_pack.pdfs)

        print(f"  ✓ Evidence pack ready")
        print(f"    {page_count} pages, {pdf_count} PDFs")

        # Stage 4: Fact Extraction
        self._print_stage(4, total_stages, self.STAGES[3])

        extraction_client = LLMClient(
            provider=context.llm_provider,
            usage_tracker=context.usage_tracker,
            stage="extraction",
            program_id=program_id,
        )

        extractor = KnowledgeExtractor(
            client=extraction_client,
        )

        context.raw_facts = extractor.extract(
            evidence_pack.program,
        )
        raw_facts = context.raw_facts

        raw_facts_path = (
            workspace.facts_dir(program_id)
            / "raw_program_facts.json"
        )

        self.fact_repository.save(
            raw_facts.facts,
            raw_facts_path,
        )

        print(f"  ✓ {len(raw_facts.facts)} raw facts extracted")

        # Stage 5: Semantic Normalization
        self._print_stage(5, total_stages, self.STAGES[4])

        normalization_client = LLMClient(
            provider=context.llm_provider,
            usage_tracker=context.usage_tracker,
            stage="normalization",
            program_id=program_id,
        )

        chunker = NormalizationChunker()

        chunks = chunker.chunk(raw_facts.facts)

        normalizer = SemanticNormalizer(
            client=normalization_client,
        )

        context.normalized_facts = normalizer.normalize(chunks)
        normalized_facts = context.normalized_facts

        if normalized_facts is None:
            raise RuntimeError("Semantic normalization failed.")

        normalized_path = (
            workspace.facts_dir(program_id)
            / "normalized_program_facts.json"
        )

        self.fact_repository.save(
            normalized_facts.facts,
            normalized_path,
        )

        print(f"  ✓ {len(normalized_facts.facts)} normalized facts")

        # Stage 6: Final Output
        self._print_stage(6, total_stages, self.STAGES[5])

        output_dir = workspace.final_dir(program_id)

        builder = FinalOutputBuilder(
            output_directory=output_dir,
        )

        context.final_output = builder.build(
            facts=normalized_facts.facts,
            program_id=program_id,
            program_name=program.display_name,
        )
        result = context.final_output

        if result is None:
            raise RuntimeError("Final output generation failed.")

        written = len(result.get("output_files", {}))

        print(f"  ✓ {written} output files written")

    # ==============================================================
    # Stage 1: Programme Discovery
    # ==============================================================

    def _discover_programs(
        self,
        context: PipelineContext,
    ) -> List[ProgramMetadata]:
        """
        Discover programme URLs from the university website.

        Delegates to main.discover_programs() and converts
        the raw dict results into ProgramMetadata objects.
        """

        import main

        result = main.discover_programs(
            context.university_url.rstrip("/")
        )

        raw_programs = result.get("program_urls", [])

        programs = [
            ProgramMetadata.from_dict(p)
            for p in raw_programs
        ]

        # Save discovery result to workspace
        import json

        discovery_path = (
            context.workspace.university_root
            / "discovery.json"
        )

        with open(discovery_path, "w", encoding="utf-8") as f:
            json.dump(result, f, indent=2, ensure_ascii=False)

        return programs

    # ==============================================================
    # LLM Provider
    # ==============================================================

    @staticmethod
    def _create_llm_provider() -> LLMProvider:
        """
        Create the LLM provider with Groq primary and
        NVIDIA fallback.
        """

        try:
            primary = GroqProvider()
        except ValueError:
            raise RuntimeError(
                "Groq API key is not configured. "
                "Set GROQ_API_KEY in your .env file."
            )

        try:
            fallback = NvidiaProvider()
            return FallbackProvider(primary, fallback)
        except Exception:
            # NVIDIA fallback not available — use Groq only
            return primary

    # ==============================================================
    # URL Helpers
    # ==============================================================

    @staticmethod
    def _university_from_url(url: str) -> str:
        """Extract a university identifier from a URL."""

        parsed = urlparse(url)
        domain = parsed.netloc or ""

        if domain.startswith("www."):
            domain = domain[4:]

        # Remove TLD: "lmu.de" -> "lmu"
        name = domain.rsplit(".", 1)[0] if "." in domain else domain

        return name or "university"

    @staticmethod
    def _country_from_url(url: str) -> str:
        """Infer country from URL domain TLD."""

        parsed = urlparse(url)
        domain = parsed.netloc or ""

        if domain.startswith("www."):
            domain = domain[4:]

        tld = domain.rsplit(".", 1)[-1] if "." in domain else ""

        return TLD_COUNTRIES.get(tld.lower(), tld.lower() or "international")

    # ==============================================================
    # Display
    # ==============================================================

    @staticmethod
    def _print_header(
        university_url: str,
        workspace: WorkspaceManager,
    ) -> None:

        print()
        print("═" * 65)
        print("  University Pipeline")
        print(f"  {university_url}")
        print(f"  Workspace: {workspace.university_root}")
        print("═" * 65)
        print()

    @staticmethod
    def _print_stage(
        stage_number: int,
        total_stages: int,
        stage_name: str,
    ) -> None:

        print(f"  ── Stage {stage_number}/{total_stages} — {stage_name}")

    @staticmethod
    def _print_program_header(
        index: int,
        total: int,
        program: ProgramMetadata,
    ) -> None:

        print()
        print("─" * 65)
        print(f"  Programme {index}/{total}")
        print(f"  {program.display_name}")
        print("─" * 65)
        print()

    @staticmethod
    def _print_error(message: str) -> None:
        print(message)

    @staticmethod
    def _print_footer(
        succeeded: int,
        failed: int,
        total: int,
        elapsed: float,
        failed_programs: list,
    ) -> None:

        minutes = int(elapsed // 60)
        seconds = int(elapsed % 60)

        print()
        print("═" * 65)

        if failed == 0:
            print("  ✓ Pipeline Complete")
        else:
            print(f"  ⚠ Pipeline Complete (with {failed} failures)")

        print(f"  Programmes processed: {succeeded}/{total}")

        if failed_programs:
            print(f"  Failed programmes:")
            for pid, name, error in failed_programs:
                print(f"    [{pid}] {name}: {error}")

        print(f"  Total time: {minutes}m {seconds:02d}s")
        print("═" * 65)
        print()