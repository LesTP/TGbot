"""Tests for the public summarization API (generate_deep_dive, generate_quick_hit)."""

from datetime import datetime
from unittest.mock import MagicMock, patch

import pytest

from storage.types import RepoRecord
from summarization.summarize import (
    DEEP_DIVE_MAX_TOKENS,
    QUICK_HIT_MAX_TOKENS,
    generate_deep_dive,
    generate_quick_hit,
)
from summarization.types import (
    InsufficientContentError,
    LLMAPIError,
    LLMConfig,
    LLMResponseError,
    SummaryResult,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_repo(raw_content="# Test Repo\n\nThis is a sufficiently long README for testing the summarization pipeline. " * 5) -> RepoRecord:
    return RepoRecord(
        id=1,
        source="github",
        source_id="12345",
        name="owner/test-repo",
        url="https://github.com/owner/test-repo",
        description="A test repository",
        raw_content=raw_content,
        source_metadata={"stars": 500, "forks": 50, "primary_language": "Python"},
        discovered_at=datetime(2026, 3, 1),
    )


def _make_config(
    provider="anthropic",
    deep_dive_model="claude-sonnet-4-5-20250929",
    quick_hit_model="claude-3-5-haiku-20241022",
) -> LLMConfig:
    return LLMConfig(
        provider=provider,
        api_key="sk-test-key",
        deep_dive_model=deep_dive_model,
        quick_hit_model=quick_hit_model,
    )


def _mock_provider_call(content="Generated summary text.", model="claude-sonnet-4-5-20250929",
                         input_tokens=1000, output_tokens=500):
    """Return a function that creates a mock provider with preset response."""
    def call(self_or_model, system_prompt=None, user_prompt=None, max_tokens=None, **kwargs):
        # Handle both positional and keyword args
        return {
            "content": content,
            "model": model,
            "usage": {"input_tokens": input_tokens, "output_tokens": output_tokens},
        }
    return call


# ---------------------------------------------------------------------------
# generate_deep_dive
# ---------------------------------------------------------------------------


class TestGenerateDeepDive:
    @patch("summarization.summarize.create_provider")
    def test_full_pipeline_returns_summary_result(self, mock_create):
        mock_provider = MagicMock()
        mock_provider.call.return_value = {
            "content": "Deep dive analysis of test-repo.",
            "model": "claude-sonnet-4-5-20250929",
            "usage": {"input_tokens": 1500, "output_tokens": 800},
        }
        mock_create.return_value = mock_provider

        result = generate_deep_dive(_make_repo(), _make_config())

        assert isinstance(result, SummaryResult)
        assert result.content == "Deep dive analysis of test-repo."
        assert result.model_used == "claude-sonnet-4-5-20250929"
        assert result.token_usage == {"input_tokens": 1500, "output_tokens": 800}

    @patch("summarization.summarize.create_provider")
    def test_uses_deep_dive_model(self, mock_create):
        mock_provider = MagicMock()
        mock_provider.call.return_value = {
            "content": "Summary.",
            "model": "my-deep-model",
            "usage": {"input_tokens": 100, "output_tokens": 50},
        }
        mock_create.return_value = mock_provider

        config = _make_config(deep_dive_model="my-deep-model")
        generate_deep_dive(_make_repo(), config)

        call_kwargs = mock_provider.call.call_args
        assert call_kwargs[1]["model"] == "my-deep-model" or call_kwargs[0][0] == "my-deep-model"

    @patch("summarization.summarize.create_provider")
    def test_uses_deep_dive_max_tokens(self, mock_create):
        mock_provider = MagicMock()
        mock_provider.call.return_value = {
            "content": "Summary.",
            "model": "model",
            "usage": {"input_tokens": 100, "output_tokens": 50},
        }
        mock_create.return_value = mock_provider

        generate_deep_dive(_make_repo(), _make_config())

        call_kwargs = mock_provider.call.call_args
        assert call_kwargs[1]["max_tokens"] == DEEP_DIVE_MAX_TOKENS

    @patch("summarization.summarize.create_provider")
    def test_recent_context_passed_to_prompt_builder(self, mock_create):
        mock_provider = MagicMock()
        mock_provider.call.return_value = {
            "content": "Summary with context.",
            "model": "model",
            "usage": {"input_tokens": 100, "output_tokens": 50},
        }
        mock_create.return_value = mock_provider

        context = [{"repo_name": "other/repo", "summary_content": "Other summary.", "date": "2026-03-05"}]

        with patch("summarization.summarize.build_deep_dive_prompt", wraps=None) as mock_prompt:
            mock_prompt.return_value = ("system", "user")
            generate_deep_dive(_make_repo(), _make_config(), recent_context=context)
            mock_prompt.assert_called_once()
            _, kwargs = mock_prompt.call_args
            # recent_context could be positional or keyword
            call_args = mock_prompt.call_args
            assert context in call_args.args or call_args.kwargs.get("recent_context") == context

    def test_insufficient_content_propagated(self):
        repo = _make_repo(raw_content="Short")
        with pytest.raises(InsufficientContentError):
            generate_deep_dive(repo, _make_config())

    @patch("summarization.summarize.create_provider")
    def test_llm_api_error_propagated(self, mock_create):
        mock_provider = MagicMock()
        mock_provider.call.side_effect = LLMAPIError("Rate limited", status_code=429)
        mock_create.return_value = mock_provider

        with pytest.raises(LLMAPIError) as exc_info:
            generate_deep_dive(_make_repo(), _make_config())
        assert exc_info.value.status_code == 429

    @patch("summarization.summarize.create_provider")
    def test_llm_response_error_propagated(self, mock_create):
        mock_provider = MagicMock()
        mock_provider.call.return_value = {
            "content": "",
            "model": "model",
            "usage": {"input_tokens": 100, "output_tokens": 0},
        }
        mock_create.return_value = mock_provider

        with pytest.raises(LLMResponseError):
            generate_deep_dive(_make_repo(), _make_config())

    @patch("summarization.summarize.create_provider")
    def test_token_usage_populated(self, mock_create):
        mock_provider = MagicMock()
        mock_provider.call.return_value = {
            "content": "A summary.",
            "model": "model",
            "usage": {"input_tokens": 2000, "output_tokens": 1000},
        }
        mock_create.return_value = mock_provider

        result = generate_deep_dive(_make_repo(), _make_config())
        assert result.token_usage["input_tokens"] == 2000
        assert result.token_usage["output_tokens"] == 1000


# ---------------------------------------------------------------------------
# generate_quick_hit
# ---------------------------------------------------------------------------


class TestGenerateQuickHit:
    @patch("summarization.summarize.create_provider")
    def test_full_pipeline_returns_summary_result(self, mock_create):
        mock_provider = MagicMock()
        mock_provider.call.return_value = {
            "content": "A brief summary of the tool.",
            "model": "claude-3-5-haiku-20241022",
            "usage": {"input_tokens": 800, "output_tokens": 60},
        }
        mock_create.return_value = mock_provider

        result = generate_quick_hit(_make_repo(), _make_config())

        assert isinstance(result, SummaryResult)
        assert result.content == "A brief summary of the tool."
        assert result.model_used == "claude-3-5-haiku-20241022"
        assert result.token_usage == {"input_tokens": 800, "output_tokens": 60}

    @patch("summarization.summarize.create_provider")
    def test_uses_quick_hit_model(self, mock_create):
        mock_provider = MagicMock()
        mock_provider.call.return_value = {
            "content": "Brief.",
            "model": "my-quick-model",
            "usage": {"input_tokens": 100, "output_tokens": 20},
        }
        mock_create.return_value = mock_provider

        config = _make_config(quick_hit_model="my-quick-model")
        generate_quick_hit(_make_repo(), config)

        call_kwargs = mock_provider.call.call_args
        assert call_kwargs[1]["model"] == "my-quick-model" or call_kwargs[0][0] == "my-quick-model"

    @patch("summarization.summarize.create_provider")
    def test_uses_quick_hit_max_tokens(self, mock_create):
        mock_provider = MagicMock()
        mock_provider.call.return_value = {
            "content": "Brief.",
            "model": "model",
            "usage": {"input_tokens": 100, "output_tokens": 20},
        }
        mock_create.return_value = mock_provider

        generate_quick_hit(_make_repo(), _make_config())

        call_kwargs = mock_provider.call.call_args
        assert call_kwargs[1]["max_tokens"] == QUICK_HIT_MAX_TOKENS

    def test_insufficient_content_propagated(self):
        repo = _make_repo(raw_content="Tiny")
        with pytest.raises(InsufficientContentError):
            generate_quick_hit(repo, _make_config())

    @patch("summarization.summarize.create_provider")
    def test_llm_api_error_propagated(self, mock_create):
        mock_provider = MagicMock()
        mock_provider.call.side_effect = LLMAPIError("Auth failed", status_code=401)
        mock_create.return_value = mock_provider

        with pytest.raises(LLMAPIError) as exc_info:
            generate_quick_hit(_make_repo(), _make_config())
        assert exc_info.value.status_code == 401

    @patch("summarization.summarize.create_provider")
    def test_llm_response_error_propagated(self, mock_create):
        mock_provider = MagicMock()
        mock_provider.call.return_value = {
            "content": "   ",
            "model": "model",
            "usage": {"input_tokens": 100, "output_tokens": 0},
        }
        mock_create.return_value = mock_provider

        with pytest.raises(LLMResponseError):
            generate_quick_hit(_make_repo(), _make_config())

    @patch("summarization.summarize.create_provider")
    def test_token_usage_populated(self, mock_create):
        mock_provider = MagicMock()
        mock_provider.call.return_value = {
            "content": "Quick summary.",
            "model": "model",
            "usage": {"input_tokens": 600, "output_tokens": 40},
        }
        mock_create.return_value = mock_provider

        result = generate_quick_hit(_make_repo(), _make_config())
        assert result.token_usage["input_tokens"] == 600
        assert result.token_usage["output_tokens"] == 40
