"""
Delivery module types.

Data types for the Delivery module's public API: message shapes,
result types, and error types. See ARCH_delivery.md for contracts.
"""

from dataclasses import dataclass
from datetime import date
from typing import Optional


# ---------------------------------------------------------------------------
# Message types
# ---------------------------------------------------------------------------


@dataclass
class SummaryWithRepo:
    """A summary paired with its repo metadata for message formatting.

    Assembled by Orchestrator from a SummaryRecord + RepoRecord.
    """

    summary_content: str
    repo_name: str
    repo_url: str
    stars: int
    created_at: str


@dataclass
class Digest:
    """A complete digest ready for delivery.

    Contains one deep dive and 1-3 quick hits, plus metadata
    about the ranking criteria and date.
    """

    deep_dive: SummaryWithRepo
    quick_hits: list[SummaryWithRepo]
    ranking_criteria: str
    date: date


# ---------------------------------------------------------------------------
# Result types
# ---------------------------------------------------------------------------


@dataclass
class DeliveryResult:
    """Result of a delivery attempt.

    If success is True, message_id contains the Telegram message ID.
    If success is False, error contains a description of what went wrong.
    """

    success: bool
    message_id: Optional[str] = None
    error: Optional[str] = None


# ---------------------------------------------------------------------------
# Error types
# ---------------------------------------------------------------------------


class TelegramAPIError(Exception):
    """Telegram API call failed (auth, network, invalid channel)."""

    def __init__(self, message: str, status_code: Optional[int] = None):
        super().__init__(message)
        self.message = message
        self.status_code = status_code


class MessageTooLongError(Exception):
    """Formatted message exceeds Telegram limits even after truncation."""

    def __init__(self, length: int, max_length: int = 4096):
        msg = f"Message length {length} exceeds maximum {max_length}"
        super().__init__(msg)
        self.length = length
        self.max_length = max_length


class TelegraphAPIError(Exception):
    """Telegraph API call failed. Non-fatal — caller falls back to truncation."""

    def __init__(self, message: str, status_code: Optional[int] = None):
        super().__init__(message)
        self.message = message
        self.status_code = status_code
