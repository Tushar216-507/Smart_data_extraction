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
import traceback

from pipelines.pipeline_context import PipelineContext
from pipelines.program_metadata import ProgramMetadata

from workspace.workspace_manager import WorkspaceManager

from config import Config
from knowledge.billing.usage_tracker import UsageTracker
from knowledge.llm.client import LLMClient
from knowledge.llm.provider import LLMProvider
from knowledge.llm.groq_provider import GroqProvider
from knowledge.llm.nvidia_provider import NvidiaProvider
from knowledge.llm.fallback_provider import FallbackProvider

from knowledge.evidence_pack_builder import EvidencePackBuilder
from knowledge.coverage_analyzer import CoverageAnalyzer
from discovery.strategies.search import SearchStrategy
from knowledge.extractors.program_extractor import (
    ProgramExtractor as KnowledgeExtractor,
)
from utils.timing import time_stage, logger

from knowledge.pdf.azure_document_extractor import AzureDocumentExtractor
from knowledge.pdf.pdf_evidence_builder import PDFEvidenceBuilder
from knowledge.pdf.pdf_fact_extractor import PDFFactExtractor

from knowledge.qs.qs_pipeline import QSPipeline

from knowledge.normalization.normalization_chunker import (
    NormalizationChunker,
)
from knowledge.normalization.semantic_normalizer import (
    SemanticNormalizer,
)
from knowledge.output.final_output_builder import FinalOutputBuilder
from knowledge.storage.fact_repository import FactRepository
from knowledge.facts import FactCollection

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
        "University Data Extraction",
        "Evidence Collection",
        "4. Evidence Pack Building",
        "5. Fact Extraction",
        "6. Semantic Normalization",
        "7. Targeted Search Fallback",
        "8. Final Output",
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
        qs_profile_url: Optional[str] = None,
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
        # Stage 2: University Data Extraction (QS, etc.)
        # ----------------------------------------------------------

        self._print_stage(2, total_stages, self.STAGES[1])

        if qs_profile_url:
            self._run_qs_pipeline(
                qs_profile_url=qs_profile_url,
                workspace=workspace,
                verbose=verbose,
            )
        else:
            print("  Skipped (no --qs-url provided)")

        print()

        # ----------------------------------------------------------
        # Per-programme pipeline (Stages 3–8)
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
                    f"  [FAIL] Failed: {type(error).__name__}: {error}"
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

    @time_stage("programme_pipeline")
    def _run_program_pipeline(
        self,
        context: PipelineContext,
        program_id: str,
        program_index: int,
        total_programs: int,
        total_stages: int,
    ) -> None:
        """Execute stages 2–8 for a single programme, with checkpointing."""

        program = context.program

        if program is None:
            raise RuntimeError("No program is set in the pipeline context.")

        workspace = context.workspace
        
        normalized_path = (
            workspace.facts_dir(program_id)
            / "normalized_program_facts.json"
        )
        
        # If normalization is already done, we can skip straight to final output
        if normalized_path.exists():
            print("  [PASS] Found normalized facts checkpoint. Skipping extraction stages.")
            facts = self.fact_repository.load(normalized_path)
            context.normalized_facts = FactCollection(facts=facts)
            normalized_facts = context.normalized_facts
        else:
            # Stage 3: Evidence Collection
            self._print_stage(3, total_stages, self.STAGES[2])
    
            workspace.create_program(program_id)
            
            # Use metadata.json as checkpoint for evidence collection
            metadata_path = workspace.program_root(program_id) / "metadata.json"
            if metadata_path.exists():
                print("  [PASS] Evidence already collected (checkpoint found)")
            else:
                collector = EvidenceCollector(
                    workspace=workspace,
                    program_id=program_id,
                )
        
                collector.process_program(program.to_dict())
                print("  [PASS] Evidence collected")
    
            # Stage 4: Evidence Pack Building
            self._print_stage(4, total_stages, self.STAGES[3])
    
            program_folder = workspace.program_root(program_id)
    
            context.evidence_pack = self.evidence_pack_builder.build(
                program_folder
            )
    
            evidence_pack = context.evidence_pack
    
            if evidence_pack is None:
                raise RuntimeError("Evidence pack was not created.")
    
            page_count = len(evidence_pack.pages)
            pdf_count = len(evidence_pack.pdfs)
    
            print(f"  [PASS] Evidence pack ready")
            print(f"    {page_count} pages, {pdf_count} PDFs")
    
            # Stage 5: Fact Extraction
            self._print_stage(5, total_stages, self.STAGES[4])
            
            raw_facts_path = (
                workspace.facts_dir(program_id)
                / "raw_program_facts.json"
            )
            
            if raw_facts_path.exists():
                print("  [PASS] Found raw facts checkpoint.")
                facts = self.fact_repository.load(raw_facts_path)
                context.raw_facts = FactCollection(facts=facts)
                raw_facts = context.raw_facts
            else:
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
                    evidence_pack,
                )
                raw_facts = context.raw_facts
        
                # ----------------------------------------------------------
                # PDF Fact Extraction
                # ----------------------------------------------------------
        
                pdf_facts = self._run_pdf_pipeline(
                    evidence_pack=evidence_pack,
                    context=context,
                    program_id=program_id,
                )
        
                raw_facts.facts.extend(pdf_facts)
                
                # Save after ALL facts (including PDF) are collected
                self.fact_repository.save(
                    raw_facts.facts,
                    raw_facts_path,
                )
        
                print(f"  [PASS] {len(raw_facts.facts)} raw facts extracted")
    
            # Stage 6: Semantic Normalization
            self._print_stage(6, total_stages, self.STAGES[5])
    
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
    
            self.fact_repository.save(
                normalized_facts.facts,
                normalized_path,
            )
    
            print(f"  [PASS] {len(normalized_facts.facts)} normalized facts")
            
            # Stage 7: Coverage Analysis & Targeted Search
            self._print_stage(7, total_stages, self.STAGES[6])
            
            analyzer = CoverageAnalyzer()
            coverage = analyzer.analyze(normalized_facts)
            
            if coverage["missing_fields"]:
                print(f"  [WARN] Missing critical fields: {', '.join(coverage['missing_fields'])}")
                
                from discovery.targeted_search import TargetedSearchProvider
                from extractor.page_pipeline import PagePipeline
                from urllib.parse import urlparse
                import hashlib
                import json
                from knowledge.models import EvidencePack, EvidencePage
                
                search_provider = TargetedSearchProvider(max_results_per_query=5)
                page_pipeline = PagePipeline()
                
                domain = urlparse(context.university_url).netloc
                if domain.startswith("www."):
                    domain = domain[4:]
                
                program_title = getattr(program, "title_en", None) or getattr(program, "title", "")
                
                # Prioritize fields (user requirement)
                priority = ["curriculum", "semester", "modules", "admission_requirements", "tuition_fee"]
                fields_to_search = [f for f in priority if f in coverage["missing_fields"]]
                for f in coverage["missing_fields"]:
                    if f not in fields_to_search:
                        fields_to_search.append(f)
                fields_to_search = fields_to_search[:3] # max 3 fields
                
                new_urls = []
                for field in fields_to_search:
                    if len(new_urls) >= 10:
                        break
                    clean_title = program_title.split("|")[0].strip()
                    query = f'{clean_title} site:{domain} {field.replace("_", " ")}'
                    print(f"  > Searching: {query}")
                    urls = search_provider.search_programme_pages(query)
                    for u in urls:
                        if u not in new_urls and len(new_urls) < 10:
                            new_urls.append(u)
                
                if new_urls:
                    print(f"  > Found {len(new_urls)} fallback URLs. Collecting evidence...")
                    pages_root = program_folder / "pages"
                    pages_root.mkdir(parents=True, exist_ok=True)
                    
                    new_pages = []
                    for url in new_urls:
                        print(f"    Fetching: {url}")
                        try:
                            result = page_pipeline.process(url)
                            if result.get("status") == 200 and result.get("markdown"):
                                page_id = hashlib.md5(url.encode()).hexdigest()[:10]
                                page_dir = pages_root / f"fallback_{page_id}"
                                page_dir.mkdir(exist_ok=True)
                                
                                metadata = {
                                    "url": url,
                                    "title": result.get("title", ""),
                                    "status": result.get("status"),
                                    "source": "targeted_search"
                                }
                                
                                (page_dir / "metadata.json").write_text(json.dumps(metadata, indent=2), encoding="utf-8")
                                (page_dir / "raw.html").write_text(result.get("raw_html", ""), encoding="utf-8")
                                (page_dir / "clean.html").write_text(result.get("clean_html", ""), encoding="utf-8")
                                (page_dir / "content.md").write_text(result.get("markdown", ""), encoding="utf-8")
                                
                                new_pages.append(EvidencePage(
                                    id=page_id,
                                    title=result.get("title", ""),
                                    category="targeted_search",
                                    type="page",
                                    source=url,
                                    markdown=result.get("markdown", ""),
                                    metadata=metadata
                                ))
                        except Exception as e:
                            print(f"    [WARN] Failed to process {url}: {e}")
                    
                    if new_pages:
                        print(f"  > Extracted {len(new_pages)} new pages. Re-running extraction...")
                        mini_pack = EvidencePack(
                            program=context.evidence_pack.program,
                            pages=new_pages,
                            pdfs=[],
                            crawl_manifest={},
                            links={}
                        )
                        
                        extraction_client = LLMClient(
                            provider=context.llm_provider,
                            usage_tracker=context.usage_tracker,
                            stage="targeted_extraction",
                            program_id=program_id,
                        )
                        extractor = KnowledgeExtractor(client=extraction_client)
                        new_raw_facts = extractor.extract(mini_pack)
                        
                        if new_raw_facts and new_raw_facts.facts:
                            print(f"  > Found {len(new_raw_facts.facts)} new facts. Re-normalizing...")
                            raw_facts.facts.extend(new_raw_facts.facts)
                            
                            normalization_client = LLMClient(
                                provider=context.llm_provider,
                                usage_tracker=context.usage_tracker,
                                stage="targeted_normalization",
                                program_id=program_id,
                            )
                            chunker = NormalizationChunker()
                            chunks = chunker.chunk(raw_facts.facts)
                            normalizer = SemanticNormalizer(client=normalization_client)
                            
                            context.normalized_facts = normalizer.normalize(chunks)
                            normalized_facts = context.normalized_facts
                            
                            self.fact_repository.save(raw_facts.facts, raw_facts_path)
                            self.fact_repository.save(normalized_facts.facts, normalized_path)
                            print(f"  [PASS] Updated normalized facts to {len(normalized_facts.facts)}")
                        else:
                            print("  > No new facts found from targeted search.")
                else:
                    print("  > Targeted search found no new pages.")
            else:
                print("  [PASS] Full coverage achieved")

            print(f"  [PASS] Pipeline finished for {program_id}")

        # Stage 8: Final Output
        self._print_stage(8, total_stages, self.STAGES[7])
        
        # Checkpoint final output
        output_dir = workspace.final_dir(program_id)
        if (output_dir / "programme.json").exists():
             print("  [PASS] Final output already generated (checkpoint found)")
             return
             
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

        print(f"  [PASS] {written} output files written")

    def _run_pdf_pipeline(
        self,
        evidence_pack,
        context: PipelineContext,
        program_id: str,
    ) -> list:
        """
        Run the complete PDF extraction pipeline and return extracted facts.
        """

        pdf_facts = []

        azure_extractor = AzureDocumentExtractor()
        evidence_builder = PDFEvidenceBuilder()

        fact_extractor = PDFFactExtractor(
            client=LLMClient(
                provider=context.llm_provider,
                usage_tracker=context.usage_tracker,
                stage="pdf_extraction",
                program_id=program_id,
            )
        )

        for pdf in evidence_pack.pdfs:
            print(f"    Processing PDF: {pdf.title}")

            try:

                pdf_root = (
                    context.workspace.program_root(program_id)
                    / "pdf"
                )

                from pathlib import Path

                document_path = Path(pdf.pdf_path)
                document_id = document_path.stem

                document_folder = pdf_root / document_id

                azure_result = azure_extractor.extract(
                    pdf_path=document_path,
                    output_dir=document_folder,
                    document_id=document_id,
                    source_url=pdf.metadata.get("url"),
                    source_title=pdf.title,
                )

                evidence_result = evidence_builder.build(
                    document_data_path=document_folder / "extracted" / "document_data.json",
                    output_dir=document_folder / "evidence",
                    program_id=program_id,
                    document_id=document_id,
                    source_pdf_path=document_path,
                    source_url=pdf.metadata.get("url"),
                    program_name=context.program.display_name,
                )

                fact_result = fact_extractor.extract(
                    evidence_path=document_folder / "evidence" / "pdf_evidence_chunks.json",
                    output_dir=document_folder / "facts",
                    program_id=program_id,
                    document_id=document_id,
                    university_name=context.workspace.university,
                    program_name=context.program.display_name,
                )

                pdf_facts.extend(
                    fact_result.get("facts", [])
                )

            except Exception as exc:
                print(f"      [FAIL] PDF processing failed: {pdf.title}")
                traceback.print_exc()
                continue
        return pdf_facts

    # ==============================================================
    # Stage 2: University Data Extraction (QS)
    # ==============================================================

    @staticmethod
    def _run_qs_pipeline(
        qs_profile_url: str,
        workspace: WorkspaceManager,
        verbose: bool = False,
    ) -> None:
        """
        Run QS data extraction for the university.

        This is a university-level stage — it runs once,
        not per programme. Failures are caught and logged
        without stopping the pipeline.
        """

        qs_pipeline = QSPipeline()

        try:
            result = qs_pipeline.run(
                qs_profile_url=qs_profile_url,
                output_directory=workspace.university_final_dir(),
                verbose=verbose,
            )

            print(f"  [PASS] QS data extracted ({result.get('rankings_count', 0)} rankings)")

        except Exception as error:
            print(f"  [FAIL] QS extraction failed: {type(error).__name__}: {error}")

            if verbose:
                traceback.print_exc()

            print("  Continuing pipeline without QS data.")

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
        import json

        discovery_path = (
            context.workspace.university_root
            / "discovery.json"
        )
        
        if discovery_path.exists():
            print("  [PASS] Found discovery checkpoint. Skipping discovery.")
            with open(discovery_path, "r", encoding="utf-8") as f:
                result = json.load(f)
        else:
            result = main.discover_programs(
                context.university_url.rstrip("/")
            )
            with open(discovery_path, "w", encoding="utf-8") as f:
                json.dump(result, f, indent=2, ensure_ascii=False)

        raw_programs = result.get("program_urls", [])

        programs = [
            ProgramMetadata.from_dict(p)
            for p in raw_programs
        ]

        return programs

    # ==============================================================
    # LLM Provider
    # ==============================================================

    @staticmethod
    def _create_llm_provider() -> LLMProvider:
        """
        Create the LLM provider using OpenAI.
        """
        try:
            from knowledge.llm.openai_provider import OpenAIProvider
            return OpenAIProvider(
                api_key=Config.OPENAI_API_KEY,
                model="gpt-4o-mini"
            )
        except Exception as e:
            raise RuntimeError(f"Failed to initialize LLM providers: {e}")

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
        print("=" * 65)
        print("  University Pipeline")
        print(f"  {university_url}")
        print(f"  Workspace: {workspace.university_root}")
        print("=" * 65)
        print()

    @staticmethod
    def _print_stage(
        stage_number: int,
        total_stages: int,
        stage_name: str,
    ) -> None:

        print(f"  -- Stage {stage_number}/{total_stages} — {stage_name}")

    @staticmethod
    def _print_program_header(
        index: int,
        total: int,
        program: ProgramMetadata,
    ) -> None:

        print()
        print("-" * 65)
        print(f"  Programme {index}/{total}")
        print(f"  {program.display_name}")
        print("-" * 65)
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
        print("=" * 65)

        if failed == 0:
            print("  [PASS] Pipeline Complete")
        else:
            print(f"  [WARN] Pipeline Complete (with {failed} failures)")

        print(f"  Programmes processed: {succeeded}/{total}")

        if failed_programs:
            print(f"  Failed programmes:")
            for pid, name, error in failed_programs:
                print(f"    [{pid}] {name}: {error}")

        print(f"  Total time: {minutes}m {seconds:02d}s")
        print("=" * 65)
        print()