from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ModelPricing:
    """
    Pricing is expressed in USD per 1 million tokens.

    Cost calculation:

        cost = (tokens / 1_000_000) * price
    """

    input_price_per_million: float
    output_price_per_million: float


class Pricing:

    DEFAULT = ModelPricing(
        input_price_per_million=0.0,
        output_price_per_million=0.0,
    )

    PRICING = {

        # ---------------------------------------------------------
        # OpenAI
        # ---------------------------------------------------------

        "gpt-4.1": ModelPricing(
            input_price_per_million=2.00,
            output_price_per_million=8.00,
        ),

        "gpt-4.1-mini": ModelPricing(
            input_price_per_million=0.40,
            output_price_per_million=1.60,
        ),

        "gpt-4.1-nano": ModelPricing(
            input_price_per_million=0.10,
            output_price_per_million=0.40,
        ),

        # ---------------------------------------------------------
        # NVIDIA Hosted Models
        # ---------------------------------------------------------

        "openai/gpt-oss-120b": ModelPricing(
            input_price_per_million=0.15,
            output_price_per_million=0.60,
        ),

        "meta/llama-3.1-70b-instruct": ModelPricing(
            input_price_per_million=0.90,
            output_price_per_million=0.90,
        ),

        # ---------------------------------------------------------
        # Groq
        # ---------------------------------------------------------

        "llama-3.3-70b-versatile": ModelPricing(
            input_price_per_million=0.59,
            output_price_per_million=0.79,
        ),
    }

    @classmethod
    def get(cls, model: str) -> ModelPricing:

        if not model:
            return cls.DEFAULT

        return cls.PRICING.get(
            model,
            cls.DEFAULT,
        )

    @classmethod
    def input_cost(
        cls,
        model: str,
        tokens: int,
    ) -> float:

        pricing = cls.get(model)

        return (
            tokens / 1_000_000
        ) * pricing.input_price_per_million

    @classmethod
    def output_cost(
        cls,
        model: str,
        tokens: int,
    ) -> float:

        pricing = cls.get(model)

        return (
            tokens / 1_000_000
        ) * pricing.output_price_per_million

    @classmethod
    def total_cost(
        cls,
        model: str,
        prompt_tokens: int,
        completion_tokens: int,
    ) -> float:

        return (
            cls.input_cost(
                model,
                prompt_tokens,
            )
            +
            cls.output_cost(
                model,
                completion_tokens,
            )
        )