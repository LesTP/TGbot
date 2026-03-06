"""
Content validation and LLM response parsing.

Validates that repo content is sufficient for summarization and
parses raw LLM API responses into structured output.
"""

from storage.types import RepoRecord
from summarization.types import InsufficientContentError, LLMResponseError

MIN_CONTENT_LENGTH = 100


def validate_repo_content(repo: RepoRecord) -> None:
    """Validate that a repo has sufficient content for summarization.

    Raises:
        InsufficientContentError: If raw_content is empty or below
            MIN_CONTENT_LENGTH characters.
    """
    content_length = len(repo.raw_content) if repo.raw_content else 0

    if content_length == 0:
        raise InsufficientContentError(
            "Repo has no README content",
            content_length=0,
        )

    if content_length < MIN_CONTENT_LENGTH:
        raise InsufficientContentError(
            f"Repo README too short ({content_length} chars, "
            f"minimum {MIN_CONTENT_LENGTH})",
            content_length=content_length,
        )


def parse_llm_response(raw_response: dict) -> tuple[str, dict]:
    """Extract content text and token usage from a raw LLM API response.

    Args:
        raw_response: Normalized response dict from LLMProvider.call():
            {"content": str, "model": str, "usage": {"input_tokens": int, "output_tokens": int}}

    Returns:
        (content_text, token_usage) where token_usage is
        {"input_tokens": int, "output_tokens": int}.

    Raises:
        LLMResponseError: If content is missing or empty.
    """
    content = raw_response.get("content")

    if content is None:
        raise LLMResponseError("Response missing 'content' field")

    if not content.strip():
        raise LLMResponseError("Response has empty content")

    usage = raw_response.get("usage", {})
    token_usage = {
        "input_tokens": usage.get("input_tokens", 0),
        "output_tokens": usage.get("output_tokens", 0),
    }

    return content, token_usage
