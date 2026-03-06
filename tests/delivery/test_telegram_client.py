"""Tests for Telegram API client."""

from unittest.mock import MagicMock, patch

import pytest

from delivery.telegram_client import TelegramClient, TELEGRAM_API_BASE
from delivery.types import TelegramAPIError


@pytest.fixture
def client():
    return TelegramClient(bot_token="123456:ABC-DEF")


class TestTelegramClientConstruction:
    def test_stores_token(self):
        c = TelegramClient("my-token")
        assert c._bot_token == "my-token"

    def test_builds_base_url(self):
        c = TelegramClient("123:abc")
        assert c._base_url == f"{TELEGRAM_API_BASE}/bot123:abc"


class TestSendMessageSuccess:
    def test_returns_response_dict(self, client):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "ok": True,
            "result": {"message_id": 42},
        }
        with patch("delivery.telegram_client.requests.post", return_value=mock_response):
            result = client.send_message("@channel", "hello")
        assert result["ok"] is True
        assert result["result"]["message_id"] == 42

    def test_message_id_in_result(self, client):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "ok": True,
            "result": {"message_id": 99},
        }
        with patch("delivery.telegram_client.requests.post", return_value=mock_response):
            result = client.send_message("-100123", "text")
        assert result["result"]["message_id"] == 99


class TestSendMessageRequest:
    def test_posts_to_correct_url(self, client):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"ok": True, "result": {"message_id": 1}}
        with patch("delivery.telegram_client.requests.post", return_value=mock_response) as mock_post:
            client.send_message("@chan", "text")
        call_args = mock_post.call_args
        assert "/bot123456:ABC-DEF/sendMessage" in call_args[0][0]

    def test_sends_chat_id_in_payload(self, client):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"ok": True, "result": {"message_id": 1}}
        with patch("delivery.telegram_client.requests.post", return_value=mock_response) as mock_post:
            client.send_message("-100999", "msg")
        payload = mock_post.call_args[1]["json"]
        assert payload["chat_id"] == "-100999"

    def test_sends_text_in_payload(self, client):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"ok": True, "result": {"message_id": 1}}
        with patch("delivery.telegram_client.requests.post", return_value=mock_response) as mock_post:
            client.send_message("@chan", "hello world")
        payload = mock_post.call_args[1]["json"]
        assert payload["text"] == "hello world"

    def test_sends_parse_mode_in_payload(self, client):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"ok": True, "result": {"message_id": 1}}
        with patch("delivery.telegram_client.requests.post", return_value=mock_response) as mock_post:
            client.send_message("@chan", "text")
        payload = mock_post.call_args[1]["json"]
        assert payload["parse_mode"] == "MarkdownV2"

    def test_custom_parse_mode(self, client):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"ok": True, "result": {"message_id": 1}}
        with patch("delivery.telegram_client.requests.post", return_value=mock_response) as mock_post:
            client.send_message("@chan", "text", parse_mode="HTML")
        payload = mock_post.call_args[1]["json"]
        assert payload["parse_mode"] == "HTML"


class TestSendMessageAPIErrors:
    def test_ok_false_raises(self, client):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "ok": False,
            "description": "Bad Request: chat not found",
        }
        mock_response.text = '{"ok":false,"description":"Bad Request: chat not found"}'
        with patch("delivery.telegram_client.requests.post", return_value=mock_response):
            with pytest.raises(TelegramAPIError) as exc_info:
                client.send_message("@invalid", "text")
        assert "chat not found" in str(exc_info.value)
        assert exc_info.value.status_code == 200

    def test_401_raises(self, client):
        mock_response = MagicMock()
        mock_response.status_code = 401
        mock_response.json.return_value = {
            "ok": False,
            "description": "Unauthorized",
        }
        mock_response.text = "Unauthorized"
        with patch("delivery.telegram_client.requests.post", return_value=mock_response):
            with pytest.raises(TelegramAPIError) as exc_info:
                client.send_message("@chan", "text")
        assert exc_info.value.status_code == 401

    def test_400_raises(self, client):
        mock_response = MagicMock()
        mock_response.status_code = 400
        mock_response.json.return_value = {
            "ok": False,
            "description": "Bad Request: can't parse entities",
        }
        mock_response.text = "Bad Request"
        with patch("delivery.telegram_client.requests.post", return_value=mock_response):
            with pytest.raises(TelegramAPIError) as exc_info:
                client.send_message("@chan", "bad *markdown")
        assert exc_info.value.status_code == 400
        assert "parse entities" in str(exc_info.value)

    def test_500_raises(self, client):
        mock_response = MagicMock()
        mock_response.status_code = 500
        mock_response.json.return_value = {
            "ok": False,
            "description": "Internal Server Error",
        }
        mock_response.text = "Internal Server Error"
        with patch("delivery.telegram_client.requests.post", return_value=mock_response):
            with pytest.raises(TelegramAPIError) as exc_info:
                client.send_message("@chan", "text")
        assert exc_info.value.status_code == 500

    def test_non_json_response_raises(self, client):
        mock_response = MagicMock()
        mock_response.status_code = 502
        mock_response.json.side_effect = ValueError("No JSON")
        mock_response.text = "<html>Bad Gateway</html>"
        with patch("delivery.telegram_client.requests.post", return_value=mock_response):
            with pytest.raises(TelegramAPIError) as exc_info:
                client.send_message("@chan", "text")
        assert exc_info.value.status_code == 502
        assert "non-JSON" in str(exc_info.value)


class TestSendMessageNetworkErrors:
    def test_connection_error_raises(self, client):
        import requests as req
        with patch(
            "delivery.telegram_client.requests.post",
            side_effect=req.ConnectionError("Connection refused"),
        ):
            with pytest.raises(TelegramAPIError) as exc_info:
                client.send_message("@chan", "text")
        assert "Network error" in str(exc_info.value)
        assert exc_info.value.status_code is None

    def test_timeout_raises(self, client):
        import requests as req
        with patch(
            "delivery.telegram_client.requests.post",
            side_effect=req.Timeout("timed out"),
        ):
            with pytest.raises(TelegramAPIError) as exc_info:
                client.send_message("@chan", "text")
        assert "timed out" in str(exc_info.value)
        assert exc_info.value.status_code is None

    def test_generic_request_exception_raises(self, client):
        import requests as req
        with patch(
            "delivery.telegram_client.requests.post",
            side_effect=req.RequestException("something broke"),
        ):
            with pytest.raises(TelegramAPIError) as exc_info:
                client.send_message("@chan", "text")
        assert "request failed" in str(exc_info.value)
        assert exc_info.value.status_code is None
