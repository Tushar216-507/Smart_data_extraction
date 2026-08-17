from typing import List
from duckduckgo_search import DDGS

class TargetedSearchProvider:
    """
    Provides targeted web search capabilities.
    Abstracts the underlying search engine (DuckDuckGo initially).
    """
    def __init__(self, max_results_per_query: int = 5):
        self.max_results = max_results_per_query
        
    def search_programme_pages(self, query: str) -> List[str]:
        """
        Executes a targeted search and returns a list of URLs.
        
        Args:
            query: The search query (e.g. '"Program Name" site:university.edu curriculum')
            
        Returns:
            List of discovered URLs.
        """
        urls = []
        try:
            # Using DuckDuckGo Search via DDGS
            with DDGS() as ddgs:
                results = ddgs.text(query, max_results=self.max_results)
                if results:
                    for r in results:
                        if "href" in r:
                            urls.append(r["href"])
        except Exception as e:
            print(f"  [WARN] Targeted search failed for '{query}': {e}")
            
        return urls
