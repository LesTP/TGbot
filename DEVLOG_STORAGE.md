# DEVLOG: Storage

## Step 1 — Project structure + types + schema
**Date:** 2026-03-06

**What was done:**
- Created `src/storage/` package with `__init__.py` and `types.py`
- Created `tests/storage/` package with `test_types.py` (14 tests)
- Defined 4 types matching ARCH_storage.md contract:
  - `StorageError` — exception with `message` attribute
  - `RepoRecord` — dataclass (all DiscoveredRepo fields + id, discovered_at, first/last_featured_at, feature_count)
  - `SummaryRecord` — dataclass (id, repo_id, summary_type, content, model_used, generated_at)
  - `FeatureRecord` — dataclass (id, repo_id, feature_type, featured_date, ranking_criteria)
- Created `schema.sql` with 3 tables (repos, summaries, feature_history) — SQLite syntax, MySQL adaptation handled in init code

**Decisions:**
- No validation in the type layer — types are plain dataclasses. Validation (e.g., summary_type must be "deep" | "quick") lives in the functions that create records (steps 5, 6).
- Schema uses SQLite syntax as canonical form. `AUTOINCREMENT` → `AUTO_INCREMENT` swap for MySQL will be handled by `init()` in step 2.
- `source_metadata` stored as `TEXT NOT NULL` (JSON string), not a native JSON column — maximizes MySQL/SQLite compatibility.

**Issues:** None.

## Step 5 — save_summary and get_summary
**Date:** 2026-03-06

**What was done:**
- Created `src/storage/summaries.py` with `save_summary()` and `get_summary()`
- `save_summary` validates repo_id existence (SELECT before INSERT) and summary_type ("deep" | "quick")
- `_parse_datetime()` and `_row_to_summary_record()` helpers follow same pattern as repos.py
- Created `tests/storage/test_summaries.py` with 7 tests (valid save, invalid repo_id, invalid type, special chars round-trip, unique IDs, get valid/invalid)

**Decisions:**
- Repo existence check via SELECT before INSERT rather than relying on FK constraint errors — gives a clean `ValueError` message regardless of engine. FK errors differ between SQLite and MySQL.

**Issues:** None.

## Step 6 — record_feature
**Date:** 2026-03-06

**What was done:**
- Created `src/storage/features.py` with `record_feature()`
- Inserts into feature_history, then atomically updates repo: `last_featured_at`, `feature_count + 1`, and `first_featured_at` (only on first feature)
- Checks `first_featured_at IS NULL` to determine first-feature logic, avoiding a race with separate read+conditional
- Validates feature_type ("deep" | "quick") and repo existence
- Created `tests/storage/test_features.py` with 6 tests (return value, last_featured_at, feature_count increment, first_featured_at preservation, invalid type, nonexistent repo)

**Decisions:**
- `first_featured_at` set conditionally: checked via SELECT before UPDATE rather than a single `COALESCE`-based UPDATE. Keeps the logic readable and the two UPDATE paths explicit.

**Issues:** None.

## Step 7 — Public API wiring + integration test
**Date:** 2026-03-06

**What was done:**
- Updated `src/storage/__init__.py` to re-export `init`, `close`, all 6 public API functions, and all 4 types via `__all__`
- Created `tests/storage/test_integration.py` with 5 lifecycle tests:
  1. Full pipeline: save_repo → save_summary → record_feature → get_featured_repo_ids → get_repo → get_summary
  2. Two repos: feature one, verify other not in featured set
  3. Upsert + feature: re-save repo after featuring, verify metadata updated but feature_count preserved
  4. Cooldown boundary: mock date to feature 91 days ago, verify excluded from 90-day window
  5. Summary retrieval: multiple summaries for one repo, verify both retrievable

**Decisions:**
- Cooldown boundary test uses `unittest.mock.patch` on `storage.features.date` and `storage.features.datetime` to freeze time rather than inserting raw SQL with past dates. Tests the actual code path.

**Issues:** None.

## Phase 1 — Completion
**Date:** 2026-03-06

