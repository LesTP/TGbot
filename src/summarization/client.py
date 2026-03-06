"""
LLM provider abstraction and implementations.

Defines LLMProvider ABC for provider-agnostic LLM access,
AnthropicProvider as the concrete implementation, and a
factory function to create providers from config.
"""

from abc import ABC, abstractmethod

import anthropic

from summarization.types import LLMAPIError, LLMConfig, LLMResponseError


class LLMProvider(ABC):
    """Abstract base class for LLM providers.

    Each provider normalizes its API's response into a common dict shape.
    """

    @abstractmethod
    def call(
        self,
        model: str,
        system_prompt: str,
        user_prompt: str,
        max_tokens: int,
    ) -> dict:
        """Call the LLM and return a normalized response.

        Returns:
            {
                "content": str,
                "model": str,
                "usage": {"input_tokens": int, "output_tokens": int}
            }

        Raises:
            LLMAPIError: API call failed (rate limit, auth, network).
            LLMResponseError: API returned but response is empty or unparseable.
        """


class AnthropicProvider(LLMProvider):
    """LLM provider backed by the Anthropic API (Claude models)."""

    def __init__(self, api_key: str):
        self._client = anthropic.Anthropic(api_key=api_key)

    def call(
        self,
        model: str,
        system_prompt: str,
        user_prompt: str,
        max_tokens: int,
    ) -> dict:
        try:
            response = self._client.messages.create(
                model=model,
                system=system_prompt,
                messages=[{"role": "user", "content": user_prompt}],
                max_tokens=max_tokens,
            )
        except anthropic.RateLimitError as e:
            retry_after = None
            retry_header = e.response.headers.get("retry-after")
            if retry_header is not None:
                try:
                    retry_after = float(retry_header)
                except (ValueError, TypeError):
                    pass
            raise LLMAPIError(
                str(e),
                status_code=e.status_code,
                retry_after=retry_after,
            ) from e
        except anthropic.APIStatusError as e:
            raise LLMAPIError(
                str(e),
                status_code=e.status_code,
            ) from e
        except anthropic.APIConnectionError as e:
            raise LLMAPIError(str(e)) from e

        if not response.content or not response.content[0].text:
            raise LLMResponseError("Empty response content from Anthropic API")

        return {
            "content": response.content[0].text,
            "model": response.model,
            "usage": {
                "input_tokens": response.usage.input_tokens,
                "output_tokens": response.usage.output_tokens,
            },
        }


def create_provider(config: LLMConfig) -> LLMProvider:
    """Create an LLM provider from config.

    Dispatches on config.provider. Currently supports "anthropic".

    Raises:
        ValueError: Unknown provider name.
    """
    if config.provider == "anthropic":
        return AnthropicProvider(api_key=config.api_key)
    raise ValueError(
        f"Unknown LLM provider: {config.provider!r}. "
        f"Supported providers: anthropic"
    )
