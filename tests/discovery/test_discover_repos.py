"""Tests for discover_repos() integration."""

from unittest.mock import MagicMock, patch

import pytest

from discovery.discover import discover_repos, _dedup_by_id, _to_discovered_repo
from discovery.types import (
    CategoryConfig,
    DiscoveredRepo,
    GitHubAPIError,
    NoResultsError,
    RankingCriteria,
    SeedRepo,
)


def _make_repo_dict(
    repo_id: int = 1,
    full_name: str = "owner/repo",
    stars: int = 200,
    forks: int = 20,
    subscribers: int = 10,
    language: str = "Python",
    fork: bool = False,
    archived: bool = False,
    readme: str = "x" * 500,
    updated_at: str = "2025-06-01T00:00:00Z",
    pushed_at: str = "2025-06-01T00:00:00Z",
) -> dict:
    """Create a raw GitHub API repo dict with readme_content."""
    return {
        "id": repo_id,
        "full_name": full_name,
        "html_url": f"https://github.com/{full_name}",
        "description": f"Description of {full_name}",
        "stargazers_count": stars,
        "forks_count": forks,
        "subscribers_count": subscribers,
        "language": language,
        "fork": fork,
        "archived": archived,
        "created_at": "2024-01-01T00:00:00Z",
        "updated_at": updated_at,
        "pushed_at": pushed_at,
        "topics": ["ai-coding"],
        "readme_content": readme,
    }


def _simple_config(**overrides) -> CategoryConfig:
    defaults = dict(
        name="test",
        description="test category",
        topics=["ai-coding"],
        keywords=[],
        expansion_topics=[],
        seed_repos=[],
        min_stars=50,
        min_readme_length=200,
    )
    defaults.update(overrides)
    return CategoryConfig(**defaults)


# --- Unit tests for helpers ---


class TestDedupById:
    def test_removes_duplicates(self):
        repos = [
            {"id": 1, "full_name": "a"},
            {"id": 2, "full_name": "b"},
            {"id": 1, "full_name": "a-dup"},
        ]
        result = _dedup_by_id(repos)
        assert len(result) == 2
        assert result[0]["full_name"] == "a"
        assert result[1]["full_name"] == "b"

    def test_preserves_order(self):
        repos = [{"id": 3, "full_name": "c"}, {"id": 1, "full_name": "a"}, {"id": 2, "full_name": "b"}]
        result = _dedup_by_id(repos)
        assert [r["full_name"] for r in result] == ["c", "a", "b"]

    def test_empty(self):
        assert _dedup_by_id([]) == []


class TestToDiscoveredRepo:
    def test_conversion(self):
        raw = _make_repo_dict(repo_id=42, full_name="org/tool", stars=300)
        result = _to_discovered_repo(raw)

        assert isinstance(result, DiscoveredRepo)
        assert result.source == "github"
        assert result.source_id == "42"
        assert result.name == "org/tool"
        assert result.url == "https://github.com/org/tool"
        assert result.description == "Description of org/tool"
        assert result.raw_content == raw["readme_content"]
        assert result.source_metadata["stars"] == 300
        assert result.source_metadata["pushed_at"] == "2025-06-01T00:00:00Z"
        assert result.source_metadata["topics"] == ["ai-coding"]


# --- Integration tests for discover_repos ---


