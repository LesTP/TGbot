"""
Summarization module types.

LLM infrastructure types (LLMConfig, LLMResponse, LLMAPIError,
LLMResponseError) are re-exported from toolkit.llm_client.
TGbot-specific types (SummaryResult, InsufficientContentError)
remain here.
"""

from dataclasses import dataclass

from toolkit.llm_client import (  # noqa: F401
    LLMAPIError,
    LLMConfig,
    LLMResponse,
    LLMResponseError,
    TokenUsage,
)


# ---------------------------------------------------------------------------
# TGbot-specific result types
# ---------------------------------------------------------------------------


@dataclass
class SummaryResult:
    """Result of a summary generation call.

    Contains the generated text, model identifier, and token usage
    for cost tracking.
    """

    content: str
    model_used: str
    token_usage: TokenUsage


# ---------------------------------------------------------------------------
# TGbot-specific error types
# ---------------------------------------------------------------------------


class InsufficientContentError(Exception):
    """Repo content is too short or low-quality to produce a meaningful summary."""

    def __init__(self, message: str, content_length: int):
        super().__init__(message)
        self.message = message
        self.content_length = content_length
