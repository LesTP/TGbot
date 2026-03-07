"""
Main entry point for the Delivery module.

Wires formatting, truncation, Telegraph publishing, and Telegram API
interaction into a single public function.
"""

import logging
from typing import Optional

from delivery.formatting import (
    format_digest,
    truncate_for_telegram,
)
from delivery.telegram_client import TelegramClient
from delivery.telegraph_client import TelegraphClient, text_to_telegraph_html
from delivery.types import (
    DeliveryResult,
    Digest,
    MessageTooLongError,
    TelegramAPIError,
    TelegraphAPIError,
)

logger = logging.getLogger(__name__)

TELEGRAM_MAX_LENGTH = 4096
TELEGRAPH_THRESHOLD = 1000


def _try_publish_telegraph(
    digest: Digest, telegraph_token: str
) -> Optional[str]:
    """Attempt to publish the deep dive to Telegraph.

    Returns the Telegraph page URL on success, or None on failure.
    Never raises — all errors are logged and swallowed.
    """
    content = digest.deep_dive.summary_content
    if len(content) < TELEGRAPH_THRESHOLD:
        return None

    try:
        client = TelegraphClient(telegraph_token)
        title = digest.deep_dive.repo_name
        html = text_to_telegraph_html(content)
        page_url = client.create_page(
            title=title,
            html_content=html,
            author_name="GitHub Digest Bot",
        )
        logger.info("Published deep dive to Telegraph: %s", page_url)
        return page_url
    except TelegraphAPIError as exc:
        logger.warning("Telegraph publish failed, falling back to truncation: %s", exc)
        return None
    except Exception as exc:
        logger.warning("Unexpected error publishing to Telegraph: %s", exc)
        return None


def send_digest(
    digest: Digest,
    channel_id: str,
    bot_token: str,
    telegraph_token: Optional[str] = None,
) -> DeliveryResult:
    """Format a digest and send it to Telegram.

    Orchestrates the full delivery pipeline:
    1. If telegraph_token provided, attempt to publish deep dive to Telegraph
    2. Format the digest (with Telegraph excerpt if publish succeeded)
    3. Truncate if over Telegram's 4,096 character limit
    4. Send via Telegram Bot API
    5. Return DeliveryResult

    Args:
        digest: Assembled digest from Orchestrator.
        channel_id: Telegram channel or chat ID.
        bot_token: Telegram bot API token.
        telegraph_token: Optional Telegraph access token. If provided and
            deep dive is long enough, publishes to Telegraph and links
            from the Telegram message.

    Returns:
        DeliveryResult with success status and message_id or error.

    Raises:
        MessageTooLongError: If the message exceeds the limit even
            after truncation (pathological input).
    """
    telegraph_url = None
    if telegraph_token:
        telegraph_url = _try_publish_telegraph(digest, telegraph_token)

    message = format_digest(digest, telegraph_url=telegraph_url)

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
