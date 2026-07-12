from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass
class EvidenceChunk:
    """
    A logical section of programme evidence.

    Attributes:
        chunk_id:
            Stable identifier for the chunk.

        title:
            Markdown section title or generated chunk title.

        content:
            Complete text supplied to the extractor.

        order:
            Original position in the source document.

        source_type:
            Type of source from which the chunk was created.
    """

    chunk_id: str
    title: str
    content: str
    order: int
    source_type: str = "program"


class EvidenceChunker:
    """
    Splits programme evidence into logical chunks.

    Markdown headings are used as the preferred split boundaries.
    Large sections are split further using paragraph boundaries.

    The chunker avoids cutting text blindly whenever possible.
    """

    HEADING_PATTERN = re.compile(
        r"^(#{1,6})\s+(.+?)\s*$",
        re.MULTILINE,
    )

    def __init__(
        self,
        max_characters: int = 14_000,
        minimum_chunk_characters: int = 500,
    ):
        if max_characters <= 0:
            raise ValueError(
                "max_characters must be greater than zero."
            )

        if minimum_chunk_characters < 0:
            raise ValueError(
                "minimum_chunk_characters cannot be negative."
            )

        if minimum_chunk_characters >= max_characters:
            raise ValueError(
                "minimum_chunk_characters must be smaller "
                "than max_characters."
            )

        self.max_characters = max_characters
        self.minimum_chunk_characters = (
            minimum_chunk_characters
        )

    def chunk(
        self,
        content: str,
        source_type: str = "program",
    ) -> list[EvidenceChunk]:
        """
        Split evidence into ordered logical chunks.

        Args:
            content:
                Programme Markdown or plain text.

            source_type:
                Source label stored with every chunk.

        Returns:
            Ordered EvidenceChunk objects.
        """

        content = self._clean_content(content)

        if not content:
            return []

        sections = self._split_by_headings(content)

        chunks: list[EvidenceChunk] = []

        for title, section_content in sections:
            section_parts = self._split_large_section(
                section_content
            )

            for part_number, part in enumerate(
                section_parts,
                start=1,
            ):
                chunk_title = title

                if len(section_parts) > 1:
                    chunk_title = (
                        f"{title} - Part {part_number}"
                    )

                chunks.append(
                    EvidenceChunk(
                        chunk_id="",
                        title=chunk_title,
                        content=part,
                        order=len(chunks),
                        source_type=source_type,
                    )
                )

        chunks = self._merge_small_chunks(chunks)

        for index, chunk in enumerate(
            chunks,
            start=1,
        ):
            chunk.chunk_id = (
                f"{source_type}_{index:04d}"
            )

            chunk.order = index - 1

        return chunks

    def _clean_content(
        self,
        content: str,
    ) -> str:
        """
        Normalize line endings and excessive blank lines.
        """

        if not isinstance(content, str):
            raise TypeError(
                "content must be a string."
            )

        content = content.replace(
            "\r\n",
            "\n",
        ).replace(
            "\r",
            "\n",
        )

        content = re.sub(
            r"\n{4,}",
            "\n\n\n",
            content,
        )

        return content.strip()

    def _split_by_headings(
        self,
        content: str,
    ) -> list[tuple[str, str]]:
        """
        Split Markdown using headings while preserving headings
        inside their corresponding section content.
        """

        matches = list(
            self.HEADING_PATTERN.finditer(content)
        )

        if not matches:
            return [
                (
                    "Programme Information",
                    content,
                )
            ]

        sections: list[tuple[str, str]] = []

        first_heading_position = matches[0].start()

        preamble = content[
            :first_heading_position
        ].strip()

        if preamble:
            sections.append(
                (
                    "Programme Overview",
                    preamble,
                )
            )

        for index, match in enumerate(matches):
            start = match.start()

            if index + 1 < len(matches):
                end = matches[index + 1].start()
            else:
                end = len(content)

            title = match.group(2).strip()

            section_content = content[
                start:end
            ].strip()

            if section_content:
                sections.append(
                    (
                        title,
                        section_content,
                    )
                )

        return sections

    def _split_large_section(
        self,
        content: str,
    ) -> list[str]:
        """
        Split an oversized section using paragraph boundaries.
        """

        if len(content) <= self.max_characters:
            return [content]

        paragraphs = re.split(
            r"\n\s*\n",
            content,
        )

        parts: list[str] = []
        current_part: list[str] = []
        current_length = 0

        for paragraph in paragraphs:
            paragraph = paragraph.strip()

            if not paragraph:
                continue

            paragraph_length = len(paragraph)

            if paragraph_length > self.max_characters:
                if current_part:
                    parts.append(
                        "\n\n".join(
                            current_part
                        )
                    )

                    current_part = []
                    current_length = 0

                parts.extend(
                    self._split_oversized_paragraph(
                        paragraph
                    )
                )

                continue

            added_length = (
                paragraph_length
                if not current_part
                else paragraph_length + 2
            )

            if (
                current_part
                and current_length + added_length
                > self.max_characters
            ):
                parts.append(
                    "\n\n".join(
                        current_part
                    )
                )

                current_part = [paragraph]
                current_length = paragraph_length

            else:
                current_part.append(
                    paragraph
                )

                current_length += added_length

        if current_part:
            parts.append(
                "\n\n".join(
                    current_part
                )
            )

        return [
            part.strip()
            for part in parts
            if part.strip()
        ]

    def _split_oversized_paragraph(
        self,
        paragraph: str,
    ) -> list[str]:
        """
        Split a very large paragraph using line boundaries.

        Character slicing is used only as a final fallback.
        """

        lines = paragraph.splitlines()

        parts: list[str] = []
        current_lines: list[str] = []
        current_length = 0

        for line in lines:
            line = line.strip()

            if not line:
                continue

            if len(line) > self.max_characters:
                if current_lines:
                    parts.append(
                        "\n".join(
                            current_lines
                        )
                    )

                    current_lines = []
                    current_length = 0

                parts.extend(
                    self._split_long_text(
                        line
                    )
                )

                continue

            added_length = (
                len(line)
                if not current_lines
                else len(line) + 1
            )

            if (
                current_lines
                and current_length + added_length
                > self.max_characters
            ):
                parts.append(
                    "\n".join(
                        current_lines
                    )
                )

                current_lines = [line]
                current_length = len(line)

            else:
                current_lines.append(
                    line
                )

                current_length += added_length

        if current_lines:
            parts.append(
                "\n".join(
                    current_lines
                )
            )

        return parts

    def _split_long_text(
        self,
        text: str,
    ) -> list[str]:
        """
        Final fallback for a single unbroken block.
        """

        return [
            text[
                start:
                start + self.max_characters
            ].strip()
            for start in range(
                0,
                len(text),
                self.max_characters,
            )
            if text[
                start:
                start + self.max_characters
            ].strip()
        ]

    def _merge_small_chunks(
        self,
        chunks: list[EvidenceChunk],
    ) -> list[EvidenceChunk]:
        """
        Merge very small adjacent chunks when the combined size
        remains below the configured maximum.
        """

        if not chunks:
            return []

        merged: list[EvidenceChunk] = []

        for chunk in chunks:
            if not merged:
                merged.append(chunk)
                continue

            previous = merged[-1]

            combined_length = (
                len(previous.content)
                + len(chunk.content)
                + 2
            )

            should_merge = (
                len(chunk.content)
                < self.minimum_chunk_characters
                and combined_length
                <= self.max_characters
            )

            if should_merge:
                previous.title = (
                    f"{previous.title} + "
                    f"{chunk.title}"
                )

                previous.content = (
                    f"{previous.content}\n\n"
                    f"{chunk.content}"
                )

            else:
                merged.append(chunk)

        return merged