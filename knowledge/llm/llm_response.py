from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True)
class LLMResponse:
    """
    Represents a single response returned by an LLM provider.

    The provider returns this object to the LLMClient, which can
    record usage statistics before returning only the parsed result
    to the caller.
    """

    result: dict

    provider: str
    model: str

    prompt_tokens: int
    completion_tokens: int

    duration_seconds: float = 0.0

    @property
    def total_tokens(self) -> int:
        return (
            self.prompt_tokens
            + self.completion_tokens
        )