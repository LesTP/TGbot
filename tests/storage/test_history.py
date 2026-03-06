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


def _insert_feature(conn, repo_id, days_ago):
    """Insert a feature_history record with featured_date = today - days_ago."""
    featured_date = (date.today() - timedelta(days=days_ago)).isoformat()
    conn.execute(
        "INSERT INTO feature_history (repo_id, feature_type, featured_date, ranking_criteria) "
        "VALUES (?, 'deep', ?, 'stars')",
        (repo_id, featured_date),
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
