"""Tests for save_repo and get_repo."""

import pytest

from discovery.types import DiscoveredRepo
from storage import db
from storage.repos import save_repo, get_repo


SQLITE_CONFIG = {"engine": "sqlite", "database": ":memory:"}


def _make_discovered_repo(**overrides):
    """Create a DiscoveredRepo with sensible defaults."""
    defaults = dict(
        source="github",
        source_id="12345",
        name="owner/repo",
        url="https://github.com/owner/repo",
        description="A test repository",
        raw_content="# README\nThis is a test repo.",
        source_metadata={
            "stars": 100,
            "forks": 10,
            "subscribers": 5,
            "primary_language": "Python",
            "created_at": "2025-01-01T00:00:00Z",
            "updated_at": "2025-03-01T00:00:00Z",
            "pushed_at": "2025-03-01T00:00:00Z",
            "topics": ["ai", "coding"],
        },
    )
    defaults.update(overrides)
    return DiscoveredRepo(**defaults)


@pytest.fixture(autouse=True)
def setup_db():
    """Initialize and tear down a fresh in-memory DB for each test."""
    db.close()
    db.init(SQLITE_CONFIG)
    yield
    db.close()


class TestSaveRepo:
    """save_repo persists DiscoveredRepo with upsert behavior."""

    def test_insert_new_repo(self):
        repo = _make_discovered_repo()
        record = save_repo(repo)
        assert record.id > 0
        assert record.source == "github"
        assert record.source_id == "12345"
        assert record.name == "owner/repo"
        assert record.url == "https://github.com/owner/repo"
        assert record.description == "A test repository"
        assert record.discovered_at is not None

    def test_upsert_same_repo_returns_same_id(self):
        repo = _make_discovered_repo()
        record1 = save_repo(repo)
        record2 = save_repo(repo)
        assert record1.id == record2.id

    def test_upsert_preserves_discovered_at(self):
        repo = _make_discovered_repo()
        record1 = save_repo(repo)
        original_discovered_at = record1.discovered_at
        record2 = save_repo(repo)
        assert record2.discovered_at == original_discovered_at

    def test_upsert_updates_metadata(self):
        repo1 = _make_discovered_repo(
            source_metadata={"stars": 100, "forks": 10}
        )
        save_repo(repo1)
        repo2 = _make_discovered_repo(
            source_metadata={"stars": 200, "forks": 20}
        )
        record = save_repo(repo2)
        assert record.source_metadata["stars"] == 200
        assert record.source_metadata["forks"] == 20

    def test_new_repo_has_default_feature_fields(self):
        repo = _make_discovered_repo()
        record = save_repo(repo)
        assert record.feature_count == 0
        assert record.first_featured_at is None
        assert record.last_featured_at is None

    def test_description_none(self):
        repo = _make_discovered_repo(description=None)
        record = save_repo(repo)
        assert record.description is None

    def test_source_metadata_roundtrip(self):
        metadata = {
            "stars": 500,
            "forks": 42,
            "subscribers": 15,
            "primary_language": "Python",
            "topics": ["ai", "coding"],
            "created_at": "2025-01-01T00:00:00Z",
        }
        repo = _make_discovered_repo(source_metadata=metadata)
        record = save_repo(repo)
        assert record.source_metadata == metadata

    def test_large_raw_content(self):
        large_content = "x" * 49_000
        repo = _make_discovered_repo(raw_content=large_content)
        record = save_repo(repo)
        assert record.raw_content == large_content


class TestGetRepo:
    """get_repo retrieves by internal ID."""

    def test_valid_id(self):
        repo = _make_discovered_repo()
        saved = save_repo(repo)
        fetched = get_repo(saved.id)
        assert fetched is not None
        assert fetched.id == saved.id
        assert fetched.name == "owner/repo"
        assert fetched.source_metadata == repo.source_metadata

    def test_nonexistent_id(self):
        result = get_repo(9999)
        assert result is None
