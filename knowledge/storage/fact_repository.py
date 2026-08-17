from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from knowledge.facts import (
    ExtractedFact,
)


class FactRepository:
    """
    Saves and loads extracted facts as JSON.

    This allows raw GPT extraction results to be reused
    without calling the extraction model again.
    """

    def save(
        self,
        facts: list[ExtractedFact],
        output_path: str | Path,
    ) -> Path:
        """
        Save extracted facts to a JSON file.
        """

        path = Path(output_path)

        path.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        data = {
            "fact_count": len(facts),
            "facts": [
                self._fact_to_dict(fact)
                for fact in facts
            ],
        }

        with path.open(
            "w",
            encoding="utf-8",
        ) as file:
            json.dump(
                data,
                file,
                ensure_ascii=False,
                indent=2,
                default=str,
            )

        return path

    def load(
        self,
        input_path: str | Path,
    ) -> list[ExtractedFact]:
        """
        Load extracted facts from a saved JSON file.
        """

        path = Path(input_path)

        if not path.exists():
            raise FileNotFoundError(
                f"Fact file was not found: {path}"
            )

        with path.open(
            "r",
            encoding="utf-8",
        ) as file:
            data = json.load(file)

        raw_facts = data.get(
            "facts",
            [],
        )

        if not isinstance(
            raw_facts,
            list,
        ):
            raise ValueError(
                "The 'facts' field must be a list."
            )

        facts: list[ExtractedFact] = []

        for fact_data in raw_facts:

            if not isinstance(
                fact_data,
                dict,
            ):
                raise ValueError(
                    "Every saved fact must be "
                    "a JSON object."
                )

            facts.append(
                self._dict_to_fact(
                    fact_data
                )
            )

        return facts

    @staticmethod
    def _fact_to_dict(
        fact: ExtractedFact,
    ) -> dict[str, Any]:
        """
        Convert one ExtractedFact into JSON-safe data.
        """

        source_data = None
        if fact.source_url or fact.source_type:
            source_data = {
                "source_type": fact.source_type,
                "url": fact.source_url,
            }

        metadata = fact.metadata

        if not isinstance(
            metadata,
            dict,
        ):
            metadata = {}

        return {
            "category": fact.category,
            "field": fact.field,
            "value": fact.value,
            "confidence": fact.confidence,
            "source": source_data,
            "metadata": metadata,
        }

    @staticmethod
    def _dict_to_fact(
        data: dict[str, Any],
    ) -> ExtractedFact:
        """
        Reconstruct one ExtractedFact from saved JSON.
        """

        source_url = data.get("source_url", "")
        source_type = data.get("source_type", "")
        programme_association = data.get("programme_association", "")
        
        # Backwards compatibility for old JSON
        source_data = data.get("source")
        if isinstance(source_data, dict):
            if not source_url:
                source_url = source_data.get("url", "")
            if not source_type:
                source_type = source_data.get("source_type", "")

        metadata = data.get(
            "metadata",
            {},
        )

        if not isinstance(
            metadata,
            dict,
        ):
            metadata = {}

        return ExtractedFact(
            category=data.get(
                "category",
                "other",
            ),
            field=data.get(
                "field",
                "unknown",
            ),
            value=data.get(
                "value",
            ),
            confidence=float(
                data.get(
                    "confidence",
                    1.0,
                )
            ),
            source_url=source_url,
            source_type=source_type,
            programme_association=programme_association,
            metadata=metadata,
        )