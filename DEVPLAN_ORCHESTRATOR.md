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

**Phase:** 1 — Complete
**Focus:** Phase complete — 5 steps implemented, 36 orchestrator tests, 215 total passing
**Blocked/Broken:** Nothing

---

## Phase 1: Thin Orchestrator (Build) — COMPLETE

Steps 1–5 implemented, 36 tests passing. See DEVLOG_ORCHESTRATOR.md for full details.

**Deferred:** `repos_discovered` currently reports saved count, not discovery count. Minor for thin orchestrator. Revisit in Phase 2 when the full pipeline adds more stages between discovery and persistence.

---

## Phase 2: Orchestrator Full (Build) — PLANNED

ARCHITECTURE.md step 6. Adds pipeline steps 4–12: dedup filtering, ranking rotation, candidate selection, summarization calls, digest assembly, delivery, feature history recording.

**Prerequisite:** Summarization and Delivery modules implemented (ARCHITECTURE.md steps 4–5).

**Deferred decision:** Extract environment-variable config reading into a dedicated config module. Revisit when the full pipeline shape is clear and all env vars are known.
