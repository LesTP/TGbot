"""Tests for send_digest — main Delivery public function."""

from datetime import date
from unittest.mock import patch

import pytest

from delivery.formatting import extract_excerpt
from delivery.send import send_digest, TELEGRAM_MAX_LENGTH, TELEGRAPH_THRESHOLD
from delivery.types import (
    DeliveryResult,
    Digest,
    MessageTooLongError,
    TelegramAPIError,
    TelegraphAPIError,
)
from tests.delivery.conftest import make_summary as _make_summary


def _make_digest(content="Short deep dive content."):
    return Digest(
        deep_dive=_make_summary(name="deep-repo", stars=5000, content=content),
        quick_hits=[_make_summary(name="quick-1", stars=100)],
        ranking_criteria="stars",
        date=date(2026, 3, 6),
    )


def _long_content():
    """Return content exceeding TELEGRAPH_THRESHOLD."""
    return "This is a paragraph of content. " * 80


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


# ───────────────────────────────────────────────────────────────────
# extract_excerpt
# ───────────────────────────────────────────────────────────────────


class TestExtractExcerpt:
    def test_single_paragraph(self):
        assert extract_excerpt("Hello world.") == "Hello world."

    def test_three_paragraphs_returned(self):
        text = "Para one.\n\nPara two.\n\nPara three.\n\nPara four."
        result = extract_excerpt(text)
        assert "Para one." in result
        assert "Para two." in result
        assert "Para three." in result
        assert "Para four." not in result

    def test_fewer_than_max_paragraphs(self):
        text = "Only one."
        assert extract_excerpt(text, max_paragraphs=3) == "Only one."

    def test_custom_max_paragraphs(self):
        text = "A.\n\nB.\n\nC.\n\nD."
        result = extract_excerpt(text, max_paragraphs=2)
        assert "A." in result
        assert "B." in result
        assert "C." not in result

    def test_blank_lines_stripped(self):
        text = "\n\nFirst.\n\n\n\nSecond.\n\n"
        result = extract_excerpt(text)
        assert result == "First.\n\nSecond."

    def test_preserves_paragraph_content(self):
        text = "Line one of para.\nLine two of para.\n\nSecond para."
        result = extract_excerpt(text)
        assert "Line one of para.\nLine two of para." in result


# ───────────────────────────────────────────────────────────────────
# Telegraph integration in send_digest
# ───────────────────────────────────────────────────────────────────


