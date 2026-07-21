from abc import ABC, abstractmethod

from discovery.context import DiscoveryContext
from discovery.models import CandidateURL


class DiscoveryStrategy(ABC):
    """
    Base class for all discovery strategies.

    Every strategy receives the university base URL and returns
    a list of CandidateURL objects.
    """

    @abstractmethod
    def discover(self, context: DiscoveryContext) -> list[CandidateURL]:
        """
        Discover candidate program URLs.

        Args:
            base_url: University homepage URL.

        Returns:
            List of CandidateURL objects.
        """
        raise NotImplementedError