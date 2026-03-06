"""Tests for Delivery module types."""

from datetime import date

import pytest

from delivery.types import (
    DeliveryResult,
    Digest,
    MessageTooLongError,
    SummaryWithRepo,
    TelegramAPIError,
)


class TestSummaryWithRepo:
    def test_construction(self):
        s = SummaryWithRepo(
            summary_content="A tool for building agents.",
            repo_name="langchain",
            repo_url="https://github.com/langchain-ai/langchain",
            stars=12345,
            created_at="2022-10-25",
        )
        assert s.summary_content == "A tool for building agents."
        assert s.repo_name == "langchain"
        assert s.repo_url == "https://github.com/langchain-ai/langchain"
        assert s.stars == 12345
        assert s.created_at == "2022-10-25"

    def test_has_expected_fields(self):
        s = SummaryWithRepo("content", "name", "url", 0, "2024-01-01")
        fields = {f.name for f in s.__dataclass_fields__.values()}
        assert fields == {
            "summary_content",
            "repo_name",
            "repo_url",
            "stars",
            "created_at",
        }

    def test_zero_stars(self):
        s = SummaryWithRepo("content", "name", "url", 0, "2024-01-01")
        assert s.stars == 0

    def test_large_star_count(self):
        s = SummaryWithRepo("content", "name", "url", 500000, "2024-01-01")
        assert s.stars == 500000


class TestDigest:
    def _make_summary(self, name="repo"):
        return SummaryWithRepo(
            summary_content="Summary text.",
            repo_name=name,
            repo_url=f"https://github.com/org/{name}",
            stars=100,
            created_at="2024-01-01",
        )

    def test_construction(self):
        deep = self._make_summary("deep-repo")
        quicks = [self._make_summary(f"quick-{i}") for i in range(3)]
        d = Digest(
            deep_dive=deep,
            quick_hits=quicks,
            ranking_criteria="stars",
            date=date(2026, 3, 6),
        )
        assert d.deep_dive is deep
        assert len(d.quick_hits) == 3
        assert d.ranking_criteria == "stars"
        assert d.date == date(2026, 3, 6)

    def test_has_expected_fields(self):
        deep = self._make_summary()
        d = Digest(deep, [], "stars", date(2026, 1, 1))
        fields = {f.name for f in d.__dataclass_fields__.values()}
        assert fields == {"deep_dive", "quick_hits", "ranking_criteria", "date"}

    def test_empty_quick_hits(self):
        d = Digest(self._make_summary(), [], "stars", date(2026, 1, 1))
        assert d.quick_hits == []

    def test_single_quick_hit(self):
        d = Digest(
            self._make_summary(),
            [self._make_summary("solo")],
            "activity",
            date(2026, 1, 1),
        )
        assert len(d.quick_hits) == 1


class TestDeliveryResult:
    def test_success(self):
        r = DeliveryResult(success=True, message_id="12345", error=None)
        assert r.success is True
        assert r.message_id == "12345"
        assert r.error is None

    def test_failure(self):
        r = DeliveryResult(success=False, message_id=None, error="API timeout")
        assert r.success is False
        assert r.message_id is None
        assert r.error == "API timeout"

    def test_defaults(self):
        r = DeliveryResult(success=True)
        assert r.message_id is None
        assert r.error is None

    def test_has_expected_fields(self):
        r = DeliveryResult(success=True)
        fields = {f.name for f in r.__dataclass_fields__.values()}
        assert fields == {"success", "message_id", "error"}


class TestTelegramAPIError:
    def test_with_all_fields(self):
        err = TelegramAPIError("Unauthorized", status_code=401)
        assert str(err) == "Unauthorized"
        assert err.message == "Unauthorized"
        assert err.status_code == 401

    def test_defaults(self):
        err = TelegramAPIError("Network error")
        assert str(err) == "Network error"
        assert err.message == "Network error"
        assert err.status_code is None

    def test_is_exception(self):
        assert issubclass(TelegramAPIError, Exception)

    def test_catchable(self):
        with pytest.raises(TelegramAPIError) as exc_info:
            raise TelegramAPIError("fail", status_code=500)
        assert exc_info.value.status_code == 500


class TestMessageTooLongError:
    def test_construction(self):
        err = MessageTooLongError(length=5000, max_length=4096)
        assert err.length == 5000
        assert err.max_length == 4096
        assert "5000" in str(err)
        assert "4096" in str(err)

    def test_default_max_length(self):
        err = MessageTooLongError(length=5000)
        assert err.max_length == 4096

    def test_is_exception(self):
        assert issubclass(MessageTooLongError, Exception)

    def test_catchable(self):
        with pytest.raises(MessageTooLongError) as exc_info:
            raise MessageTooLongError(length=8000)
        assert exc_info.value.length == 8000
        assert exc_info.value.max_length == 4096
