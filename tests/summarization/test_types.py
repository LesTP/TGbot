"""Tests for Summarization module types."""

import pytest

from summarization.types import (
    InsufficientContentError,
    LLMAPIError,
    LLMConfig,
    LLMResponseError,
    SummaryResult,
)


class TestLLMConfig:
    def test_construction(self):
        config = LLMConfig(
            provider="anthropic",
            api_key="sk-test-key",
            deep_dive_model="claude-sonnet-4-5-20250929",
            quick_hit_model="claude-3-5-haiku-20241022",
        )
        assert config.provider == "anthropic"
        assert config.api_key == "sk-test-key"
        assert config.deep_dive_model == "claude-sonnet-4-5-20250929"
        assert config.quick_hit_model == "claude-3-5-haiku-20241022"

    def test_carries_all_four_fields(self):
        config = LLMConfig(
            provider="openai",
            api_key="key-123",
            deep_dive_model="gpt-4o",
            quick_hit_model="gpt-4o-mini",
        )
        fields = {f.name for f in config.__dataclass_fields__.values()}
        assert fields == {"provider", "api_key", "deep_dive_model", "quick_hit_model"}

    def test_different_providers(self):
        anthropic = LLMConfig("anthropic", "key-a", "model-a", "model-b")
        openai = LLMConfig("openai", "key-o", "model-c", "model-d")
        assert anthropic.provider != openai.provider
        assert anthropic.api_key != openai.api_key


class TestSummaryResult:
    def test_construction(self):
        result = SummaryResult(
            content="This tool does X and Y.",
            model_used="claude-sonnet-4-5-20250929",
            token_usage={"input_tokens": 1500, "output_tokens": 800},
        )
        assert result.content == "This tool does X and Y."
        assert result.model_used == "claude-sonnet-4-5-20250929"
        assert result.token_usage == {"input_tokens": 1500, "output_tokens": 800}

    def test_token_usage_has_required_keys(self):
        usage = {"input_tokens": 100, "output_tokens": 50}
        result = SummaryResult(content="text", model_used="model", token_usage=usage)
        assert "input_tokens" in result.token_usage
        assert "output_tokens" in result.token_usage
        assert isinstance(result.token_usage["input_tokens"], int)
        assert isinstance(result.token_usage["output_tokens"], int)

    def test_empty_content(self):
        result = SummaryResult(content="", model_used="model", token_usage={"input_tokens": 0, "output_tokens": 0})
        assert result.content == ""

    def test_large_token_counts(self):
        usage = {"input_tokens": 100000, "output_tokens": 4096}
        result = SummaryResult(content="text", model_used="model", token_usage=usage)
        assert result.token_usage["input_tokens"] == 100000
        assert result.token_usage["output_tokens"] == 4096


class TestLLMAPIError:
    def test_with_all_fields(self):
        err = LLMAPIError("Rate limited", status_code=429, retry_after=30.0)
        assert str(err) == "Rate limited"
        assert err.message == "Rate limited"
        assert err.status_code == 429
        assert err.retry_after == 30.0

    def test_defaults(self):
        err = LLMAPIError("Network error")
        assert str(err) == "Network error"
        assert err.message == "Network error"
        assert err.status_code is None
        assert err.retry_after is None

    def test_with_status_only(self):
        err = LLMAPIError("Unauthorized", status_code=401)
        assert err.status_code == 401
        assert err.retry_after is None

    def test_with_retry_only(self):
        err = LLMAPIError("Overloaded", retry_after=5.0)
        assert err.status_code is None
        assert err.retry_after == 5.0

    def test_is_exception(self):
        assert issubclass(LLMAPIError, Exception)

    def test_catchable(self):
        with pytest.raises(LLMAPIError) as exc_info:
            raise LLMAPIError("fail", status_code=500)
        assert exc_info.value.status_code == 500


class TestLLMResponseError:
    def test_construction(self):
        err = LLMResponseError("Empty response from API")
        assert str(err) == "Empty response from API"
        assert err.message == "Empty response from API"

    def test_is_exception(self):
        assert issubclass(LLMResponseError, Exception)

    def test_catchable(self):
        with pytest.raises(LLMResponseError):
            raise LLMResponseError("bad response")


class TestInsufficientContentError:
    def test_construction(self):
        err = InsufficientContentError("README too short", content_length=42)
        assert str(err) == "README too short"
        assert err.message == "README too short"
        assert err.content_length == 42

    def test_zero_length(self):
        err = InsufficientContentError("Empty content", content_length=0)
        assert err.content_length == 0

    def test_is_exception(self):
        assert issubclass(InsufficientContentError, Exception)

    def test_catchable(self):
        with pytest.raises(InsufficientContentError) as exc_info:
            raise InsufficientContentError("too short", content_length=10)
        assert exc_info.value.content_length == 10
