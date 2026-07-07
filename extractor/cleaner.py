import trafilatura

from bs4 import BeautifulSoup
from bs4 import NavigableString


class HTMLCleaner:

    def __init__(self):
        pass

    def normalize(self, html):

        soup = BeautifulSoup(html, "html.parser")

        # --------------------------------------------------
        # Remove unwanted tags
        # --------------------------------------------------

        for tag in soup([
            "script",
            "style",
            "noscript",
            "svg",
            "iframe"
        ]):
            tag.decompose()

        # --------------------------------------------------
        # Convert Definition Lists
        #
        # <dt>ECTS</dt>
        # <dd>120</dd>
        #
        # becomes
        #
        # <p><strong>ECTS:</strong> 120</p>
        # --------------------------------------------------

        for dl in soup.find_all("dl"):

            new_nodes = []

            dts = dl.find_all("dt", recursive=False)
            dds = dl.find_all("dd", recursive=False)

            for dt, dd in zip(dts, dds):

                p = soup.new_tag("p")

                strong = soup.new_tag("strong")
                strong.string = dt.get_text(" ", strip=True) + ": "

                p.append(strong)
                p.append(
                    NavigableString(
                        dd.get_text(" ", strip=True)
                    )
                )

                new_nodes.append(p)

            dl.replace_with(*new_nodes)

        # --------------------------------------------------
        # Expand Accordion Content
        #
        # Keep heading
        # Keep body
        #
        # Flatten into normal HTML
        # --------------------------------------------------

        for accordion in soup.select(".accordion__item"):

            container = soup.new_tag("div")

            title = accordion.select_one(
                ".accordion__btn-inner"
            )

            if title:

                h3 = soup.new_tag("h3")
                h3.string = title.get_text(strip=True)

                container.append(h3)

            body = accordion.select_one(
                ".accordion__content-inner"
            )

            if body:

                for child in list(body.children):
                    container.append(child)

            accordion.replace_with(container)

        # --------------------------------------------------
        # Remove empty tags
        # --------------------------------------------------

        for tag in soup.find_all():

            if tag.name in ["p", "div", "span"]:

                if not tag.get_text(" ", strip=True):

                    tag.decompose()

        # Remove empty links
        for a in soup.find_all("a"):

            if not a.get_text(strip=True):

                a.decompose()

        return str(soup)

    def clean(self, html):

        normalized = self.normalize(html)

        cleaned = trafilatura.extract(
            normalized,
            output_format="html",
            include_tables=True,
            include_comments=False,
            include_links=True,
            include_images=False,
            deduplicate=True,
            favor_precision=True
        )

        if cleaned is None:
            return ""

        return cleaned