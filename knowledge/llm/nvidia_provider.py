import json
import time

from openai import OpenAI

from config import Config

from .provider import LLMProvider

from .llm_response import LLMResponse


class NvidiaProvider(LLMProvider):
    """
    LLM provider for the NVIDIA API.

    NVIDIA exposes an OpenAI-compatible API, so this
    provider uses the official OpenAI Python client.

    Includes bounded exponential backoff for transient
    failures (500, 502, 503, 504, 429, connection errors).
    """

    # HTTP status codes that are safe to retry.
    RETRYABLE_STATUS_CODES = {429, 500, 502, 503, 504}

    def __init__(
        self,
        api_key: str,
        model: str = Config.NVIDIA_MODEL,
        max_tokens: int = 4096,
        max_retries: int = 3,
        base_retry_delay: float = 2.0,
    ):
        if not api_key:
            raise ValueError(
                "NVIDIA API key is missing."
            )

        self.client = OpenAI(
            base_url=(
                "https://integrate.api.nvidia.com/v1"
            ),
            api_key=api_key,
            timeout=20.0,
            max_retries=0
        )

        self.model = model
        self.provider_name = "NVIDIA"
        self.max_tokens = max_tokens
        self.max_retries = max(1, max_retries)
        self.base_retry_delay = max(0.5, base_retry_delay)

    def extract(
        self,
        system_prompt: str,
        user_prompt: str,
        response_schema=None,
        temperature: float = 0.0,
    ):
        """
        Send an extraction or normalization request
        through the NVIDIA API.

        Retries transient failures with bounded
        exponential backoff (2s → 4s → 8s).
        """

        messages = [
            {
                "role": "system",
                "content": system_prompt,
            },
            {
                "role": "user",
                "content": user_prompt,
            },
        ]

        request_options = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": self.max_tokens,
            "stream": False,
        }

        if response_schema is not None:
            request_options[
                "response_format"
            ] = response_schema

        # -------------------------------------------------
        # Retry loop with exponential backoff
        # -------------------------------------------------

        last_error = None

        for attempt in range(1, self.max_retries + 1):
            try:
                response = (
                    self.client
                    .chat
                    .completions
                    .create(
                        **request_options
                    )
                )

                # Successful API call — break out of retry loop
                return self._parse_response(response)

            except Exception as error:
                last_error = error

                if self._is_retryable(error) and attempt < self.max_retries:
                    delay = self.base_retry_delay * (2 ** (attempt - 1))
                    print(
                        f"  [RETRY] NVIDIA attempt {attempt}/{self.max_retries} failed: "
                        f"{type(error).__name__}: {error}"
                    )
                    print(f"    Retrying in {delay:.0f}s...")
                    time.sleep(delay)
                    continue

                # Non-retryable or final attempt
                raise

        # Should not reach here, but safety net
        raise last_error

    def _parse_response(self, response) -> LLMResponse:
        """
        Parse a successful NVIDIA API response into
        an LLMResponse object.

        The provider parses JSON but does NOT validate
        the response schema (e.g. requiring 'facts').
        That validation belongs to the caller.
        """

        usage = response.usage

        content = (
            response
            .choices[0]
            .message
            .content
        )

        if not content:
            raise ValueError(
                "NVIDIA returned an empty response."
            )

        # Remove markdown code fences if present
        content = content.strip()

        if content.startswith("```json"):
            content = content[7:]

        if content.startswith("```"):
            content = content[3:]

        if content.endswith("```"):
            content = content[:-3]

        content = content.strip()

        try:
            data = json.loads(content)

        except json.JSONDecodeError:
            print("\nInvalid JSON received from NVIDIA.")
            print("Response length:", len(content))
            print(content[:1000])
            raise

        if not isinstance(
            data,
            dict,
        ):
            raise ValueError(
                "NVIDIA response must be "
                "a JSON object."
            )

        return LLMResponse(
            result=data,

            provider=self.provider_name,

            model=self.model,

            prompt_tokens=(
                usage.prompt_tokens
                if usage
                else 0
            ),

            completion_tokens=(
                usage.completion_tokens
                if usage
                else 0
            ),
        )

    def _is_retryable(self, error: Exception) -> bool:
        """
        Determine whether an error is transient and
        safe to retry.
        """

        error_str = str(error).lower()

        # Check for retryable HTTP status codes
        for code in self.RETRYABLE_STATUS_CODES:
            if str(code) in str(error):
                return True

        if isinstance(error, json.JSONDecodeError):
            return True

        # Check for rate limit indicators
        if "rate" in error_str and "limit" in error_str:
            return True

        # Check for connection/timeout errors
        if any(
            keyword in error_str
            for keyword in [
                "connection",
                "timeout",
                "timed out",
                "temporarily",
                "unavailable",
                "reset by peer",
                "broken pipe",
            ]
        ):
            return True

        return False