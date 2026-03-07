"""
Daily pipeline — full end-to-end: discover, persist, filter, select,
summarize, assemble, deliver, and record features.

Implements ARCH_orchestrator.md pipeline steps 1-12.
Step 13 (review/cleanup) is a non-code step.
"""

import logging
import os
from datetime import date

import storage
from delivery import send_digest
from delivery.types import (
    DeliveryResult,
    Digest,
    SummaryWithRepo,
)
from discovery import discover_repos
from discovery.types import GitHubAPIError, NoResultsError
from orchestrator.ranking import get_todays_ranking
from orchestrator.types import PipelineConfig, PipelineResult
from storage.types import RepoRecord, StorageError, SummaryRecord
from summarization import generate_deep_dive, generate_quick_hit
from summarization.types import (
    InsufficientContentError,
    LLMAPIError,
    LLMConfig,
    LLMResponseError,
    SummaryResult,
)

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


def _build_llm_config() -> LLMConfig:
    """Build LLM config from environment variables."""
    return LLMConfig(
        provider=os.environ.get("LLM_PROVIDER", "anthropic"),
        api_key=os.environ["ANTHROPIC_API_KEY"],
        deep_dive_model=os.environ.get("LLM_DEEP_DIVE_MODEL", "claude-sonnet-4-5-20250929"),
        quick_hit_model=os.environ.get("LLM_QUICK_HIT_MODEL", "claude-3-5-haiku-20241022"),
    )


def _build_recent_context(summary_records: list[SummaryRecord]) -> list[dict]:
    """Convert SummaryRecords to the dict shape expected by generate_deep_dive.

    Shape: {"repo_name": str, "summary_content": str, "date": str}
    Orchestrator joins repo name by querying Storage.
    """
    context = []
    for sr in summary_records:
        repo = storage.get_repo(sr.repo_id)
        repo_name = repo.name if repo else f"repo-{sr.repo_id}"
        context.append({
            "repo_name": repo_name,
            "summary_content": sr.content,
            "date": sr.generated_at.strftime("%Y-%m-%d"),
        })
    return context


def _select_candidates(
    saved_repos: list[RepoRecord],
    deep_excluded: set[int],
    quick_excluded: set[int],
    deep_dive_count: int,
    quick_hit_count: int,
) -> tuple[list[RepoRecord], list[RepoRecord]]:
    """Filter repos with tiered cooldown and split into deep/quick pools.

    Repos are already in ranked order from Discovery. Each pool has its
    own exclusion set (tiered cooldown):
      - deep pool: excludes repos deep-dived within cooldown_days OR
        quick-hit within promotion_gap_days
      - quick pool: excludes repos deep-dived within cooldown_days OR
        quick-hit within quick_hit_cooldown_days

    A repo may appear in the deep pool even if excluded from the quick pool
    (the promotion path: quick-hit 8+ days ago → eligible for deep dive).

    Returns:
        (deep_dive_candidates, quick_hit_candidates)
    """
    deep_eligible = [r for r in saved_repos if r.id not in deep_excluded]
    quick_eligible = [r for r in saved_repos if r.id not in quick_excluded]

    deep = deep_eligible[:deep_dive_count]

    # Quick pool excludes repos already selected for deep dive
    deep_ids = {r.id for r in deep}
    quick_pool = [r for r in quick_eligible if r.id not in deep_ids]
    quick = quick_pool[:quick_hit_count]

    return deep, quick


def _generate_deep_dive_with_fallback(
    candidates: list[RepoRecord],
    remaining_eligible: list[RepoRecord],
    llm_config: LLMConfig,
    recent_context: list[dict] | None,
    errors: list[str],
) -> tuple[RepoRecord, SummaryResult] | None:
    """Try deep-dive generation on candidates, falling back through the list.

    If all initial candidates fail, tries remaining eligible repos.

    Returns:
        (repo, summary_result) on success, None if all candidates exhausted.
    """
    all_candidates = list(candidates)
    for repo in remaining_eligible:
        if repo not in all_candidates:
            all_candidates.append(repo)

    for repo in all_candidates:
        try:
            result = generate_deep_dive(repo, llm_config, recent_context)
            return repo, result
        except (LLMAPIError, LLMResponseError, InsufficientContentError) as e:
            msg = f"Deep dive failed for {repo.name}: {e}"
            logger.warning(msg)
            errors.append(msg)

    return None


