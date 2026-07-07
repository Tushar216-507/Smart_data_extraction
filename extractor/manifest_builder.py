import json
import os
from datetime import datetime


class ManifestBuilder:

    MAX_DEPTH = 2
    best_links = {}

    EXPAND_CATEGORIES = {
        "admission",
        "fees",
        "curriculum",
        "department",
        "international"
    }

    def build(self, program_folder):

        links_path = os.path.join(
            program_folder,
            "links.json"
        )

        if not os.path.exists(links_path):
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

            manifest["queue"].append({

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

                "parent": "program"
            })

        manifest["queue"].sort(

            key=lambda x: (

                x["depth"],

                -x["priority"],

                x["category"],

                x["title"].lower()
            )
        )

        manifest["statistics"]["pending"] = len(
            manifest["queue"]
        )

        output = os.path.join(

            program_folder,

            "crawl_manifest.json"
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