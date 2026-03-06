"""Tests for record_feature."""

from datetime import date

import pytest

from discovery.types import DiscoveredRepo
from storage import db
from storage.features import record_feature
from storage.repos import save_repo, get_repo


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
    return save_repo(_make_discovered_repo())


class TestRecordFeature:
    """record_feature inserts history and updates repo."""

    def test_returns_feature_record_with_today(self, repo_record):
        feature = record_feature(repo_record.id, "deep", "stars")
        assert feature.id > 0
        assert feature.repo_id == repo_record.id
        assert feature.feature_type == "deep"
        assert feature.featured_date == date.today()
        assert feature.ranking_criteria == "stars"

    def test_updates_last_featured_at(self, repo_record):
        record_feature(repo_record.id, "deep", "stars")
        updated = get_repo(repo_record.id)
        assert updated.last_featured_at is not None

    def test_increments_feature_count(self, repo_record):
        assert repo_record.feature_count == 0
        record_feature(repo_record.id, "deep", "stars")
        updated = get_repo(repo_record.id)
        assert updated.feature_count == 1
        record_feature(repo_record.id, "quick", "forks")
        updated = get_repo(repo_record.id)
        assert updated.feature_count == 2

    def test_first_feature_sets_first_featured_at(self, repo_record):
        assert repo_record.first_featured_at is None
        record_feature(repo_record.id, "deep", "stars")
        updated = get_repo(repo_record.id)
        assert updated.first_featured_at is not None
        first_time = updated.first_featured_at
        record_feature(repo_record.id, "quick", "forks")
        updated = get_repo(repo_record.id)
        assert updated.first_featured_at == first_time

    def test_invalid_feature_type_raises(self, repo_record):
        with pytest.raises(ValueError, match="Invalid feature_type"):
            record_feature(repo_record.id, "medium", "stars")

    def test_nonexistent_repo_raises(self):
        with pytest.raises(ValueError, match="does not exist"):
            record_feature(9999, "deep", "stars")
