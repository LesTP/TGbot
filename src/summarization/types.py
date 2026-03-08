"""
Summarization module types.

Data types for the Summarization module's public API: configuration,
result shapes, and error types. See ARCH_summarization.md for contracts.
"""

from dataclasses import dataclass
from typing import Optional


# ---------------------------------------------------------------------------
# Configuration types
# ---------------------------------------------------------------------------


@dataclass
class LLMConfig:
    """Configuration for the LLM provider.

    Carries provider selection, credentials, and per-tier model names.
    Passed into generate functions — no env var reads inside the module.
    """

    provider: str  # e.g. "anthropic"
    api_key: str
    deep_dive_model: str  # e.g. "claude-sonnet-4-5-20250929"
    quick_hit_model: str  # e.g. "claude-haiku-4-5-20251001"


# ---------------------------------------------------------------------------
# Result types
# ---------------------------------------------------------------------------


@dataclass
class SummaryResult:
    """Result of a summary generation call.

    Contains the generated text, model identifier, and token usage
    for cost tracking.
    """

    content: str
    model_used: str
    token_usage: dict  # {"input_tokens": int, "output_tokens": int}


# ---------------------------------------------------------------------------
# Error types
# ---------------------------------------------------------------------------


class LLMAPIError(Exception):
    """LLM API call failed (rate limit, auth, network)."""

    def __init__(
        self,
        message: str,
        status_code: Optional[int] = None,
        retry_after: Optional[float] = None,
    ):
        super().__init__(message)
        self.message = message
        self.status_code = status_code
        self.retry_after = retry_after


class LLMResponseError(Exception):
    """LLM API returned successfully but response couldn't be parsed or was empty."""

    def __init__(self, message: str):
        super().__init__(message)
        self.message = message


class InsufficientContentError(Exception):
    """Repo content is too short or low-quality to produce a meaningful summary."""

    def __init__(self, message: str, content_length: int):
        super().__init__(message)
        self.message = message
        self.content_length = content_length
