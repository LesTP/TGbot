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

### Step 2 — Summarization calls (2026-03-06)

Wired summarization into the pipeline: LLM config from env vars, recent-context conversion, deep-dive generation with fallback, quick-hit generation with skip-on-failure, and summary persistence.

**New helpers (`src/orchestrator/pipeline.py`):**
- `_build_llm_config()` — reads `ANTHROPIC_API_KEY` (required), `LLM_PROVIDER` (default "anthropic"), `LLM_DEEP_DIVE_MODEL` (default "claude-sonnet-4-5-20250929"), `LLM_QUICK_HIT_MODEL` (default "claude-3-5-haiku-20241022")
- `_build_recent_context(summary_records)` — converts `list[SummaryRecord]` → `list[dict]` with keys `repo_name`, `summary_content`, `date`. Joins repo name via `storage.get_repo()`, falls back to `"repo-{id}"` if repo not found
- `_generate_deep_dive_with_fallback(candidates, remaining, config, context, errors)` — tries candidates in order, on any summarization error logs and tries next. If initial candidates exhausted, tries remaining eligible repos. Returns `(repo, SummaryResult)` or `None`
- `_generate_quick_hits(candidates, config, errors)` — generates per candidate, skips failures, returns `list[(repo, SummaryResult)]`

**Pipeline steps added:**
- Step 6: build LLM config (fails pipeline if `ANTHROPIC_API_KEY` missing)
- Step 6b: query `storage.get_recent_summaries(context_lookback_days)`, convert to dict context for deep dive. Failure here is non-fatal (warning only, context=None)
- Step 7: deep dive with fallback. All candidates fail → `success=False`
- Step 8: quick hits with skip
- Step 9: persist summaries via `storage.save_summary()`. Save failures logged but don't fail pipeline

**Tests:** 41 pipeline tests (was 22) + 5 integration tests (was 4). New test classes: `TestBuildLLMConfig` (3), `TestBuildRecentContext` (3), `TestDeepDiveFallback` (4), `TestQuickHits` (3), `TestSummarizationErrors` (5), `TestRecentContextWiring` (1). All existing tests updated to mock summarization layer. 469 total suite passing (was 449).

### Steps 3–4 — Digest assembly and delivery (2026-03-06)

Added pipeline steps 10–11: assemble `Digest` from summarization results and repo records, deliver to Telegram via `send_digest`.

**New helpers (`src/orchestrator/pipeline.py`):**
- `_build_summary_with_repo(repo, summary_content)` — maps `RepoRecord` fields + content → `SummaryWithRepo`. Reads `stars` and `created_at` from `source_metadata` with safe `.get()` defaults (0 and "" respectively)
- `_assemble_digest(deep_repo, deep_summary, quick_results, ranking_criteria)` — builds `Digest(deep_dive, quick_hits, ranking_criteria, date.today())`

**Pipeline steps added:**
- Step 10: assemble digest from deep dive + quick hit results
- Step 11: read `TELEGRAM_BOT_TOKEN` from env var, call `delivery.send_digest(digest, channel_id, bot_token)`, propagate `DeliveryResult` to `PipelineResult.delivery_result`
  - Missing bot token → `success=False`
  - `send_digest` raises → `success=False`, `DeliveryResult(success=False, error=str(e))`
  - `send_digest` returns failure → `success=False`, delivery_result preserved

**Tests:** 51 pipeline tests (was 41) + 6 integration tests (was 5). New test classes: `TestBuildSummaryWithRepo` (2), `TestAssembleDigest` (3), `TestDeliveryErrors` (3). New: `TestHappyPath.test_digest_passed_to_delivery`, integration `test_digest_structure`. All existing tests updated with `send_digest` mock. 479 total suite passing (was 469).

### Step 5 — Feature recording (2026-03-06)

After successful delivery, pipeline records all featured repos via `storage.record_feature()`. Feature recording failure is non-fatal — errors captured but pipeline stays `success=True`.

**Pipeline step added:**
- Step 12: iterate `[(deep_repo, "deep")] + [(r, "quick") for r, _ in quick_results]`, call `storage.record_feature(repo.id, feature_type, ranking.value)` for each. Tracks `recorded_count` for accurate logging: `"Recorded %d/%d featured repos"`

**Test updates:**
- 4 new tests in `TestFeatureRecording`: features recorded on success (correct count via `get_featured_repo_ids`), feature types correct (deep/quick verified via direct SQL), no features on delivery failure, recording failure still succeeds
- 4 existing `TestDedupFiltering` tests updated: first `run_daily_pipeline` now automatically records features, so dedup assertions adjusted accordingly
- Code review fix: removed dead `with patch.dict(...): pass` block in `test_old_features_not_excluded`

**Tests:** 54 pipeline tests (was 51) + 6 integration tests. 483 total suite passing (was 479).

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
