"""Integration test — pipeline end-to-end.

Mocks only the HTTP layer (search_repos, fetch_readme, fetch_seed_repos),
the LLM layer (generate_deep_dive, generate_quick_hit), and the Telegram
layer (send_digest). Real Discovery processing, real SQLite Storage,
real Orchestrator wiring.
"""

from datetime import date, timedelta
from unittest.mock import patch

import pytest

import storage
from delivery.types import DeliveryResult, Digest
from discovery.types import CategoryConfig, RankingCriteria
from orchestrator import PipelineConfig, run_daily_pipeline
from storage.db import get_connection
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


def _make_config(**overrides) -> PipelineConfig:
    """Build a PipelineConfig with defaults suitable for integration tests."""
    defaults = dict(
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
    defaults.update(overrides)
    return PipelineConfig(**defaults)


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


@patch("orchestrator.pipeline.send_digest", return_value=_MOCK_DELIVERY)
@patch("orchestrator.pipeline.generate_quick_hit", return_value=_QUICK_RESULT)
@patch("orchestrator.pipeline.generate_deep_dive", return_value=_DEEP_RESULT)
@patch("discovery.discover.fetch_seed_repos")
@patch("discovery.discover.fetch_readme")
@patch("discovery.discover.search_repos")
class TestFullPipelineEndToEnd:
    """Step 6 — end-to-end integration tests.

    Mock only HTTP boundaries (GitHub API, Anthropic API, Telegram API).
    All internal wiring and SQLite storage are real. Verifies the complete
    pipeline: persist, dedup, summarize, assemble, deliver, record features.
    """

    def test_full_pipeline_all_steps(self, mock_search, mock_readme, mock_seeds, mock_deep, mock_quick, mock_send):
        """Full pipeline run verifies every step executed: repos persisted,
        dedup applied, summaries generated and persisted, digest assembled,
        delivery called, features recorded."""
        mock_search.return_value = [
            _make_repo_dict(1, "org/alpha", stars=500),
            _make_repo_dict(2, "org/beta", stars=400),
            _make_repo_dict(3, "org/gamma", stars=300),
            _make_repo_dict(4, "org/delta", stars=200),
            _make_repo_dict(5, "org/epsilon", stars=100),
        ]
        mock_readme.side_effect = lambda o, r, **kw: "# README\n" + "x" * 500
        mock_seeds.return_value = []

        config = _make_config()

        with patch.dict("os.environ", _MOCK_ENV):
            result = run_daily_pipeline(config)

        # Pipeline succeeds
        assert result.success is True
        assert result.errors == []

        # Repos persisted
        for i in range(1, 6):
            assert storage.get_repo(i) is not None

        # Summaries persisted (1 deep + 3 quick = 4 summaries in DB)
        deep_summary = storage.get_summary(1)
        assert deep_summary is not None
        assert deep_summary.summary_type == "deep"
        for i in range(2, 5):
            qs = storage.get_summary(i)
            assert qs is not None
            assert qs.summary_type == "quick"

        # Delivery called with correct Digest
        mock_send.assert_called_once()
        digest = mock_send.call_args[0][0]
        assert isinstance(digest, Digest)
        assert digest.deep_dive.repo_name == "org/alpha"
        assert len(digest.quick_hits) == 3

        # Features recorded
        featured = storage.get_featured_repo_ids(since_days=1)
        assert len(featured) == 4  # 1 deep + 3 quick

    def test_pipeline_result_counts(self, mock_search, mock_readme, mock_seeds, mock_deep, mock_quick, mock_send):
        """PipelineResult has correct counts for all fields."""
        mock_search.return_value = [
            _make_repo_dict(1, "org/alpha", stars=500),
            _make_repo_dict(2, "org/beta", stars=400),
            _make_repo_dict(3, "org/gamma", stars=300),
            _make_repo_dict(4, "org/delta", stars=200),
            _make_repo_dict(5, "org/epsilon", stars=100),
        ]
        mock_readme.side_effect = lambda o, r, **kw: "# README\n" + "x" * 500
        mock_seeds.return_value = []

        config = _make_config()

        with patch.dict("os.environ", _MOCK_ENV):
            result = run_daily_pipeline(config)

        assert result.repos_discovered == 5
        assert result.repos_after_dedup == 5
        assert result.summaries_generated == 4  # 1 deep + 3 quick
        assert result.delivery_result is not None
        assert result.delivery_result.success is True
        assert result.delivery_result.message_id == "99"

    def test_second_run_deep_dive_excluded_from_both_pools(self, mock_search, mock_readme, mock_seeds, mock_deep, mock_quick, mock_send):
        """Second pipeline run: previously deep-dived repos excluded from
        both deep and quick pools (within 90-day cooldown)."""
        repos = [
            _make_repo_dict(1, "org/alpha", stars=500),
            _make_repo_dict(2, "org/beta", stars=400),
            _make_repo_dict(3, "org/gamma", stars=300),
            _make_repo_dict(4, "org/delta", stars=200),
            _make_repo_dict(5, "org/epsilon", stars=100),
            _make_repo_dict(6, "org/zeta", stars=90),
            _make_repo_dict(7, "org/eta", stars=80),
            _make_repo_dict(8, "org/theta", stars=70),
        ]
        mock_search.return_value = repos
        mock_readme.side_effect = lambda o, r, **kw: "# README\n" + "x" * 500
        mock_seeds.return_value = []

        config = _make_config()

        # Run 1: alpha=deep, beta+gamma+delta=quick
        with patch.dict("os.environ", _MOCK_ENV):
            r1 = run_daily_pipeline(config)
        assert r1.success is True

        # Verify first run's features
        first_digest = mock_send.call_args[0][0]
        assert first_digest.deep_dive.repo_name == "org/alpha"
        first_quick_names = {qh.repo_name for qh in first_digest.quick_hits}
        assert first_quick_names == {"org/beta", "org/gamma", "org/delta"}

        # Run 2: same repos discovered, but featured ones excluded
        mock_send.reset_mock()
        with patch.dict("os.environ", _MOCK_ENV):
            r2 = run_daily_pipeline(config)
        assert r2.success is True

        second_digest = mock_send.call_args[0][0]
        # alpha was deep-dived — excluded from both pools
        assert second_digest.deep_dive.repo_name != "org/alpha"
        all_second_names = {second_digest.deep_dive.repo_name} | {
            qh.repo_name for qh in second_digest.quick_hits
        }
        assert "org/alpha" not in all_second_names

    def test_second_run_quick_hit_excluded_from_quick_pool(self, mock_search, mock_readme, mock_seeds, mock_deep, mock_quick, mock_send):
        """Second run: previously quick-hit repos excluded from quick pool
        (within 30-day quick cooldown), but deep-dived repos also excluded
        from quick pool."""
        repos = [
            _make_repo_dict(1, "org/alpha", stars=500),
            _make_repo_dict(2, "org/beta", stars=400),
            _make_repo_dict(3, "org/gamma", stars=300),
            _make_repo_dict(4, "org/delta", stars=200),
            _make_repo_dict(5, "org/epsilon", stars=100),
            _make_repo_dict(6, "org/zeta", stars=90),
            _make_repo_dict(7, "org/eta", stars=80),
            _make_repo_dict(8, "org/theta", stars=70),
        ]
        mock_search.return_value = repos
        mock_readme.side_effect = lambda o, r, **kw: "# README\n" + "x" * 500
        mock_seeds.return_value = []

        config = _make_config()

        # Run 1
        with patch.dict("os.environ", _MOCK_ENV):
            r1 = run_daily_pipeline(config)
        assert r1.success is True

        first_digest = mock_send.call_args[0][0]
        first_quick_names = {qh.repo_name for qh in first_digest.quick_hits}

        # Run 2
        mock_send.reset_mock()
        with patch.dict("os.environ", _MOCK_ENV):
            r2 = run_daily_pipeline(config)
        assert r2.success is True

        second_digest = mock_send.call_args[0][0]
        second_quick_names = {qh.repo_name for qh in second_digest.quick_hits}

        # No overlap: quick-hit repos from run 1 should not reappear as quick hits
        assert first_quick_names.isdisjoint(second_quick_names)

    def test_tiered_cooldown_promotion(self, mock_search, mock_readme, mock_seeds, mock_deep, mock_quick, mock_send):
        """Tiered cooldown: a repo quick-hit'd more than promotion_gap_days ago
        becomes eligible for deep dive on a subsequent run, even though it's still
        within the 30-day quick-hit cooldown.

        Uses backdated feature records to simulate passage of time.
        """
        # 6 repos: alpha is highest-ranked, will be deep-dive candidate
        repos = [
            _make_repo_dict(1, "org/alpha", stars=500),
            _make_repo_dict(2, "org/beta", stars=400),
            _make_repo_dict(3, "org/gamma", stars=300),
            _make_repo_dict(4, "org/delta", stars=200),
            _make_repo_dict(5, "org/epsilon", stars=100),
            _make_repo_dict(6, "org/zeta", stars=90),
        ]
        mock_search.return_value = repos
        mock_readme.side_effect = lambda o, r, **kw: "# README\n" + "x" * 500
        mock_seeds.return_value = []

        config = _make_config()

        # Run 1: establish repos in storage
        with patch.dict("os.environ", _MOCK_ENV):
            r1 = run_daily_pipeline(config)
        assert r1.success is True

        first_digest = mock_send.call_args[0][0]
        deep_repo = first_digest.deep_dive.repo_name  # org/alpha

        # Now simulate time passing: backdate all run-1 features to 10 days ago.
        # This means:
        #   - deep-dived repo (alpha): 10 days ago, still within 90-day deep cooldown → excluded from both
        #   - quick-hit repos (beta, gamma, delta): 10 days ago
        #     → within 30-day quick cooldown → excluded from quick pool
        #     → past 7-day promotion gap → ELIGIBLE for deep dive
        conn = get_connection()
        conn.execute(
            "UPDATE feature_history SET featured_date = ?",
            ((date.today() - timedelta(days=10)).isoformat(),),
        )
        conn.commit()

        # Run 2: with backdated features, beta should now be eligible for deep dive
        # (it was quick-hit'd 10 days ago, past the 7-day promotion gap)
        mock_send.reset_mock()
        with patch.dict("os.environ", _MOCK_ENV):
            r2 = run_daily_pipeline(config)
        assert r2.success is True

        second_digest = mock_send.call_args[0][0]

        # alpha still blocked (deep-dived 10 days ago, within 90-day deep cooldown)
        assert second_digest.deep_dive.repo_name != deep_repo

        # One of the previously quick-hit repos should now be the deep dive
        # (promoted from quick to deep after promotion gap)
        first_quick_names = {qh.repo_name for qh in first_digest.quick_hits}
        assert second_digest.deep_dive.repo_name in first_quick_names

        # The promoted repo should NOT appear in quick hits too
        second_quick_names = {qh.repo_name for qh in second_digest.quick_hits}
        assert second_digest.deep_dive.repo_name not in second_quick_names

    def test_tiered_cooldown_promotion_blocked_within_gap(self, mock_search, mock_readme, mock_seeds, mock_deep, mock_quick, mock_send):
        """Quick-hit repo featured within promotion_gap_days is NOT eligible
        for deep dive — the gap hasn't elapsed yet."""
        repos = [
            _make_repo_dict(1, "org/alpha", stars=500),
            _make_repo_dict(2, "org/beta", stars=400),
            _make_repo_dict(3, "org/gamma", stars=300),
            _make_repo_dict(4, "org/delta", stars=200),
            _make_repo_dict(5, "org/epsilon", stars=100),
            _make_repo_dict(6, "org/zeta", stars=90),
            _make_repo_dict(7, "org/eta", stars=80),
            _make_repo_dict(8, "org/theta", stars=70),
        ]
        mock_search.return_value = repos
        mock_readme.side_effect = lambda o, r, **kw: "# README\n" + "x" * 500
        mock_seeds.return_value = []

        config = _make_config()

        # Run 1: alpha=deep, beta+gamma+delta=quick
        with patch.dict("os.environ", _MOCK_ENV):
            r1 = run_daily_pipeline(config)
        assert r1.success is True

        # Run 2 immediately (same day) — quick-hit repos are within the 7-day
        # promotion gap, so they're excluded from deep dive too
        mock_send.reset_mock()
        with patch.dict("os.environ", _MOCK_ENV):
            r2 = run_daily_pipeline(config)
        assert r2.success is True

        second_digest = mock_send.call_args[0][0]
        first_digest_quick_names = {"org/beta", "org/gamma", "org/delta"}
        assert second_digest.deep_dive.repo_name not in first_digest_quick_names
        assert second_digest.deep_dive.repo_name != "org/alpha"

        # Deep dive should be from the unfeatured repos
        assert second_digest.deep_dive.repo_name in {
            "org/epsilon", "org/zeta", "org/eta", "org/theta",
        }
