# DEVLOG: Orchestrator

## Phase 1: Thin Orchestrator (Build)

### Step 1 — Types (2026-03-06)

Created `src/orchestrator/types.py` with `PipelineConfig` and `PipelineResult` dataclasses. Set up package structure (`src/orchestrator/__init__.py`, `tests/orchestrator/__init__.py`).

`PipelineConfig`: category and channel_id required (no defaults), all others have defaults matching ARCH spec. `ranking_criteria` is `Optional[RankingCriteria]`, defaults to None (auto-rotate).

`PipelineResult`: `delivery_result` typed as `Any` with a comment referencing ARCH_delivery — avoids creating a placeholder type for an unwritten module. `errors` uses `field(default_factory=list)` to prevent shared mutable default.

11 tests, all passing. 190 total suite green.

**Files created:**
- `src/orchestrator/__init__.py`
- `src/orchestrator/types.py`
- `tests/orchestrator/__init__.py`
- `tests/orchestrator/test_types.py`

### Step 2 — get_todays_ranking (2026-03-06)

Created `src/orchestrator/ranking.py` with `get_todays_ranking(date) → RankingCriteria`. Dict lookup keyed by `date.weekday()`. Mon=STARS, Tue=ACTIVITY, Wed=FORKS, Thu=RECENCY, Fri=SUBSCRIBERS, Sat/Sun=STARS.

7 parametrized tests, all passing. 197 total suite green.

**Files created:**
- `src/orchestrator/ranking.py`
- `tests/orchestrator/test_ranking.py`

### Step 3 — run_daily_pipeline thin (2026-03-06)

Created `src/orchestrator/pipeline.py` with `run_daily_pipeline` and `_build_storage_config`. Thin pipeline: resolve ranking → init storage → discover → persist → return PipelineResult.

Storage init reads env vars (DB_ENGINE, DB_HOST, etc.), defaults to in-memory SQLite. GitHub token from GITHUB_TOKEN env var. Storage init happens inside the pipeline (self-contained); revisit when config module is extracted.

Partial save failure: `success=True` when at least one repo saved. Errors logged per-repo.

**Issue:** Partial-failure test initially caused infinite recursion — mock on `storage.save_repo` intercepted the real call inside the side_effect. Fixed by importing directly from `storage.repos`.

9 tests, all passing. 206 total suite green.

**Files created:**
- `src/orchestrator/pipeline.py`
- `tests/orchestrator/test_pipeline.py`

### Step 4 — Module wiring (2026-03-06)

Wired `src/orchestrator/__init__.py` with exports: `run_daily_pipeline`, `get_todays_ranking`, `PipelineConfig`, `PipelineResult`. Added `__all__`. Import smoke test confirms all 4 names importable.

1 test, 207 total suite green.

**Files modified/created:**
- `src/orchestrator/__init__.py`
- `tests/orchestrator/test_init.py`
