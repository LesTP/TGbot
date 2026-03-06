"""Tests for save_summary and get_summary."""

import pytest

from discovery.types import DiscoveredRepo
from storage import db
from storage.repos import save_repo
from storage.summaries import save_summary, get_summary


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
