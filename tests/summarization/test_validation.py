"""Tests for content validation and LLM response parsing."""

import pytest

from datetime import datetime
from storage.types import RepoRecord
from summarization.validation import (
    MIN_CONTENT_LENGTH,
    parse_llm_response,
    validate_repo_content,
)
from summarization.types import InsufficientContentError, LLMResponseError


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_repo(raw_content="# Test Repo\n\nThis is a test repository with sufficient content for validation. " * 3) -> RepoRecord:
    return RepoRecord(
        id=1,
        source="github",
        source_id="12345",
        name="owner/test-repo",
        url="https://github.com/owner/test-repo",
        description="A test repo",
        raw_content=raw_content,
        source_metadata={"stars": 100},
        discovered_at=datetime(2026, 3, 1),
    )


# ---------------------------------------------------------------------------
# validate_repo_content
# ---------------------------------------------------------------------------


class TestValidateRepoContent:
    def test_adequate_content_passes(self):
        repo = _make_repo(raw_content="x" * MIN_CONTENT_LENGTH)
        validate_repo_content(repo)  # should not raise

    def test_long_content_passes(self):
        repo = _make_repo(raw_content="x" * 50000)
        validate_repo_content(repo)  # should not raise

    def test_empty_content_raises(self):
        repo = _make_repo(raw_content="")
        with pytest.raises(InsufficientContentError) as exc_info:
            validate_repo_content(repo)
        assert exc_info.value.content_length == 0

    def test_none_like_empty_string_raises(self):
        repo = _make_repo(raw_content="")
        with pytest.raises(InsufficientContentError):
            validate_repo_content(repo)

    def test_short_content_raises(self):
        repo = _make_repo(raw_content="Short")
        with pytest.raises(InsufficientContentError) as exc_info:
            validate_repo_content(repo)
        assert exc_info.value.content_length == 5

    def test_one_below_minimum_raises(self):
        repo = _make_repo(raw_content="x" * (MIN_CONTENT_LENGTH - 1))
        with pytest.raises(InsufficientContentError) as exc_info:
            validate_repo_content(repo)
        assert exc_info.value.content_length == MIN_CONTENT_LENGTH - 1

    def test_exactly_minimum_passes(self):
        repo = _make_repo(raw_content="x" * MIN_CONTENT_LENGTH)
        validate_repo_content(repo)  # should not raise

    def test_error_message_includes_length(self):
        repo = _make_repo(raw_content="x" * 42)
        with pytest.raises(InsufficientContentError, match="42"):
            validate_repo_content(repo)


# ---------------------------------------------------------------------------
# parse_llm_response
# ---------------------------------------------------------------------------


class TestParseLLMResponse:
    def test_valid_response_returns_content_and_usage(self):
        raw = {
            "content": "This is a generated summary.",
            "model": "claude-sonnet-4-5-20250929",
            "usage": {"input_tokens": 1500, "output_tokens": 800},
        }
        content, usage = parse_llm_response(raw)
        assert content == "This is a generated summary."
        assert usage == {"input_tokens": 1500, "output_tokens": 800}

    def test_missing_content_raises(self):
        raw = {
            "model": "claude-sonnet-4-5-20250929",
            "usage": {"input_tokens": 100, "output_tokens": 50},
        }
        with pytest.raises(LLMResponseError, match="missing"):
            parse_llm_response(raw)

    def test_none_content_raises(self):
        raw = {
            "content": None,
            "model": "model",
            "usage": {"input_tokens": 0, "output_tokens": 0},
        }
        with pytest.raises(LLMResponseError, match="missing"):
            parse_llm_response(raw)

    def test_empty_content_raises(self):
        raw = {
            "content": "",
            "model": "model",
            "usage": {"input_tokens": 100, "output_tokens": 0},
        }
        with pytest.raises(LLMResponseError, match="empty"):
            parse_llm_response(raw)

    def test_whitespace_only_content_raises(self):
        raw = {
            "content": "   \n\t  ",
            "model": "model",
            "usage": {"input_tokens": 100, "output_tokens": 0},
        }
        with pytest.raises(LLMResponseError, match="empty"):
            parse_llm_response(raw)

    def test_missing_usage_defaults_to_zero(self):
        raw = {
            "content": "Summary text.",
            "model": "model",
        }
        content, usage = parse_llm_response(raw)
        assert content == "Summary text."
        assert usage == {"input_tokens": 0, "output_tokens": 0}

    def test_partial_usage_defaults_missing_to_zero(self):
        raw = {
            "content": "Summary text.",
            "model": "model",
            "usage": {"input_tokens": 500},
        }
        content, usage = parse_llm_response(raw)
        assert usage == {"input_tokens": 500, "output_tokens": 0}

    def test_content_preserves_whitespace(self):
        raw = {
            "content": "  Leading and trailing whitespace  ",
            "model": "model",
            "usage": {"input_tokens": 10, "output_tokens": 5},
        }
        content, _ = parse_llm_response(raw)
        assert content == "  Leading and trailing whitespace  "
