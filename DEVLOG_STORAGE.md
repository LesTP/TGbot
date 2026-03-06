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
