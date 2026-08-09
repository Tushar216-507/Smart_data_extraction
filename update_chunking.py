import re
from pathlib import Path

path = Path("knowledge/pdf/pdf_evidence_builder.py")
content = path.read_text(encoding="utf-8")

# Add import tiktoken
if "import tiktoken" not in content:
    content = content.replace("import re\n", "import re\nimport tiktoken\n")

# Replace variable names
content = content.replace("target_chunk_characters", "target_chunk_tokens")
content = content.replace("max_chunk_characters", "max_chunk_tokens")
content = content.replace("min_chunk_characters", "min_chunk_tokens")
content = content.replace("overlap_characters", "overlap_tokens")

# Replace default values in __init__
content = content.replace("target_chunk_tokens: int = 6500", "target_chunk_tokens: int = 1600")
content = content.replace("max_chunk_tokens: int = 9000", "max_chunk_tokens: int = 2200")
content = content.replace("min_chunk_tokens: int = 250", "min_chunk_tokens: int = 60")
content = content.replace("overlap_tokens: int = 350", "overlap_tokens: int = 80")

# The limit check in __init__ is `if target_chunk_tokens < 500:` -> `if target_chunk_tokens < 100:`
content = content.replace("if target_chunk_tokens < 500:", "if target_chunk_tokens < 100:")
content = content.replace("target_chunk_tokens must be at least 500", "target_chunk_tokens must be at least 100")

# Add encoder and measure_length to __init__
init_replacement = """        self.include_empty_sections = (
            bool(
                include_empty_sections
            )
        )

        self.output_filename = (
            str(
                output_filename
            ).strip()
            or self.DEFAULT_OUTPUT_FILENAME
        )

        self.encoder = tiktoken.get_encoding("cl100k_base")

    def _measure_length(self, text: str) -> int:
        return len(self.encoder.encode(text))"""

content = content.replace(
    "        self.output_filename = (\n            str(\n                output_filename\n            ).strip()\n            or self.DEFAULT_OUTPUT_FILENAME\n        )",
    "        self.output_filename = (\n            str(\n                output_filename\n            ).strip()\n            or self.DEFAULT_OUTPUT_FILENAME\n        )\n\n        self.encoder = tiktoken.get_encoding(\"cl100k_base\")\n\n    def _measure_length(self, text: str) -> int:\n        return len(self.encoder.encode(text))"
)

# Now manually replace len() with self._measure_length() in critical spots where text blocks are measured for chunking.
# But `len()` is also used for lists and tuples (e.g. len(section.blocks), len(paragraphs)). We must only replace len(content), len(section_heading), len(block.content), len(fragment), len(paragraph_part), len(sentence), len(group), len(current_parts), etc when it's text.
# The simplest approach is to use regex for common string length checks we saw.

patterns_to_replace = [
    (r"len\(\n\s*section_heading\n\s*\)", "self._measure_length(\n                section_heading\n            )"),
    (r"len\(\n\s*block\.content\n\s*\)", "self._measure_length(\n                block.content\n            )"),
    (r"len\(\n\s*current_group_text\n\s*\)", "self._measure_length(\n                current_group_text\n            )"),
    (r"len\(\n\s*overlap_text\n\s*\)", "self._measure_length(\n                overlap_text\n            )"),
    (r"len\(\n\s*content\n\s*\)", "self._measure_length(\n                content\n            )"),
    (r"len\(\n\s*paragraph_part\n\s*\)", "self._measure_length(\n                paragraph_part\n            )"),
    (r"len\(\n\s*overlap\n\s*\)", "self._measure_length(\n                overlap\n            )"),
    (r"len\(\n\s*paragraph\n\s*\)", "self._measure_length(\n                paragraph\n            )"),
    (r"len\(\n\s*sentence\n\s*\)", "self._measure_length(\n                sentence\n            )"),
]

for old, new in patterns_to_replace:
    content = re.sub(old, new, content)

# Check if there's any `len(text)` that needs to be replaced.
# In _hard_split_text: cursor + self.target_chunk_tokens is used, but that slices characters, not tokens!
# Wait, hard splitting by slicing text based on tokens is tricky: `text[cursor:end]`. 
# If `target_chunk_tokens` is 1600, doing `text[cursor: cursor + 1600]` slices 1600 CHARACTERS.
# We need to change `_hard_split_text` to correctly slice text into tokens, or just leave it slicing characters but proportionally larger (1600 * 4 = 6400 characters). Let's change `_hard_split_text` to slice by character proportion (target_chunk_tokens * 4) to keep it simple, since it's a fallback.

hard_split_replacement = """    def _hard_split_text(
        self,
        content: str,
    ) -> List[str]:
        \"\"\"
        Last-resort splitting. Uses an estimated character equivalent of tokens.
        \"\"\"
        
        target_chars = self.target_chunk_tokens * 4
        parts: List[str] = []

        cursor = 0
        content_length = len(
            content
        )

        while cursor < content_length:
            end = min(
                cursor
                + target_chars,
                content_length,
            )

            if end < content_length:
                last_space = content.rfind(
                    " ",
                    cursor,
                    end,
                )

                if (
                    last_space
                    != -1
                    and last_space
                    > cursor
                    + (
                        target_chars
                        // 2
                    )
                ):
                    end = last_space

            part = content[
                cursor:end
            ].strip()

            if part:
                parts.append(
                    part
                )

            cursor = end

        return parts"""

content = re.sub(r"    def _hard_split_text\(.*?return parts", hard_split_replacement, content, flags=re.DOTALL)


path.write_text(content, encoding="utf-8")
print("Update applied")
