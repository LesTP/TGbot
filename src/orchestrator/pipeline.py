"""
Thin daily pipeline — discover repos and persist to storage.

Implements ARCH_orchestrator.md pipeline steps 1-3 (thin orchestrator).
Steps 4-12 are added in Orchestrator Full (Phase 2).
"""

import logging
import os
from datetime import date

import storage
from discovery import discover_repos
from discovery.types import GitHubAPIError, NoResultsError
from orchestrator.ranking import get_todays_ranking
from orchestrator.types import PipelineConfig, PipelineResult
from storage.types import StorageError

logger = logging.getLogger(__name__)


def _build_storage_config() -> dict:
    """Build storage config from environment variables.

    Defaults to in-memory SQLite if DB_ENGINE is not set.
    """
    engine = os.environ.get("DB_ENGINE", "sqlite")

    if engine == "mysql":
        return {
            "engine": "mysql",
            "host": os.environ["DB_HOST"],
            "user": os.environ["DB_USER"],
            "password": os.environ["DB_PASSWORD"],
            "database": os.environ["DB_NAME"],
        }

    return {
        "engine": "sqlite",
        "database": os.environ.get("DB_PATH", ":memory:"),
    }


def run_daily_pipeline(config: PipelineConfig) -> PipelineResult:
    """Execute the thin daily pipeline: discover → persist.

    Does not raise — all errors captured in PipelineResult.errors.
    """
    errors: list[str] = []

    # Step 1: Resolve ranking
    ranking = config.ranking_criteria
    if ranking is None:
        ranking = get_todays_ranking(date.today())
    logger.info("Ranking criteria: %s", ranking.value)

    # Init storage
    try:
        storage_config = _build_storage_config()
        storage.init(storage_config)
    except (StorageError, KeyError) as e:
        msg = f"Storage init failed: {e}"
        logger.error(msg)
        return PipelineResult(
            success=False,
            repos_discovered=0,
            repos_after_dedup=0,
            summaries_generated=0,
            errors=[msg],
        )

    # Step 2: Discover repos
    try:
        token = os.environ.get("GITHUB_TOKEN")
        discovered = discover_repos(
            category=config.category,
            ranking=ranking,
            limit=config.discovery_limit,
            token=token,
        )
    except (GitHubAPIError, NoResultsError) as e:
        msg = f"Discovery failed: {e}"
        logger.error(msg)
        return PipelineResult(
            success=False,
            repos_discovered=0,
            repos_after_dedup=0,
            summaries_generated=0,
            errors=[msg],
        )

    logger.info("Discovered %d repos", len(discovered))

    # Step 3: Persist to storage
    saved_count = 0
    for repo in discovered:
        try:
            storage.save_repo(repo)
            saved_count += 1
        except StorageError as e:
            msg = f"Failed to save repo {repo.name}: {e}"
            logger.error(msg)
            errors.append(msg)

    logger.info("Persisted %d/%d repos", saved_count, len(discovered))

    return PipelineResult(
        success=saved_count > 0 or not errors,
        repos_discovered=saved_count,
        repos_after_dedup=0,
        summaries_generated=0,
        errors=errors,
    )