**Summary:** Storage module complete. 7 steps implemented, 71 tests passing. All source files in `src/storage/`, all tests in `tests/storage/`.

**Deferred:** MySQL integration test — requires `DB_HOST` env var. Write before first server deployment.

**DEVLOG learning review:** No trial-and-error patterns to promote to Gotchas. The dual-engine (SQLite/MySQL) approach worked cleanly — main divergences were placeholder style (`?` vs `%s`), upsert syntax, and datetime parsing. All handled with inline branching rather than an abstraction layer.

## Step 4 — get_featured_repo_ids
**Date:** 2026-03-06

**What was done:**
- Created `src/storage/history.py` with `get_featured_repo_ids(since_days=90) -> set[int]`
- Lookback cutoff computed in Python (`date.today() - timedelta(days=since_days)`) and passed as parameter — consistent across engines
- SQLite receives `cutoff.isoformat()` (string comparison works for ISO dates), MySQL receives `date` object directly
- `DISTINCT` in query handles repos featured multiple times
- Created `tests/storage/test_history.py` with 7 tests using direct SQL fixture helpers (`_insert_repo`, `_insert_feature`) since `record_feature` isn't built yet

**Decisions:**
- Date arithmetic in Python rather than SQL (`DATE_SUB` vs `date('now', '-N days')` divergence). Keeps engine-specific code to placeholder style only.

**Issues:** None.

## Step 2 — Database connection management
**Date:** 2026-03-06

**What was done:**
- Created `src/storage/db.py` with module-level connection lifecycle: `init(config)`, `close()`, `get_connection()`, `get_engine()`
- `init()` is idempotent (returns early if already initialized), `close()` is safe without prior init
- SQLite connections get `row_factory = sqlite3.Row` for dict-like access and `PRAGMA foreign_keys = ON`
- MySQL path swaps `AUTOINCREMENT` → `AUTO_INCREMENT` before executing schema DDL
- Schema loaded from `schema.sql` at runtime via `pathlib.Path(__file__).parent`
- Created `tests/storage/test_db.py` with 22 tests across 5 classes (Init, Close, GetConnection, GetEngine, SchemaIntegrity)

**Decisions:**
- Schema DDL loaded and executed at `init()` time rather than requiring a separate migration step. `CREATE TABLE IF NOT EXISTS` makes this idempotent.
- `row_factory = sqlite3.Row` chosen for SQLite to enable dict-like column access (`row["name"]`), matching how MySQL connector returns rows.

**Issues:**
- SQLite creates an internal `sqlite_sequence` table when `AUTOINCREMENT` is used. Table count test initially expected 3 but got 4. Fixed by filtering `NOT LIKE 'sqlite_%'` in the count query.

## Step 3 — save_repo and get_repo
**Date:** 2026-03-06

**What was done:**
- Created `src/storage/repos.py` with `save_repo()` and `get_repo()`
- Engine-aware upsert: SQLite uses `ON CONFLICT(source, source_id) DO UPDATE`, MySQL uses `ON DUPLICATE KEY UPDATE`
- Placeholder style branches on engine: `?` for SQLite, `%s` for MySQL
- `_parse_datetime()` helper handles SQLite (returns strings) vs MySQL (returns datetime objects)
- `_row_to_repo_record()` centralizes row-to-dataclass conversion with JSON deserialization of `source_metadata`
- Upsert does INSERT then SELECT-back by `(source, source_id)` to return the full record regardless of insert vs update
- Created `tests/storage/test_repos.py` with 10 tests (insert, upsert identity/preservation/update, default feature fields, None description, JSON round-trip, large content, get valid/invalid ID)

**Decisions:**
- SELECT-back after upsert rather than relying on `cursor.lastrowid` — `lastrowid` behavior on conflict/update varies between engines. SELECT by unique key is reliable in both.
- Placeholder branching (`?` vs `%s`) kept inline rather than abstracting into a query builder. The SQL divergence is small and a wrapper would add complexity without benefit at this scale.

**Issues:** None.
