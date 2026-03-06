"""
Summary persistence — save_summary and get_summary.
"""

from datetime import datetime
from typing import Optional

from storage import db
from storage.types import StorageError, SummaryRecord

_VALID_SUMMARY_TYPES = ("deep", "quick")


def _parse_datetime(value) -> datetime:
    """Parse a datetime from DB. SQLite returns strings, MySQL returns datetime."""
    if isinstance(value, datetime):
        return value
    return datetime.fromisoformat(value)


def _row_to_summary_record(row) -> SummaryRecord:
    """Convert a database row to a SummaryRecord."""
    return SummaryRecord(
        id=row["id"],
        repo_id=row["repo_id"],
        summary_type=row["summary_type"],
        content=row["content"],
        model_used=row["model_used"],
        generated_at=_parse_datetime(row["generated_at"]),
    )


def save_summary(
    repo_id: int, summary_type: str, content: str, model_used: str
) -> SummaryRecord:
    """Persist a generated summary.

    Args:
        repo_id: Must reference an existing repo.
        summary_type: "deep" or "quick".
        content: The generated summary text.
        model_used: Model identifier.

    Returns:
        SummaryRecord with assigned id and generated_at.

    Raises:
        ValueError: repo_id doesn't exist or invalid summary_type.
        StorageError: Database write failed.
    """
    if summary_type not in _VALID_SUMMARY_TYPES:
        raise ValueError(
            f"Invalid summary_type: {summary_type!r}. Must be one of {_VALID_SUMMARY_TYPES}."
        )

    conn = db.get_connection()
    engine = db.get_engine()

    try:
        if engine == "sqlite":
            cursor = conn.execute(
                "SELECT id FROM repos WHERE id = ?", (repo_id,)
            )
        else:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT id FROM repos WHERE id = %s", (repo_id,)
            )

        if cursor.fetchone() is None:
            raise ValueError(f"repo_id {repo_id} does not exist.")

        if engine == "sqlite":
            cursor = conn.execute(
                "INSERT INTO summaries (repo_id, summary_type, content, model_used) "
                "VALUES (?, ?, ?, ?)",
                (repo_id, summary_type, content, model_used),
            )
            conn.commit()
            summary_id = cursor.lastrowid
            cursor = conn.execute(
                "SELECT * FROM summaries WHERE id = ?", (summary_id,)
            )
        else:
            cursor = conn.cursor(dictionary=True)
            cursor.execute(
                "INSERT INTO summaries (repo_id, summary_type, content, model_used) "
                "VALUES (%s, %s, %s, %s)",
                (repo_id, summary_type, content, model_used),
            )
            conn.commit()
            summary_id = cursor.lastrowid
            cursor.execute(
                "SELECT * FROM summaries WHERE id = %s", (summary_id,)
            )

        row = cursor.fetchone()
        return _row_to_summary_record(row)
    except (ValueError, StorageError):
        raise
    except Exception as e:
        raise StorageError(f"save_summary failed: {e}")


def get_summary(summary_id: int) -> Optional[SummaryRecord]:
    """Fetch a summary by internal ID. Returns None if not found."""
    conn = db.get_connection()
    engine = db.get_engine()

    try:
        if engine == "sqlite":
            cursor = conn.execute(
                "SELECT * FROM summaries WHERE id = ?", (summary_id,)
            )
        else:
            cursor = conn.cursor(dictionary=True)
            cursor.execute(
                "SELECT * FROM summaries WHERE id = %s", (summary_id,)
            )

        row = cursor.fetchone()
        if row is None:
            return None
        return _row_to_summary_record(row)
    except StorageError:
        raise
    except Exception as e:
        raise StorageError(f"get_summary failed: {e}")


def get_recent_summaries(since_days: int = 14) -> list[SummaryRecord]:
    """Fetch summaries generated within the lookback window.

    Returns SummaryRecords ordered by generated_at descending (newest first).
    Empty list if none found.

    Raises:
        StorageError: Database read failed.
    """
    conn = db.get_connection()
    engine = db.get_engine()

    try:
        if engine == "sqlite":
            cursor = conn.execute(
                "SELECT * FROM summaries "
                "WHERE generated_at >= datetime('now', '-' || ? || ' days') "
                "ORDER BY generated_at DESC",
                (since_days,),
            )
            rows = cursor.fetchall()
        else:
            cursor = conn.cursor(dictionary=True)
            cursor.execute(
                "SELECT * FROM summaries "
                "WHERE generated_at >= NOW() - INTERVAL %s DAY "
                "ORDER BY generated_at DESC",
                (since_days,),
            )
            rows = cursor.fetchall()

        return [_row_to_summary_record(row) for row in rows]
    except StorageError:
        raise
    except Exception as e:
        raise StorageError(f"get_recent_summaries failed: {e}")
