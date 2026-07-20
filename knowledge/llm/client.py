from .provider import LLMProvider
from .llm_response import LLMResponse

from knowledge.billing.usage_record import UsageRecord
from knowledge.billing.usage_tracker import UsageTracker


class LLMClient:

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

        self.stage = stage
        self.program_id = program_id

    def extract(
        self,
        system_prompt: str,
        user_prompt: str,
        response_schema=None,
        temperature: float = 0.0
    ):

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

        return response.result