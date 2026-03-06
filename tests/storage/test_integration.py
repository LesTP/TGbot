"""Integration tests for the storage module public API.

Exercises the full lifecycle through the public API (no internal imports).
"""

from datetime import date, timedelta
from unittest.mock import patch

import pytest

import storage
from discovery.types import DiscoveredRepo


SQLITE_CONFIG = {"engine": "sqlite", "database": ":memory:"}


def _make_discovered_repo(**overrides):
    defaults = dict(
        source="github",
        source_id="12345",
        name="owner/repo-a",
        url="https://github.com/owner/repo-a",
        description="Repository A",
        raw_content="# Repo A\nA test repository.",
        source_metadata={
            "stars": 100,
            "forks": 10,
            "subscribers": 5,
            "primary_language": "Python",
            "topics": ["ai"],
        },
    )
    defaults.update(overrides)
    return DiscoveredRepo(**defaults)


@pytest.fixture(autouse=True)
def setup_db():
    storage.close()
    storage.init(SQLITE_CONFIG)
    yield
    storage.close()


class TestFullLifecycle:
    """End-to-end: discover → persist → summarize → feature → verify."""

    def test_complete_lifecycle(self):
        # 1. Save a discovered repo
        repo = _make_discovered_repo()
        record = storage.save_repo(repo)
        assert record.id > 0
        assert record.feature_count == 0

        # 2. Save a summary for it
        summary = storage.save_summary(
            record.id, "deep", "Deep dive analysis...", "claude-sonnet-4-5"
        )
        assert summary.id > 0
        assert summary.repo_id == record.id

        # 3. Record it as featured
        feature = storage.record_feature(record.id, "deep", "stars")
        assert feature.featured_date == date.today()

        # 4. Verify it appears in featured set
        featured = storage.get_featured_repo_ids()
        assert record.id in featured

        # 5. Verify repo tracking updated
        updated = storage.get_repo(record.id)
        assert updated.feature_count == 1
        assert updated.first_featured_at is not None
        assert updated.last_featured_at is not None

        # 6. Verify summary retrievable
        fetched_summary = storage.get_summary(summary.id)
        assert fetched_summary.content == "Deep dive analysis..."

    def test_two_repos_feature_one(self):
        repo_a = _make_discovered_repo(source_id="aaa", name="owner/repo-a")
        repo_b = _make_discovered_repo(source_id="bbb", name="owner/repo-b")

        record_a = storage.save_repo(repo_a)
        record_b = storage.save_repo(repo_b)

        storage.record_feature(record_a.id, "deep", "stars")

        featured = storage.get_featured_repo_ids()
        assert record_a.id in featured
        assert record_b.id not in featured

    def test_upsert_preserves_feature_tracking(self):
        # Save and feature a repo
        repo = _make_discovered_repo(source_metadata={"stars": 100})
        record = storage.save_repo(repo)
        storage.record_feature(record.id, "deep", "stars")

        # Re-discover with updated metadata
        updated_repo = _make_discovered_repo(source_metadata={"stars": 200})
        re_saved = storage.save_repo(updated_repo)

        # Same ID, metadata updated, feature tracking preserved
        assert re_saved.id == record.id
        assert re_saved.source_metadata["stars"] == 200
        assert re_saved.feature_count == 1
        assert re_saved.first_featured_at is not None

    def test_cooldown_boundary(self):
        repo = _make_discovered_repo()
        record = storage.save_repo(repo)

        # Feature the repo "91 days ago" by patching date.today in both modules
        past_date = date.today() - timedelta(days=91)
        with patch("storage.features.date") as mock_date_features, \
             patch("storage.features.datetime") as mock_dt_features:
            mock_date_features.today.return_value = past_date
            mock_date_features.side_effect = lambda *a, **kw: date(*a, **kw)
            mock_dt_features.now.return_value = past_date
            mock_dt_features.side_effect = lambda *a, **kw: date(*a, **kw)
            storage.record_feature(record.id, "deep", "stars")

        # With default 90-day window, repo should NOT be in featured set
        featured = storage.get_featured_repo_ids(since_days=90)
        assert record.id not in featured

    def test_get_summary_from_lifecycle(self):
        repo = _make_discovered_repo()
        record = storage.save_repo(repo)
        s1 = storage.save_summary(record.id, "deep", "Deep content", "model-a")
        s2 = storage.save_summary(record.id, "quick", "Quick content", "model-b")

        assert storage.get_summary(s1.id).summary_type == "deep"
        assert storage.get_summary(s2.id).summary_type == "quick"
        assert storage.get_summary(s1.id).content == "Deep content"
        assert storage.get_summary(s2.id).content == "Quick content"
