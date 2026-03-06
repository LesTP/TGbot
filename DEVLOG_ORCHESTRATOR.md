# DEVLOG: Orchestrator

## Phase 2: Orchestrator Full (Build)

### Step 0 — Prerequisites (2026-03-06)

Added `get_recent_summaries` to Storage and `context_lookback_days` to PipelineConfig — prerequisites for the full pipeline's recent-context feature.

**Storage addition:**
- `get_recent_summaries(since_days: int = 14) -> list[SummaryRecord]` in `src/storage/summaries.py`
- Engine-aware SQL: SQLite uses `datetime('now', '-N days')`, MySQL uses `NOW() - INTERVAL N DAY`
- Returns summaries within lookback window, ordered `generated_at` DESC (newest first)
- Exported from `storage/__init__.py`, added to `__all__`

**PipelineConfig update:**
- Added `context_lookback_days: int = 14` to `src/orchestrator/types.py`

**Tests:** 7 new tests in `TestGetRecentSummaries` — empty list, within window, outside window, mixed, ordering, default window, multiple repos. 440 total suite passing (was 433).

### Contract Changes
- **ARCH_storage.md** — added `get_recent_summaries` function contract (new public API)

### Step 1 — Dedup filtering and candidate selection (2026-03-06)

Added pipeline steps 4–5: query feature history, filter recently featured repos, split eligible repos into deep-dive and quick-hit candidate pools.

**Pipeline changes (`src/orchestrator/pipeline.py`):**
- Added `_select_candidates(saved_repos, featured_ids, deep_dive_count, quick_hit_count)` — filters out recently featured repos, splits remainder into deep/quick pools preserving Discovery's ranked order
- Step 4: query `storage.get_featured_repo_ids(config.cooldown_days)` for exclusion set
- Step 5: filter and select candidates; pipeline returns `success=False` if no deep-dive candidates remain
- Fixed `repos_discovered` to report `len(discovered)` instead of saved count (resolved Phase 1 deferred item)
- `repos_after_dedup` now reports actual eligible count
- Step 3 tracks `saved_repos` as `list[RepoRecord]` (was just a count) to feed candidate selection

**Tests (`tests/orchestrator/test_pipeline.py`):**
- 5 unit tests for `_select_candidates`: no featured, featured excluded, all featured empty, fewer than requested, preserves ranked order
- 4 end-to-end dedup tests: recently featured filtered, all featured fails pipeline, old features not excluded, repos_after_dedup count correct
- Updated happy-path tests for new `repos_discovered` semantics
- Updated integration test (`repos_after_dedup` now reflects real dedup)

**Tests:** 22 pipeline tests (was 13), 449 total suite passing (was 440).

---

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
