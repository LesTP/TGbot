"""
Storage module types.

Data types for the Storage module's public API: record shapes
and error types. See ARCH_storage.md for contracts.
"""

from dataclasses import dataclass
from datetime import date, datetime
from typing import Optional


class StorageError(Exception):
    """Database operation failed."""

    def __init__(self, message: str):
        super().__init__(message)
        self.message = message


@dataclass
class RepoRecord:
    """A persisted repository record.

    Extends DiscoveredRepo fields with persistence metadata
    (id, timestamps, feature tracking).
    """

    id: int
    source: str
    source_id: str
    name: str
    url: str
    description: Optional[str]
    raw_content: str
    source_metadata: dict
    discovered_at: datetime
    first_featured_at: Optional[datetime] = None
    last_featured_at: Optional[datetime] = None
    feature_count: int = 0


@dataclass
class SummaryRecord:
    """A persisted summary record."""

    id: int
    repo_id: int
    summary_type: str  # "deep" | "quick"
    content: str
    model_used: str
    generated_at: datetime


@dataclass
class FeatureRecord:
    """A record of a repo being featured in a digest."""

    id: int
    repo_id: int
    feature_type: str  # "deep" | "quick"
    featured_date: date
    ranking_criteria: str
