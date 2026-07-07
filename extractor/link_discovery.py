from bs4 import BeautifulSoup
from urllib.parse import (
    urljoin,
    urlparse,
    urldefrag
)


class LinkDiscovery:

    IGNORE_SCHEMES = [
        "mailto:",
        "tel:",
        "javascript:"
    ]

    IGNORE_DOMAINS = [
        "facebook.com",
        "instagram.com",
        "linkedin.com",
        "youtube.com",
        "twitter.com",
        "x.com",
        "bsky.app",
        "goo.gl",
        "google.com/maps"
    ]

    NAVIGATION_KEYWORDS = [
        "privacy",
        "datenschutz",
        "impressum",
        "accessibility",
        "barrierefreiheit",
        "cookie",
        "facebook",
        "instagram",
        "linkedin",
        "youtube",
        "bluesky",
        "route anzeigen",
        "kontaktformular",
        "share",
        "teilen"
    ]

    def __init__(self):
        pass

    def classify(self, url, text):

        value = f"{url} {text}".lower()

        parsed = urlparse(url)

        path = parsed.path.lower()

        title = text.lower()

        category = "other"

        purpose = "navigation"

        priority = 10

        # -----------------------------
        # PDFs
        # -----------------------------

        if url.lower().endswith(".pdf"):

            purpose = "evidence"

            priority = 100

            if any(x in value for x in [
                "modul",
                "module",
                "modulhandbuch",
                "module handbook",
                "handbook"
            ]):
                category = "module_handbook"

            elif any(x in value for x in [
                "studienordnung",
                "prüfungsordnung",
                "prufungsordnung",
                "pruefungsordnung",
                "satzung"
            ]):
                category = "study_regulations"

            elif any(x in value for x in [
                "brochure",
                "brosch",
                "flyer",
                "prospectus",
                "prospekt"
            ]):
                category = "brochure"

            else:
                category = "pdf"

            return {

                "type": "pdf",

                "category": category,

                "purpose": purpose,

                "priority": priority
            }

        # -----------------------------
        # Admission
        # -----------------------------

        if any(x in path for x in [

            "admission",

            "zulassung",

            "bewerbung",

            "application",

            "apply",

            "immatrikulation"

        ]):

            return {

                "type": "page",

                "category": "admission",

                "purpose": "evidence",

                "priority": 95
            }

        # -----------------------------
        # Curriculum
        # -----------------------------

        if any(x in value for x in [

            "curriculum",

            "module",

            "modul",

            "studienaufbau"

        ]):

            return {

                "type": "page",

                "category": "curriculum",

                "purpose": "evidence",

                "priority": 90
            }

        # -----------------------------
        # Fees
        # -----------------------------

        if any(x in value for x in [

            "fee",

            "tuition",

            "cost",

            "gebühr",

            "beitrag"

        ]):

            return {

                "type": "page",

                "category": "fees",

                "purpose": "evidence",

                "priority": 90
            }

        # -----------------------------
        # Scholarships
        # -----------------------------

        if any(x in value for x in [

            "scholarship",

            "stipendium",

            "funding"

        ]):

            return {

                "type": "page",

                "category": "scholarship",

                "purpose": "evidence",

                "priority": 85
            }

        # -----------------------------
        # Department
        # -----------------------------

        if any(x in path for x in [

            "department",

            "faculty",

            "institut",

            "fakult"

        ]):

            return {

                "type": "page",

                "category": "department",

                "purpose": "evidence",

                "priority": 80
            }

        # -----------------------------
        # International
        # -----------------------------

        if any(x in path for x in [

            "international",

            "exchange",

            "erasmus"

        ]):

            return {

                "type": "page",

                "category": "international",

                "purpose": "evidence",

                "priority": 80
            }
        
        # -----------------------------
        # Career
        # -----------------------------

        if any(x in value for x in [

            "career",

            "employment",

            "internship",

            "praktikum"

        ]):

            return {

                "type": "page",

                "category": "career",

                "purpose": "evidence",

                "priority": 70
            }


        # -----------------------------
        # Contact
        # -----------------------------

        if any(x in path for x in [

            "contact",

            "beratung",

            "advisor",

            "ansprechpartner"

        ]):

            return {

                "type": "page",

                "category": "contact",

                "purpose": "evidence",

                "priority": 60
            }

        # -----------------------------
        # Discovery
        # -----------------------------

        if "sitemap" in value:

            return {

                "type": "page",

                "category": "sitemap",

                "purpose": "discovery",

                "priority": 40
            }

        if "search" in value:

            return {

                "type": "page",

                "category": "search",

                "purpose": "discovery",

                "priority": 30
            }

        return {

            "type": "page",

            "category": category,

            "purpose": purpose,

            "priority": priority
        }
        
    def discover(self, html, base_url):

        soup = BeautifulSoup(html, "html.parser")

        seen = set()

        results = []

        for a in soup.find_all("a", href=True):

            href = a["href"].strip()

            if not href:
                continue

            if any(
                href.startswith(x)
                for x in self.IGNORE_SCHEMES
            ):
                continue

            url = urljoin(base_url, href)

            url, _ = urldefrag(url)

            url = url.strip("/")

            if url == base_url.strip("/"):
                continue

            if url in seen:
                continue

            seen.add(url)

            text = a.get_text(" ", strip=True)

            if not text:
                continue

            if any(
                x in text.lower()
                for x in self.NAVIGATION_KEYWORDS
            ):
                continue

            parsed = urlparse(url)

            if any(
                domain in parsed.netloc.lower()
                for domain in self.IGNORE_DOMAINS
            ):
                continue

            is_pdf = url.lower().endswith(".pdf")

            info = self.classify(
                url,
                text
            )

            results.append({

                "source": "program_page",

                "relation": "direct",

                "type": info["type"],

                "title": text,

                "url": url,

                "domain": parsed.netloc,

                "internal": (
                    parsed.netloc ==
                    urlparse(base_url).netloc
                ),

                "category": info["category"],

                "purpose": info["purpose"],

                "priority": info["priority"],

                "visited": False
            })

        results.sort(
            key=lambda x: (

                -x["priority"],

                x["type"],

                x["category"],

                x["title"].lower()
            )
        )

        return results