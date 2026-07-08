import json
from pathlib import Path

from .models import (
    EvidencePack,
    EvidencePage,
    PdfEvidence
)


class EvidencePackBuilder:

    def __init__(self):
        pass

    def load_json(self, path: Path):

        if not path.exists():
            return {}

        with open(
            path,
            "r",
            encoding="utf-8"
        ) as f:

            return json.load(f)

    def load_text(self, path: Path):

        if not path.exists():
            return ""

        return path.read_text(
            encoding="utf-8"
        )

    def build(
        self,
        program_folder
    ):

        root = Path(program_folder)

        program_dir = root / "program"

        program_metadata = self.load_json(
            program_dir / "metadata.json"
        )

        program_markdown = self.load_text(
            program_dir / "program.md"
        )

        pack = EvidencePack(

            university=program_metadata.get(
                "university",
                ""
            ),

            program_name=program_metadata.get(
                "title",
                ""
            ),

            program_markdown=program_markdown,

            program_metadata=program_metadata,

            crawl_manifest=self.load_json(
                root / "crawl_manifest.json"
            ),

            links=self.load_json(
                root / "links.json"
            )
        )

        pages_root = root / "pages"

        if not pages_root.exists():
            return pack

        for folder in sorted(
            pages_root.iterdir()
        ):

            if not folder.is_dir():
                continue

            metadata = self.load_json(
                folder / "metadata.json"
            )

            if metadata.get("type") == "pdf":

                pdf = folder / "assets" / "source.pdf"

                pack.pdfs.append(

                    PdfEvidence(

                        id=metadata.get("id", ""),

                        title=metadata.get("title", ""),

                        category=metadata.get(
                            "category",
                            ""
                        ),

                        pdf_path=str(pdf),

                        metadata=metadata
                    )
                )

            else:

                page_md = self.load_text(
                    folder / "page.md"
                )

                pack.pages.append(

                    EvidencePage(

                        id=metadata.get("id", ""),

                        title=metadata.get("title", ""),

                        category=metadata.get(
                            "category",
                            ""
                        ),

                        type=metadata.get(
                            "type",
                            "page"
                        ),

                        markdown=page_md,

                        metadata=metadata
                    )
                )

        return pack