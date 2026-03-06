"""Tests for send_digest — main Delivery public function."""

from datetime import date
from unittest.mock import MagicMock, patch

import pytest

from delivery.send import send_digest, TELEGRAM_MAX_LENGTH
from delivery.types import (
    DeliveryResult,
    Digest,
    MessageTooLongError,
    SummaryWithRepo,
    TelegramAPIError,
)


def _make_summary(
    name="test-repo",
    url="https://github.com/org/test-repo",
    stars=1234,
    content="A great tool for testing.",
    created_at="2024-06-15",
):
    return SummaryWithRepo(
        summary_content=content,
        repo_name=name,
        repo_url=url,
        stars=stars,
        created_at=created_at,
    )


def _make_digest(content="Short deep dive content."):
    return Digest(
        deep_dive=_make_summary(name="deep-repo", stars=5000, content=content),
        quick_hits=[_make_summary(name="quick-1", stars=100)],
        ranking_criteria="stars",
        date=date(2026, 3, 6),
    )


def _mock_successful_send():
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "ok": True,
        "result": {"message_id": 42},
    }
    return mock_response


class TestSendDigestSuccess:
    def test_returns_success_result(self):
        with patch("delivery.send.TelegramClient") as MockClient:
            MockClient.return_value.send_message.return_value = {
                "ok": True,
                "result": {"message_id": 42},
            }
            result = send_digest(_make_digest(), "@channel", "bot-token")
        assert result.success is True
        assert result.message_id == "42"
        assert result.error is None

    def test_returns_delivery_result_type(self):
        with patch("delivery.send.TelegramClient") as MockClient:
            MockClient.return_value.send_message.return_value = {
                "ok": True,
                "result": {"message_id": 1},
            }
            result = send_digest(_make_digest(), "@channel", "token")
        assert isinstance(result, DeliveryResult)

    def test_passes_channel_id_to_client(self):
        with patch("delivery.send.TelegramClient") as MockClient:
            MockClient.return_value.send_message.return_value = {
                "ok": True,
                "result": {"message_id": 1},
            }
            send_digest(_make_digest(), "-100999", "token")
        call_args = MockClient.return_value.send_message.call_args
        assert call_args[0][0] == "-100999"

    def test_passes_bot_token_to_client(self):
        with patch("delivery.send.TelegramClient") as MockClient:
            MockClient.return_value.send_message.return_value = {
                "ok": True,
                "result": {"message_id": 1},
            }
            send_digest(_make_digest(), "@chan", "my-secret-token")
        MockClient.assert_called_once_with("my-secret-token")

    def test_message_id_is_string(self):
        with patch("delivery.send.TelegramClient") as MockClient:
            MockClient.return_value.send_message.return_value = {
                "ok": True,
                "result": {"message_id": 99},
            }
            result = send_digest(_make_digest(), "@chan", "token")
        assert isinstance(result.message_id, str)


class TestSendDigestAPIError:
    def test_returns_failure_on_telegram_error(self):
        with patch("delivery.send.TelegramClient") as MockClient:
            MockClient.return_value.send_message.side_effect = TelegramAPIError(
                "Unauthorized", status_code=401
            )
            result = send_digest(_make_digest(), "@chan", "bad-token")
        assert result.success is False
        assert result.message_id is None
        assert "Unauthorized" in result.error

    def test_does_not_raise_on_telegram_error(self):
        with patch("delivery.send.TelegramClient") as MockClient:
            MockClient.return_value.send_message.side_effect = TelegramAPIError(
                "Network error"
            )
            result = send_digest(_make_digest(), "@chan", "token")
        assert result.success is False


class TestSendDigestTruncation:
    def test_long_content_truncated_before_sending(self):
        long_content = "This is a sentence. " * 500  # ~10,000 chars
        digest = _make_digest(content=long_content)

        with patch("delivery.send.TelegramClient") as MockClient:
            MockClient.return_value.send_message.return_value = {
                "ok": True,
                "result": {"message_id": 1},
            }
            result = send_digest(digest, "@chan", "token")

        sent_text = MockClient.return_value.send_message.call_args[0][1]
        assert len(sent_text) <= TELEGRAM_MAX_LENGTH
        assert result.success is True

    def test_short_content_not_truncated(self):
        digest = _make_digest(content="Short.")

        with patch("delivery.send.TelegramClient") as MockClient:
            MockClient.return_value.send_message.return_value = {
                "ok": True,
                "result": {"message_id": 1},
            }
            send_digest(digest, "@chan", "token")

        sent_text = MockClient.return_value.send_message.call_args[0][1]
        assert "[Read more]" not in sent_text


class TestSendDigestMessageTooLong:
    def test_raises_when_still_over_limit_after_truncation(self):
        digest = _make_digest(content="Short.")
        with patch("delivery.send.format_digest") as mock_format:
            # Return a message that's over the limit
            mock_format.return_value = "x" * 5000
            with patch("delivery.send.truncate_for_telegram") as mock_trunc:
                # Truncation still returns something over the limit
                mock_trunc.return_value = "x" * 5000
                with pytest.raises(MessageTooLongError) as exc_info:
                    send_digest(digest, "@chan", "token")
        assert exc_info.value.length == 5000
        assert exc_info.value.max_length == TELEGRAM_MAX_LENGTH


class TestSendDigestFormatting:
    def test_formatted_message_contains_digest_content(self):
        digest = _make_digest(content="Unique content here.")

        with patch("delivery.send.TelegramClient") as MockClient:
            MockClient.return_value.send_message.return_value = {
                "ok": True,
                "result": {"message_id": 1},
            }
            send_digest(digest, "@chan", "token")

        sent_text = MockClient.return_value.send_message.call_args[0][1]
        assert "Unique content here" in sent_text
        assert "DEEP DIVE" in sent_text
