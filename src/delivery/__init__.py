"""
Delivery module — formats and sends digests to Telegram.
"""

from delivery.send import send_digest
from delivery.types import (
    DeliveryResult,
    Digest,
    MessageTooLongError,
    SummaryWithRepo,
    TelegramAPIError,
)

__all__ = [
    "send_digest",
    "DeliveryResult",
    "Digest",
    "MessageTooLongError",
    "SummaryWithRepo",
    "TelegramAPIError",
]
