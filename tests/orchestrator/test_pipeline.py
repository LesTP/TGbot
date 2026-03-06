"""Tests for run_daily_pipeline (thin) — discover and persist."""

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
from orchestrator.pipeline import _build_storage_config, run_daily_pipeline
from orchestrator.types import PipelineConfig
from storage.types import StorageError


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
# Happy path
# ---------------------------------------------------------------------------


class TestHappyPath:

    @patch("orchestrator.pipeline.discover_repos")
    def test_discovers_and_persists(self, mock_discover):
        repos = [_make_repo(1), _make_repo(2), _make_repo(3)]
        mock_discover.return_value = repos

        result = run_daily_pipeline(_make_config())

        assert result.success is True
        assert result.repos_discovered == 3
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
    def test_result_fields(self, mock_discover):
        mock_discover.return_value = [_make_repo(1)]

        result = run_daily_pipeline(_make_config())

        assert result.repos_after_dedup == 0
        assert result.summaries_generated == 0
        assert result.delivery_result is None


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
        assert result.repos_discovered == 0
        assert len(result.errors) == 3

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
            # Call the real implementation directly via the module internals
            from storage.repos import save_repo as _real_save
            return _real_save(repo)

        mock_save.side_effect = save_side_effect

        result = run_daily_pipeline(_make_config())

        assert result.success is True
        assert result.repos_discovered == 2
        assert len(result.errors) == 1
        assert "db write failed" in result.errors[0]
