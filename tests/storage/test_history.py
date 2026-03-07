"""Tests for get_featured_repo_ids."""

from datetime import date, timedelta

import pytest

from storage import db
from storage.history import get_featured_repo_ids


SQLITE_CONFIG = {"engine": "sqlite", "database": ":memory:"}


@pytest.fixture(autouse=True)
def setup_db():
    """Initialize and tear down a fresh in-memory DB for each test."""
    db.close()
    db.init(SQLITE_CONFIG)
    yield
    db.close()


def _insert_repo(conn, repo_id, source_id):
    """Insert a minimal repo row for foreign key satisfaction."""
    conn.execute(
        "INSERT INTO repos (id, source, source_id, name, url, raw_content, source_metadata) "
        "VALUES (?, 'github', ?, 'test/repo', 'https://github.com/test/repo', 'readme', '{}')",
        (repo_id, source_id),
    )
    conn.commit()


def _insert_feature(conn, repo_id, days_ago, feature_type="deep"):
    """Insert a feature_history record with featured_date = today - days_ago."""
    featured_date = (date.today() - timedelta(days=days_ago)).isoformat()
    conn.execute(
        "INSERT INTO feature_history (repo_id, feature_type, featured_date, ranking_criteria) "
        "VALUES (?, ?, ?, 'stars')",
        (repo_id, feature_type, featured_date),
    )
    conn.commit()


class TestGetFeaturedRepoIds:
    """get_featured_repo_ids queries feature history with lookback window."""

    def test_no_records_returns_empty(self):
        result = get_featured_repo_ids()
        assert result == set()

    def test_featured_within_window_included(self):
        conn = db.get_connection()
        _insert_repo(conn, 1, "100")
        _insert_feature(conn, 1, days_ago=30)
        result = get_featured_repo_ids(since_days=90)
        assert 1 in result

    def test_featured_outside_window_excluded(self):
        conn = db.get_connection()
        _insert_repo(conn, 1, "100")
        _insert_feature(conn, 1, days_ago=100)
        result = get_featured_repo_ids(since_days=90)
        assert 1 not in result

    def test_boundary_exactly_at_window_included(self):
        conn = db.get_connection()
        _insert_repo(conn, 1, "100")
        _insert_feature(conn, 1, days_ago=90)
        result = get_featured_repo_ids(since_days=90)
        assert 1 in result

    def test_multiple_repos_all_returned(self):
        conn = db.get_connection()
        _insert_repo(conn, 1, "100")
        _insert_repo(conn, 2, "200")
        _insert_repo(conn, 3, "300")
        _insert_feature(conn, 1, days_ago=10)
        _insert_feature(conn, 2, days_ago=50)
        _insert_feature(conn, 3, days_ago=80)
        result = get_featured_repo_ids(since_days=90)
        assert result == {1, 2, 3}

    def test_same_repo_featured_twice_appears_once(self):
        conn = db.get_connection()
        _insert_repo(conn, 1, "100")
        _insert_feature(conn, 1, days_ago=10)
        _insert_feature(conn, 1, days_ago=50)
        result = get_featured_repo_ids(since_days=90)
        assert result == {1}

    def test_default_since_days_is_90(self):
        conn = db.get_connection()
        _insert_repo(conn, 1, "100")
        _insert_repo(conn, 2, "200")
        _insert_feature(conn, 1, days_ago=89)
        _insert_feature(conn, 2, days_ago=91)
        result = get_featured_repo_ids()
        assert 1 in result
        assert 2 not in result


