from .provider import LLMProvider
from .llm_response import LLMResponse

from knowledge.billing.usage_record import UsageRecord
from knowledge.billing.usage_tracker import UsageTracker
from knowledge.llm.llm_cache import LLMCache


class LLMClient:
    """
    Thin wrapper around an LLM provider that:
    - Validates the response shape (expects 'facts')
    - Tracks token usage and cost
    - Records failed items gracefully instead of crashing
    """

    def __init__(
    self,
        provider: LLMProvider,
        usage_tracker: UsageTracker | None = None,
        stage: str = "Unknown",
        program_id: str = "",
    ):

        self.provider = provider

        self.usage_tracker = (
            usage_tracker
            if usage_tracker
            else UsageTracker()
        )
        
        self.cache = LLMCache()

        self.stage = stage
        self.program_id = program_id

    def extract(
        self,
        system_prompt: str,
        user_prompt: str,
        response_schema=None,
        temperature: float = 0.0
    ):

        # Check cache first
        cached_result = self.cache.get(
            provider_name=self.provider.provider_name,
            model=self.provider.model,
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            response_schema=response_schema,
            temperature=temperature,
        )

        if cached_result is not None:
            # Validate facts shape even for cached results
            if not isinstance(cached_result, dict) or "facts" not in cached_result or not isinstance(cached_result["facts"], list):
                # Invalid cache, proceed to fetch
                pass
            else:
                return cached_result

        response: LLMResponse = self.provider.extract(

            system_prompt=system_prompt,

            user_prompt=user_prompt,

            response_schema=response_schema,

            temperature=temperature
        )

        self.usage_tracker.add(

            UsageRecord(

                provider=response.provider,

                model=response.model,

                stage=self.stage,

                program_id=self.program_id,

                prompt_tokens=response.prompt_tokens,

                completion_tokens=response.completion_tokens,

                duration_seconds=response.duration_seconds,
            )
        )

        # Validate that the response contains a 'facts' list.
        # This validation was previously in the NVIDIA provider
        # but belongs here so the provider remains reusable for
        # non-fact responses.
        result = response.result

        if not isinstance(result, dict):
            raise ValueError(
                f"LLM response must be a JSON object, "
                f"got {type(result).__name__}."
            )

        if "facts" not in result:
            raise ValueError(
                "Missing 'facts' in LLM response."
            )

        if not isinstance(result["facts"], list):
            raise ValueError(
                "'facts' must be a list."
            )

        self.cache.set(
            provider_name=self.provider.provider_name,
            model=self.provider.model,
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            response_schema=response_schema,
            temperature=temperature,
            result=result,
        )

        return result

    def extract_raw(
        self,
        system_prompt: str,
        user_prompt: str,
        response_schema=None,
        temperature: float = 0.0,
    ):
        """
        Extract without validating 'facts' shape.

        Use this for non-fact LLM calls such as
        classification, translation, or summarization.
        """

        # Check cache first
        cached_result = self.cache.get(
            provider_name=self.provider.provider_name,
            model=self.provider.model,
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            response_schema=response_schema,
            temperature=temperature,
        )

        if cached_result is not None:
            return cached_result

        response: LLMResponse = self.provider.extract(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            response_schema=response_schema,
            temperature=temperature,
        )

        self.usage_tracker.add(
            UsageRecord(
                provider=response.provider,
                model=response.model,
                stage=self.stage,
                program_id=self.program_id,
                prompt_tokens=response.prompt_tokens,
                completion_tokens=response.completion_tokens,
                duration_seconds=response.duration_seconds,
            )
        )

        self.cache.set(
            provider_name=self.provider.provider_name,
            model=self.provider.model,
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            response_schema=response_schema,
            temperature=temperature,
            result=response.result,
        )

        return response.result