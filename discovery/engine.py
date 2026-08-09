from discovery.context import DiscoveryContext
from discovery.models import CandidateURL, DiscoveryResult
from discovery.scoring import URLScorer
from discovery.strategies.sitemap import SitemapStrategy
from discovery.strategies.navigation import NavigationStrategy
from discovery.strategies.catalog import CatalogStrategy
from discovery.strategies.search import SearchStrategy
from discovery.strategies.crawler import CrawlerStrategy
from discovery.url_utils import URLCanonicalizer, ConservativeFilter


class DiscoveryEngine:
    """
    Coordinates all discovery strategies.

    Responsibilities:
    - Execute strategies
    - Merge results
    - Remove duplicates
    - Score candidates
    - Rank candidates
    """

    def __init__(self, strategies=None):

        if strategies is None:
            strategies = [
                SitemapStrategy(),
                NavigationStrategy(),
                CatalogStrategy(),
                SearchStrategy(),
                CrawlerStrategy(),
            ]

        self.strategies = sorted(
            strategies,
            key=self._strategy_priority,
        )

        self.scorer = URLScorer()
    
    def _strategy_priority(self, strategy) -> int:

        priorities = {
            "SitemapStrategy": 10,
            "NavigationStrategy": 20,
            "CatalogStrategy": 30,
            "SearchStrategy": 40,
            "CrawlerStrategy": 50,
        }

        return priorities.get(
            strategy.__class__.__name__,
            999,
        )

    def discover(self, base_url: str) -> DiscoveryResult:

        context = DiscoveryContext(base_url=base_url)

        result = DiscoveryResult()

        merged = {}

        for strategy in self.strategies:

            print(f"Running {strategy.__class__.__name__}...")

            candidates = strategy.discover(context)

            strategy_name = strategy.__class__.__name__

            result.strategy_stats[strategy_name] = {
                "found": len(candidates),
            }

            for candidate in candidates:
                
                # 1. Canonicalize
                candidate.url = URLCanonicalizer.canonicalize(candidate.url)
                
                # 2. Filter
                if not ConservativeFilter.is_valid(candidate.url):
                    result.strategy_stats[strategy_name]["filtered"] = result.strategy_stats[strategy_name].get("filtered", 0) + 1
                    continue

                # 3. Deduplicate
                if candidate.url in context.candidate_urls:
                    result.strategy_stats[strategy_name]["duplicates"] = result.strategy_stats[strategy_name].get("duplicates", 0) + 1
                    continue

                context.candidate_urls[candidate.url] = candidate

        scored = []

        for candidate in context.candidate_urls.values():

            scored.append(
                self.scorer.score(candidate)
            )

        scored.sort(
            key=lambda x: x.score,
            reverse=True,
        )

        for candidate in scored:
            result.add(candidate)

        print("\nDiscovery Summary")
        print("-" * 50)

        for strategy_name, stats in result.strategy_stats.items():
            found = stats.get('found', 0)
            filtered = stats.get('filtered', 0)
            dups = stats.get('duplicates', 0)
            print(f"{strategy_name:<20} Found: {found:>5} | Filtered: {filtered:>5} | Duplicates: {dups:>5}")

        print("-" * 70)
        print(f"Total candidates: {len(result.candidates)}\n")

        return result