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
- `_build_llm_config()` — reads `ANTHROPIC_API_KEY` (required), `LLM_PROVIDER` (default "anthropic"), `LLM_DEEP_DIVE_MODEL` (default "claude-sonnet-4-5-20250929"), `LLM_QUICK_HIT_MODEL` (default "claude-haiku-4-5-20251001")
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

### Step 5b — Tiered cooldown (2026-03-07)

Implemented tiered cooldown: deep dives block all features for 90 days, quick hits block quick-hit re-featuring for 30 days but only block deep-dive promotion for 7 days. Allows high-quality repos to "promote" from a brief quick-hit mention to a full deep-dive analysis.

**Storage change (`src/storage/history.py`):**
- `get_featured_repo_ids` gains optional `feature_type: str | None = None` parameter
- When provided, adds `AND feature_type = ?` to SQL WHERE clause
- Backward-compatible: `None` returns all types (existing behavior unchanged)

**PipelineConfig change (`src/orchestrator/types.py`):**
- Added `quick_hit_cooldown_days: int = 30` and `promotion_gap_days: int = 7`

**Pipeline change (`src/orchestrator/pipeline.py`):**
- Step 4 now makes three `get_featured_repo_ids` calls with `feature_type` filter:
  - `(cooldown_days, "deep")` → deep exclusion set
  - `(quick_hit_cooldown_days, "quick")` → quick exclusion set
  - `(promotion_gap_days, "quick")` → promotion gap set
- Combines into per-pool exclusion: `deep_excluded = deep_featured ∪ promotion_blocked`, `quick_excluded = deep_featured ∪ quick_cooldown`
- `_select_candidates` signature changed from single `featured_ids` to `deep_excluded, quick_excluded` sets. Pools filter independently; repos selected for deep dive excluded from quick pool.
- `repos_after_dedup` reports union of both pools' eligible repos

**Tests:**
- Storage: 7 new in `TestFeatureTypeFilter` (None/deep/quick filters, window+filter combo, both types, no matches, full tiered scenario)
- Orchestrator types: updated defaults + overrides tests for new config fields
- `TestSelectCandidates`: 5 updated for new signature + 2 new (tiered exclusion, deep excludes from quick)
- `TestDedupFiltering`: 4 updated for tiered behavior
- `TestTieredCooldown`: 5 new end-to-end (promotion gap blocks, promotion works, quick cooldown expires, deep blocks both, custom values)

**Tests:** 61 pipeline tests (was 54) + 6 integration. 497 total suite passing (was 490).

### Contract Changes
- **ARCH_storage.md** — `get_featured_repo_ids` gains `feature_type` parameter
- **ARCH_orchestrator.md** — `PipelineConfig` gains `quick_hit_cooldown_days`, `promotion_gap_days`; pipeline steps 4-5 updated; tiered cooldown note added
- **ARCHITECTURE.md** — Provisional Contracts updated with tiered cooldown description

### Step 6 — End-to-end integration test (2026-03-07)

Added 6 comprehensive integration tests verifying the full pipeline with real SQLite storage and real internal wiring. Mocks only HTTP boundaries (GitHub API, Anthropic API, Telegram API).

**New test class: `TestFullPipelineEndToEnd` (`tests/orchestrator/test_integration.py`):**
- `test_full_pipeline_all_steps` — verifies every pipeline step executed: repos persisted in DB, summaries persisted with correct types, delivery called with correct Digest, features recorded
- `test_pipeline_result_counts` — all PipelineResult fields have correct values (repos_discovered, repos_after_dedup, summaries_generated, delivery_result)
- `test_second_run_deep_dive_excluded_from_both_pools` — two pipeline runs, deep-dived repo from run 1 excluded from both deep and quick pools in run 2
- `test_second_run_quick_hit_excluded_from_quick_pool` — quick-hit repos from run 1 excluded from quick pool in run 2, no overlap between runs
- `test_tiered_cooldown_promotion` — backdates run-1 features to 10 days ago, verifies quick-hit repos become eligible for deep dive (past 7-day promotion gap), while deep-dived repo stays excluded (within 90-day cooldown)
- `test_tiered_cooldown_promotion_blocked_within_gap` — two immediate runs (same day), quick-hit repos still within promotion gap so NOT eligible for deep dive; deep dive falls through to unfeatured repos

**Helpers added:**
- `_make_config(**overrides)` — builds PipelineConfig with test defaults, reduces boilerplate
- `_backdate_feature(repo_id, feature_type, days_ago)` — inserts backdated feature_history record via direct SQL for simulating passage of time

**Tests:** 12 integration tests (was 6), 503 total suite passing (was 497).

### Step 7 — Review and cleanup (2026-03-07)

Code review and cleanup to close Phase 2.

**`repos_discovered` semantics:** Already fixed in Step 1 (`len(discovered)` instead of saved count). No change needed.

**Type fix (`src/orchestrator/types.py`):**
- Replaced `delivery_result: Any = None` with `delivery_result: Optional[DeliveryResult] = None`
- Removed `Any` import, added `from delivery.types import DeliveryResult`

**Dead code removal (`src/orchestrator/pipeline.py`):**
- Removed unused imports: `TelegramAPIError`, `MessageTooLongError`
- Simplified `except (MessageTooLongError, Exception)` → `except Exception` (redundant — `MessageTooLongError` is a subclass of `Exception`)

**Exports verified:** `orchestrator/__init__.py` exports all 4 public names, no new public names added in Phase 2. All pipeline helpers are `_` prefixed (private).

**Logging verified:** All 12 pipeline steps have appropriate logging (info for normal flow, error for failures, warning for non-fatal issues).

**Tests:** 503 total suite passing (unchanged — cleanup only).

---

## Phase 3: Production Deployment (2026-03-08)

### Quick-hit model fix

**What was done:**
- Default `LLM_QUICK_HIT_MODEL` in `_build_llm_config()` changed from `claude-3-5-haiku-20241022` to `claude-haiku-4-5-20251001`. The old model returned HTTP 404 from Anthropic's API — it was not available on the production account (verified via `models.json`).

**Test count:** 1 test updated (`test_defaults_for_optional_vars`), 570 total passing.

### Production entry point and deployment

**What was done:**
- Created `run_daily.py` — production entry point. Inserts `src/` into `sys.path`, loads `.env` via `python-dotenv`, configures dual logging (file + stderr), runs `run_daily_pipeline()` with `CategoryConfig` for "agentic-coding" category, `channel_id="@github_discovery"`.
- Created `run_cron.sh` on server — shell wrapper for web UI cron scheduler. Sets working directory and invokes venv Python.
- Created `.gitignore` — protects `.env`, `__pycache__/`, `data/*.db`, `data/*.log`, `venv/`.
- Fixed `.env`: uncommented `DB_ENGINE=sqlite` and `DB_PATH=...` — without these, pipeline defaulted to in-memory SQLite, losing all dedup/cooldown history.
- Deployed to `s501.sureserver.com:/home/mikey/private/tgbot/`.
- Cron: `1 6 * * *` (06:01 EDT = 10:01 UTC daily).

### Deployment gotchas (documented in DEPLOY.md)
- Windows SCP doesn't expand `~` — use absolute paths
- `scp -r src/ host:path/src/` creates nested `src/src/` — upload to parent instead
- CRLF line endings from Windows corrupt `.env` keys and shebangs — `sed -i 's/\r$//'`
- `chmod 775` required for cron scripts
- Server timezone is EDT (UTC-4), not UTC
- Full hostname `s501.sureserver.com` required (not just `s501`)

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
