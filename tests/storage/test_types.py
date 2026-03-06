"""Tests for storage types."""

import json
from datetime import date, datetime

from storage.types import FeatureRecord, RepoRecord, StorageError, SummaryRecord


class TestStorageError:
    """StorageError is a proper Exception subclass."""

    def test_is_exception(self):
        err = StorageError("db failed")
        assert isinstance(err, Exception)

    def test_has_message(self):
        err = StorageError("connection lost")
        assert err.message == "connection lost"

    def test_str_representation(self):
        err = StorageError("timeout")
        assert str(err) == "timeout"


class TestRepoRecord:
    """RepoRecord has all fields per ARCH_storage.md."""

    def _make_record(self, **overrides):
        defaults = dict(
            id=1,
            source="github",
            source_id="12345",
            name="owner/repo",
            url="https://github.com/owner/repo",
            description="A test repo",
            raw_content="# README\nHello world",
            source_metadata={"stars": 100, "forks": 10},
            discovered_at=datetime(2026, 3, 5, 12, 0, 0),
            first_featured_at=None,
            last_featured_at=None,
            feature_count=0,
        )
        defaults.update(overrides)
        return RepoRecord(**defaults)

    def test_all_fields_present(self):
        record = self._make_record()
        assert record.id == 1
        assert record.source == "github"
        assert record.source_id == "12345"
        assert record.name == "owner/repo"
        assert record.url == "https://github.com/owner/repo"
        assert record.description == "A test repo"
        assert record.raw_content == "# README\nHello world"
        assert record.source_metadata == {"stars": 100, "forks": 10}
        assert record.discovered_at == datetime(2026, 3, 5, 12, 0, 0)
        assert record.first_featured_at is None
        assert record.last_featured_at is None
        assert record.feature_count == 0

    def test_description_accepts_none(self):
        record = self._make_record(description=None)
        assert record.description is None

    def test_first_featured_at_accepts_datetime(self):
        dt = datetime(2026, 3, 6, 8, 0, 0)
        record = self._make_record(first_featured_at=dt)
        assert record.first_featured_at == dt

    def test_last_featured_at_accepts_datetime(self):
        dt = datetime(2026, 3, 6, 8, 0, 0)
        record = self._make_record(last_featured_at=dt)
        assert record.last_featured_at == dt

    def test_feature_count_defaults_to_zero(self):
        record = self._make_record()
        assert record.feature_count == 0

    def test_source_metadata_json_roundtrip(self):
        metadata = {
            "stars": 500,
            "forks": 42,
            "subscribers": 15,
            "primary_language": "Python",
            "topics": ["ai", "coding"],
            "created_at": "2025-01-01T00:00:00Z",
        }
        record = self._make_record(source_metadata=metadata)
        serialized = json.dumps(record.source_metadata)
        deserialized = json.loads(serialized)
        assert deserialized == metadata

    def test_source_metadata_nested_roundtrip(self):
        metadata = {"nested": {"key": [1, 2, 3]}, "flag": True, "count": None}
        serialized = json.dumps(metadata)
        deserialized = json.loads(serialized)
        assert deserialized == metadata


class TestSummaryRecord:
    """SummaryRecord has all fields per ARCH_storage.md."""

    def test_all_fields_present(self):
        record = SummaryRecord(
            id=1,
            repo_id=10,
            summary_type="deep",
            content="This is a deep dive summary...",
            model_used="claude-sonnet-4-5",
            generated_at=datetime(2026, 3, 5, 14, 0, 0),
        )
        assert record.id == 1
        assert record.repo_id == 10
        assert record.summary_type == "deep"
        assert record.content == "This is a deep dive summary..."
        assert record.model_used == "claude-sonnet-4-5"
        assert record.generated_at == datetime(2026, 3, 5, 14, 0, 0)

    def test_quick_summary_type(self):
        record = SummaryRecord(
            id=2,
            repo_id=10,
            summary_type="quick",
            content="Short summary.",
            model_used="claude-haiku",
            generated_at=datetime(2026, 3, 5, 14, 0, 0),
        )
        assert record.summary_type == "quick"


class TestFeatureRecord:
    """FeatureRecord has all fields per ARCH_storage.md."""

    def test_all_fields_present(self):
        record = FeatureRecord(
            id=1,
            repo_id=10,
            feature_type="deep",
            featured_date=date(2026, 3, 5),
            ranking_criteria="stars",
        )
        assert record.id == 1
        assert record.repo_id == 10
        assert record.feature_type == "deep"
        assert record.featured_date == date(2026, 3, 5)
        assert record.ranking_criteria == "stars"

    def test_quick_feature_type(self):
        record = FeatureRecord(
            id=2,
            repo_id=10,
            feature_type="quick",
            featured_date=date(2026, 3, 5),
            ranking_criteria="forks",
        )
        assert record.feature_type == "quick"