@patch("discovery.discover.fetch_seed_repos")
@patch("discovery.discover.fetch_readme")
@patch("discovery.discover.search_repos")
class TestDiscoverReposHappyPath:
    def test_basic_flow(self, mock_search, mock_readme, mock_seeds):
        """Topic search → README fetch → filter → sort → convert."""
        mock_search.return_value = [
            _make_repo_dict(1, "owner/repo-a", stars=200),
            _make_repo_dict(2, "owner/repo-b", stars=500),
            _make_repo_dict(3, "owner/repo-c", stars=100),
        ]
        mock_readme.side_effect = lambda o, r, **kw: "x" * 500
        mock_seeds.return_value = []

        config = _simple_config()
        result = discover_repos(config, RankingCriteria.STARS, limit=10)

        assert len(result) == 3
        assert all(isinstance(r, DiscoveredRepo) for r in result)
        # Sorted by stars descending
        assert result[0].source_metadata["stars"] == 500
        assert result[1].source_metadata["stars"] == 200
        assert result[2].source_metadata["stars"] == 100

    def test_limit_respected(self, mock_search, mock_readme, mock_seeds):
        repos = [_make_repo_dict(i, f"owner/repo-{i}", stars=1000 - i) for i in range(30)]
        mock_search.return_value = repos
        mock_readme.side_effect = lambda o, r, **kw: "x" * 500
        mock_seeds.return_value = []

        result = discover_repos(_simple_config(), RankingCriteria.STARS, limit=10)
        assert len(result) == 10

    def test_limit_capped_at_100(self, mock_search, mock_readme, mock_seeds):
        repos = [_make_repo_dict(i, f"owner/repo-{i}") for i in range(5)]
        mock_search.return_value = repos
        mock_readme.side_effect = lambda o, r, **kw: "x" * 500
        mock_seeds.return_value = []

        result = discover_repos(_simple_config(), RankingCriteria.STARS, limit=999)
        assert len(result) == 5  # only 5 available, but limit was capped


@patch("discovery.discover.fetch_seed_repos")
@patch("discovery.discover.fetch_readme")
@patch("discovery.discover.search_repos")
class TestDiscoverReposDedup:
    def test_same_repo_from_two_queries(self, mock_search, mock_readme, mock_seeds):
        """Same repo ID appearing in two topic searches → appears once."""
        repo = _make_repo_dict(1, "owner/repo-a", stars=200)
        mock_search.return_value = [repo]  # same repo from each query
        mock_readme.side_effect = lambda o, r, **kw: "x" * 500
        mock_seeds.return_value = []

        config = _simple_config(topics=["topic-a", "topic-b"])
        result = discover_repos(config, RankingCriteria.STARS)

        assert len(result) == 1

    def test_seed_overlaps_with_search(self, mock_search, mock_readme, mock_seeds):
        """Seed repo that also appeared in search → appears once."""
        search_repo = _make_repo_dict(1, "owner/repo-a", stars=200)
        seed_repo = _make_repo_dict(1, "owner/repo-a", stars=200)
        seed_repo["readme_content"] = "x" * 500

        mock_search.return_value = [search_repo]
        mock_readme.side_effect = lambda o, r, **kw: "x" * 500
        mock_seeds.return_value = [seed_repo]

        config = _simple_config(
            seed_repos=[SeedRepo("owner/repo-a", "Repo A", "test")],
        )
        result = discover_repos(config, RankingCriteria.STARS)

        assert len(result) == 1


