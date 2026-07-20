from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from dataclasses import dataclass, field


@dataclass(slots=True)
class UsageRecord:
    """
    Represents one LLM API call.
    """

    provider: str
    model: str

    stage: str
    program_id: str

    prompt_tokens: int
    completion_tokens: int

    duration_seconds: float = 0.0

    chunk_id: str | None = None

    timestamp: datetime = field(
        default_factory=datetime.utcnow
    )

    @property
    def total_tokens(self) -> int:
        return (
            self.prompt_tokens
            + self.completion_tokens
        )