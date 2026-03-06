"""
Storage module — data access layer for repos, summaries, and feature history.

Public API matches ARCH_storage.md. Supports SQLite (dev/test) and
MySQL (production) via engine-aware init().
"""

from storage.db import close, get_engine, init
from storage.features import record_feature
from storage.history import get_featured_repo_ids
from storage.repos import get_repo, save_repo
from storage.summaries import get_summary, get_recent_summaries, save_summary
from storage.types import FeatureRecord, RepoRecord, StorageError, SummaryRecord

__all__ = [
    "init",
    "close",
    "save_repo",
    "get_repo",
    "get_featured_repo_ids",
    "save_summary",
    "get_summary",
    "get_recent_summaries",
    "record_feature",
    "StorageError",
    "RepoRecord",
    "SummaryRecord",
    "FeatureRecord",
]
