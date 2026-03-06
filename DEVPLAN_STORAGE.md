# DEVPLAN: Storage

## Cold Start Summary

**What this is:** Storage module — persists and queries all durable data (repos, summaries, feature history). Provides a data access layer that isolates the rest of the system from database details. Public API: 6 functions matching ARCH_storage.md (`save_repo`, `get_repo`, `get_featured_repo_ids`, `save_summary`, `get_summary`, `record_feature`).

**Key constraints:**
- MySQL/MariaDB in production (host s501), SQLite for local dev and tests. All SQL must be compatible with both engines.
- `mysql-connector-python` for MySQL (already installed on host). `sqlite3` (stdlib) for tests.
- Module-level `init(config)` / `close()` pattern — storage owns the connection internally. Functions match ARCH_storage.md signatures (no connection parameter).
- Schema managed via one-shot `schema.sql` with `CREATE TABLE IF NOT EXISTS`. Auto-run on `init()`. No migration framework.
- Upsert divergence: MySQL uses `ON DUPLICATE KEY UPDATE`, SQLite uses `INSERT ... ON CONFLICT DO UPDATE`. Handled by engine-aware helper.
- `source_metadata` stored as JSON text column — must round-trip dict → str → dict.
- Storage owns all DB writes. No other module touches the database directly.

**Gotchas:**
- SQLite creates an internal `sqlite_sequence` table when `AUTOINCREMENT` is used. Any query counting or listing tables must filter `NOT LIKE 'sqlite_%'`.
- `COALESCE(column, value)` works identically in SQLite and MySQL — use it to avoid conditional UPDATE branching (e.g., "set only if NULL" logic).

## Current Status

**Phase:** 1 — Complete
**Focus:** Phase complete — all 7 steps implemented, 71 tests passing
**Blocked/Broken:** MySQL integration test deferred — requires DB_HOST env var

---

## Phase 1: Storage Implementation (Build) — COMPLETE

Steps 1–7 implemented, 71 tests passing. Step 8 (MySQL integration test) deferred. See DEVLOG_STORAGE.md for full details.

**Deferred: MySQL integration test.** Write `tests/storage/test_mysql_integration.py` when DB_HOST is available. Single test running full lifecycle against real MySQL. Mark `@pytest.mark.skipif(not os.environ.get("DB_HOST"))`. Validate before first server deployment.
