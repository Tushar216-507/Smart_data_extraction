from dataclasses import dataclass, field
from requests import Session
from discovery.models import CandidateURL


@dataclass
class DiscoveryContext:
    """
    Shared state across all discovery strategies.
    """

    base_url: str

    session: Session = field(default_factory=Session)

    visited_urls: set[str] = field(default_factory=set)

    discovered_urls: set[str] = field(default_factory=set)

    candidate_urls: dict[str, CandidateURL] = field(default_factory=dict)