def _generate_quick_hits(
    candidates: list[RepoRecord],
    llm_config: LLMConfig,
    errors: list[str],
) -> list[tuple[RepoRecord, SummaryResult]]:
    """Generate quick hits, skipping failures.

    Returns:
        List of (repo, summary_result) for successful generations.
    """
    results = []
    for repo in candidates:
        try:
            result = generate_quick_hit(repo, llm_config)
            results.append((repo, result))
        except (LLMAPIError, LLMResponseError, InsufficientContentError) as e:
            msg = f"Quick hit failed for {repo.name}: {e}"
            logger.warning(msg)
            errors.append(msg)
    return results


def _build_summary_with_repo(repo: RepoRecord, summary_content: str) -> SummaryWithRepo:
    """Build a SummaryWithRepo from a RepoRecord and summary text."""
    return SummaryWithRepo(
        summary_content=summary_content,
        repo_name=repo.name,
        repo_url=repo.url,
        stars=repo.source_metadata.get("stars", 0),
        created_at=repo.source_metadata.get("created_at", ""),
    )


def _assemble_digest(
    deep_repo: RepoRecord,
    deep_summary: SummaryResult,
    quick_results: list[tuple[RepoRecord, SummaryResult]],
    ranking_criteria: str,
) -> Digest:
    """Assemble a Digest from summarization results and repo records."""
    deep_dive = _build_summary_with_repo(deep_repo, deep_summary.content)
    quick_hits = [
        _build_summary_with_repo(repo, summary.content)
        for repo, summary in quick_results
    ]
    return Digest(
        deep_dive=deep_dive,
        quick_hits=quick_hits,
        ranking_criteria=ranking_criteria,
        date=date.today(),
    )


