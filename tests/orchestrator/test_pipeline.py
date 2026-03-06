"""Tests for run_daily_pipeline — discover, persist, dedup, select."""

from datetime import date, timedelta
from unittest.mock import patch

import pytest

import storage
from discovery.types import (
    CategoryConfig,
    DiscoveredRepo,
    GitHubAPIError,
    NoResultsError,
    RankingCriteria,
)
from orchestrator.pipeline import _build_storage_config, _select_candidates, run_daily_pipeline
from orchestrator.types import PipelineConfig
from storage.types import RepoRecord, StorageError


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


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
    from datetime import datetime

    defaults = dict(
        id=id,
        source="github",
        source_id=str(id),
        name=f"owner/repo-{id}",
        url=f"https://github.com/owner/repo-{id}",
        description=f"Repo {id}",
        raw_content=f"# Repo {id}\nREADME content",
        source_metadata={"stars": 100 + id},
        discovered_at=datetime(2025, 6, 1),
    )
    defaults.update(overrides)
    return RepoRecord(**defaults)


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
# Happy path (with dedup)
# ---------------------------------------------------------------------------


class TestHappyPath:

    @patch("orchestrator.pipeline.discover_repos")
    def test_discovers_persists_and_selects(self, mock_discover):
        repos = [_make_repo(i) for i in range(1, 8)]
        mock_discover.return_value = repos

        result = run_daily_pipeline(_make_config())

        assert result.success is True
        assert result.repos_discovered == 7
        assert result.repos_after_dedup == 7
        assert result.errors == []

    @patch("orchestrator.pipeline.discover_repos")
    def test_repos_actually_in_storage(self, mock_discover):
        repos = [_make_repo(1)]
        mock_discover.return_value = repos

        run_daily_pipeline(_make_config())

        record = storage.get_repo(1)
        assert record is not None
        assert record.name == "owner/repo-1"

    @patch("orchestrator.pipeline.discover_repos")
    def test_result_fields_with_no_further_steps(self, mock_discover):
        mock_discover.return_value = [_make_repo(i) for i in range(1, 6)]

        result = run_daily_pipeline(_make_config())

        assert result.repos_discovered == 5
        assert result.repos_after_dedup == 5
        assert result.summaries_generated == 0
        assert result.delivery_result is None


# ---------------------------------------------------------------------------
# Dedup filtering (end-to-end through pipeline)
# ---------------------------------------------------------------------------


class TestDedupFiltering:

    @patch("orchestrator.pipeline.discover_repos")
    def test_recently_featured_filtered(self, mock_discover):
        """Repos featured within cooldown window are excluded."""
        repos = [_make_repo(i) for i in range(1, 6)]
        mock_discover.return_value = repos

        result1 = run_daily_pipeline(_make_config())
        assert result1.success is True

        # Feature repos 1, 2, 3 (within default 90-day window)
        _feature_repo(1, days_ago=5)
        _feature_repo(2, days_ago=10)
        _feature_repo(3, days_ago=20)

        # Second run — same repos discovered, but 3 are featured
        result2 = run_daily_pipeline(_make_config())
        assert result2.repos_discovered == 5
        assert result2.repos_after_dedup == 2

    @patch("orchestrator.pipeline.discover_repos")
    def test_all_repos_featured_fails(self, mock_discover):
        """Pipeline fails when all discovered repos are recently featured."""
        repos = [_make_repo(i) for i in range(1, 4)]
        mock_discover.return_value = repos

        run_daily_pipeline(_make_config())

        # Feature all repos
        _feature_repo(1, days_ago=5)
        _feature_repo(2, days_ago=10)
        _feature_repo(3, days_ago=20)

        result = run_daily_pipeline(_make_config())
        assert result.success is False
        assert result.repos_after_dedup == 0
        assert any("No eligible" in e for e in result.errors)

    @patch("orchestrator.pipeline.discover_repos")
    def test_old_features_not_excluded(self, mock_discover):
        """Repos featured outside cooldown window are eligible."""
        repos = [_make_repo(i) for i in range(1, 4)]
        mock_discover.return_value = repos

        run_daily_pipeline(_make_config(cooldown_days=90))

        # Feature repo 1 long ago (outside 90-day window)
        _feature_repo(1, days_ago=100)

        result = run_daily_pipeline(_make_config(cooldown_days=90))
        assert result.repos_after_dedup == 3

    @patch("orchestrator.pipeline.discover_repos")
    def test_repos_after_dedup_count_correct(self, mock_discover):
        """repos_after_dedup reflects total eligible, not just selected."""
        repos = [_make_repo(i) for i in range(1, 11)]
        mock_discover.return_value = repos

        run_daily_pipeline(_make_config())

        # Feature 3 repos
        _feature_repo(1, days_ago=5)
        _feature_repo(2, days_ago=10)
        _feature_repo(3, days_ago=20)

        result = run_daily_pipeline(_make_config())
        # 10 discovered, 3 featured = 7 eligible
        assert result.repos_after_dedup == 7


# ---------------------------------------------------------------------------
# Ranking resolution
# ---------------------------------------------------------------------------


class TestRankingResolution:

    @patch("orchestrator.pipeline.discover_repos")
    def test_explicit_ranking_passed_through(self, mock_discover):
        mock_discover.return_value = [_make_repo(1)]

        run_daily_pipeline(_make_config(ranking_criteria=RankingCriteria.FORKS))

        _, kwargs = mock_discover.call_args
        assert kwargs["ranking"] == RankingCriteria.FORKS

    @patch("orchestrator.pipeline.discover_repos")
    @patch("orchestrator.pipeline.get_todays_ranking")
    def test_none_ranking_auto_resolves(self, mock_ranking, mock_discover):
        mock_ranking.return_value = RankingCriteria.RECENCY
        mock_discover.return_value = [_make_repo(1)]

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
        assert result.repos_discovered == 0
        assert any("rate limited" in e for e in result.errors)

    @patch("orchestrator.pipeline.discover_repos")
    def test_no_results_error(self, mock_discover):
        mock_discover.side_effect = NoResultsError("no repos found")

        result = run_daily_pipeline(_make_config())

        assert result.success is False
        assert result.repos_discovered == 0
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

    @patch("orchestrator.pipeline.discover_repos")
    @patch("orchestrator.pipeline.storage.save_repo")
    def test_partial_save_failure(self, mock_save, mock_discover):
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

        result = run_daily_pipeline(_make_config())

        assert result.success is True
        assert result.repos_discovered == 3
        assert len(result.errors) == 1
        assert "db write failed" in result.errors[0]
