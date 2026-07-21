import json

from openai import OpenAI
from config import Config

from .provider import LLMProvider
from .llm_response import LLMResponse


class OpenAIProvider(LLMProvider):

    def __init__(
        self,
        api_key: str,
        model: str = Config.OPENAI_MODEL
    ):

        self.client = OpenAI(
            api_key=api_key
        )

        self.model = model
        self.provider_name = "OpenAI"

    def extract(
        self,
        system_prompt: str,
        user_prompt: str,
        response_schema=None,
        temperature: float = 0.0
    ):

        messages = [

            {
                "role": "system",
                "content": system_prompt
            },

            {
                "role": "user",
                "content": user_prompt
            }

        ]

        kwargs = {

            "model": self.model,

            "messages": messages
        }

        if response_schema:

            kwargs["response_format"] = response_schema

        import time
        max_retries = 3
        for attempt in range(max_retries):
            try:
                response = self.client.chat.completions.create(**kwargs)
                break
            except Exception as e:
                if "429" in str(e) or "rate" in str(e).lower():
                    if attempt < max_retries - 1:
                        time.sleep(10)
                        continue
                raise

        usage = response.usage

        content = response.choices[0].message.content

        if not content:
            raise ValueError("OpenAI returned an empty response.")

        try:

            data = json.loads(content)

            if "facts" not in data:
                raise ValueError("Missing 'facts' in response.")

            if not isinstance(data["facts"], list):
                raise ValueError("'facts' must be a list.")

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

        except json.JSONDecodeError as e:

            raise ValueError(
                f"Invalid JSON returned by OpenAI:\n\n{content}"
            ) from e