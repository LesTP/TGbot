"""
Main entry point for the Delivery module.

Wires formatting, truncation, and Telegram API interaction
into a single public function.
"""

import logging

from delivery.formatting import format_digest, truncate_for_telegram
from delivery.telegram_client import TelegramClient
from delivery.types import (
    DeliveryResult,
    Digest,
    MessageTooLongError,
    TelegramAPIError,
)

logger = logging.getLogger(__name__)

TELEGRAM_MAX_LENGTH = 4096


def send_digest(
    digest: Digest, channel_id: str, bot_token: str
) -> DeliveryResult:
    """Format a digest and send it to Telegram.

    Orchestrates the full delivery pipeline:
    1. Format the digest into a MarkdownV2 message
    2. Truncate if over Telegram's 4,096 character limit
    3. Raise MessageTooLongError if still over limit after truncation
    4. Send via Telegram Bot API
    5. Return DeliveryResult

    Args:
        digest: Assembled digest from Orchestrator.
        channel_id: Telegram channel or chat ID.
        bot_token: Telegram bot API token.

    Returns:
        DeliveryResult with success status and message_id or error.

    Raises:
        MessageTooLongError: If the message exceeds the limit even
            after truncation (pathological input).
    """
    message = format_digest(digest)

    if len(message) > TELEGRAM_MAX_LENGTH:
        message = truncate_for_telegram(
            message, digest.deep_dive.repo_url, TELEGRAM_MAX_LENGTH
        )

    if len(message) > TELEGRAM_MAX_LENGTH:
        raise MessageTooLongError(
            length=len(message), max_length=TELEGRAM_MAX_LENGTH
        )

    client = TelegramClient(bot_token)
    try:
        data = client.send_message(channel_id, message)
        message_id = str(data["result"]["message_id"])
        return DeliveryResult(success=True, message_id=message_id, error=None)
    except TelegramAPIError as exc:
        logger.error("Telegram delivery failed: %s", exc)
        return DeliveryResult(success=False, message_id=None, error=str(exc))
