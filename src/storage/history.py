"""
Feature history queries.

Provides lookback queries against the feature_history table
to support dedup filtering in the Orchestrator.
"""

from datetime import date, timedelta

from storage import db
from storage.types import StorageError


def get_featured_repo_ids(since_days: int = 90) -> set[int]:
    """Return IDs of repos featured within the lookback window.

    Args:
        since_days: Number of days to look back (default 90).
            A repo featured exactly since_days ago is included.

    Returns:
        Set of repo IDs featured within the window.
    """
    conn = db.get_connection()
    engine = db.get_engine()
    cutoff = date.today() - timedelta(days=since_days)

    try:
        if engine == "sqlite":
            cursor = conn.execute(
                "SELECT DISTINCT repo_id FROM feature_history "
                "WHERE featured_date >= ?",
                (cutoff.isoformat(),),
            )
        else:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT DISTINCT repo_id FROM feature_history "
                "WHERE featured_date >= %s",
                (cutoff,),
            )

        return {row[0] for row in cursor.fetchall()}
    except StorageError:
        raise
    except Exception as e:
        raise StorageError(f"get_featured_repo_ids failed: {e}")
