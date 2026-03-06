"""Integration test — pipeline end-to-end.

Mocks only the HTTP layer (search_repos, fetch_readme, fetch_seed_repos),
the LLM layer (generate_deep_dive, generate_quick_hit), and the Telegram
layer (send_digest). Real Discovery processing, real SQLite Storage,
real Orchestrator wiring.
"""

from unittest.mock import patch

import pytest

import storage
from delivery.types import DeliveryResult, Digest
from discovery.types import CategoryConfig, RankingCriteria
from orchestrator import PipelineConfig, run_daily_pipeline
from summarization.types import SummaryResult

_MOCK_ENV = {
    "ANTHROPIC_API_KEY": "sk-test-key",
    "TELEGRAM_BOT_TOKEN": "bot123:test-token",
}

_DEEP_RESULT = SummaryResult(
    content="Deep dive analysis.", model_used="test-deep",
    token_usage={"input_tokens": 100, "output_tokens": 50},
)
_QUICK_RESULT = SummaryResult(
    content="Quick hit.", model_used="test-quick",
    token_usage={"input_tokens": 50, "output_tokens": 20},
)
_MOCK_DELIVERY = DeliveryResult(success=True, message_id="99")


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


@patch("orchestrator.pipeline.send_digest", return_value=_MOCK_DELIVERY)
@patch("orchestrator.pipeline.generate_quick_hit", return_value=_QUICK_RESULT)
@patch("orchestrator.pipeline.generate_deep_dive", return_value=_DEEP_RESULT)
@patch("discovery.discover.fetch_seed_repos")
@patch("discovery.discover.fetch_readme")
@patch("discovery.discover.search_repos")
class TestPipelineIntegration:

    def test_end_to_end(self, mock_search, mock_readme, mock_seeds, mock_deep, mock_quick, mock_send):
        """Full pipeline: discover → persist → dedup → summarize → deliver."""
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

        with patch.dict("os.environ", _MOCK_ENV):
            result = run_daily_pipeline(config)

        assert result.success is True
        assert result.repos_discovered == 3
        assert result.repos_after_dedup == 3
        assert result.summaries_generated == 3  # 1 deep + 2 quick (3 repos total)
        assert result.delivery_result.success is True
        assert result.errors == []

    def test_repos_persisted_correctly(self, mock_search, mock_readme, mock_seeds, mock_deep, mock_quick, mock_send):
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

        with patch.dict("os.environ", _MOCK_ENV):
            run_daily_pipeline(config)

        record = storage.get_repo(1)
        assert record is not None
        assert record.name == "org/persisted-repo"
        assert record.source_id == "42"
        assert record.source_metadata["stars"] == 999

    def test_summaries_persisted(self, mock_search, mock_readme, mock_seeds, mock_deep, mock_quick, mock_send):
        """Verify summaries are saved to Storage after pipeline run."""
        mock_search.return_value = [
            _make_repo_dict(1, "org/alpha", stars=500),
            _make_repo_dict(2, "org/beta", stars=300),
        ]
        mock_readme.side_effect = lambda o, r, **kw: "# README\n" + "x" * 500
        mock_seeds.return_value = []

        config = PipelineConfig(
            category=CategoryConfig(
                name="test", description="test",
                topics=["ai-coding"], min_stars=50, min_readme_length=200,
            ),
            channel_id="@test",
            ranking_criteria=RankingCriteria.STARS,
        )

        with patch.dict("os.environ", _MOCK_ENV):
            run_daily_pipeline(config)

        deep_summary = storage.get_summary(1)
        assert deep_summary is not None
        assert deep_summary.summary_type == "deep"
        assert deep_summary.content == "Deep dive analysis."

    def test_digest_structure(self, mock_search, mock_readme, mock_seeds, mock_deep, mock_quick, mock_send):
        """Verify the Digest passed to delivery has correct structure."""
        mock_search.return_value = [
            _make_repo_dict(1, "org/alpha", stars=500),
            _make_repo_dict(2, "org/beta", stars=300),
            _make_repo_dict(3, "org/gamma", stars=100),
        ]
        mock_readme.side_effect = lambda o, r, **kw: "# README\n" + "x" * 500
        mock_seeds.return_value = []

        config = PipelineConfig(
            category=CategoryConfig(
                name="test", description="test",
                topics=["ai-coding"], min_stars=50, min_readme_length=200,
            ),
            channel_id="@test-channel",
            ranking_criteria=RankingCriteria.STARS,
        )

        with patch.dict("os.environ", _MOCK_ENV):
            run_daily_pipeline(config)

        digest = mock_send.call_args[0][0]
        assert isinstance(digest, Digest)
        assert digest.deep_dive.repo_name == "org/alpha"
        assert digest.deep_dive.stars == 500
        assert len(digest.quick_hits) == 2

    def test_filtering_applied(self, mock_search, mock_readme, mock_seeds, mock_deep, mock_quick, mock_send):
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

        with patch.dict("os.environ", _MOCK_ENV):
            result = run_daily_pipeline(config)

        assert result.repos_discovered == 1

    def test_discovery_failure_captured(self, mock_search, mock_readme, mock_seeds, mock_deep, mock_quick, mock_send):
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
