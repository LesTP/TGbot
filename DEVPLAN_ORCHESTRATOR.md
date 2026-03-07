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

**Phase:** 2 — Orchestrator Full (Build) — COMPLETE
**Focus:** Phase 2 complete — all steps done, 503 tests passing
**Blocked/Broken:** Nothing

---

## Phase 1: Thin Orchestrator (Build) — COMPLETE

Steps 1–5 implemented, 36 tests passing. See DEVLOG_ORCHESTRATOR.md for full details.

**Deferred:** `repos_discovered` currently reports saved count, not discovery count. Minor for thin orchestrator. Revisit in Phase 2 when the full pipeline adds more stages between discovery and persistence.

---

## Phase 2: Orchestrator Full (Build) — COMPLETE

Steps 0–7 implemented, 503 tests passing. Full pipeline: discover → persist → dedup → select → summarize → persist summaries → assemble digest → deliver → record features. See DEVLOG_ORCHESTRATOR.md for full details.

### Decisions

D-1: Bot token sourcing — Read from env var, same as GITHUB_TOKEN. (Closed)
D-2: Summarization failure handling — Deep dive falls back to next candidate; quick hits skip failures. (Closed)
D-3: Partial delivery — Deliver whatever succeeded; pipeline succeeds if deep dive present. (Closed)
D-4: Tiered cooldown — Deep=90d block all, quick=30d block quick + 7d promotion gap. (Closed)