class TestSendDigestTelegraph:
    def test_no_token_skips_telegraph(self):
        with patch("delivery.send.TelegramClient") as MockTG:
            MockTG.return_value.send_message.return_value = {
                "ok": True, "result": {"message_id": 1},
            }
            with patch("delivery.send.TelegraphClient") as MockTP:
                send_digest(_make_digest(content=_long_content()), "@chan", "token")
        MockTP.assert_not_called()

    def test_none_token_skips_telegraph(self):
        with patch("delivery.send.TelegramClient") as MockTG:
            MockTG.return_value.send_message.return_value = {
                "ok": True, "result": {"message_id": 1},
            }
            with patch("delivery.send.TelegraphClient") as MockTP:
                send_digest(
                    _make_digest(content=_long_content()),
                    "@chan", "token", telegraph_token=None,
                )
        MockTP.assert_not_called()

    def test_short_content_skips_telegraph(self):
        with patch("delivery.send.TelegramClient") as MockTG:
            MockTG.return_value.send_message.return_value = {
                "ok": True, "result": {"message_id": 1},
            }
            with patch("delivery.send.TelegraphClient") as MockTP:
                send_digest(
                    _make_digest(content="Short."),
                    "@chan", "token", telegraph_token="tph-token",
                )
        MockTP.assert_not_called()

    def test_telegraph_success_includes_telegraph_link(self):
        with patch("delivery.send.TelegramClient") as MockTG:
            MockTG.return_value.send_message.return_value = {
                "ok": True, "result": {"message_id": 1},
            }
            with patch("delivery.send.TelegraphClient") as MockTP:
                MockTP.return_value.create_page.return_value = (
                    "https://telegra.ph/Test-Page"
                )
                send_digest(
                    _make_digest(content=_long_content()),
                    "@chan", "token", telegraph_token="tph-token",
                )
        sent_text = MockTG.return_value.send_message.call_args[0][1]
        assert "Read full analysis" in sent_text
        assert "telegra.ph/Test-Page" in sent_text

    def test_telegraph_success_contains_excerpt(self):
        long = "First paragraph here.\n\nSecond paragraph here.\n\nThird.\n\n" + "More. " * 200
        with patch("delivery.send.TelegramClient") as MockTG:
            MockTG.return_value.send_message.return_value = {
                "ok": True, "result": {"message_id": 1},
            }
            with patch("delivery.send.TelegraphClient") as MockTP:
                MockTP.return_value.create_page.return_value = (
                    "https://telegra.ph/Test-Page"
                )
                send_digest(
                    _make_digest(content=long),
                    "@chan", "token", telegraph_token="tph-token",
                )
        sent_text = MockTG.return_value.send_message.call_args[0][1]
        assert "First paragraph here" in sent_text
        assert "Second paragraph here" in sent_text

    def test_telegraph_success_does_not_contain_full_content(self):
        paras = [f"Paragraph {i} with additional filler text to make it longer." for i in range(20)]
        long = "\n\n".join(paras)
        assert len(long) >= TELEGRAPH_THRESHOLD
        with patch("delivery.send.TelegramClient") as MockTG:
            MockTG.return_value.send_message.return_value = {
                "ok": True, "result": {"message_id": 1},
            }
            with patch("delivery.send.TelegraphClient") as MockTP:
                MockTP.return_value.create_page.return_value = (
                    "https://telegra.ph/Test-Page"
                )
                send_digest(
                    _make_digest(content=long),
                    "@chan", "token", telegraph_token="tph-token",
                )
        sent_text = MockTG.return_value.send_message.call_args[0][1]
        assert "Paragraph 0" in sent_text
        assert "Paragraph 2" in sent_text
        assert "Paragraph 19" not in sent_text

    def test_telegraph_failure_falls_back_to_truncation(self):
        with patch("delivery.send.TelegramClient") as MockTG:
            MockTG.return_value.send_message.return_value = {
                "ok": True, "result": {"message_id": 1},
            }
            with patch("delivery.send.TelegraphClient") as MockTP:
                MockTP.return_value.create_page.side_effect = TelegraphAPIError(
                    "Connection refused"
                )
                result = send_digest(
                    _make_digest(content=_long_content()),
                    "@chan", "token", telegraph_token="tph-token",
                )
        assert result.success is True
        sent_text = MockTG.return_value.send_message.call_args[0][1]
        assert "Read full analysis" not in sent_text
        assert "telegra.ph" not in sent_text

    def test_telegraph_failure_does_not_crash_pipeline(self):
        with patch("delivery.send.TelegramClient") as MockTG:
            MockTG.return_value.send_message.return_value = {
                "ok": True, "result": {"message_id": 1},
            }
            with patch("delivery.send.TelegraphClient") as MockTP:
                MockTP.return_value.create_page.side_effect = Exception(
                    "Unexpected boom"
                )
                result = send_digest(
                    _make_digest(content=_long_content()),
                    "@chan", "token", telegraph_token="tph-token",
                )
        assert result.success is True

    def test_telegraph_success_preserves_quick_hits(self):
        with patch("delivery.send.TelegramClient") as MockTG:
            MockTG.return_value.send_message.return_value = {
                "ok": True, "result": {"message_id": 1},
            }
            with patch("delivery.send.TelegraphClient") as MockTP:
                MockTP.return_value.create_page.return_value = (
                    "https://telegra.ph/Test-Page"
                )
                send_digest(
                    _make_digest(content=_long_content()),
                    "@chan", "token", telegraph_token="tph-token",
                )
        sent_text = MockTG.return_value.send_message.call_args[0][1]
        assert "QUICK HITS" in sent_text
        assert "quick\\-1" in sent_text

    def test_telegraph_success_preserves_header(self):
        with patch("delivery.send.TelegramClient") as MockTG:
            MockTG.return_value.send_message.return_value = {
                "ok": True, "result": {"message_id": 1},
            }
            with patch("delivery.send.TelegraphClient") as MockTP:
                MockTP.return_value.create_page.return_value = (
                    "https://telegra.ph/Test-Page"
                )
                send_digest(
                    _make_digest(content=_long_content()),
                    "@chan", "token", telegraph_token="tph-token",
                )
        sent_text = MockTG.return_value.send_message.call_args[0][1]
        assert "Daily Digest" in sent_text
        assert "DEEP DIVE" in sent_text

    def test_telegraph_passes_repo_name_as_title(self):
        with patch("delivery.send.TelegramClient") as MockTG:
            MockTG.return_value.send_message.return_value = {
                "ok": True, "result": {"message_id": 1},
            }
            with patch("delivery.send.TelegraphClient") as MockTP:
                MockTP.return_value.create_page.return_value = (
                    "https://telegra.ph/Test-Page"
                )
                send_digest(
                    _make_digest(content=_long_content()),
                    "@chan", "token", telegraph_token="tph-token",
                )
        create_call = MockTP.return_value.create_page.call_args
        assert create_call[1]["title"] == "deep-repo"
