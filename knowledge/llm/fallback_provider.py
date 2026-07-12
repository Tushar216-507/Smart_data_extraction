from .provider import LLMProvider


class FallbackProvider(LLMProvider):
    """
    Tries the primary LLM provider first.

    If the primary provider fails because of an API,
    quota, rate-limit, timeout, or provider error,
    the same request is sent to the fallback provider.
    """

    def __init__(
        self,
        primary_provider: LLMProvider,
        fallback_provider: LLMProvider,
    ):
        self.primary_provider = (
            primary_provider
        )

        self.fallback_provider = (
            fallback_provider
        )

    def extract(
        self,
        system_prompt: str,
        user_prompt: str,
        response_schema=None,
        temperature: float = 0.0,
    ):
        try:
            return (
                self.primary_provider.extract(
                    system_prompt=system_prompt,
                    user_prompt=user_prompt,
                    response_schema=(
                        response_schema
                    ),
                    temperature=temperature,
                )
            )

        except Exception as primary_error:
            print()

            print(
                "⚠ Primary LLM provider failed."
            )

            print(
                f"Reason: {primary_error}"
            )

            print(
                "→ Retrying with fallback "
                "LLM provider..."
            )

            return (
                self.fallback_provider.extract(
                    system_prompt=system_prompt,
                    user_prompt=user_prompt,
                    response_schema=(
                        response_schema
                    ),
                    temperature=temperature,
                )
            )