@patch("discovery.discover.fetch_seed_repos")
@patch("discovery.discover.fetch_readme")
@patch("discovery.discover.search_repos")
class TestDiscoverReposFiltering:
    def test_low_stars_filtered(self, mock_search, mock_readme, mock_seeds):
        mock_search.return_value = [
            _make_repo_dict(1, "owner/good", stars=200),
            _make_repo_dict(2, "owner/bad", stars=10),
        ]
        mock_readme.side_effect = lambda o, r, **kw: "x" * 500
        mock_seeds.return_value = []

        result = discover_repos(_simple_config(min_stars=50), RankingCriteria.STARS)
        assert len(result) == 1
        assert result[0].name == "owner/good"

    def test_no_readme_filtered(self, mock_search, mock_readme, mock_seeds):
        mock_search.return_value = [
            _make_repo_dict(1, "owner/has-readme", stars=200),
            _make_repo_dict(2, "owner/no-readme", stars=200),
        ]
        mock_readme.side_effect = lambda o, r, **kw: "x" * 500 if r == "has-readme" else None
        mock_seeds.return_value = []

        result = discover_repos(_simple_config(), RankingCriteria.STARS)
        assert len(result) == 1
        assert result[0].name == "owner/has-readme"

    def test_all_filtered_raises_no_results(self, mock_search, mock_readme, mock_seeds):
        mock_search.return_value = [
            _make_repo_dict(1, "owner/bad", stars=1),
        ]
        mock_readme.side_effect = lambda o, r, **kw: "x" * 500
        mock_seeds.return_value = []

        with pytest.raises(NoResultsError) as exc_info:
            discover_repos(_simple_config(min_stars=50), RankingCriteria.STARS)

        assert exc_info.value.query_details["category"] == "test"

    def test_expansion_higher_star_bar(self, mock_search, mock_readme, mock_seeds):
        """Expansion topic repos need min_stars + 50."""
        regular_repo = _make_repo_dict(1, "owner/regular", stars=60)
        expansion_repo = _make_repo_dict(2, "owner/expansion", stars=60)

        # First call: primary topic, second call: expansion topic
        mock_search.side_effect = [[regular_repo], [expansion_repo]]
        mock_readme.side_effect = lambda o, r, **kw: "x" * 500
        mock_seeds.return_value = []

        config = _simple_config(
            topics=["primary"],
            expansion_topics=["broad"],
            min_stars=50,
        )
        result = discover_repos(config, RankingCriteria.STARS)

        # regular (60 >= 50) passes, expansion (60 < 100) fails
        assert len(result) == 1
        assert result[0].name == "owner/regular"


@patch("discovery.discover.fetch_seed_repos")
@patch("discovery.discover.fetch_readme")
@patch("discovery.discover.search_repos")
class TestDiscoverReposSeeds:
    def test_seeds_included(self, mock_search, mock_readme, mock_seeds):
        mock_search.return_value = [_make_repo_dict(1, "owner/search", stars=200)]
        mock_readme.side_effect = lambda o, r, **kw: "x" * 500
        seed = _make_repo_dict(2, "owner/seed", stars=300)
        seed["readme_content"] = "x" * 500
        mock_seeds.return_value = [seed]

        config = _simple_config(
            seed_repos=[SeedRepo("owner/seed", "Seed", "test")],
        )
        result = discover_repos(config, RankingCriteria.STARS)

        assert len(result) == 2
        assert result[0].name == "owner/seed"  # higher stars

    def test_no_seeds_configured(self, mock_search, mock_readme, mock_seeds):
        mock_search.return_value = [_make_repo_dict(1, "owner/repo", stars=200)]
        mock_readme.side_effect = lambda o, r, **kw: "x" * 500

        result = discover_repos(_simple_config(), RankingCriteria.STARS)
        mock_seeds.assert_not_called()
        assert len(result) == 1


@patch("discovery.discover.fetch_seed_repos")
@patch("discovery.discover.fetch_readme")
@patch("discovery.discover.search_repos")
class TestDiscoverReposErrors:
    def test_search_api_error_propagates(self, mock_search, mock_readme, mock_seeds):
        mock_search.side_effect = GitHubAPIError("rate limited", status_code=403)

        with pytest.raises(GitHubAPIError):
            discover_repos(_simple_config(), RankingCriteria.STARS)

    def test_empty_search_no_seeds_raises(self, mock_search, mock_readme, mock_seeds):
        mock_search.return_value = []
        mock_seeds.return_value = []

        with pytest.raises(NoResultsError):
            discover_repos(_simple_config(), RankingCriteria.STARS)


@patch("discovery.discover.fetch_seed_repos")
@patch("discovery.discover.fetch_readme")
@patch("discovery.discover.search_repos")
class TestDiscoverReposKeywords:
    def test_keyword_queries_executed(self, mock_search, mock_readme, mock_seeds):
        mock_search.return_value = [_make_repo_dict(1, "owner/repo")]
        mock_readme.side_effect = lambda o, r, **kw: "x" * 500
        mock_seeds.return_value = []

        config = _simple_config(topics=[], keywords=["agentic coding"])
        result = discover_repos(config, RankingCriteria.STARS)

        call_args = mock_search.call_args_list[0]
        query = call_args[0][0]
        assert "agentic coding" in query
        assert len(result) == 1
