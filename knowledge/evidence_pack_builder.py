import json
from pathlib import Path

from .models import (
    EvidencePack,
    EvidencePage,
    PdfEvidence,
    ProgramEvidence
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

        program=ProgramEvidence(

            markdown=program_markdown,

            metadata=program_metadata,

            raw_html=self.load_text(
                program_dir / "raw.html"
            ),

            clean_html=self.load_text(
                program_dir / "clean.html"
            )

        ),

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

                        document_type=metadata.get(
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

                        clean_html=self.load_text(
                            folder / "clean.html"
                        ),

                        metadata=metadata
                    )
                )

        return pack