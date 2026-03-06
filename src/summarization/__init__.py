"""Summarization module — generate AI-powered repo summaries via LLM.

Provider-agnostic: configure via LLMConfig with provider name,
API key, and per-tier model names. Currently supports Anthropic.
"""

from summarization.client import LLMProvider, create_provider
from summarization.summarize import generate_deep_dive, generate_quick_hit
from summarization.types import (
    InsufficientContentError,
    LLMAPIError,
    LLMConfig,
    LLMResponseError,
    SummaryResult,
)

__all__ = [
    "generate_deep_dive",
    "generate_quick_hit",
    "LLMConfig",
    "SummaryResult",
    "LLMAPIError",
    "LLMResponseError",
    "InsufficientContentError",
    "LLMProvider",
    "create_provider",
]