class TestFeatureTypeFilter:
    """get_featured_repo_ids with feature_type filter for tiered cooldown."""

    def test_none_returns_all_types(self):
        conn = db.get_connection()
        _insert_repo(conn, 1, "100")
        _insert_repo(conn, 2, "200")
        _insert_feature(conn, 1, days_ago=10, feature_type="deep")
        _insert_feature(conn, 2, days_ago=10, feature_type="quick")
        result = get_featured_repo_ids(since_days=90, feature_type=None)
        assert result == {1, 2}

    def test_deep_returns_only_deep(self):
        conn = db.get_connection()
        _insert_repo(conn, 1, "100")
        _insert_repo(conn, 2, "200")
        _insert_feature(conn, 1, days_ago=10, feature_type="deep")
        _insert_feature(conn, 2, days_ago=10, feature_type="quick")
        result = get_featured_repo_ids(since_days=90, feature_type="deep")
        assert result == {1}

    def test_quick_returns_only_quick(self):
        conn = db.get_connection()
        _insert_repo(conn, 1, "100")
        _insert_repo(conn, 2, "200")
        _insert_feature(conn, 1, days_ago=10, feature_type="deep")
        _insert_feature(conn, 2, days_ago=10, feature_type="quick")
        result = get_featured_repo_ids(since_days=90, feature_type="quick")
        assert result == {2}

    def test_filter_combines_with_window(self):
        """feature_type filter AND since_days window both apply."""
        conn = db.get_connection()
        _insert_repo(conn, 1, "100")
        _insert_repo(conn, 2, "200")
        _insert_repo(conn, 3, "300")
        _insert_feature(conn, 1, days_ago=5, feature_type="quick")
        _insert_feature(conn, 2, days_ago=20, feature_type="quick")
        _insert_feature(conn, 3, days_ago=5, feature_type="deep")
        result = get_featured_repo_ids(since_days=7, feature_type="quick")
        assert result == {1}

    def test_repo_with_both_types_appears_in_each_filter(self):
        """A repo featured as both deep and quick appears in both filtered queries."""
        conn = db.get_connection()
        _insert_repo(conn, 1, "100")
        _insert_feature(conn, 1, days_ago=10, feature_type="deep")
        _insert_feature(conn, 1, days_ago=5, feature_type="quick")
        assert 1 in get_featured_repo_ids(since_days=90, feature_type="deep")
        assert 1 in get_featured_repo_ids(since_days=90, feature_type="quick")

    def test_no_matches_returns_empty(self):
        conn = db.get_connection()
        _insert_repo(conn, 1, "100")
        _insert_feature(conn, 1, days_ago=10, feature_type="deep")
        result = get_featured_repo_ids(since_days=90, feature_type="quick")
        assert result == set()

    def test_tiered_cooldown_scenario(self):
        """Simulate the tiered cooldown logic the orchestrator will use.

        Repo 1: deep-dived 30 days ago → excluded from both pools
        Repo 2: quick-hit 3 days ago → excluded from both (promotion gap)
        Repo 3: quick-hit 10 days ago → excluded from quick, eligible for deep
        Repo 4: quick-hit 45 days ago → eligible for both
        Repo 5: never featured → eligible for both
        """
        conn = db.get_connection()
        for i in range(1, 6):
            _insert_repo(conn, i, str(i * 100))
        _insert_feature(conn, 1, days_ago=30, feature_type="deep")
        _insert_feature(conn, 2, days_ago=3, feature_type="quick")
        _insert_feature(conn, 3, days_ago=10, feature_type="quick")
        _insert_feature(conn, 4, days_ago=45, feature_type="quick")

        deep_excluded = get_featured_repo_ids(since_days=90, feature_type="deep")
        promotion_blocked = get_featured_repo_ids(since_days=7, feature_type="quick")
        quick_excluded = get_featured_repo_ids(since_days=30, feature_type="quick")

        assert deep_excluded == {1}
        assert promotion_blocked == {2}
        assert quick_excluded == {2, 3}

        deep_pool_excluded = deep_excluded | promotion_blocked
        quick_pool_excluded = deep_excluded | quick_excluded

        all_ids = {1, 2, 3, 4, 5}
        deep_eligible = all_ids - deep_pool_excluded
        quick_eligible = all_ids - quick_pool_excluded

        assert deep_eligible == {3, 4, 5}
        assert quick_eligible == {4, 5}
