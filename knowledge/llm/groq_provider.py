import json

from groq import Groq

from config import Config

from .provider import LLMProvider


class GroqProvider(LLMProvider):
    """
    LLM provider using the official Groq Python SDK.

    It follows the same interface as OpenAIProvider so it
    can be used through the existing LLMClient.
    """

    def __init__(
        self,
        api_key: str = Config.GROQ_API_KEY,
        model: str = Config.GROQ_MODEL,
    ):

        if not api_key:
            raise ValueError(
                "Groq API key is missing."
            )

        self.client = Groq(
            api_key=api_key
        )

        self.model = model

    def extract(
        self,
        system_prompt: str,
        user_prompt: str,
        response_schema=None,
        temperature: float = 0.0,
    ):
        """
        Send an extraction or normalization request to Groq.

        Returns:
            Parsed JSON response as a dictionary.
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
                "Groq returned an empty response."
            )

        try:

            data = json.loads(
                content
            )

        except json.JSONDecodeError as error:

            raise ValueError(
                "Invalid JSON returned by Groq:"
                f"\n\n{content}"
            ) from error

        if not isinstance(
            data,
            dict,
        ):
            raise ValueError(
                "Groq response must be "
                "a JSON object."
            )

        if "facts" not in data:
            raise ValueError(
                "Missing 'facts' in "
                "Groq response."
            )

        if not isinstance(
            data["facts"],
            list,
        ):
            raise ValueError(
                "'facts' must be a list."
            )

        return data