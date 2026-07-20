import json
from datetime import datetime
from workspace.workspace_manager import WorkspaceManager


class ManifestBuilder:

    def __init__(
        self,
        workspace: WorkspaceManager,
        program_id: str,
    ):
        self.workspace = workspace
        self.program_id = program_id

    MAX_DEPTH = 2

    EXPAND_CATEGORIES = {
        "admission",
        "curriculum",
        "department",
        "international"
    }

    def build(self):

        links_path = (
            self.workspace.program_root(self.program_id)
            / "links.json"
        )

        if not links_path.exists():
            return  

        with open(
            links_path,
            "r",
            encoding="utf-8"
        ) as f:

            links_data = json.load(f)

        manifest = {

            "version": 1,

            "created_at": datetime.now().astimezone().isoformat(),

            "max_depth": self.MAX_DEPTH,

            "statistics": {

                "pending": 0,

                "completed": 0,

                "failed": 0
            },

            "queue": []
        }

        best_links = {}

        seen = set()

        for link in links_data["links"]:

            if link["purpose"] != "evidence":
                continue

            url = link["url"]

            if url in seen:
                continue

            seen.add(url)

            category = link["category"]

            current = best_links.get(category)

            if current is None:

                best_links[category] = link

            elif link["priority"] > current["priority"]:

                best_links[category] = link

            elif (

                link["priority"] == current["priority"]

                and

                len(link["url"]) < len(current["url"])

            ):

                best_links[category] = link

        for link in best_links.values():

            if link["priority"] < 50:
                continue

            manifest["queue"].append({

                "id": None,

                "url": link["url"],

                "title": link["title"],

                "category": link["category"],

                "type": link["type"],

                "priority": link["priority"],

                "depth": 1,

                "expand": (
                    link["category"]
                    in self.EXPAND_CATEGORIES
                ),

                "status": "pending",

                "parent": "program",

                "children_discovered": False,

                "page_folder": None,

                "downloaded_at": None
            })

        CATEGORY_PRIORITY = {
            "admission": 1,
            "curriculum": 2,
            "department": 3,
            "international": 4,
            "fees": 5,
            "career": 6,
            "module_handbook": 7,
            "study_regulations": 8,
            "brochure": 9,
            "contact": 10
        }

        manifest["queue"].sort(

            key=lambda x: (

                x["depth"],

                CATEGORY_PRIORITY.get(
                    x["category"],
                    99
                ),

                -x["priority"]

            )
        )

        manifest["statistics"]["pending"] = len(
            manifest["queue"]
        )

        output = (
            self.workspace.program_root(self.program_id)
            / "crawl_manifest.json"
        )

        with open(
            output,
            "w",
            encoding="utf-8"
        ) as f:

            json.dump(

                manifest,

                f,

                indent=4,

                ensure_ascii=False
            )

        return manifest