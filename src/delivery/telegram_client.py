"""
Telegram Bot API client.

Handles HTTP interaction with Telegram's sendMessage endpoint.
All Telegram-specific error handling lives here.
"""

import requests

from delivery.types import TelegramAPIError

TELEGRAM_API_BASE = "https://api.telegram.org"


class TelegramClient:
    """Minimal Telegram Bot API client for sending messages."""

    def __init__(self, bot_token: str):
        self._bot_token = bot_token
        self._base_url = f"{TELEGRAM_API_BASE}/bot{bot_token}"

    def send_message(
        self,
        chat_id: str,
        text: str,
        parse_mode: str = "MarkdownV2",
    ) -> dict:
        """Send a text message via the Telegram Bot API.

        Args:
            chat_id: Target chat or channel ID.
            text: Message text (already formatted for parse_mode).
            parse_mode: Telegram parse mode (default "MarkdownV2").

        Returns:
            Telegram API response dict (contains result.message_id on success).

        Raises:
            TelegramAPIError: On API errors, HTTP errors, or network failures.
        """
        url = f"{self._base_url}/sendMessage"
        payload = {
            "chat_id": chat_id,
            "text": text,
            "parse_mode": parse_mode,
        }

        try:
            response = requests.post(url, json=payload, timeout=30)
        except requests.ConnectionError as exc:
            raise TelegramAPIError(
                f"Network error connecting to Telegram: {exc}"
            ) from exc
        except requests.Timeout as exc:
            raise TelegramAPIError(
                "Telegram API request timed out."
            ) from exc
        except requests.RequestException as exc:
            raise TelegramAPIError(
                f"Telegram API request failed: {exc}"
            ) from exc

        try:
            data = response.json()
        except ValueError:
            raise TelegramAPIError(
                f"Telegram returned non-JSON response (HTTP {response.status_code})",
                status_code=response.status_code,
            )

        if response.status_code != 200 or not data.get("ok"):
            description = data.get("description", response.text)
            raise TelegramAPIError(
                f"Telegram API error: {description}",
                status_code=response.status_code,
            )

        return data
