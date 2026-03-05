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
      category: CategoryConfig        # from Discovery contract
      ranking_criteria: str            # today's ranking (or auto-rotate)
      deep_dive_count: int             # default 1
      quick_hit_count: int             # default 3
      discovery_limit: int             # how many to discover (default 20)
      cooldown_days: int               # dedup window (default 90)
      channel_id: str                  # Telegram channel
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
1. Call `Discovery.discover_repos(category, ranking, limit)` → DiscoveredRepo list
2. Persist each via `Storage.save_repo()` → RepoRecord list
3. Query `Storage.get_featured_repo_ids(cooldown_days)` → exclusion set
4. Filter candidates: remove recently featured, select top 1 for deep dive + top 3 for quick hits
5. Call `Summarization.generate_deep_dive()` for the deep-dive candidate
6. Call `Summarization.generate_quick_hit()` for each quick-hit candidate
7. Persist summaries via `Storage.save_summary()`
8. Assemble Digest object
9. Call `Delivery.send_digest(digest, channel_id)`
10. If delivery succeeds, call `Storage.record_feature()` for each featured repo
11. Return PipelineResult

### get_todays_ranking
- **Signature:** `get_todays_ranking(date: date) -> str`
- **Parameters:** date — the current date
- **Returns:** Ranking criteria string based on day-of-week rotation: Monday=stars, Tuesday=activity, Wednesday=forks, Thursday=recency, Friday=subscribers. Saturday/Sunday=stars (default fallback).
- **Errors:** None.

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
# main.py — the cron entry point
from orchestrator import run_daily_pipeline, get_todays_ranking
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
    # Exit with non-zero for cron alerting
    exit(1)
```
