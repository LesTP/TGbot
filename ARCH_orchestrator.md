# ARCH: Orchestrator

## Purpose
Coordinate the daily digest pipeline: discover repos, filter out recently featured, select candidates, generate summaries, assemble the digest, deliver to Telegram, and record feature history. Orchestrator is the only component that knows the full pipeline sequence. It is the entry point invoked by cron.

## Public API

### run_daily_pipeline
- **Signature:** `run_daily_pipeline(config: PipelineConfig) -> PipelineResult`
- **Parameters:**
  - config: PipelineConfig
    ```
    PipelineConfig:
      category: CategoryConfig              # (ARCH_discovery)
      ranking_criteria: RankingCriteria | None  # (ARCH_discovery) None = auto-rotate by day
      deep_dive_count: int                   # default 1
      quick_hit_count: int                   # default 3
      discovery_limit: int                   # how many to discover (default 20)
      cooldown_days: int                     # dedup window (default 90)
      context_lookback_days: int             # recent summaries for LLM context (default 14)
      channel_id: str                        # Telegram channel
    ```
- **Returns:** PipelineResult summarizing what happened.
  ```
  PipelineResult:
    success: bool
    repos_discovered: int
    repos_after_dedup: int
    summaries_generated: int
    delivery_result: DeliveryResult | None
    errors: list[str]
  ```
- **Errors:** Does not raise — captures all errors in PipelineResult.errors and logs them. Returns success=False if the pipeline cannot complete (e.g., no eligible repos, all summarizations fail, delivery fails).

### Pipeline Steps (internal sequence)
1. Resolve ranking: if `config.ranking_criteria` is None, call `get_todays_ranking(today)` to determine it
2. Call `Discovery.discover_repos(category, ranking, discovery_limit)` → DiscoveredRepo list (already ranked)
3. Persist each via `Storage.save_repo()` → RepoRecord list
4. Query `Storage.get_featured_repo_ids(cooldown_days)` → exclusion set
5. Filter candidates: remove recently featured from the ranked list, select top `deep_dive_count` for deep dive + next `quick_hit_count` for quick hits
6. Query `Storage.get_recent_summaries(context_lookback_days)` → recent summary context for LLM comparison/positioning
7. Call `Summarization.generate_deep_dive()` for each deep-dive candidate, passing recent summaries as context
8. Call `Summarization.generate_quick_hit()` for each quick-hit candidate (no recent context — too short to benefit)
9. Persist summaries via `Storage.save_summary()` (pass `summary_type` as str: `"deep"` or `"quick"`)
10. Assemble Digest object
11. Call `Delivery.send_digest(digest, channel_id)`
12. If delivery succeeds, call `Storage.record_feature()` for each featured repo (pass `feature_type` as str: `"deep"` or `"quick"`, `ranking_criteria` as `RankingCriteria.value`)
13. Return PipelineResult

### get_todays_ranking
- **Signature:** `get_todays_ranking(date: date) -> RankingCriteria`
- **Parameters:** date — the current date
- **Returns:** RankingCriteria based on day-of-week rotation: Monday=stars, Tuesday=activity, Wednesday=forks, Thursday=recency, Friday=subscribers. Saturday/Sunday=stars (default fallback).
- **Errors:** None.

## Cross-Module Types Used
- **CategoryConfig**, **RankingCriteria**, **DiscoveredRepo** — from ARCH_discovery
- **RepoRecord**, **SummaryRecord**, **FeatureRecord**, **StorageError** — from ARCH_storage

**New Storage dependency (Orchestrator Full):** `Storage.get_recent_summaries(since_days)` — not yet in ARCH_storage. Must be added before Orchestrator Full implementation.

**Type boundary note:** Storage accepts plain strings for `summary_type` (`"deep"` | `"quick"`), `feature_type` (`"deep"` | `"quick"`), and `ranking_criteria` (e.g. `"stars"`). Orchestrator uses Discovery's `RankingCriteria` enum internally and passes `.value` when calling Storage.

## Inputs
- PipelineConfig (from environment/config + cron invocation)
- All other modules (Discovery, Storage, Summarization, Delivery) as dependencies

## Outputs
- PipelineResult (see above)
- Side effects: repos persisted, summaries persisted, feature history recorded, Telegram message sent
- Logging: structured log output for each pipeline step (timing, counts, errors)

## State
No persistent state of its own. All state flows through Storage. Pipeline config comes from environment or config file.

## Usage Example
```python
from orchestrator import run_daily_pipeline, get_todays_ranking
from discovery.types import CategoryConfig, SeedRepo, RankingCriteria
from config import load_pipeline_config
from datetime import date

config = load_pipeline_config()
config.ranking_criteria = get_todays_ranking(date.today())

result = run_daily_pipeline(config)

if result.success:
    print(f"Pipeline complete: {result.repos_discovered} discovered, "
          f"{result.summaries_generated} summarized, delivered.")
else:
    print(f"Pipeline failed: {result.errors}")
    exit(1)
```
