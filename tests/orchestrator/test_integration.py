"""Integration test — thin pipeline end-to-end.

Mocks only the HTTP layer (search_repos, fetch_readme, fetch_seed_repos).
Real Discovery processing, real SQLite Storage, real Orchestrator wiring.
"""

from unittest.mock import patch

import pytest

import storage
from discovery.types import CategoryConfig, RankingCriteria
from orchestrator import PipelineConfig, run_daily_pipeline


def _make_repo_dict(repo_id: int, full_name: str, stars: int = 200) -> dict:
    """Raw GitHub API repo dict (pre-README-fetch)."""
    return {
        "id": repo_id,
        "full_name": full_name,
        "html_url": f"https://github.com/{full_name}",
        "description": f"Description of {full_name}",
        "stargazers_count": stars,
        "forks_count": 10,
        "subscribers_count": 5,
        "language": "Python",
        "fork": False,
        "archived": False,
        "created_at": "2025-01-01T00:00:00Z",
        "updated_at": "2025-06-01T00:00:00Z",
        "pushed_at": "2025-06-01T00:00:00Z",
        "topics": ["ai-coding"],
    }


@pytest.fixture(autouse=True)
def _init_storage():
    """Init SQLite in-memory storage, close after each test."""
    storage.init({"engine": "sqlite", "database": ":memory:"})
    yield
    storage.close()


@patch("discovery.discover.fetch_seed_repos")
@patch("discovery.discover.fetch_readme")
@patch("discovery.discover.search_repos")
class TestThinPipelineIntegration:

    def test_end_to_end(self, mock_search, mock_readme, mock_seeds):
        """Mock API → Discovery processing → Storage persistence → PipelineResult."""
        mock_search.return_value = [
            _make_repo_dict(1, "org/alpha", stars=500),
            _make_repo_dict(2, "org/beta", stars=300),
            _make_repo_dict(3, "org/gamma", stars=100),
        ]
        mock_readme.side_effect = lambda o, r, **kw: "# README\n" + "x" * 500
        mock_seeds.return_value = []

        config = PipelineConfig(
            category=CategoryConfig(
                name="test-category",
                description="Integration test category",
                topics=["ai-coding"],
                min_stars=50,
                min_readme_length=200,
            ),
            channel_id="@test-channel",
            ranking_criteria=RankingCriteria.STARS,
        )

        result = run_daily_pipeline(config)

        assert result.success is True
        assert result.repos_discovered == 3
        assert result.repos_after_dedup == 0
        assert result.summaries_generated == 0
        assert result.delivery_result is None
        assert result.errors == []

    def test_repos_persisted_correctly(self, mock_search, mock_readme, mock_seeds):
        """Verify repos are actually in the database after pipeline run."""
        mock_search.return_value = [
            _make_repo_dict(42, "org/persisted-repo", stars=999),
        ]
        mock_readme.side_effect = lambda o, r, **kw: "# Great README\n" + "x" * 500
        mock_seeds.return_value = []

        config = PipelineConfig(
            category=CategoryConfig(
                name="test", description="test",
                topics=["ai-coding"], min_stars=50, min_readme_length=200,
            ),
            channel_id="@test",
            ranking_criteria=RankingCriteria.STARS,
        )

        run_daily_pipeline(config)

        record = storage.get_repo(1)
        assert record is not None
        assert record.name == "org/persisted-repo"
        assert record.source == "github"
        assert record.source_id == "42"
        assert record.source_metadata["stars"] == 999

    def test_filtering_applied(self, mock_search, mock_readme, mock_seeds):
        """Low-star repos filtered by Discovery before reaching Storage."""
        mock_search.return_value = [
            _make_repo_dict(1, "org/good", stars=200),
            _make_repo_dict(2, "org/bad", stars=10),
        ]
        mock_readme.side_effect = lambda o, r, **kw: "x" * 500
        mock_seeds.return_value = []

        config = PipelineConfig(
            category=CategoryConfig(
                name="test", description="test",
                topics=["ai-coding"], min_stars=50, min_readme_length=200,
            ),
            channel_id="@test",
            ranking_criteria=RankingCriteria.STARS,
        )

        result = run_daily_pipeline(config)

        assert result.repos_discovered == 1

    def test_discovery_failure_captured(self, mock_search, mock_readme, mock_seeds):
        """API failure → success=False, error captured, no crash."""
        mock_search.return_value = []
        mock_seeds.return_value = []

        config = PipelineConfig(
            category=CategoryConfig(
                name="test", description="test",
                topics=["ai-coding"], min_stars=50,
            ),
            channel_id="@test",
            ranking_criteria=RankingCriteria.STARS,
        )

        result = run_daily_pipeline(config)

        assert result.success is False
        assert result.repos_discovered == 0
        assert len(result.errors) == 1
