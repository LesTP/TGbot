"""Tests for LLM provider abstraction and Anthropic implementation."""

from unittest.mock import MagicMock, patch

import anthropic
import httpx
import pytest

from summarization.client import AnthropicProvider, LLMProvider, create_provider
from summarization.types import LLMAPIError, LLMConfig, LLMResponseError


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_mock_response(text="Generated summary", model="claude-sonnet-4-5-20250929",
                        input_tokens=500, output_tokens=200):
    """Create a mock Anthropic API response."""
    content_block = MagicMock()
    content_block.text = text

    usage = MagicMock()
    usage.input_tokens = input_tokens
    usage.output_tokens = output_tokens

    response = MagicMock()
    response.content = [content_block]
    response.model = model
    response.usage = usage
    return response


def _make_httpx_response(status_code, headers=None):
    """Create an httpx.Response with a request attached (required by anthropic errors)."""
    req = httpx.Request("POST", "https://api.anthropic.com/v1/messages")
    return httpx.Response(status_code, headers=headers or {}, request=req)


# ---------------------------------------------------------------------------
# LLMProvider ABC
# ---------------------------------------------------------------------------


class TestLLMProviderABC:
    def test_cannot_instantiate_directly(self):
        with pytest.raises(TypeError):
            LLMProvider()

    def test_is_abstract(self):
        assert hasattr(LLMProvider.call, "__isabstractmethod__")

    def test_subclass_must_implement_call(self):
        class IncompleteProvider(LLMProvider):
            pass

        with pytest.raises(TypeError):
            IncompleteProvider()

    def test_subclass_with_call_can_instantiate(self):
        class DummyProvider(LLMProvider):
            def call(self, model, system_prompt, user_prompt, max_tokens):
                return {}

        provider = DummyProvider()
        assert isinstance(provider, LLMProvider)


# ---------------------------------------------------------------------------
# AnthropicProvider
# ---------------------------------------------------------------------------


class TestAnthropicProviderSuccess:
    @patch("summarization.client.anthropic.Anthropic")
    def test_returns_expected_dict_shape(self, mock_anthropic_cls):
        mock_client = MagicMock()
        mock_anthropic_cls.return_value = mock_client
        mock_client.messages.create.return_value = _make_mock_response(
            text="This is a deep dive summary.",
            model="claude-sonnet-4-5-20250929",
            input_tokens=1200,
            output_tokens=800,
        )

        provider = AnthropicProvider(api_key="sk-test")
        result = provider.call(
            model="claude-sonnet-4-5-20250929",
            system_prompt="You are a tech analyst.",
            user_prompt="Summarize this repo.",
            max_tokens=2000,
        )

        assert result["content"] == "This is a deep dive summary."
        assert result["model"] == "claude-sonnet-4-5-20250929"
        assert result["usage"]["input_tokens"] == 1200
        assert result["usage"]["output_tokens"] == 800

    @patch("summarization.client.anthropic.Anthropic")
    def test_passes_correct_params_to_api(self, mock_anthropic_cls):
        mock_client = MagicMock()
        mock_anthropic_cls.return_value = mock_client
        mock_client.messages.create.return_value = _make_mock_response()

        provider = AnthropicProvider(api_key="sk-test")
        provider.call(
            model="claude-3-5-haiku-20241022",
            system_prompt="System prompt here.",
            user_prompt="User prompt here.",
            max_tokens=500,
        )

        mock_client.messages.create.assert_called_once_with(
            model="claude-3-5-haiku-20241022",
            system="System prompt here.",
            messages=[{"role": "user", "content": "User prompt here."}],
            max_tokens=500,
        )

    @patch("summarization.client.anthropic.Anthropic")
    def test_api_key_passed_to_client(self, mock_anthropic_cls):
        AnthropicProvider(api_key="sk-my-secret-key")
        mock_anthropic_cls.assert_called_once_with(api_key="sk-my-secret-key")


