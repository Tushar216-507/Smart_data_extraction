import json
import os

from extractor.page_pipeline import PagePipeline


class EvidenceExpander:

    CATEGORIES = [

        "admission",

        "fees",

        "curriculum",

        "department",

        "international",

        "scholarship",

        "career",

        "contact"
    ]

    def __init__(self):

        self.pipeline = PagePipeline()

    def expand(self, folder):

        links_file = os.path.join(
            folder,
            "links.json"
        )

        if not os.path.exists(links_file):
            return

        with open(
            links_file,
            "r",
            encoding="utf-8"
        ) as f:

            data = json.load(f)

        for link in data["links"]:

            if link["visited"]:
                continue

            if link["category"] not in self.CATEGORIES:
                continue

            print(
                f'  -> {link["category"]}'
            )

            page = self.pipeline.process(
                link["url"]
            )

            page_folder = os.path.join(

                folder,

                "pages",

                link["category"]

            )

            os.makedirs(
                page_folder,
                exist_ok=True
            )

            with open(
                os.path.join(page_folder, "raw.html"),
                "w",
                encoding="utf-8"
            ) as f:

                f.write(page["raw_html"])

            with open(
                os.path.join(page_folder, "clean.html"),
                "w",
                encoding="utf-8"
            ) as f:

                f.write(page["clean_html"])

            filename = f"{link['category']}.md"

            with open(
                os.path.join(page_folder, filename),
                "w",
                encoding="utf-8"
            ) as f:

                f.write(page["markdown"])

            link["visited"] = True

        with open(
            links_file,
            "w",
            encoding="utf-8"
        ) as f:

            json.dump(
                data,
                f,
                indent=4,
                ensure_ascii=False
            )