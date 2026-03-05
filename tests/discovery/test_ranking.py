"""Tests for ranking/sorting."""

from discovery.ranking import sort_repos
from discovery.types import RankingCriteria


def _make_repo(
    name: str = "owner/repo",
    stars: int = 100,
    forks: int = 10,
    subscribers: int = 5,
    updated_at: str = "2025-06-01T00:00:00Z",
    pushed_at: str = "2025-06-01T00:00:00Z",
) -> dict:
    return {
        "full_name": name,
        "stargazers_count": stars,
        "forks_count": forks,
        "subscribers_count": subscribers,
        "updated_at": updated_at,
        "pushed_at": pushed_at,
    }


class TestSortByStars:
    def test_descending_order(self):
        repos = [
            _make_repo(name="low", stars=10),
            _make_repo(name="high", stars=500),
            _make_repo(name="mid", stars=100),
        ]
        result = sort_repos(repos, RankingCriteria.STARS)
        assert [r["full_name"] for r in result] == ["high", "mid", "low"]


class TestSortByForks:
    def test_descending_order(self):
        repos = [
            _make_repo(name="low", forks=2),
            _make_repo(name="high", forks=200),
            _make_repo(name="mid", forks=50),
        ]
        result = sort_repos(repos, RankingCriteria.FORKS)
        assert [r["full_name"] for r in result] == ["high", "mid", "low"]


class TestSortBySubscribers:
    def test_descending_order(self):
        repos = [
            _make_repo(name="low", subscribers=1),
            _make_repo(name="high", subscribers=100),
            _make_repo(name="mid", subscribers=20),
        ]
        result = sort_repos(repos, RankingCriteria.SUBSCRIBERS)
        assert [r["full_name"] for r in result] == ["high", "mid", "low"]


class TestSortByRecency:
    def test_descending_order(self):
        repos = [
            _make_repo(name="old", updated_at="2024-01-01T00:00:00Z"),
            _make_repo(name="new", updated_at="2026-03-01T00:00:00Z"),
            _make_repo(name="mid", updated_at="2025-06-15T00:00:00Z"),
        ]
        result = sort_repos(repos, RankingCriteria.RECENCY)
        assert [r["full_name"] for r in result] == ["new", "mid", "old"]


class TestSortByActivity:
    def test_descending_order(self):
        repos = [
            _make_repo(name="stale", pushed_at="2023-01-01T00:00:00Z"),
            _make_repo(name="active", pushed_at="2026-03-05T00:00:00Z"),
            _make_repo(name="moderate", pushed_at="2025-09-01T00:00:00Z"),
        ]
        result = sort_repos(repos, RankingCriteria.ACTIVITY)
        assert [r["full_name"] for r in result] == ["active", "moderate", "stale"]


class TestStableSort:
    def test_ties_preserve_original_order(self):
        repos = [
            _make_repo(name="first", stars=100),
            _make_repo(name="second", stars=100),
            _make_repo(name="third", stars=100),
        ]
        result = sort_repos(repos, RankingCriteria.STARS)
        assert [r["full_name"] for r in result] == ["first", "second", "third"]


class TestEdgeCases:
    def test_empty_list(self):
        assert sort_repos([], RankingCriteria.STARS) == []

    def test_single_item(self):
        repos = [_make_repo(name="only")]
        result = sort_repos(repos, RankingCriteria.STARS)
        assert len(result) == 1
        assert result[0]["full_name"] == "only"

    def test_missing_key_uses_default(self):
        repos = [
            {"full_name": "no-stars"},
            _make_repo(name="has-stars", stars=50),
        ]
        result = sort_repos(repos, RankingCriteria.STARS)
        assert [r["full_name"] for r in result] == ["has-stars", "no-stars"]

    def test_returns_new_list(self):
        repos = [_make_repo(name="a"), _make_repo(name="b")]
        result = sort_repos(repos, RankingCriteria.STARS)
        assert result is not repos
