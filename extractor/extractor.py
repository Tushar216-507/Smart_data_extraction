import json 
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
        self.manifest_builder = ManifestBuilder(workspace,program_id)
        self.link_discovery = LinkDiscovery()
        self.evidence_expander = EvidenceExpander(workspace, program_id)

    def load_programs(self, json_file):

        with open(json_file, "r", encoding="utf-8") as f:
            data = json.load(f)

        return data["program_urls"]

    def save_metadata(self, metadata):

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

    def save_html(self, html):

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

    def save_clean_html(self, html):

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

    def save_markdown(self, markdown):

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

    def save_links(self, metadata, links):

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

        try:
            page = self.page_pipeline.process(
                metadata["url"]
            )
        except Exception as e:
            print(f"    [WARN] Primary fetch failed ({e}). Attempting fallback...")
            page = self._fallback_process(metadata["url"])
            if not page:
                raise e

        program_folder = self.workspace.program_root(self.program_id)

        links = self.link_discovery.discover(
            page["raw_html"],
            metadata['url']
        )

        self.save_metadata(
            metadata
        )

        self.save_html(
            page["raw_html"]
        )

        self.save_clean_html(
            page["clean_html"]
        )

        self.save_markdown(
            page["markdown"]
        )

        self.save_links(
            metadata,
            links
        )

        self.manifest_builder.build()

        self.evidence_expander.expand()

        print(
            f"[PASS] {metadata['title_en']}"
        )

    def _fallback_process(self, url):
        # 1. Playwright fallback
        try:
            from playwright.sync_api import sync_playwright
            with sync_playwright() as p:
                browser = p.chromium.launch(headless=True)
                browser_page = browser.new_page()
                browser_page.goto(url, timeout=30000, wait_until="domcontentloaded")
                html = browser_page.content()
                browser.close()
                
            clean_html = self.page_pipeline.cleaner.clean(html)
            markdown = self.page_pipeline.markdown.convert(clean_html)
            return {
                "url": url,
                "status": 200,
                "title": "",
                "raw_html": html,
                "clean_html": clean_html,
                "markdown": markdown
            }
        except ImportError:
            print("    [WARN] Playwright not installed. Skipping local fallback.")
        except Exception as e:
            print(f"    [WARN] Playwright fallback failed: {e}")
            
        # 2. ScrapingBee fallback
        import os
        api_key = os.getenv("SCRAPINGBEE_API_KEY")
        if api_key:
            import requests
            try:
                response = requests.get(
                    url="https://app.scrapingbee.com/api/v1/",
                    params={
                        "api_key": api_key,
                        "url": url,
                        "render_js": "false"
                    }
                )
                response.raise_for_status()
                html = response.text
                clean_html = self.page_pipeline.cleaner.clean(html)
                markdown = self.page_pipeline.markdown.convert(clean_html)
                return {
                    "url": url,
                    "status": response.status_code,
                    "title": "",
                    "raw_html": html,
                    "clean_html": clean_html,
                    "markdown": markdown
                }
            except Exception as e:
                print(f"    [WARN] ScrapingBee fallback failed: {e}")
        else:
            print("    [WARN] ScrapingBee API key not configured. Skipping fallback.")
            
        return None

    def run(

        self,

        input_json,

    ):

        programs = self.load_programs(
            input_json
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

            self.workspace.create_program(
                self.program_id
            )

            try:

                self.process_program(
                    metadata
                )

            except Exception as e:

                print(e)