import json
import os
from datetime import datetime

from extractor.page_pipeline import PagePipeline
from extractor.manifest_builder import ManifestBuilder
from extractor.link_discovery import LinkDiscovery


class ProgramExtractor:

    def __init__(self):

        self.page_pipeline = PagePipeline()
        self.manifest_builder = ManifestBuilder()
        self.link_discovery = LinkDiscovery()

    def load_programs(self, json_file):

        with open(json_file, "r", encoding="utf-8") as f:
            data = json.load(f)

        return data["program_urls"]

    def create_program_folder(self, base_path, index):

        folder = os.path.join(
            base_path,
            f"{index:04d}"
        )

        os.makedirs(folder, exist_ok=True)

        os.makedirs(
            os.path.join(folder, "program"),
            exist_ok=True
        )

        os.makedirs(
            os.path.join(folder, "pages"),
            exist_ok=True
        )

        os.makedirs(
            os.path.join(folder, "assets"),
            exist_ok=True
        )

        return folder

    def save_metadata(self, folder, metadata):

        path = os.path.join(
            folder,
            "metadata.json"
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

        path = os.path.join(
            folder,
            "program",
            "raw.html"
        )

        with open(
            path,
            "w",
            encoding="utf-8"
        ) as f:

            f.write(html)

    def save_clean_html(self, folder, html):

        path = os.path.join(
            folder,
            "program",
            "clean.html"
        )

        with open(
            path,
            "w",
            encoding="utf-8"
        ) as f:

            f.write(html)

    def save_markdown(self, folder, markdown):

        path = os.path.join(
            folder,
            "program",
            "program.md"
        )

        with open(
            path,
            "w",
            encoding="utf-8"
        ) as f:

            f.write(markdown)

    def save_links(self, folder, metadata, links):

        path = os.path.join(
            folder,
            "links.json"
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

    def process_program(self, folder, metadata):

        page = self.page_pipeline.process(
            metadata["url"]
        )

        links = self.link_discovery.discover(
            page["raw_html"],
            metadata['url']
        )

        self.save_metadata(
            folder,
            metadata
        )

        self.save_html(
            folder,
            page["raw_html"]
        )

        self.save_clean_html(
            folder,
            page["clean_html"]
        )

        self.save_markdown(
            folder,
            page["markdown"]
        )

        self.save_links(
            folder,
            metadata,
            links
        )

        self.manifest_builder.build(
            folder
        )

        print(
            f"✓ {metadata['title_en']}"
        )

    def run(

        self,

        input_json,

        output_folder="data"

    ):

        programs = self.load_programs(
            input_json
        )

        os.makedirs(
            output_folder,
            exist_ok=True
        )

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
                output_folder,
                index
            )

            try:

                self.process_program(
                    folder,
                    metadata
                )

            except Exception as e:

                print(e)