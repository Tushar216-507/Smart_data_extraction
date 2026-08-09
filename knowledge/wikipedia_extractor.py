import urllib.parse
import requests
import json
from typing import Optional

class WikipediaExtractor:
    """
    Searches Wikipedia for a university and extracts its summary.
    """

    SEARCH_API = "https://en.wikipedia.org/w/api.php"
    SUMMARY_API = "https://en.wikipedia.org/api/rest_v1/page/summary/"

    def __init__(self):
        self.headers = {
            "User-Agent": "UniversityDataExtractionBot/1.0"
        }

    def search_university(self, query: str) -> Optional[str]:
        """
        Search Wikipedia for the university and return the best matching page title.
        """
        params = {
            "action": "query",
            "list": "search",
            "srsearch": query,
            "utf8": "1",
            "format": "json",
            "srlimit": 1
        }
        try:
            response = requests.get(self.SEARCH_API, params=params, headers=self.headers, timeout=10)
            if response.status_code == 200:
                data = response.json()
                results = data.get("query", {}).get("search", [])
                if results:
                    return results[0]["title"]
        except Exception as e:
            print(f"Wikipedia search error: {e}")
            
        return None

    def get_summary(self, page_title: str) -> Optional[dict]:
        """
        Get the summary (extract) of a Wikipedia page.
        """
        title_encoded = urllib.parse.quote(page_title)
        url = f"{self.SUMMARY_API}{title_encoded}"
        try:
            response = requests.get(url, headers=self.headers, timeout=10)
            if response.status_code == 200:
                data = response.json()
                return {
                    "title": data.get("title", page_title),
                    "extract": data.get("extract", ""),
                    "description": data.get("description", ""),
                    "url": data.get("content_urls", {}).get("desktop", {}).get("page", "")
                }
        except Exception as e:
            print(f"Wikipedia summary error: {e}")
            
        return None

    def extract(self, university_name: str) -> Optional[dict]:
        """
        Searches for the university and returns its summary info.
        """
        title = self.search_university(university_name)
        if not title:
            return None
            
        return self.get_summary(title)
