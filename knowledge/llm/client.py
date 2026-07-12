from typing import Optional

from .provider import LLMProvider


class LLMClient:

    def __init__(
        self,
        provider: LLMProvider
    ):

        self.provider = provider

    def extract(
        self,
        system_prompt: str,
        user_prompt: str,
        response_schema=None,
        temperature: float = 0.0
    ):

        return self.provider.extract(

            system_prompt=system_prompt,

            user_prompt=user_prompt,

            response_schema=response_schema,

            temperature=temperature
        )