# DEVPLAN: Orchestrator

## Cold Start Summary

**What this is:** Orchestrator module — coordinates the daily digest pipeline. Entry point for cron. Wires Discovery → Storage → Summarization → Delivery. Only component that knows the full pipeline sequence. Public API: `run_daily_pipeline(PipelineConfig) → PipelineResult`, `get_todays_ranking(date) → RankingCriteria`.

**Key constraints:**
- Orchestrator never raises — all errors captured in `PipelineResult.errors`, returns `success=False`.
- Storage accepts plain strings for `summary_type`, `feature_type`, `ranking_criteria`. Orchestrator uses Discovery's `RankingCriteria` enum internally and passes `.value` at the Storage boundary.
- Config via environment variables for now (DB_ENGINE, DB_HOST, DB_USER, DB_PASSWORD, DB_NAME, DB_PATH, GITHUB_TOKEN). Revisit after Orchestrator Full — extract to a config module if the shape is stable.
- Storage init is idempotent (`storage.init()` returns early if already initialized). Pipeline calls init internally; tests pre-init with SQLite.

**Gotchas:**
- (none yet)

## Current Status

**Phase:** 2 — Orchestrator Full (Build)
**Focus:** Step 1 complete — ready for Step 2 (summarization calls)
**Blocked/Broken:** Nothing

---

## Phase 1: Thin Orchestrator (Build) — COMPLETE

Steps 1–5 implemented, 36 tests passing. See DEVLOG_ORCHESTRATOR.md for full details.

**Deferred:** `repos_discovered` currently reports saved count, not discovery count. Minor for thin orchestrator. Revisit in Phase 2 when the full pipeline adds more stages between discovery and persistence.

---

## Phase 2: Orchestrator Full (Build)

ARCHITECTURE.md step 6. Completes the pipeline from thin (steps 1–3: discover → persist) to full (steps 1–13): discover → persist → dedup → select → summarize → persist summaries → assemble digest → deliver → record features.

### Decisions

D-1: Bot token sourcing
Date: 2026-03-06 | Status: Closed
Decision: Read `TELEGRAM_BOT_TOKEN` from env var inside pipeline, same pattern as `GITHUB_TOKEN`.
Rationale: Consistent with existing env-var approach. Config module extraction is deferred.
Revisit if: Config module is introduced.

D-2: Summarization failure handling
Date: 2026-03-06 | Status: Closed
Decision: On deep-dive failure, try the next candidate in the ranked list. On quick-hit failure, skip that candidate and continue.
Rationale: The ranked list has more repos than needed. Falling back is cheap and avoids wasting a day's post.
Revisit if: Failure rate is high enough that fallback candidates are also failing.

D-3: Partial delivery
Date: 2026-03-06 | Status: Closed
Decision: Deliver whatever succeeded (e.g., 1 deep + 2 quick if one quick-hit failed). Pipeline succeeds if at least the deep dive is present.
Rationale: Better to send a partial digest than nothing.
Revisit if: Users report confusion from inconsistent digest sizes.

### Step 0 — Prerequisites

Add `get_recent_summaries` to Storage and update `PipelineConfig`.

- Add `get_recent_summaries(since_days: int) -> list[SummaryRecord]` to `src/storage/summaries.py`
  - Returns summaries generated within the lookback window, ordered by `generated_at` desc
  - Joins with repos table to include `repo_name` in results (or Orchestrator joins after)
- Export from `storage/__init__.py`
- Update ARCH_storage.md with new function contract
- Add `context_lookback_days: int = 14` to `PipelineConfig`
- Tests:
  - No summaries → empty list
  - Summaries within window returned, outside window excluded
  - Ordering is newest-first

### Step 1 — Dedup filtering and candidate selection

Add pipeline steps 4–5: query featured history, filter candidates, split into deep-dive and quick-hit pools.

- Call `storage.get_featured_repo_ids(config.cooldown_days)` → exclusion set
- Filter ranked repo list: remove recently featured
- Select top `deep_dive_count` for deep dive, next `quick_hit_count` for quick hits
- Track `repos_after_dedup` in PipelineResult (was always 0 in thin pipeline)
- Tests:
  - 10 discovered, 3 recently featured → 7 candidates, correct deep/quick split
  - All repos recently featured → no candidates, pipeline returns `success=False`
  - Fewer candidates than requested → uses what's available
  - `repos_after_dedup` count is correct

