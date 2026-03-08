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

**Phase:** 2 — Orchestrator Full (Build) — COMPLETE; Phase 3 — Production Deployment — COMPLETE
**Focus:** Deployed and running on s501.sureserver.com. Cron at 06:01 EDT.
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
D-5: Quick-hit model — Changed default from `claude-3-5-haiku-20241022` (404 on production) to `claude-haiku-4-5-20251001`. (Closed)

---

## Phase 3: Production Deployment (2026-03-08)

See DEPLOY.md for full deployment guide. Summary of deployment-related code changes:

### Quick-hit model fix

**What was done:**
- Default `LLM_QUICK_HIT_MODEL` changed from `claude-3-5-haiku-20241022` to `claude-haiku-4-5-20251001` in `_build_llm_config()`. The old model returned 404 from the Anthropic API on the production server — it was not available on the account (verified via `models.json`).
- Test updated: `test_defaults_for_optional_vars` in `tests/orchestrator/test_pipeline.py`.

### Production entry point

**Files created (not in src/):**
- `run_daily.py` — production entry point for cron. Inserts `src/` into `sys.path`, loads `.env`, configures logging to `data/pipeline.log` + stderr, runs pipeline with `CategoryConfig` for "agentic-coding" category, `channel_id="@github_discovery"`.
- `run_cron.sh` — shell wrapper for cron job (created on server, not in repo). `cd`s to project dir, runs `run_daily.py` via venv Python.
- `.gitignore` — protects `.env`, `__pycache__/`, `data/*.db`, `data/*.log`, `venv/`.

### Environment fixes
- `.env`: Uncommented `DB_ENGINE=sqlite` and `DB_PATH=/home/mikey/private/tgbot/data/bot.db` — without these, the pipeline defaults to in-memory SQLite, losing all dedup/cooldown history between runs.

### Deployment gotchas documented
- Windows SCP doesn't expand `~` — use absolute paths
- `scp -r src/ host:path/src/` creates `src/src/` — upload to parent directory instead
- CRLF line endings from Windows corrupt `.env` keys and shebangs — fix with `sed -i 's/\r$//'`
- `chmod 775` required on scripts for hosting panel cron
- Server timezone is EDT (UTC-4), not UTC — cron times are in server time
- Hostname is `s501.sureserver.com` (not just `s501`)

**Test count:** 570 total passing (1 test updated for model default).
