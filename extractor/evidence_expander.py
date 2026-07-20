import json
from datetime import datetime

from workspace.workspace_manager import WorkspaceManager

from extractor.page_pipeline import PagePipeline
from extractor.link_discovery import LinkDiscovery
from extractor.downloader import PageDownloader


class EvidenceExpander:

    def __init__(
        self,
        workspace: WorkspaceManager,
        program_id: str,
    ):

        self.workspace = workspace
        self.program_id = program_id

        self.pipeline = PagePipeline()
        self.discovery = LinkDiscovery()
        self.downloader = PageDownloader()

    ###########################################################
    # Manifest
    ###########################################################

    def load_manifest(self):

        path = (
            self.workspace.program_root(self.program_id)
            / "crawl_manifest.json"
        )

        with open(
            path,
            "r",
            encoding="utf-8"
        ) as f:

            return json.load(f)

    def save_manifest(self, manifest):

        path = (
            self.workspace.program_root(self.program_id)
            / "crawl_manifest.json"
        )

        with open(
            path,
            "w",
            encoding="utf-8"
        ) as f:

            json.dump(
                manifest,
                f,
                indent=4,
                ensure_ascii=False
            )

    ###########################################################
    # Folder creation
    ###########################################################

    def create_page_folder(self):

        pages_folder = self.workspace.pages_dir(
            self.program_id
        )

        pages_folder.mkdir(
            parents=True,
            exist_ok=True
        )

        existing = []

        for child in pages_folder.iterdir():

            if child.is_dir():

                try:
                    existing.append(
                        int(child.name)
                    )
                except ValueError:
                    pass

        if existing:

            next_id = max(existing) + 1

        else:

            next_id = 1

        folder_name = f"{next_id:04d}"

        folder = (
            pages_folder
            / folder_name
        )

        folder.mkdir(
            parents=True,
            exist_ok=True
        )

        return folder_name, folder

    ###########################################################
    # Save files
    ###########################################################

    def save_metadata(self, folder, metadata):

        with open(

            folder / "metadata.json",

            "w",

            encoding="utf-8"

        ) as f:

            json.dump(

                metadata,

                f,

                indent=4,

                ensure_ascii=False
            )

    def save_raw_html(self, folder, html):

        with open(

            folder / "raw.html",

            "w",

            encoding="utf-8"

        ) as f:

            f.write(html)

    def save_clean_html(self, folder, html):

        with open(

            folder / "clean.html",

            "w",

            encoding="utf-8"

        ) as f:

            f.write(html)

    def save_markdown(self, folder, markdown):

        with open(

            folder / "page.md",

            "w",

            encoding="utf-8"

        ) as f:

            f.write(markdown)

    def save_links(self, folder, links):

        with open(

            folder / "links.json",

            "w",

            encoding="utf-8"

        ) as f:

            json.dump(

                links,

                f,

                indent=4,

                ensure_ascii=False
            )

    ###########################################################
    # Process One Page
    ###########################################################

    def process_page(
        self,
        queue_item,
    ):

        print(
            f'Processing: {queue_item["title"]}'
        )

        folder_name, folder = self.create_page_folder()

        ##################################################
        # PDF
        ##################################################

        if queue_item["type"] == "pdf":

            assets = folder / "assets"

            assets.mkdir(
                parents=True,
                exist_ok=True
            )

            pdf_file = assets / "source.pdf"

            result = self.downloader.download_file(

                queue_item["url"],

                pdf_file
            )

            metadata = {

                "id": folder_name,

                "title": queue_item["title"],

                "url": result["url"],

                "type": "pdf",

                "category": queue_item["category"],

                "depth": queue_item["depth"],

                "parent": queue_item["parent"],

                "filename": "source.pdf",

                "ocr_processed": False,

                "status": "completed",

                "downloaded_at":
                    datetime.now().astimezone().isoformat()
            }

            self.save_metadata(
                folder,
                metadata
            )

            queue_item["status"] = "completed"

            queue_item["page_folder"] = folder_name

            queue_item["downloaded_at"] = (
                datetime.now()
                .astimezone()
                .isoformat()
            )

            return []

        page = self.pipeline.process(
            queue_item["url"]
        )

        metadata = {

            "id": folder_name,

            "title": queue_item["title"],

            "url": queue_item["url"],

            "category": queue_item["category"],

            "depth": queue_item["depth"],

            "parent": queue_item["parent"],

            "status": "completed",

            "downloaded_at":
                datetime.now().astimezone().isoformat()
        }

        self.save_metadata(
            folder,
            metadata
        )

        self.save_raw_html(
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

        ##################################################
        # Discover child links
        ##################################################

        links = self.discovery.discover(

            page["raw_html"],

            queue_item["url"]

        )

        self.save_links(
            folder,
            links
        )

        queue_item["status"] = "completed"

        queue_item["page_folder"] = folder_name

        queue_item["downloaded_at"] = (
            datetime.now()
            .astimezone()
            .isoformat()
        )

        queue_item["children_discovered"] = False

        return links
    
    ###########################################################
    # Queue Helpers
    ###########################################################

    def update_statistics(self, manifest):

        pending = 0
        completed = 0
        failed = 0

        for item in manifest["queue"]:

            status = item.get("status", "pending")

            if status == "pending":
                pending += 1

            elif status == "completed":
                completed += 1

            elif status == "failed":
                failed += 1

        manifest["statistics"]["pending"] = pending
        manifest["statistics"]["completed"] = completed
        manifest["statistics"]["failed"] = failed


    def enqueue_children(
        self,
        manifest,
        parent_item,
        links
    ):

        if parent_item["depth"] >= manifest["max_depth"]:
            return

        if not parent_item["expand"]:
            return

        existing_urls = {
            item["url"]
            for item in manifest["queue"]
        }

        for link in links:

            if link["purpose"] != "evidence":
                continue

            if link["url"] in existing_urls:
                continue

            manifest["queue"].append({

                "id": None,

                "url": link["url"],

                "title": link["title"],

                "category": link["category"],

                "type": link["type"],

                "priority": link["priority"],

                "depth": parent_item["depth"] + 1,

                "expand": (
                    link["category"]
                    in
                    (
                        "admission",
                        "fees",
                        "department",
                        "curriculum",
                        "international"
                    )
                ),

                "status": "pending",

                "parent": parent_item["page_folder"],

                "children_discovered": False,

                "page_folder": None,

                "downloaded_at": None
            })

            existing_urls.add(link["url"])

        parent_item["children_discovered"] = True

    ###########################################################
    # Expand
    ###########################################################

    def expand(self):

        manifest = self.load_manifest()

        while True:

            pending = None

            for item in manifest["queue"]:

                if item["status"] == "pending":

                    pending = item
                    break

            if pending is None:
                break

            try:

                links = self.process_page(
                    pending
                )

                self.enqueue_children(
                    manifest,
                    pending,
                    links
                )

            except Exception as e:

                print(f"404/ERROR: {pending['url']}")

                pending["status"] = "failed"

                pending["error"] = str(e)

                continue

            self.update_statistics(
                manifest
            )

            self.save_manifest(
                manifest
            )

        print()

        print("Evidence expansion completed.")