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

### Step 5 — Integration test (2026-03-06)

Created `tests/orchestrator/test_integration.py`. Mocks only HTTP layer (`search_repos`, `fetch_readme`, `fetch_seed_repos`). Real Discovery processing, real SQLite Storage, real Orchestrator wiring. 4 tests: end-to-end flow, persistence verification, filtering applied, discovery failure captured.

4 tests, 211 total suite green.

**Files created:**
- `tests/orchestrator/test_integration.py`

### Review (2026-03-06)

Code review after Step 5. Found and fixed:
- Added 4 unit tests for `_build_storage_config()` (env-var paths had zero test coverage)
- Removed dead variable (`real_save`) in `test_partial_save_failure`
- Removed unused import (`from datetime import date`) in `test_pipeline.py`

Noted but not fixed (deferred to Phase 2):
- `repos_discovered` semantics: currently reports saved count, not discovery count. Minor for thin orchestrator (no partial-pipeline path besides save failures). Revisit when full pipeline adds more stages.

215 total tests after review cleanup.

### Phase 1 Complete (2026-03-06)

All 5 steps implemented. 36 orchestrator tests, 215 total suite passing.

**Production files:**
- `src/orchestrator/__init__.py` — module exports
- `src/orchestrator/types.py` — PipelineConfig, PipelineResult
- `src/orchestrator/ranking.py` — get_todays_ranking (day-of-week rotation)
- `src/orchestrator/pipeline.py` — run_daily_pipeline (thin: discover → persist)

**Test files:**
- `tests/orchestrator/test_types.py` — 11 tests
- `tests/orchestrator/test_ranking.py` — 7 tests
- `tests/orchestrator/test_pipeline.py` — 13 tests
- `tests/orchestrator/test_integration.py` — 4 tests
- `tests/orchestrator/test_init.py` — 1 test
