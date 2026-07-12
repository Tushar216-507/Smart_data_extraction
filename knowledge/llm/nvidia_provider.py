import json

from openai import OpenAI

from config import Config

from .provider import LLMProvider


class NvidiaProvider(LLMProvider):
    """
    LLM provider for the NVIDIA API.

    NVIDIA exposes an OpenAI-compatible API, so this
    provider uses the official OpenAI Python client.
    """

    def __init__(
        self,
        api_key: str,
        model: str = Config.NVIDIA_MODEL,
        max_tokens: int = 4096,
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
        )

        self.model = model
        self.max_tokens = max_tokens

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

        response = (
            self.client
            .chat
            .completions
            .create(
                **request_options
            )
        )

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

        try:
            data = json.loads(
                content
            )

        except json.JSONDecodeError as error:
            raise ValueError(
                "Invalid JSON returned by NVIDIA:"
                f"\n\n{content}"
            ) from error

        if not isinstance(
            data,
            dict,
        ):
            raise ValueError(
                "NVIDIA response must be "
                "a JSON object."
            )

        if "facts" not in data:
            raise ValueError(
                "Missing 'facts' in "
                "NVIDIA response."
            )

        if not isinstance(
            data["facts"],
            list,
        ):
            raise ValueError(
                "'facts' must be a list."
            )

        return data