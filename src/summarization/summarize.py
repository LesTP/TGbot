"""
Public API for summarization: generate_deep_dive and generate_quick_hit.

Orchestrates the summarization pipeline: validate → build prompt →
call LLM → parse response → return SummaryResult.
"""

from typing import Optional

from storage.types import RepoRecord
from summarization.client import create_provider
from summarization.prompts import build_deep_dive_prompt, build_quick_hit_prompt
from summarization.types import LLMConfig, LLMResponse, SummaryResult
from summarization.validation import validate_repo_content

DEEP_DIVE_MAX_TOKENS = 2000
QUICK_HIT_MAX_TOKENS = 300


def _to_summary_result(response: LLMResponse) -> SummaryResult:
    """Convert an LLMResponse to a TGbot SummaryResult."""
    return SummaryResult(
        content=response.content,
        model_used=response.model,
        token_usage=response.token_usage,
    )


def generate_deep_dive(
    repo: RepoRecord,
    config: LLMConfig,
    recent_context: Optional[list[dict]] = None,
) -> SummaryResult:
    """Generate a deep-dive summary for a repository.

    Pipeline: validate content → build prompt → call LLM → result.

    Args:
        repo: The repository to summarize. Must have populated raw_content.
        config: LLM provider configuration with model selection.
        recent_context: Optional recent summary dicts for comparison context.

    Returns:
        SummaryResult with generated content, model used, and token usage.

    Raises:
        InsufficientContentError: Repo content too short.
        LLMAPIError: LLM API call failed.
        LLMResponseError: LLM response empty or unparseable.
    """
    validate_repo_content(repo)

    system_prompt, user_prompt = build_deep_dive_prompt(repo, recent_context)

    provider = create_provider(config)
    response = provider.call(
        model=config.models["quality"],
        system_prompt=system_prompt,
        user_prompt=user_prompt,
        max_tokens=DEEP_DIVE_MAX_TOKENS,
    )

    return _to_summary_result(response)


def generate_quick_hit(
    repo: RepoRecord,
    config: LLMConfig,
) -> SummaryResult:
    """Generate a quick-hit summary for a repository.

    Pipeline: validate content → build prompt → call LLM → result.

    Args:
        repo: The repository to summarize. Must have populated raw_content.
        config: LLM provider configuration with model selection.

    Returns:
        SummaryResult with generated content, model used, and token usage.

    Raises:
        InsufficientContentError: Repo content too short.
        LLMAPIError: LLM API call failed.
        LLMResponseError: LLM response empty or unparseable.
    """
    validate_repo_content(repo)

    system_prompt, user_prompt = build_quick_hit_prompt(repo)

    provider = create_provider(config)
    response = provider.call(
        model=config.models["commodity"],
        system_prompt=system_prompt,
        user_prompt=user_prompt,
        max_tokens=QUICK_HIT_MAX_TOKENS,
    )

    return _to_summary_result(response)
