from discovery.context import DiscoveryContext
from discovery.models import CandidateURL, DiscoveryResult
from discovery.scoring import URLScorer
from discovery.strategies.sitemap import SitemapStrategy
from discovery.strategies.navigation import NavigationStrategy
from discovery.strategies.catalog import CatalogStrategy
from discovery.strategies.search import SearchStrategy
from discovery.strategies.crawler import CrawlerStrategy


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

                if candidate.url in context.candidate_urls:
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
            print(f"{strategy_name:<25} {stats['found']:>5}")

        print("-" * 50)
        print(f"Total candidates: {len(result.candidates)}\n")

        return result