def run_daily_pipeline(config: PipelineConfig) -> PipelineResult:
    """Execute the daily pipeline: discover → persist → dedup → select →
    summarize → assemble → deliver → record features.

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

    # Step 4: Query feature history for tiered cooldown
    try:
        deep_featured = storage.get_featured_repo_ids(
            config.cooldown_days, feature_type="deep"
        )
        quick_cooldown = storage.get_featured_repo_ids(
            config.quick_hit_cooldown_days, feature_type="quick"
        )
        promotion_blocked = storage.get_featured_repo_ids(
            config.promotion_gap_days, feature_type="quick"
        )
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

    deep_excluded = deep_featured | promotion_blocked
    quick_excluded = deep_featured | quick_cooldown

    # Step 5: Filter candidates and select deep/quick pools
    deep_candidates, quick_candidates = _select_candidates(
        saved_repos, deep_excluded, quick_excluded,
        config.deep_dive_count, config.quick_hit_count,
    )
    all_deep_eligible = [r for r in saved_repos if r.id not in deep_excluded]
    all_quick_eligible = [r for r in saved_repos if r.id not in quick_excluded]
    all_eligible_ids = {r.id for r in all_deep_eligible} | {r.id for r in all_quick_eligible}
    repos_after_dedup = len(all_eligible_ids)

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

    # Step 6: Build LLM config
    try:
        llm_config = _build_llm_config()
    except KeyError as e:
        msg = f"LLM config missing: {e}"
        logger.error(msg)
        return PipelineResult(
            success=False,
            repos_discovered=len(discovered),
            repos_after_dedup=repos_after_dedup,
            summaries_generated=0,
            errors=errors + [msg],
        )

    # Query recent summaries for deep-dive context
    recent_context = None
    try:
        recent_records = storage.get_recent_summaries(config.context_lookback_days)
        if recent_records:
            recent_context = _build_recent_context(recent_records)
    except StorageError as e:
        logger.warning("Failed to fetch recent summaries for context: %s", e)

    # Step 7: Generate deep dive (with fallback)
    remaining_eligible = [r for r in all_deep_eligible if r not in deep_candidates]
    deep_result = _generate_deep_dive_with_fallback(
        deep_candidates, remaining_eligible, llm_config, recent_context, errors
    )

    if deep_result is None:
        msg = "All deep dive candidates failed summarization"
        logger.error(msg)
        return PipelineResult(
            success=False,
            repos_discovered=len(discovered),
            repos_after_dedup=repos_after_dedup,
            summaries_generated=0,
            errors=errors + [msg],
        )

    deep_repo, deep_summary = deep_result
    summaries_generated = 1

    # Step 8: Generate quick hits (skip failures)
    quick_results = _generate_quick_hits(quick_candidates, llm_config, errors)
    summaries_generated += len(quick_results)

    logger.info("Generated %d summaries (1 deep + %d quick)", summaries_generated, len(quick_results))

    # Step 9: Persist summaries
    try:
        storage.save_summary(deep_repo.id, "deep", deep_summary.content, deep_summary.model_used)
    except StorageError as e:
        msg = f"Failed to save deep dive summary: {e}"
        logger.error(msg)
        errors.append(msg)

    for repo, summary in quick_results:
        try:
            storage.save_summary(repo.id, "quick", summary.content, summary.model_used)
        except StorageError as e:
            msg = f"Failed to save quick hit summary for {repo.name}: {e}"
            logger.error(msg)
            errors.append(msg)

    # Step 10: Assemble digest
    digest = _assemble_digest(deep_repo, deep_summary, quick_results, ranking.value)

    logger.info(
        "Assembled digest: 1 deep dive + %d quick hits",
        len(digest.quick_hits),
    )

    # Step 11: Deliver to Telegram
    bot_token = os.environ.get("TELEGRAM_BOT_TOKEN")
    if not bot_token:
        msg = "TELEGRAM_BOT_TOKEN not set"
        logger.error(msg)
        return PipelineResult(
            success=False,
            repos_discovered=len(discovered),
            repos_after_dedup=repos_after_dedup,
            summaries_generated=summaries_generated,
            errors=errors + [msg],
        )

    try:
        delivery_result = send_digest(digest, config.channel_id, bot_token)
    except Exception as e:
        msg = f"Delivery failed: {e}"
        logger.error(msg)
        return PipelineResult(
            success=False,
            repos_discovered=len(discovered),
            repos_after_dedup=repos_after_dedup,
            summaries_generated=summaries_generated,
            delivery_result=DeliveryResult(success=False, error=str(e)),
            errors=errors + [msg],
        )

    if not delivery_result.success:
        msg = f"Delivery failed: {delivery_result.error}"
        logger.error(msg)
        return PipelineResult(
            success=False,
            repos_discovered=len(discovered),
            repos_after_dedup=repos_after_dedup,
            summaries_generated=summaries_generated,
            delivery_result=delivery_result,
            errors=errors + [msg],
        )

    logger.info("Delivered to %s (message %s)", config.channel_id, delivery_result.message_id)

    # Step 12: Record featured repos
    featured_repos = [(deep_repo, "deep")] + [(r, "quick") for r, _ in quick_results]
    recorded_count = 0
    for repo, feature_type in featured_repos:
        try:
            storage.record_feature(repo.id, feature_type, ranking.value)
            recorded_count += 1
        except StorageError as e:
            msg = f"Failed to record feature for {repo.name}: {e}"
            logger.error(msg)
            errors.append(msg)

    logger.info("Recorded %d/%d featured repos", recorded_count, len(featured_repos))

    return PipelineResult(
        success=True,
        repos_discovered=len(discovered),
        repos_after_dedup=repos_after_dedup,
        summaries_generated=summaries_generated,
        delivery_result=delivery_result,
        errors=errors,
    )
