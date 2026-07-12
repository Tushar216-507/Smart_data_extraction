from abc import ABC, abstractmethod


class LLMProvider(ABC):

    @abstractmethod
    def extract(
        self,
        system_prompt: str,
        user_prompt: str,
        response_schema=None,
        temperature: float = 0.0
    ):
        """
        Execute an extraction request.

        Returns:
            dict | str
        """
        pass