class TestAnthropicProviderErrors:
    @patch("summarization.client.anthropic.Anthropic")
    def test_rate_limit_raises_llm_api_error_with_retry(self, mock_anthropic_cls):
        mock_client = MagicMock()
        mock_anthropic_cls.return_value = mock_client

        response = _make_httpx_response(429, headers={"retry-after": "30"})
        mock_client.messages.create.side_effect = anthropic.RateLimitError(
            message="Rate limited", response=response, body=None,
        )

        provider = AnthropicProvider(api_key="sk-test")
        with pytest.raises(LLMAPIError) as exc_info:
            provider.call("model", "system", "user", 100)

        assert exc_info.value.status_code == 429
        assert exc_info.value.retry_after == 30.0

    @patch("summarization.client.anthropic.Anthropic")
    def test_rate_limit_without_retry_header(self, mock_anthropic_cls):
        mock_client = MagicMock()
        mock_anthropic_cls.return_value = mock_client

        response = _make_httpx_response(429)
        mock_client.messages.create.side_effect = anthropic.RateLimitError(
            message="Rate limited", response=response, body=None,
        )

        provider = AnthropicProvider(api_key="sk-test")
        with pytest.raises(LLMAPIError) as exc_info:
            provider.call("model", "system", "user", 100)

        assert exc_info.value.status_code == 429
        assert exc_info.value.retry_after is None

    @patch("summarization.client.anthropic.Anthropic")
    def test_auth_error_raises_llm_api_error(self, mock_anthropic_cls):
        mock_client = MagicMock()
        mock_anthropic_cls.return_value = mock_client

        response = _make_httpx_response(401)
        mock_client.messages.create.side_effect = anthropic.AuthenticationError(
            message="Invalid API key", response=response, body=None,
        )

        provider = AnthropicProvider(api_key="sk-bad-key")
        with pytest.raises(LLMAPIError) as exc_info:
            provider.call("model", "system", "user", 100)

        assert exc_info.value.status_code == 401

    @patch("summarization.client.anthropic.Anthropic")
    def test_server_error_raises_llm_api_error(self, mock_anthropic_cls):
        mock_client = MagicMock()
        mock_anthropic_cls.return_value = mock_client

        response = _make_httpx_response(500)
        mock_client.messages.create.side_effect = anthropic.InternalServerError(
            message="Internal server error", response=response, body=None,
        )

        provider = AnthropicProvider(api_key="sk-test")
        with pytest.raises(LLMAPIError) as exc_info:
            provider.call("model", "system", "user", 100)

        assert exc_info.value.status_code == 500

    @patch("summarization.client.anthropic.Anthropic")
    def test_connection_error_raises_llm_api_error_no_status(self, mock_anthropic_cls):
        mock_client = MagicMock()
        mock_anthropic_cls.return_value = mock_client

        request = httpx.Request("POST", "https://api.anthropic.com/v1/messages")
        mock_client.messages.create.side_effect = anthropic.APIConnectionError(
            request=request,
        )

        provider = AnthropicProvider(api_key="sk-test")
        with pytest.raises(LLMAPIError) as exc_info:
            provider.call("model", "system", "user", 100)

        assert exc_info.value.status_code is None
        assert exc_info.value.retry_after is None

    @patch("summarization.client.anthropic.Anthropic")
    def test_empty_content_list_raises_response_error(self, mock_anthropic_cls):
        mock_client = MagicMock()
        mock_anthropic_cls.return_value = mock_client

        response = MagicMock()
        response.content = []
        mock_client.messages.create.return_value = response

        provider = AnthropicProvider(api_key="sk-test")
        with pytest.raises(LLMResponseError):
            provider.call("model", "system", "user", 100)

    @patch("summarization.client.anthropic.Anthropic")
    def test_empty_text_raises_response_error(self, mock_anthropic_cls):
        mock_client = MagicMock()
        mock_anthropic_cls.return_value = mock_client

        content_block = MagicMock()
        content_block.text = ""
        response = MagicMock()
        response.content = [content_block]
        mock_client.messages.create.return_value = response

        provider = AnthropicProvider(api_key="sk-test")
        with pytest.raises(LLMResponseError):
            provider.call("model", "system", "user", 100)


# ---------------------------------------------------------------------------
# create_provider factory
# ---------------------------------------------------------------------------


class TestCreateProvider:
    def test_anthropic_returns_anthropic_provider(self):
        config = LLMConfig(
            provider="anthropic",
            api_key="sk-test",
            deep_dive_model="claude-sonnet-4-5-20250929",
            quick_hit_model="claude-3-5-haiku-20241022",
        )
        provider = create_provider(config)
        assert isinstance(provider, AnthropicProvider)
        assert isinstance(provider, LLMProvider)

    def test_unknown_provider_raises_value_error(self):
        config = LLMConfig(
            provider="unknown-llm",
            api_key="key",
            deep_dive_model="model",
            quick_hit_model="model",
        )
        with pytest.raises(ValueError, match="Unknown LLM provider"):
            create_provider(config)

    def test_error_message_includes_provider_name(self):
        config = LLMConfig(
            provider="google",
            api_key="key",
            deep_dive_model="model",
            quick_hit_model="model",
        )
        with pytest.raises(ValueError, match="google"):
            create_provider(config)
