"""Tests for save_summary, get_summary, and get_recent_summaries."""

import pytest
from datetime import datetime, timedelta

from discovery.types import DiscoveredRepo
from storage import db
from storage.repos import save_repo
from storage.summaries import save_summary, get_summary, get_recent_summaries


SQLITE_CONFIG = {"engine": "sqlite", "database": ":memory:"}


def _make_discovered_repo(**overrides):
    defaults = dict(
        source="github",
        source_id="12345",
        name="owner/repo",
        url="https://github.com/owner/repo",
        description="A test repository",
        raw_content="# README\nTest.",
        source_metadata={"stars": 100},
    )
    defaults.update(overrides)
    return DiscoveredRepo(**defaults)


@pytest.fixture(autouse=True)
def setup_db():
    db.close()
    db.init(SQLITE_CONFIG)
    yield
    db.close()


@pytest.fixture
def repo_record():
    """Insert a repo and return its record for FK satisfaction."""
    return save_repo(_make_discovered_repo())


def _insert_repo(conn, repo_id, source_id):
    """Insert a minimal repo row for foreign key satisfaction."""
    conn.execute(
        "INSERT INTO repos (id, source, source_id, name, url, raw_content, source_metadata) "
        "VALUES (?, 'github', ?, 'test/repo', 'https://github.com/test/repo', 'readme', '{}')",
        (repo_id, source_id),
    )
    conn.commit()


def _insert_summary(conn, repo_id, summary_type, content, days_ago):
    """Insert a summary with generated_at = now - days_ago."""
    generated_at = (datetime.now() - timedelta(days=days_ago)).isoformat()
    conn.execute(
        "INSERT INTO summaries (repo_id, summary_type, content, model_used, generated_at) "
        "VALUES (?, ?, ?, 'test-model', ?)",
        (repo_id, summary_type, content, generated_at),
    )
    conn.commit()


class TestSaveSummary:
    """save_summary persists summaries with validation."""

    def test_save_with_valid_repo(self, repo_record):
        summary = save_summary(repo_record.id, "deep", "Summary text.", "claude-sonnet-4-5")
        assert summary.id > 0
        assert summary.repo_id == repo_record.id
        assert summary.summary_type == "deep"
        assert summary.content == "Summary text."
        assert summary.model_used == "claude-sonnet-4-5"
        assert summary.generated_at is not None

    def test_invalid_repo_id_raises(self):
        with pytest.raises(ValueError, match="does not exist"):
            save_summary(9999, "deep", "content", "model")

    def test_invalid_summary_type_raises(self, repo_record):
        with pytest.raises(ValueError, match="Invalid summary_type"):
            save_summary(repo_record.id, "medium", "content", "model")

    def test_content_roundtrip_special_chars(self, repo_record):
        content = "Unicode: 🚀✨ | Newlines:\nLine2\n\nLine4 | Quotes: \"it's\" | HTML: <b>bold</b>"
        summary = save_summary(repo_record.id, "quick", content, "model")
        assert summary.content == content

    def test_multiple_summaries_unique_ids(self, repo_record):
        s1 = save_summary(repo_record.id, "deep", "Deep dive.", "model-a")
        s2 = save_summary(repo_record.id, "quick", "Quick hit.", "model-b")
        assert s1.id != s2.id


class TestGetSummary:
    """get_summary retrieves by internal ID."""

    def test_valid_id(self, repo_record):
        saved = save_summary(repo_record.id, "deep", "Content here.", "model")
        fetched = get_summary(saved.id)
        assert fetched is not None
        assert fetched.id == saved.id
        assert fetched.content == "Content here."
        assert fetched.summary_type == "deep"

    def test_nonexistent_id(self):
        result = get_summary(9999)
        assert result is None


class TestGetRecentSummaries:
    """get_recent_summaries queries summaries within a lookback window."""

    def test_no_summaries_returns_empty(self):
        result = get_recent_summaries()
        assert result == []

    def test_recent_summary_returned(self):
        conn = db.get_connection()
        _insert_repo(conn, 1, "100")
        _insert_summary(conn, 1, "deep", "Recent deep dive.", days_ago=3)
        result = get_recent_summaries(since_days=14)
        assert len(result) == 1
        assert result[0].content == "Recent deep dive."
        assert result[0].summary_type == "deep"

    def test_old_summary_excluded(self):
        conn = db.get_connection()
        _insert_repo(conn, 1, "100")
        _insert_summary(conn, 1, "deep", "Old summary.", days_ago=20)
        result = get_recent_summaries(since_days=14)
        assert result == []

    def test_mixed_inside_and_outside_window(self):
        conn = db.get_connection()
        _insert_repo(conn, 1, "100")
        _insert_repo(conn, 2, "200")
        _insert_summary(conn, 1, "deep", "Recent.", days_ago=5)
        _insert_summary(conn, 2, "quick", "Old.", days_ago=30)
        result = get_recent_summaries(since_days=14)
        assert len(result) == 1
        assert result[0].content == "Recent."

    def test_ordered_newest_first(self):
        conn = db.get_connection()
        _insert_repo(conn, 1, "100")
        _insert_summary(conn, 1, "deep", "Older.", days_ago=10)
        _insert_summary(conn, 1, "quick", "Newer.", days_ago=2)
        result = get_recent_summaries(since_days=14)
        assert len(result) == 2
        assert result[0].content == "Newer."
        assert result[1].content == "Older."

    def test_default_since_days_is_14(self):
        conn = db.get_connection()
        _insert_repo(conn, 1, "100")
        _insert_summary(conn, 1, "deep", "Within default.", days_ago=13)
        _insert_summary(conn, 1, "quick", "Outside default.", days_ago=15)
        result = get_recent_summaries()
        assert len(result) == 1
        assert result[0].content == "Within default."

    def test_multiple_repos_all_returned(self):
        conn = db.get_connection()
        _insert_repo(conn, 1, "100")
        _insert_repo(conn, 2, "200")
        _insert_repo(conn, 3, "300")
        _insert_summary(conn, 1, "deep", "Repo 1 deep.", days_ago=1)
        _insert_summary(conn, 2, "quick", "Repo 2 quick.", days_ago=5)
        _insert_summary(conn, 3, "deep", "Repo 3 deep.", days_ago=10)
        result = get_recent_summaries(since_days=14)
        assert len(result) == 3
