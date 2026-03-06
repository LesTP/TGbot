"""
Feature recording — record_feature.

Records a repo being featured in a digest. Inserts into feature_history
and atomically updates the repo's feature tracking fields.
"""

from datetime import date, datetime

from storage import db
from storage.types import FeatureRecord, StorageError

_VALID_FEATURE_TYPES = ("deep", "quick")


def record_feature(
    repo_id: int, feature_type: str, ranking_criteria: str
) -> FeatureRecord:
    """Record that a repo was featured in a digest.

    Inserts a feature_history record and updates the repo's
    last_featured_at, feature_count, and (on first feature) first_featured_at.

    Args:
        repo_id: Must reference an existing repo.
        feature_type: "deep" or "quick".
        ranking_criteria: Which ranking was used.

    Returns:
        FeatureRecord with featured_date set to today.

    Raises:
        ValueError: repo_id doesn't exist or invalid feature_type.
        StorageError: Database write failed.
    """
    if feature_type not in _VALID_FEATURE_TYPES:
        raise ValueError(
            f"Invalid feature_type: {feature_type!r}. Must be one of {_VALID_FEATURE_TYPES}."
        )

    conn = db.get_connection()
    engine = db.get_engine()
    today = date.today()
    now = datetime.now()

    try:
        # Verify repo exists
        if engine == "sqlite":
            cursor = conn.execute(
                "SELECT id FROM repos WHERE id = ?", (repo_id,),
            )
        else:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT id FROM repos WHERE id = %s", (repo_id,),
            )

        if cursor.fetchone() is None:
            raise ValueError(f"repo_id {repo_id} does not exist.")

        # Insert feature history record
        if engine == "sqlite":
            cursor = conn.execute(
                "INSERT INTO feature_history (repo_id, feature_type, featured_date, ranking_criteria) "
                "VALUES (?, ?, ?, ?)",
                (repo_id, feature_type, today.isoformat(), ranking_criteria),
            )
            feature_id = cursor.lastrowid

            # Update repo: COALESCE preserves first_featured_at if already set
            conn.execute(
                "UPDATE repos SET "
                "first_featured_at = COALESCE(first_featured_at, ?), "
                "last_featured_at = ?, "
                "feature_count = feature_count + 1 "
                "WHERE id = ?",
                (now.isoformat(), now.isoformat(), repo_id),
            )
        else:
            cursor = conn.cursor()
            cursor.execute(
                "INSERT INTO feature_history (repo_id, feature_type, featured_date, ranking_criteria) "
                "VALUES (%s, %s, %s, %s)",
                (repo_id, feature_type, today, ranking_criteria),
            )
            feature_id = cursor.lastrowid

            cursor.execute(
                "UPDATE repos SET "
                "first_featured_at = COALESCE(first_featured_at, %s), "
                "last_featured_at = %s, "
                "feature_count = feature_count + 1 "
                "WHERE id = %s",
                (now, now, repo_id),
            )

        conn.commit()

        return FeatureRecord(
            id=feature_id,
            repo_id=repo_id,
            feature_type=feature_type,
            featured_date=today,
            ranking_criteria=ranking_criteria,
        )
    except (ValueError, StorageError):
        raise
    except Exception as e:
        raise StorageError(f"record_feature failed: {e}")
