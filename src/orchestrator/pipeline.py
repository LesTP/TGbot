"""
Daily pipeline — discover, persist, filter, and select candidates.

Implements ARCH_orchestrator.md pipeline steps 1-5.
Steps 6-13 are added in subsequent steps.
"""

import logging
import os
from datetime import date

import storage
from discovery import discover_repos
from discovery.types import GitHubAPIError, NoResultsError
from orchestrator.ranking import get_todays_ranking
from orchestrator.types import PipelineConfig, PipelineResult
from storage.types import RepoRecord, StorageError

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


def _select_candidates(
    saved_repos: list[RepoRecord],
    featured_ids: set[int],
    deep_dive_count: int,
    quick_hit_count: int,
) -> tuple[list[RepoRecord], list[RepoRecord]]:
    """Filter out recently featured repos and split into deep/quick pools.

    Repos are already in ranked order from Discovery. After removing
    recently featured repos, the top deep_dive_count become deep-dive
    candidates and the next quick_hit_count become quick-hit candidates.

    Returns:
        (deep_dive_candidates, quick_hit_candidates)
    """
    eligible = [r for r in saved_repos if r.id not in featured_ids]
    deep = eligible[:deep_dive_count]
    quick = eligible[deep_dive_count : deep_dive_count + quick_hit_count]
    return deep, quick


def run_daily_pipeline(config: PipelineConfig) -> PipelineResult:
    """Execute the daily pipeline: discover → persist → filter → select.

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

    # Step 3: Persist to storage (preserve order for ranked selection)
    saved_repos: list[RepoRecord] = []
    for repo in discovered:
        try:
            record = storage.save_repo(repo)
            saved_repos.append(record)
        except StorageError as e:
            msg = f"Failed to save repo {repo.name}: {e}"
            logger.error(msg)
            errors.append(msg)

    logger.info("Persisted %d/%d repos", len(saved_repos), len(discovered))

    # Step 4: Query feature history for dedup
    try:
        featured_ids = storage.get_featured_repo_ids(config.cooldown_days)
    except StorageError as e:
        msg = f"Feature history query failed: {e}"
        logger.error(msg)
        return PipelineResult(
            success=False,
            repos_discovered=len(discovered),
            repos_after_dedup=0,
            summaries_generated=0,
            errors=errors + [msg],
        )

    # Step 5: Filter candidates and select deep/quick pools
    deep_candidates, quick_candidates = _select_candidates(
        saved_repos, featured_ids, config.deep_dive_count, config.quick_hit_count
    )
    repos_after_dedup = len(
        [r for r in saved_repos if r.id not in featured_ids]
    )

    logger.info(
        "After dedup: %d eligible, %d deep candidates, %d quick candidates",
        repos_after_dedup,
        len(deep_candidates),
        len(quick_candidates),
    )

    if not deep_candidates:
        msg = "No eligible repos for deep dive after dedup filtering"
        logger.error(msg)
        return PipelineResult(
            success=False,
            repos_discovered=len(discovered),
            repos_after_dedup=repos_after_dedup,
            summaries_generated=0,
            errors=errors + [msg],
        )

    # Steps 6-13 will be added in subsequent steps.

    return PipelineResult(
        success=True,
        repos_discovered=len(discovered),
        repos_after_dedup=repos_after_dedup,
        summaries_generated=0,
        errors=errors,
    )
