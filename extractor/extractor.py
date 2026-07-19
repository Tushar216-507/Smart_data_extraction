import json
import os
from datetime import datetime
from workspace.workspace_manager import WorkspaceManager

from extractor.page_pipeline import PagePipeline
from extractor.manifest_builder import ManifestBuilder
from extractor.link_discovery import LinkDiscovery
from extractor.evidence_expander import EvidenceExpander


class ProgramExtractor:

    def __init__(
        self,
        workspace: WorkspaceManager,
        program_id: str,
    ):
        self.workspace = workspace
        self.program_id = program_id

        self.page_pipeline = PagePipeline()
        self.manifest_builder = ManifestBuilder()
        self.link_discovery = LinkDiscovery()
        self.evidence_expander = EvidenceExpander()

    def load_programs(self, json_file):

        with open(json_file, "r", encoding="utf-8") as f:
            data = json.load(f)

        return data["program_urls"]

    def save_metadata(self, folder, metadata):

        path = (
            self.workspace.program_root(self.program_id)
            / "metadata.json"
        )

        with open(
            path,
            "w",
            encoding="utf-8"
        ) as f:

            json.dump(
                metadata,
                f,
                indent=4,
                ensure_ascii=False
            )

    def save_html(self, folder, html):

        path = (
            self.workspace.webpage_dir(self.program_id)
            / "raw.html"
        )

        with open(
            path,
            "w",
            encoding="utf-8"
        ) as f:

            f.write(html)

    def save_clean_html(self, folder, html):

        path = (
            self.workspace.webpage_dir(self.program_id)
            / "clean.html"
        )

        with open(
            path,
            "w",
            encoding="utf-8"
        ) as f:

            f.write(html)

    def save_markdown(self, folder, markdown):

        path = (
            self.workspace.webpage_dir(self.program_id)
            / "program.md"
        )

        with open(
            path,
            "w",
            encoding="utf-8"
        ) as f:

            f.write(markdown)

    def save_links(self, folder, metadata, links):

        path = (
            self.workspace.program_root(self.program_id)
            / "links.json"
        )

        summary = {

            "total_links": len(links),

            "evidence_links": sum(
                1
                for x in links
                if x["purpose"] == "evidence"
            ),

            "pdf_links": sum(
                1
                for x in links
                if x["type"] == "pdf"
            ),

            "discovery_links": sum(
                1
                for x in links
                if x["purpose"] == "discovery"
            )
        }

        data = {

            "program_url": metadata["url"],

            "generated_at": datetime.now().astimezone().isoformat(),

            "summary": summary,

            "links": links
        }

        with open(
            path,
            "w",
            encoding="utf-8"
        ) as f:

            json.dump(
                data,
                f,
                indent=4,
                ensure_ascii=False
            )

    def process_program(self, metadata):

        page = self.page_pipeline.process(
            metadata["url"]
        )

        program_folder = self.workspace.program_root(self.program_id)

        links = self.link_discovery.discover(
            page["raw_html"],
            metadata['url']
        )

        self.save_metadata(
            program_folder,
            metadata
        )

        self.save_html(
            program_folder,
            page["raw_html"]
        )

        self.save_clean_html(
            program_folder,
            page["clean_html"]
        )

        self.save_markdown(
            program_folder,
            page["markdown"]
        )

        self.save_links(
            program_folder,
            metadata,
            links
        )

        self.manifest_builder.build(
            program_folder
        )

        self.evidence_expander.expand(
            program_folder
        )

        print(
            f"✓ {metadata['title_en']}"
        )

    def run(

        self,

        input_json,

    ):

        programs = self.load_programs(
            input_json
        )[:1]

        total = len(programs)

        print(
            f"\nDownloading {total} program pages...\n"
        )

        for index, metadata in enumerate(
            programs,
            start=1
        ):

            print(
                f"[{index}/{total}]"
            )

            folder = self.create_program_folder(
                self.program_id
            )

            try:

                self.process_program(
                    metadata
                )

            except Exception as e:

                print(e)