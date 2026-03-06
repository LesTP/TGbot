"""Tests for run_daily_pipeline — full pipeline through delivery."""

from datetime import date, datetime, timedelta
from unittest.mock import patch, MagicMock

import pytest

import storage
from delivery.types import DeliveryResult, Digest, SummaryWithRepo
from discovery.types import (
    CategoryConfig,
    DiscoveredRepo,
    GitHubAPIError,
    NoResultsError,
    RankingCriteria,
)
from orchestrator.pipeline import (
    _assemble_digest,
    _build_llm_config,
    _build_recent_context,
    _build_storage_config,
    _build_summary_with_repo,
    _generate_deep_dive_with_fallback,
    _generate_quick_hits,
    _select_candidates,
    run_daily_pipeline,
)
from orchestrator.types import PipelineConfig
from storage.types import RepoRecord, StorageError, SummaryRecord
from summarization.types import (
    InsufficientContentError,
    LLMAPIError,
    LLMConfig,
    LLMResponseError,
    SummaryResult,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_MOCK_ENV = {
    "ANTHROPIC_API_KEY": "sk-test-key",
    "LLM_PROVIDER": "anthropic",
    "LLM_DEEP_DIVE_MODEL": "test-deep-model",
    "LLM_QUICK_HIT_MODEL": "test-quick-model",
    "TELEGRAM_BOT_TOKEN": "bot123:test-token",
}

_MOCK_DELIVERY = DeliveryResult(success=True, message_id="42")


def _make_category() -> CategoryConfig:
    return CategoryConfig(name="test", description="test category")


def _make_config(**overrides) -> PipelineConfig:
    defaults = dict(
        category=_make_category(),
        channel_id="@test",
        ranking_criteria=RankingCriteria.STARS,
    )
    defaults.update(overrides)
    return PipelineConfig(**defaults)


def _make_repo(n: int) -> DiscoveredRepo:
    return DiscoveredRepo(
        source="github",
        source_id=str(n),
        name=f"owner/repo-{n}",
        url=f"https://github.com/owner/repo-{n}",
        description=f"Repo {n}",
        raw_content=f"# Repo {n}\nREADME content",
        source_metadata={
            "stars": 100 + n,
            "forks": 10 + n,
            "subscribers": 5 + n,
            "primary_language": "Python",
            "created_at": "2025-01-01T00:00:00Z",
            "updated_at": "2025-06-01T00:00:00Z",
            "pushed_at": "2025-06-01T00:00:00Z",
            "topics": ["test"],
        },
    )


def _make_repo_record(id: int, **overrides) -> RepoRecord:
    defaults = dict(
        id=id,
        source="github",
        source_id=str(id),
        name=f"owner/repo-{id}",
        url=f"https://github.com/owner/repo-{id}",
        description=f"Repo {id}",
        raw_content=f"# Repo {id}\nREADME content",
        source_metadata={
            "stars": 100 + id,
            "created_at": "2025-01-01T00:00:00Z",
        },
        discovered_at=datetime(2025, 6, 1),
    )
    defaults.update(overrides)
    return RepoRecord(**defaults)


def _make_summary_result(content: str = "Generated summary.") -> SummaryResult:
    return SummaryResult(
        content=content,
        model_used="test-model",
        token_usage={"input_tokens": 100, "output_tokens": 50},
    )


def _feature_repo(repo_id: int, days_ago: int = 0) -> None:
    """Insert a feature_history record via direct SQL for test setup."""
    conn = storage.db.get_connection()
    featured_date = (date.today() - timedelta(days=days_ago)).isoformat()
    conn.execute(
        "INSERT INTO feature_history (repo_id, feature_type, featured_date, ranking_criteria) "
        "VALUES (?, 'deep', ?, 'stars')",
        (repo_id, featured_date),
    )
    conn.commit()


@pytest.fixture(autouse=True)
def _init_storage():
    """Init SQLite in-memory storage for each test, close after."""
    storage.init({"engine": "sqlite", "database": ":memory:"})
    yield
    storage.close()


# ---------------------------------------------------------------------------
# _build_storage_config
# ---------------------------------------------------------------------------


class TestBuildStorageConfig:

    def test_defaults_to_sqlite_memory(self):
        with patch.dict("os.environ", {}, clear=True):
            config = _build_storage_config()
        assert config == {"engine": "sqlite", "database": ":memory:"}

    def test_sqlite_with_db_path(self):
        with patch.dict("os.environ", {"DB_PATH": "/tmp/test.db"}, clear=True):
            config = _build_storage_config()
        assert config == {"engine": "sqlite", "database": "/tmp/test.db"}

    def test_mysql_config(self):
        env = {
            "DB_ENGINE": "mysql",
            "DB_HOST": "localhost",
            "DB_USER": "root",
            "DB_PASSWORD": "secret",
            "DB_NAME": "tgbot",
        }
        with patch.dict("os.environ", env, clear=True):
            config = _build_storage_config()
        assert config == {
            "engine": "mysql",
            "host": "localhost",
            "user": "root",
            "password": "secret",
            "database": "tgbot",
        }

    def test_mysql_missing_env_var_raises(self):
        env = {"DB_ENGINE": "mysql", "DB_HOST": "localhost"}
        with patch.dict("os.environ", env, clear=True):
            with pytest.raises(KeyError):
                _build_storage_config()


# ---------------------------------------------------------------------------
# _build_llm_config
# ---------------------------------------------------------------------------


class TestBuildLLMConfig:

    def test_with_all_env_vars(self):
        with patch.dict("os.environ", _MOCK_ENV, clear=True):
            config = _build_llm_config()
        assert config.provider == "anthropic"
        assert config.api_key == "sk-test-key"
        assert config.deep_dive_model == "test-deep-model"
        assert config.quick_hit_model == "test-quick-model"

    def test_defaults_for_optional_vars(self):
        with patch.dict("os.environ", {"ANTHROPIC_API_KEY": "sk-key"}, clear=True):
            config = _build_llm_config()
        assert config.provider == "anthropic"
        assert config.deep_dive_model == "claude-sonnet-4-5-20250929"
        assert config.quick_hit_model == "claude-3-5-haiku-20241022"

    def test_missing_api_key_raises(self):
        with patch.dict("os.environ", {}, clear=True):
            with pytest.raises(KeyError):
                _build_llm_config()


# ---------------------------------------------------------------------------
# _build_recent_context
# ---------------------------------------------------------------------------


class TestBuildRecentContext:

    def test_empty_list(self):
        assert _build_recent_context([]) == []

    def test_converts_summary_records(self):
        repo = storage.save_repo(_make_repo(1))
        records = [
            SummaryRecord(
                id=1, repo_id=repo.id, summary_type="deep",
                content="Deep summary.", model_used="model",
                generated_at=datetime(2025, 6, 1, 12, 0),
            ),
        ]
        context = _build_recent_context(records)
        assert len(context) == 1
        assert context[0]["repo_name"] == "owner/repo-1"
        assert context[0]["summary_content"] == "Deep summary."
        assert context[0]["date"] == "2025-06-01"

    def test_missing_repo_uses_fallback_name(self):
        records = [
            SummaryRecord(
                id=1, repo_id=9999, summary_type="quick",
                content="Quick summary.", model_used="model",
                generated_at=datetime(2025, 6, 1),
            ),
        ]
        context = _build_recent_context(records)
        assert context[0]["repo_name"] == "repo-9999"


# ---------------------------------------------------------------------------
# _select_candidates (unit tests)
# ---------------------------------------------------------------------------


class TestSelectCandidates:

    def test_no_featured_returns_top_split(self):
        repos = [_make_repo_record(i) for i in range(1, 8)]
        deep, quick = _select_candidates(repos, featured_ids=set(), deep_dive_count=1, quick_hit_count=3)
        assert len(deep) == 1
        assert deep[0].id == 1
        assert len(quick) == 3
        assert [r.id for r in quick] == [2, 3, 4]

    def test_featured_excluded(self):
        repos = [_make_repo_record(i) for i in range(1, 8)]
        deep, quick = _select_candidates(repos, featured_ids={1, 2, 3}, deep_dive_count=1, quick_hit_count=3)
        assert deep[0].id == 4
        assert [r.id for r in quick] == [5, 6, 7]

    def test_all_featured_returns_empty(self):
        repos = [_make_repo_record(i) for i in range(1, 4)]
        deep, quick = _select_candidates(repos, featured_ids={1, 2, 3}, deep_dive_count=1, quick_hit_count=3)
        assert deep == []
        assert quick == []

    def test_fewer_than_requested(self):
        repos = [_make_repo_record(i) for i in range(1, 4)]
        deep, quick = _select_candidates(repos, featured_ids=set(), deep_dive_count=1, quick_hit_count=5)
        assert len(deep) == 1
        assert len(quick) == 2

    def test_preserves_ranked_order(self):
        repos = [_make_repo_record(i) for i in range(1, 11)]
        deep, quick = _select_candidates(repos, featured_ids={2, 4}, deep_dive_count=1, quick_hit_count=3)
        assert deep[0].id == 1
        assert [r.id for r in quick] == [3, 5, 6]


# ---------------------------------------------------------------------------
# _build_summary_with_repo (unit tests)
# ---------------------------------------------------------------------------


class TestBuildSummaryWithRepo:

    def test_maps_fields_correctly(self):
        repo = _make_repo_record(1)
        swr = _build_summary_with_repo(repo, "Summary text.")
        assert swr.summary_content == "Summary text."
        assert swr.repo_name == "owner/repo-1"
        assert swr.repo_url == "https://github.com/owner/repo-1"
        assert swr.stars == 101
        assert swr.created_at == "2025-01-01T00:00:00Z"

    def test_missing_metadata_defaults(self):
        repo = _make_repo_record(1, source_metadata={})
        swr = _build_summary_with_repo(repo, "Content.")
        assert swr.stars == 0
        assert swr.created_at == ""


# ---------------------------------------------------------------------------
# _assemble_digest (unit tests)
# ---------------------------------------------------------------------------


class TestAssembleDigest:

    def test_assembles_complete_digest(self):
        deep_repo = _make_repo_record(1)
        deep_summary = _make_summary_result("Deep analysis.")
        quick_results = [
            (_make_repo_record(2), _make_summary_result("Quick 2.")),
            (_make_repo_record(3), _make_summary_result("Quick 3.")),
        ]

        digest = _assemble_digest(deep_repo, deep_summary, quick_results, "stars")

        assert digest.deep_dive.summary_content == "Deep analysis."
        assert digest.deep_dive.repo_name == "owner/repo-1"
        assert len(digest.quick_hits) == 2
        assert digest.quick_hits[0].summary_content == "Quick 2."
        assert digest.quick_hits[1].repo_name == "owner/repo-3"
        assert digest.ranking_criteria == "stars"
        assert digest.date == date.today()

    def test_empty_quick_hits(self):
        deep_repo = _make_repo_record(1)
        deep_summary = _make_summary_result("Deep.")

        digest = _assemble_digest(deep_repo, deep_summary, [], "forks")

        assert digest.deep_dive.summary_content == "Deep."
        assert digest.quick_hits == []

    def test_partial_quick_hits(self):
        deep_repo = _make_repo_record(1)
        deep_summary = _make_summary_result("Deep.")
        quick_results = [
            (_make_repo_record(2), _make_summary_result("Quick.")),
        ]

        digest = _assemble_digest(deep_repo, deep_summary, quick_results, "recency")

        assert len(digest.quick_hits) == 1


# ---------------------------------------------------------------------------
# _generate_deep_dive_with_fallback (unit tests)
# ---------------------------------------------------------------------------


class TestDeepDiveFallback:

    def test_first_candidate_succeeds(self):
        repos = [_make_repo_record(1), _make_repo_record(2)]
        expected = _make_summary_result("Deep dive for repo 1.")
        errors = []

        with patch("orchestrator.pipeline.generate_deep_dive", return_value=expected):
            result = _generate_deep_dive_with_fallback(
                repos, [], MagicMock(), None, errors
            )

        assert result is not None
        assert result[0].id == 1
        assert result[1].content == "Deep dive for repo 1."
        assert errors == []

    def test_falls_back_on_failure(self):
        repos = [_make_repo_record(1), _make_repo_record(2)]
        expected = _make_summary_result("Fallback deep dive.")
        errors = []

        call_count = 0

        def side_effect(repo, config, context=None):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise LLMAPIError("rate limited", status_code=429)
            return expected

        with patch("orchestrator.pipeline.generate_deep_dive", side_effect=side_effect):
            result = _generate_deep_dive_with_fallback(
                repos, [], MagicMock(), None, errors
            )

        assert result is not None
        assert result[0].id == 2
        assert len(errors) == 1
        assert "rate limited" in errors[0]

    def test_falls_back_to_remaining_eligible(self):
        candidates = [_make_repo_record(1)]
        remaining = [_make_repo_record(5)]
        expected = _make_summary_result("From remaining.")
        errors = []

        call_count = 0

        def side_effect(repo, config, context=None):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise InsufficientContentError("too short", content_length=10)
            return expected

        with patch("orchestrator.pipeline.generate_deep_dive", side_effect=side_effect):
            result = _generate_deep_dive_with_fallback(
                candidates, remaining, MagicMock(), None, errors
            )

        assert result is not None
        assert result[0].id == 5

    def test_all_fail_returns_none(self):
        repos = [_make_repo_record(1), _make_repo_record(2)]
        errors = []

        with patch("orchestrator.pipeline.generate_deep_dive",
                    side_effect=LLMAPIError("failed")):
            result = _generate_deep_dive_with_fallback(
                repos, [], MagicMock(), None, errors
            )

        assert result is None
        assert len(errors) == 2


# ---------------------------------------------------------------------------
# _generate_quick_hits (unit tests)
# ---------------------------------------------------------------------------


class TestQuickHits:

    def test_all_succeed(self):
        repos = [_make_repo_record(1), _make_repo_record(2), _make_repo_record(3)]
        errors = []

        with patch("orchestrator.pipeline.generate_quick_hit",
                    return_value=_make_summary_result("Quick.")):
            results = _generate_quick_hits(repos, MagicMock(), errors)

        assert len(results) == 3
        assert errors == []

    def test_failure_skipped(self):
        repos = [_make_repo_record(1), _make_repo_record(2), _make_repo_record(3)]
        errors = []

        call_count = 0

        def side_effect(repo, config):
            nonlocal call_count
            call_count += 1
            if call_count == 2:
                raise LLMResponseError("empty response")
            return _make_summary_result("Quick.")

        with patch("orchestrator.pipeline.generate_quick_hit", side_effect=side_effect):
            results = _generate_quick_hits(repos, MagicMock(), errors)

        assert len(results) == 2
        assert len(errors) == 1

    def test_all_fail_returns_empty(self):
        repos = [_make_repo_record(1), _make_repo_record(2)]
        errors = []

        with patch("orchestrator.pipeline.generate_quick_hit",
                    side_effect=InsufficientContentError("too short", 10)):
            results = _generate_quick_hits(repos, MagicMock(), errors)

        assert results == []
        assert len(errors) == 2


# ---------------------------------------------------------------------------
# Happy path (full pipeline)
# ---------------------------------------------------------------------------


class TestHappyPath:

    @patch("orchestrator.pipeline.send_digest", return_value=_MOCK_DELIVERY)
    @patch("orchestrator.pipeline.generate_quick_hit", return_value=_make_summary_result("Quick."))
    @patch("orchestrator.pipeline.generate_deep_dive", return_value=_make_summary_result("Deep."))
    @patch("orchestrator.pipeline.discover_repos")
    def test_full_pipeline(self, mock_discover, mock_deep, mock_quick, mock_send):
        repos = [_make_repo(i) for i in range(1, 8)]
        mock_discover.return_value = repos

        with patch.dict("os.environ", _MOCK_ENV):
            result = run_daily_pipeline(_make_config())

        assert result.success is True
        assert result.repos_discovered == 7
        assert result.repos_after_dedup == 7
        assert result.summaries_generated == 4
        assert result.delivery_result.success is True
        assert result.delivery_result.message_id == "42"
        assert result.errors == []

    @patch("orchestrator.pipeline.send_digest", return_value=_MOCK_DELIVERY)
    @patch("orchestrator.pipeline.generate_quick_hit", return_value=_make_summary_result("Quick."))
    @patch("orchestrator.pipeline.generate_deep_dive", return_value=_make_summary_result("Deep."))
    @patch("orchestrator.pipeline.discover_repos")
    def test_summaries_persisted_in_storage(self, mock_discover, mock_deep, mock_quick, mock_send):
        repos = [_make_repo(i) for i in range(1, 6)]
        mock_discover.return_value = repos

        with patch.dict("os.environ", _MOCK_ENV):
            run_daily_pipeline(_make_config())

        deep_summary = storage.get_summary(1)
        assert deep_summary is not None
        assert deep_summary.summary_type == "deep"
        assert deep_summary.content == "Deep."

    @patch("orchestrator.pipeline.send_digest", return_value=_MOCK_DELIVERY)
    @patch("orchestrator.pipeline.generate_quick_hit", return_value=_make_summary_result("Quick."))
    @patch("orchestrator.pipeline.generate_deep_dive", return_value=_make_summary_result("Deep."))
    @patch("orchestrator.pipeline.discover_repos")
    def test_correct_repos_passed_to_summarization(self, mock_discover, mock_deep, mock_quick, mock_send):
        repos = [_make_repo(i) for i in range(1, 8)]
        mock_discover.return_value = repos

        with patch.dict("os.environ", _MOCK_ENV):
            run_daily_pipeline(_make_config())

        deep_repo = mock_deep.call_args[0][0]
        assert deep_repo.name == "owner/repo-1"

        quick_repos = [call[0][0].name for call in mock_quick.call_args_list]
        assert quick_repos == ["owner/repo-2", "owner/repo-3", "owner/repo-4"]

    @patch("orchestrator.pipeline.send_digest", return_value=_MOCK_DELIVERY)
    @patch("orchestrator.pipeline.generate_quick_hit", return_value=_make_summary_result("Quick."))
    @patch("orchestrator.pipeline.generate_deep_dive", return_value=_make_summary_result("Deep."))
    @patch("orchestrator.pipeline.discover_repos")
    def test_digest_passed_to_delivery(self, mock_discover, mock_deep, mock_quick, mock_send):
        repos = [_make_repo(i) for i in range(1, 6)]
        mock_discover.return_value = repos

        with patch.dict("os.environ", _MOCK_ENV):
            run_daily_pipeline(_make_config())

        digest = mock_send.call_args[0][0]
        assert isinstance(digest, Digest)
        assert digest.deep_dive.summary_content == "Deep."
        assert digest.deep_dive.repo_name == "owner/repo-1"
        assert len(digest.quick_hits) == 3
        assert digest.ranking_criteria == "stars"
        assert digest.date == date.today()

        channel = mock_send.call_args[0][1]
        assert channel == "@test"

        bot_token = mock_send.call_args[0][2]
        assert bot_token == "bot123:test-token"


# ---------------------------------------------------------------------------
# Delivery errors
# ---------------------------------------------------------------------------


class TestDeliveryErrors:

    @patch("orchestrator.pipeline.generate_quick_hit", return_value=_make_summary_result("Quick."))
    @patch("orchestrator.pipeline.generate_deep_dive", return_value=_make_summary_result("Deep."))
    @patch("orchestrator.pipeline.discover_repos")
    def test_delivery_failure_returns_false(self, mock_discover, mock_deep, mock_quick):
        mock_discover.return_value = [_make_repo(i) for i in range(1, 6)]
        failed_delivery = DeliveryResult(success=False, error="Telegram 403")

        with patch("orchestrator.pipeline.send_digest", return_value=failed_delivery):
            with patch.dict("os.environ", _MOCK_ENV):
                result = run_daily_pipeline(_make_config())

        assert result.success is False
        assert result.delivery_result.success is False
        assert result.summaries_generated == 4
        assert any("Telegram 403" in e for e in result.errors)

    @patch("orchestrator.pipeline.generate_quick_hit", return_value=_make_summary_result("Quick."))
    @patch("orchestrator.pipeline.generate_deep_dive", return_value=_make_summary_result("Deep."))
    @patch("orchestrator.pipeline.discover_repos")
    def test_delivery_exception_captured(self, mock_discover, mock_deep, mock_quick):
        mock_discover.return_value = [_make_repo(i) for i in range(1, 6)]

        with patch("orchestrator.pipeline.send_digest", side_effect=Exception("network error")):
            with patch.dict("os.environ", _MOCK_ENV):
                result = run_daily_pipeline(_make_config())

        assert result.success is False
        assert result.delivery_result is not None
        assert result.delivery_result.success is False
        assert any("network error" in e for e in result.errors)

    @patch("orchestrator.pipeline.generate_quick_hit", return_value=_make_summary_result("Quick."))
    @patch("orchestrator.pipeline.generate_deep_dive", return_value=_make_summary_result("Deep."))
    @patch("orchestrator.pipeline.discover_repos")
    def test_missing_bot_token_fails(self, mock_discover, mock_deep, mock_quick):
        mock_discover.return_value = [_make_repo(i) for i in range(1, 6)]
        env_no_token = {k: v for k, v in _MOCK_ENV.items() if k != "TELEGRAM_BOT_TOKEN"}

        with patch.dict("os.environ", env_no_token, clear=True):
            result = run_daily_pipeline(_make_config())

        assert result.success is False
        assert any("TELEGRAM_BOT_TOKEN" in e for e in result.errors)


# ---------------------------------------------------------------------------
# Feature recording
# ---------------------------------------------------------------------------


class TestFeatureRecording:

    @patch("orchestrator.pipeline.send_digest", return_value=_MOCK_DELIVERY)
    @patch("orchestrator.pipeline.generate_quick_hit", return_value=_make_summary_result("Quick."))
    @patch("orchestrator.pipeline.generate_deep_dive", return_value=_make_summary_result("Deep."))
    @patch("orchestrator.pipeline.discover_repos")
    def test_features_recorded_on_success(self, mock_discover, mock_deep, mock_quick, mock_send):
        """After successful delivery, all featured repos are recorded."""
        repos = [_make_repo(i) for i in range(1, 6)]
        mock_discover.return_value = repos

        with patch.dict("os.environ", _MOCK_ENV):
            result = run_daily_pipeline(_make_config())

        assert result.success is True

        featured_ids = storage.get_featured_repo_ids(since_days=90)
        # 1 deep + 3 quick = 4 featured repos
        assert len(featured_ids) == 4

    @patch("orchestrator.pipeline.send_digest", return_value=_MOCK_DELIVERY)
    @patch("orchestrator.pipeline.generate_quick_hit", return_value=_make_summary_result("Quick."))
    @patch("orchestrator.pipeline.generate_deep_dive", return_value=_make_summary_result("Deep."))
    @patch("orchestrator.pipeline.discover_repos")
    def test_feature_types_correct(self, mock_discover, mock_deep, mock_quick, mock_send):
        """Deep dive recorded as 'deep', quick hits as 'quick'."""
        repos = [_make_repo(i) for i in range(1, 6)]
        mock_discover.return_value = repos

        with patch.dict("os.environ", _MOCK_ENV):
            run_daily_pipeline(_make_config())

        conn = storage.db.get_connection()
        rows = conn.execute(
            "SELECT repo_id, feature_type, ranking_criteria FROM feature_history "
            "ORDER BY id"
        ).fetchall()

        assert len(rows) == 4
        # First record is deep dive (repo 1)
        assert rows[0]["feature_type"] == "deep"
        assert rows[0]["ranking_criteria"] == "stars"
        # Remaining are quick hits
        for row in rows[1:]:
            assert row["feature_type"] == "quick"

    @patch("orchestrator.pipeline.generate_quick_hit", return_value=_make_summary_result("Quick."))
    @patch("orchestrator.pipeline.generate_deep_dive", return_value=_make_summary_result("Deep."))
    @patch("orchestrator.pipeline.discover_repos")
    def test_no_features_recorded_on_delivery_failure(self, mock_discover, mock_deep, mock_quick):
        """Features NOT recorded when delivery fails."""
        repos = [_make_repo(i) for i in range(1, 6)]
        mock_discover.return_value = repos
        failed_delivery = DeliveryResult(success=False, error="Telegram 403")

        with patch("orchestrator.pipeline.send_digest", return_value=failed_delivery):
            with patch.dict("os.environ", _MOCK_ENV):
                result = run_daily_pipeline(_make_config())

        assert result.success is False
        featured_ids = storage.get_featured_repo_ids(since_days=90)
        assert len(featured_ids) == 0

    @patch("orchestrator.pipeline.send_digest", return_value=_MOCK_DELIVERY)
    @patch("orchestrator.pipeline.generate_quick_hit", return_value=_make_summary_result("Quick."))
    @patch("orchestrator.pipeline.generate_deep_dive", return_value=_make_summary_result("Deep."))
    @patch("orchestrator.pipeline.discover_repos")
    def test_feature_recording_failure_still_succeeds(self, mock_discover, mock_deep, mock_quick, mock_send):
        """Feature recording failure captured but pipeline still success=True."""
        repos = [_make_repo(i) for i in range(1, 6)]
        mock_discover.return_value = repos

        with patch("orchestrator.pipeline.storage.record_feature",
                    side_effect=StorageError("db write failed")):
            with patch.dict("os.environ", _MOCK_ENV):
                result = run_daily_pipeline(_make_config())

        assert result.success is True
        assert result.delivery_result.success is True
        assert any("Failed to record feature" in e for e in result.errors)


# ---------------------------------------------------------------------------
# Summarization errors (through pipeline)
# ---------------------------------------------------------------------------


class TestSummarizationErrors:

    @patch("orchestrator.pipeline.send_digest", return_value=_MOCK_DELIVERY)
    @patch("orchestrator.pipeline.generate_quick_hit", return_value=_make_summary_result("Quick."))
    @patch("orchestrator.pipeline.discover_repos")
    def test_deep_dive_fallback_in_pipeline(self, mock_discover, mock_quick, mock_send):
        repos = [_make_repo(i) for i in range(1, 8)]
        mock_discover.return_value = repos

        call_count = 0

        def deep_side_effect(repo, config, recent_context=None):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise LLMAPIError("rate limited", status_code=429)
            return _make_summary_result("Fallback deep.")

        with patch("orchestrator.pipeline.generate_deep_dive", side_effect=deep_side_effect):
            with patch.dict("os.environ", _MOCK_ENV):
                result = run_daily_pipeline(_make_config())

        assert result.success is True
        assert result.summaries_generated == 4
        assert any("rate limited" in e for e in result.errors)

    @patch("orchestrator.pipeline.discover_repos")
    def test_all_deep_dives_fail(self, mock_discover):
        repos = [_make_repo(i) for i in range(1, 6)]
        mock_discover.return_value = repos

        with patch("orchestrator.pipeline.generate_deep_dive",
                    side_effect=LLMAPIError("all fail")):
            with patch.dict("os.environ", _MOCK_ENV):
                result = run_daily_pipeline(_make_config())

        assert result.success is False
        assert result.summaries_generated == 0
        assert any("All deep dive" in e for e in result.errors)

    @patch("orchestrator.pipeline.send_digest", return_value=_MOCK_DELIVERY)
    @patch("orchestrator.pipeline.generate_deep_dive", return_value=_make_summary_result("Deep."))
    @patch("orchestrator.pipeline.discover_repos")
    def test_quick_hit_failure_skipped(self, mock_discover, mock_deep, mock_send):
        repos = [_make_repo(i) for i in range(1, 6)]
        mock_discover.return_value = repos

        call_count = 0

        def quick_side_effect(repo, config):
            nonlocal call_count
            call_count += 1
            if call_count == 2:
                raise LLMResponseError("empty response")
            return _make_summary_result("Quick.")

        with patch("orchestrator.pipeline.generate_quick_hit", side_effect=quick_side_effect):
            with patch.dict("os.environ", _MOCK_ENV):
                result = run_daily_pipeline(_make_config())

        assert result.success is True
        assert result.summaries_generated == 3
        assert any("empty response" in e for e in result.errors)

    @patch("orchestrator.pipeline.discover_repos")
    def test_missing_llm_config_fails(self, mock_discover):
        mock_discover.return_value = [_make_repo(1)]

        with patch.dict("os.environ", {}, clear=True):
            result = run_daily_pipeline(_make_config())

        assert result.success is False
        assert any("LLM config" in e for e in result.errors)

    @patch("orchestrator.pipeline.send_digest", return_value=_MOCK_DELIVERY)
    @patch("orchestrator.pipeline.generate_quick_hit", return_value=_make_summary_result("Quick."))
    @patch("orchestrator.pipeline.generate_deep_dive", return_value=_make_summary_result("Deep."))
    @patch("orchestrator.pipeline.discover_repos")
    def test_summaries_generated_count_matches(self, mock_discover, mock_deep, mock_quick, mock_send):
        repos = [_make_repo(i) for i in range(1, 6)]
        mock_discover.return_value = repos

        with patch.dict("os.environ", _MOCK_ENV):
            result = run_daily_pipeline(_make_config())

        assert result.summaries_generated == 4


# ---------------------------------------------------------------------------
# Recent context wiring
# ---------------------------------------------------------------------------


class TestRecentContextWiring:

    @patch("orchestrator.pipeline.send_digest", return_value=_MOCK_DELIVERY)
    @patch("orchestrator.pipeline.generate_quick_hit", return_value=_make_summary_result("Quick."))
    @patch("orchestrator.pipeline.generate_deep_dive", return_value=_make_summary_result("Deep."))
    @patch("orchestrator.pipeline.discover_repos")
    def test_recent_context_passed_to_deep_dive(self, mock_discover, mock_deep, mock_quick, mock_send):
        repos = [_make_repo(i) for i in range(1, 6)]
        mock_discover.return_value = repos

        with patch.dict("os.environ", _MOCK_ENV):
            run_daily_pipeline(_make_config())

        mock_deep.reset_mock()
        with patch.dict("os.environ", _MOCK_ENV):
            run_daily_pipeline(_make_config())

        call_kwargs = mock_deep.call_args
        recent_ctx = call_kwargs[0][2] if len(call_kwargs[0]) > 2 else call_kwargs[1].get("recent_context")
        assert recent_ctx is not None
        assert len(recent_ctx) > 0
        assert "repo_name" in recent_ctx[0]


# ---------------------------------------------------------------------------
# Dedup filtering (end-to-end through pipeline)
# ---------------------------------------------------------------------------


class TestDedupFiltering:

    @patch("orchestrator.pipeline.send_digest", return_value=_MOCK_DELIVERY)
    @patch("orchestrator.pipeline.generate_quick_hit", return_value=_make_summary_result("Quick."))
    @patch("orchestrator.pipeline.generate_deep_dive", return_value=_make_summary_result("Deep."))
    @patch("orchestrator.pipeline.discover_repos")
    def test_recently_featured_filtered(self, mock_discover, mock_deep, mock_quick, mock_send):
        repos = [_make_repo(i) for i in range(1, 8)]
        mock_discover.return_value = repos

        # First run persists repos (and records features for 1 deep + 3 quick)
        with patch.dict("os.environ", _MOCK_ENV):
            run_daily_pipeline(_make_config())

        # Additionally feature repos 5, 6 (manually, within cooldown)
        _feature_repo(5, days_ago=5)
        _feature_repo(6, days_ago=10)

        # Second run: repos 1-4 featured by first run + repos 5-6 manually = 6 featured
        # Only repo 7 eligible
        with patch.dict("os.environ", _MOCK_ENV):
            result = run_daily_pipeline(_make_config())
        assert result.repos_discovered == 7
        assert result.repos_after_dedup == 1

    @patch("orchestrator.pipeline.send_digest", return_value=_MOCK_DELIVERY)
    @patch("orchestrator.pipeline.generate_quick_hit", return_value=_make_summary_result("Quick."))
    @patch("orchestrator.pipeline.generate_deep_dive", return_value=_make_summary_result("Deep."))
    @patch("orchestrator.pipeline.discover_repos")
    def test_all_repos_featured_fails(self, mock_discover, mock_deep, mock_quick, mock_send):
        repos = [_make_repo(i) for i in range(1, 4)]
        mock_discover.return_value = repos

        # First run features all 3 repos (1 deep + 2 quick)
        with patch.dict("os.environ", _MOCK_ENV):
            run_daily_pipeline(_make_config())

        # Second run: all 3 repos already featured
        with patch.dict("os.environ", _MOCK_ENV):
            result = run_daily_pipeline(_make_config())
        assert result.success is False
        assert result.repos_after_dedup == 0

    @patch("orchestrator.pipeline.send_digest", return_value=_MOCK_DELIVERY)
    @patch("orchestrator.pipeline.generate_quick_hit", return_value=_make_summary_result("Quick."))
    @patch("orchestrator.pipeline.generate_deep_dive", return_value=_make_summary_result("Deep."))
    @patch("orchestrator.pipeline.discover_repos")
    def test_old_features_not_excluded(self, mock_discover, mock_deep, mock_quick, mock_send):
        """Repos featured outside cooldown window are eligible."""
        repos = [_make_repo(i) for i in range(1, 4)]
        mock_discover.return_value = repos

        # Persist repos manually so _feature_repo can reference them
        for r in repos:
            storage.save_repo(r)

        _feature_repo(1, days_ago=100)
        _feature_repo(2, days_ago=100)
        _feature_repo(3, days_ago=100)

        # All 3 features are outside the 90-day window → all eligible
        with patch.dict("os.environ", _MOCK_ENV):
            result = run_daily_pipeline(_make_config(cooldown_days=90))
        assert result.repos_after_dedup == 3

    @patch("orchestrator.pipeline.send_digest", return_value=_MOCK_DELIVERY)
    @patch("orchestrator.pipeline.generate_quick_hit", return_value=_make_summary_result("Quick."))
    @patch("orchestrator.pipeline.generate_deep_dive", return_value=_make_summary_result("Deep."))
    @patch("orchestrator.pipeline.discover_repos")
    def test_repos_after_dedup_count_correct(self, mock_discover, mock_deep, mock_quick, mock_send):
        """repos_after_dedup reflects total eligible, not just selected."""
        repos = [_make_repo(i) for i in range(1, 11)]
        mock_discover.return_value = repos

        # First run features 4 repos (1 deep + 3 quick = repos 1-4)
        with patch.dict("os.environ", _MOCK_ENV):
            run_daily_pipeline(_make_config())

        # Second run: 4 featured from first run → 6 eligible
        with patch.dict("os.environ", _MOCK_ENV):
            result = run_daily_pipeline(_make_config())
        assert result.repos_after_dedup == 6


# ---------------------------------------------------------------------------
# Ranking resolution
# ---------------------------------------------------------------------------


class TestRankingResolution:

    @patch("orchestrator.pipeline.send_digest", return_value=_MOCK_DELIVERY)
    @patch("orchestrator.pipeline.generate_quick_hit", return_value=_make_summary_result("Quick."))
    @patch("orchestrator.pipeline.generate_deep_dive", return_value=_make_summary_result("Deep."))
    @patch("orchestrator.pipeline.discover_repos")
    def test_explicit_ranking_passed_through(self, mock_discover, mock_deep, mock_quick, mock_send):
        mock_discover.return_value = [_make_repo(1)]

        with patch.dict("os.environ", _MOCK_ENV):
            run_daily_pipeline(_make_config(ranking_criteria=RankingCriteria.FORKS))

        _, kwargs = mock_discover.call_args
        assert kwargs["ranking"] == RankingCriteria.FORKS

    @patch("orchestrator.pipeline.send_digest", return_value=_MOCK_DELIVERY)
    @patch("orchestrator.pipeline.generate_quick_hit", return_value=_make_summary_result("Quick."))
    @patch("orchestrator.pipeline.generate_deep_dive", return_value=_make_summary_result("Deep."))
    @patch("orchestrator.pipeline.discover_repos")
    @patch("orchestrator.pipeline.get_todays_ranking")
    def test_none_ranking_auto_resolves(self, mock_ranking, mock_discover, mock_deep, mock_quick, mock_send):
        mock_ranking.return_value = RankingCriteria.RECENCY
        mock_discover.return_value = [_make_repo(1)]

        with patch.dict("os.environ", _MOCK_ENV):
            run_daily_pipeline(_make_config(ranking_criteria=None))

        mock_ranking.assert_called_once()
        _, kwargs = mock_discover.call_args
        assert kwargs["ranking"] == RankingCriteria.RECENCY


# ---------------------------------------------------------------------------
# Discovery errors
# ---------------------------------------------------------------------------


class TestDiscoveryErrors:

    @patch("orchestrator.pipeline.discover_repos")
    def test_github_api_error(self, mock_discover):
        mock_discover.side_effect = GitHubAPIError("rate limited", status_code=403)
        result = run_daily_pipeline(_make_config())
        assert result.success is False
        assert any("rate limited" in e for e in result.errors)

    @patch("orchestrator.pipeline.discover_repos")
    def test_no_results_error(self, mock_discover):
        mock_discover.side_effect = NoResultsError("no repos found")
        result = run_daily_pipeline(_make_config())
        assert result.success is False
        assert any("no repos found" in e for e in result.errors)


# ---------------------------------------------------------------------------
# Storage errors
# ---------------------------------------------------------------------------


class TestStorageErrors:

    @patch("orchestrator.pipeline.discover_repos")
    @patch("orchestrator.pipeline.storage.save_repo")
    def test_save_repo_failure(self, mock_save, mock_discover):
        mock_discover.return_value = [_make_repo(1), _make_repo(2), _make_repo(3)]
        mock_save.side_effect = StorageError("db write failed")
        result = run_daily_pipeline(_make_config())
        assert result.success is False
        assert len(result.errors) >= 3

    @patch("orchestrator.pipeline.send_digest", return_value=_MOCK_DELIVERY)
    @patch("orchestrator.pipeline.generate_quick_hit", return_value=_make_summary_result("Quick."))
    @patch("orchestrator.pipeline.generate_deep_dive", return_value=_make_summary_result("Deep."))
    @patch("orchestrator.pipeline.discover_repos")
    @patch("orchestrator.pipeline.storage.save_repo")
    def test_partial_save_failure(self, mock_save, mock_discover, mock_deep, mock_quick, mock_send):
        repos = [_make_repo(1), _make_repo(2), _make_repo(3)]
        mock_discover.return_value = repos

        call_count = 0

        def save_side_effect(repo):
            nonlocal call_count
            call_count += 1
            if call_count == 2:
                raise StorageError("db write failed")
            from storage.repos import save_repo as _real_save
            return _real_save(repo)

        mock_save.side_effect = save_side_effect

        with patch.dict("os.environ", _MOCK_ENV):
            result = run_daily_pipeline(_make_config())

        assert result.success is True
        assert result.repos_discovered == 3
        assert any("db write failed" in e for e in result.errors)
