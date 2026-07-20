from __future__ import annotations

from collections import defaultdict
from typing import Dict, List

from .pricing import Pricing
from .usage_record import UsageRecord


class UsageTracker:
    """
    Tracks every LLM call made during a pipeline run.

    A single UsageTracker instance can be shared across the
    entire program extraction pipeline.
    """

    def __init__(self):

        self.records: List[UsageRecord] = []

    # ------------------------------------------------------------------
    # Recording
    # ------------------------------------------------------------------

    def add(
        self,
        record: UsageRecord,
    ) -> None:

        self.records.append(record)

    # ------------------------------------------------------------------
    # Counts
    # ------------------------------------------------------------------

    @property
    def total_calls(self) -> int:

        return len(self.records)

    @property
    def prompt_tokens(self) -> int:

        return sum(
            r.prompt_tokens
            for r in self.records
        )

    @property
    def completion_tokens(self) -> int:

        return sum(
            r.completion_tokens
            for r in self.records
        )

    @property
    def total_tokens(self) -> int:

        return (
            self.prompt_tokens
            + self.completion_tokens
        )

    @property
    def total_cost(self) -> float:

        return sum(
            Pricing.total_cost(
                r.model,
                r.prompt_tokens,
                r.completion_tokens,
            )
            for r in self.records
        )

    # ------------------------------------------------------------------
    # Stage Summary
    # ------------------------------------------------------------------

    def stage_summary(self) -> Dict[str, dict]:

        summary = defaultdict(
            lambda: {
                "calls": 0,
                "prompt_tokens": 0,
                "completion_tokens": 0,
                "total_tokens": 0,
                "cost": 0.0,
            }
        )

        for record in self.records:

            stage = summary[
                record.stage
            ]

            stage["calls"] += 1

            stage["prompt_tokens"] += (
                record.prompt_tokens
            )

            stage["completion_tokens"] += (
                record.completion_tokens
            )

            stage["total_tokens"] += (
                record.prompt_tokens
                + record.completion_tokens
            )

            stage["cost"] += Pricing.total_cost(
                record.model,
                record.prompt_tokens,
                record.completion_tokens,
            )

        return dict(summary)

    # ------------------------------------------------------------------
    # Printing
    # ------------------------------------------------------------------

    def print_summary(self) -> None:

        print()
        print("=" * 80)
        print("LLM BILLING SUMMARY")
        print("=" * 80)

        print()

        print(
            f"LLM Calls          : {self.total_calls}"
        )

        print(
            f"Prompt Tokens     : {self.prompt_tokens:,}"
        )

        print(
            f"Completion Tokens : {self.completion_tokens:,}"
        )

        print(
            f"Total Tokens      : {self.total_tokens:,}"
        )

        print(
            f"Total Cost (USD)  : ${self.total_cost:.6f}"
        )

        print()