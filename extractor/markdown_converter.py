from markdownify import markdownify as md


class MarkdownConverter:

    def __init__(self):
        pass

    def convert(self, clean_html):

        if not clean_html:
            return ""

        markdown = md(
            clean_html,
            heading_style="ATX",
            bullets="-",
            strip=[
                "script",
                "style"
            ]
        )

        markdown = self.cleanup(markdown)

        return markdown

    def cleanup(self, markdown):

        lines = []

        previous_blank = False

        for line in markdown.splitlines():

            line = line.rstrip()

            if line == "":

                if previous_blank:
                    continue

                previous_blank = True

            else:

                previous_blank = False

            lines.append(line)

        return "\n".join(lines).strip()