### Step 2 — Summarization calls

Add pipeline steps 6–9: build LLM config, generate summaries, persist them.

- Build `LLMConfig` from env vars: `LLM_PROVIDER`, `ANTHROPIC_API_KEY`, `LLM_DEEP_DIVE_MODEL`, `LLM_QUICK_HIT_MODEL`
- Query `storage.get_recent_summaries(config.context_lookback_days)` → convert `SummaryRecord` list to `list[dict]` with keys `repo_name`, `summary_content`, `date`
- Call `generate_deep_dive(repo, llm_config, recent_context)` for deep-dive candidates
  - On failure (any summarization error): log, try next candidate in ranked list
  - If all candidates exhausted: pipeline returns `success=False`
- Call `generate_quick_hit(repo, llm_config)` for quick-hit candidates
  - On failure: log, skip candidate, continue with remaining
- Persist each successful summary via `storage.save_summary(repo_id, type, content, model_used)`
- Track `summaries_generated` in PipelineResult
- Tests:
  - Happy path: mock summarization returns results, summaries persisted with correct types
  - Deep-dive failure on first candidate → falls back to next candidate
  - All deep-dive candidates fail → `success=False`
  - Quick-hit failure on one → skipped, others succeed, pipeline continues
  - `summaries_generated` count matches actual successes
  - Recent context correctly converted from SummaryRecord to dict shape

### Step 3 — Digest assembly

Add pipeline step 10: build `Digest` from summaries and repo records.

- Build `SummaryWithRepo` for each summary: combine `SummaryResult.content` with `RepoRecord` fields (`name`, `url`, `source_metadata["stars"]`, `source_metadata["created_at"]`)
- Assemble `Digest(deep_dive, quick_hits, ranking_criteria.value, date.today())`
- Tests:
  - Given known summary + repo data → correct `Digest` with all fields populated
  - `SummaryWithRepo` fields map correctly from `RepoRecord.source_metadata`
  - Partial quick hits (2 of 3) → `Digest.quick_hits` has length 2

### Step 4 — Delivery

Add pipeline step 11: send digest to Telegram.

- Read `TELEGRAM_BOT_TOKEN` from env var
- Call `delivery.send_digest(digest, config.channel_id, bot_token)`
- Propagate `DeliveryResult` to `PipelineResult.delivery_result`
- Tests:
  - Mock `send_digest` → verify receives correct Digest and channel_id
  - Successful delivery → `PipelineResult.success=True`, `delivery_result.success=True`
  - Delivery failure → `PipelineResult.success=False`, error captured
  - Missing bot token → error captured, pipeline returns `success=False`

### Step 5 — Feature recording

Add pipeline step 12: on delivery success, record featured repos.

- For each featured repo (deep dive + quick hits): call `storage.record_feature(repo_id, feature_type, ranking.value)`
- Only record if delivery succeeded
- Tests:
  - Successful delivery → `record_feature` called once per featured repo
  - Correct `feature_type` ("deep" vs "quick") and `ranking_criteria` string
  - Delivery failure → no `record_feature` calls
  - Feature recording failure → error captured but pipeline still `success=True` (delivery already succeeded)

### Step 6 — End-to-end integration test

Mock only HTTP boundaries (GitHub API, Anthropic API, Telegram API). All internal wiring and SQLite storage are real.

- Tests:
  - Full pipeline: repos persisted, dedup applied, summaries generated and persisted, digest assembled, delivery called, features recorded
  - `PipelineResult` has correct counts for all fields
  - Second pipeline run: previously featured repos excluded by dedup

### Step 7 — Review and cleanup

- Fix `repos_discovered` semantics: report discovery count, not saved count (deferred from Phase 1)
- Replace `delivery_result: Any` with `delivery_result: DeliveryResult | None` in PipelineResult
- Verify `__init__.py` exports include any new public names
- Remove dead code, ensure logging covers all pipeline steps
