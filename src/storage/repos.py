"""
Repo persistence — save_repo and get_repo.

Handles upsert logic (insert or update by source + source_id)
with engine-aware SQL for SQLite and MySQL compatibility.
"""

import json
from datetime import datetime
from typing import Optional

from discovery.types import DiscoveredRepo
from storage import db
from storage.types import RepoRecord, StorageError


def _parse_datetime(value) -> Optional[datetime]:
    """Parse a datetime from DB. SQLite returns strings, MySQL returns datetime."""
    if value is None:
        return None
    if isinstance(value, datetime):
        return value
    return datetime.fromisoformat(value)


def _row_to_repo_record(row) -> RepoRecord:
    """Convert a database row to a RepoRecord."""
    return RepoRecord(
        id=row["id"],
        source=row["source"],
        source_id=row["source_id"],
        name=row["name"],
        url=row["url"],
        description=row["description"],
        raw_content=row["raw_content"],
        source_metadata=json.loads(row["source_metadata"]),
        discovered_at=_parse_datetime(row["discovered_at"]),
        first_featured_at=_parse_datetime(row["first_featured_at"]),
        last_featured_at=_parse_datetime(row["last_featured_at"]),
        feature_count=row["feature_count"],
    )


def save_repo(repo: DiscoveredRepo) -> RepoRecord:
    """Persist a discovered repo. Upserts by (source, source_id).

    On insert: sets discovered_at to now, feature fields to defaults.
    On conflict: updates name, url, description, raw_content, source_metadata.
    Preserves discovered_at, feature tracking fields on update.
    """
    conn = db.get_connection()
    engine = db.get_engine()
    metadata_json = json.dumps(repo.source_metadata)

    try:
        if engine == "sqlite":
            conn.execute(
                "INSERT INTO repos (source, source_id, name, url, description, "
                "raw_content, source_metadata) "
                "VALUES (?, ?, ?, ?, ?, ?, ?) "
                "ON CONFLICT(source, source_id) DO UPDATE SET "
                "name = excluded.name, "
                "url = excluded.url, "
                "description = excluded.description, "
                "raw_content = excluded.raw_content, "
                "source_metadata = excluded.source_metadata",
                (
                    repo.source, repo.source_id, repo.name, repo.url,
                    repo.description, repo.raw_content, metadata_json,
                ),
            )
            conn.commit()
            cursor = conn.execute(
                "SELECT * FROM repos WHERE source = ? AND source_id = ?",
                (repo.source, repo.source_id),
            )
        else:
            cursor = conn.cursor()
            cursor.execute(
                "INSERT INTO repos (source, source_id, name, url, description, "
                "raw_content, source_metadata) "
                "VALUES (%s, %s, %s, %s, %s, %s, %s) "
                "ON DUPLICATE KEY UPDATE "
                "name = VALUES(name), "
                "url = VALUES(url), "
                "description = VALUES(description), "
                "raw_content = VALUES(raw_content), "
                "source_metadata = VALUES(source_metadata)",
                (
                    repo.source, repo.source_id, repo.name, repo.url,
                    repo.description, repo.raw_content, metadata_json,
                ),
            )
            conn.commit()
            cursor.execute(
                "SELECT * FROM repos WHERE source = %s AND source_id = %s",
                (repo.source, repo.source_id),
            )

        row = cursor.fetchone()
        return _row_to_repo_record(row)
    except StorageError:
        raise
    except Exception as e:
        raise StorageError(f"save_repo failed: {e}")


def get_repo(repo_id: int) -> Optional[RepoRecord]:
    """Fetch a repo by internal ID. Returns None if not found."""
    conn = db.get_connection()
    engine = db.get_engine()

    try:
        if engine == "sqlite":
            cursor = conn.execute(
                "SELECT * FROM repos WHERE id = ?", (repo_id,)
            )
        else:
            cursor = conn.cursor(dictionary=True)
            cursor.execute(
                "SELECT * FROM repos WHERE id = %s", (repo_id,)
            )

        row = cursor.fetchone()
        if row is None:
            return None
        return _row_to_repo_record(row)
    except StorageError:
        raise
    except Exception as e:
        raise StorageError(f"get_repo failed: {e}")
