"""
Feature history queries.

Provides lookback queries against the feature_history table
to support dedup filtering in the Orchestrator.
"""

from datetime import date, timedelta
from typing import Optional

from storage import db
from storage.types import StorageError


def get_featured_repo_ids(
    since_days: int = 90,
    feature_type: Optional[str] = None,
) -> set[int]:
    """Return IDs of repos featured within the lookback window.

    Args:
        since_days: Number of days to look back (default 90).
            A repo featured exactly since_days ago is included.
        feature_type: Optional filter — "deep", "quick", or None for all types.

    Returns:
        Set of repo IDs featured within the window, optionally
        filtered by feature type.
    """
    conn = db.get_connection()
    engine = db.get_engine()
    cutoff = date.today() - timedelta(days=since_days)

    where = "WHERE featured_date >= "
    params: list = []

    if engine == "sqlite":
        where += "?"
        params.append(cutoff.isoformat())
    else:
        where += "%s"
        params.append(cutoff)

    if feature_type is not None:
        placeholder = "?" if engine == "sqlite" else "%s"
        where += f" AND feature_type = {placeholder}"
        params.append(feature_type)

    sql = f"SELECT DISTINCT repo_id FROM feature_history {where}"

    try:
        if engine == "sqlite":
            cursor = conn.execute(sql, tuple(params))
        else:
            cursor = conn.cursor()
            cursor.execute(sql, tuple(params))

        return {row[0] for row in cursor.fetchall()}
    except StorageError:
        raise
    except Exception as e:
        raise StorageError(f"get_featured_repo_ids failed: {e}")
