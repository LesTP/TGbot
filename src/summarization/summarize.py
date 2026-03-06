"""
Public API for summarization: generate_deep_dive and generate_quick_hit.

Orchestrates the summarization pipeline: validate → build prompt →
call LLM → parse response → return SummaryResult.
"""

from typing import Optional

from storage.types import RepoRecord
from summarization.client import create_provider
from summarization.prompts import build_deep_dive_prompt, build_quick_hit_prompt
from summarization.types import LLMConfig, SummaryResult
from summarization.validation import parse_llm_response, validate_repo_content

DEEP_DIVE_MAX_TOKENS = 2000
QUICK_HIT_MAX_TOKENS = 300


def generate_deep_dive(
    repo: RepoRecord,
    config: LLMConfig,
    recent_context: Optional[list[dict]] = None,
) -> SummaryResult:
    """Generate a deep-dive summary for a repository.

    Pipeline: validate content → build prompt → call LLM → parse → result.

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
    raw_response = provider.call(
        model=config.deep_dive_model,
        system_prompt=system_prompt,
        user_prompt=user_prompt,
        max_tokens=DEEP_DIVE_MAX_TOKENS,
    )

    content, token_usage = parse_llm_response(raw_response)

    return SummaryResult(
        content=content,
        model_used=raw_response["model"],
        token_usage=token_usage,
    )


def generate_quick_hit(
    repo: RepoRecord,
    config: LLMConfig,
) -> SummaryResult:
    """Generate a quick-hit summary for a repository.

    Pipeline: validate content → build prompt → call LLM → parse → result.

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
    raw_response = provider.call(
        model=config.quick_hit_model,
        system_prompt=system_prompt,
        user_prompt=user_prompt,
        max_tokens=QUICK_HIT_MAX_TOKENS,
    )

    content, token_usage = parse_llm_response(raw_response)

    return SummaryResult(
        content=content,
        model_used=raw_response["model"],
        token_usage=token_usage,
    )
