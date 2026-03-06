# DEVPLAN: Orchestrator

## Cold Start Summary

**What this is:** Orchestrator module — coordinates the daily digest pipeline. Entry point for cron. Wires Discovery → Storage → Summarization → Delivery. Only component that knows the full pipeline sequence.

**Key constraints:**
- Orchestrator never raises — all errors captured in `PipelineResult.errors`, returns `success=False`.
- Storage accepts plain strings for `summary_type`, `feature_type`, `ranking_criteria`. Orchestrator uses Discovery's `RankingCriteria` enum internally and passes `.value` at the Storage boundary.
- Config via environment variables for now (DB config, GITHUB_TOKEN). Revisit after Orchestrator Full — extract to a config module if the shape is stable.
- Tests mock Discovery (HTTP layer), use real SQLite Storage.

**Gotchas:**
- (none yet)

## Current Status

**Phase:** 1 — Thin Orchestrator
**Focus:** Wire Discovery → Storage. First working pipeline segment.
**Blocked/Broken:** Nothing

---

## Phase 1: Thin Orchestrator (Build)

Implements ARCHITECTURE.md step 3: "Wire Discovery → Storage. First working pipeline segment — discover and persist repos."

Covers ARCH_orchestrator.md pipeline steps 1–3 only. Steps 4–12 belong to Phase 2 (Orchestrator Full, ARCHITECTURE.md step 6).

### Step 1 — Types

`src/orchestrator/types.py`

Define `PipelineConfig` and `PipelineResult` dataclasses matching ARCH_orchestrator.md.

**Tests** (`tests/orchestrator/test_types.py`):
- PipelineConfig defaults: deep_dive_count=1, quick_hit_count=3, discovery_limit=20, cooldown_days=90
- PipelineConfig requires category and channel_id (no defaults for these)
- PipelineResult constructable with all fields
- ranking_criteria=None is valid (auto-rotate)

### Step 2 — get_todays_ranking

`src/orchestrator/ranking.py`

Pure function: `date → RankingCriteria`. Day-of-week mapping per ARCH spec.

**Tests** (`tests/orchestrator/test_ranking.py`):
- Monday→STARS, Tuesday→ACTIVITY, Wednesday→FORKS, Thursday→RECENCY, Friday→SUBSCRIBERS
- Saturday→STARS, Sunday→STARS
- All 7 days parametrized

### Step 3 — run_daily_pipeline (thin)

`src/orchestrator/pipeline.py`

Sequence:
1. Resolve ranking: if None, call get_todays_ranking(today)
2. Init Storage from env vars (DB_ENGINE, DB_HOST, DB_USER, DB_PASSWORD, DB_NAME — or SQLite defaults)
3. Call discover_repos(category, ranking, limit, token from env)
4. Loop: save_repo() for each DiscoveredRepo
5. Return PipelineResult(success=True, repos_discovered=N, repos_after_dedup=0, summaries_generated=0, delivery_result=None)
6. On any error: return PipelineResult(success=False, errors=[...])

**Tests** (`tests/orchestrator/test_pipeline.py`, mock Discovery, real SQLite Storage):
- Happy path: 3 discovered repos → 3 persisted → success=True, repos_discovered=3
- Discovery raises GitHubAPIError → success=False, error message captured
- Discovery raises NoResultsError → success=False, error message captured
- Storage raises StorageError → success=False, error message captured
- ranking_criteria=None → auto-resolves via get_todays_ranking
- ranking_criteria=RankingCriteria.FORKS → passed through to Discovery

### Step 4 — Module wiring

`src/orchestrator/__init__.py`

Export: run_daily_pipeline, get_todays_ranking, PipelineConfig, PipelineResult.

**Tests** (`tests/orchestrator/test_init.py`):
- Import smoke test: all 4 names importable from `orchestrator`

### Step 5 — Integration test

`tests/orchestrator/test_integration.py`

Mock only HTTP (requests layer). Real Discovery processing, real SQLite Storage. Verify: mock API responses → Discovery finds repos → Storage persists them → PipelineResult reflects correct counts.

---

## Phase 2: Orchestrator Full (Build) — PLANNED

ARCHITECTURE.md step 6. Adds pipeline steps 4–12: dedup filtering, ranking rotation, candidate selection, summarization calls, digest assembly, delivery, feature history recording.

**Prerequisite:** Summarization and Delivery modules implemented (ARCHITECTURE.md steps 4–5).

**Deferred decision:** Extract environment-variable config reading into a dedicated config module. Revisit when the full pipeline shape is clear and all env vars are known.
