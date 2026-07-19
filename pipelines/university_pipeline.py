"""
pipelines/university_pipeline.py
"""

from __future__ import annotations

from typing import Optional

from workspace.workspace_manager import WorkspaceManager


class UniversityPipeline:
    """
    Orchestrates the complete university extraction pipeline.

    Responsibilities:
        - Create workspace
        - Create program workspace
        - Execute each pipeline stage
        - Handle logging/errors
    """

    def __init__(
        self,
        workspace: WorkspaceManager,
        program_id: str = "0001",
    ):
        self.workspace = workspace
        self.program_id = program_id

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def run(self):

        print("=" * 70)
        print(f"University : {self.workspace.university}")
        print(f"Program    : {self.program_id}")
        print("=" * 70)

        self.workspace.initialize()
        self.workspace.create_program(self.program_id)

        self.discover()
        self.collect_evidence()
        self.extract_web()
        self.process_pdfs()
        self.extract_facts()
        self.merge()
        self.export()

        print("\nPipeline completed successfully.")

    # ------------------------------------------------------------------
    # Pipeline Stages
    # ------------------------------------------------------------------

    def discover(self):
        print("\n[1/7] Program Discovery")

        # TODO:
        #
        # links = LinkDiscovery(...)
        # links.run()

        pass

    def collect_evidence(self):
        print("\n[2/7] Evidence Collection")

        # TODO:
        #
        # expander = EvidenceExpander(...)
        # expander.run()

        pass

    def extract_web(self):
        print("\n[3/7] Website Extraction")

        # TODO:
        #
        # extractor = WebExtractor(...)
        # extractor.run()

        pass

    def process_pdfs(self):
        print("\n[4/7] PDF Processing")

        # TODO:
        #
        # PDF Downloader
        # OCR
        # Markdown
        # Chunking

        pass

    def extract_facts(self):
        print("\n[5/7] Fact Extraction")

        # TODO:
        #
        # ProgramExtractor(...)
        # extractor.run()

        pass

    def merge(self):
        print("\n[6/7] Merge")

        # TODO:
        #
        # Merge website + pdf facts

        pass

    def export(self):
        print("\n[7/7] Export")

        # TODO:
        #
        # Save final program.json

        pass