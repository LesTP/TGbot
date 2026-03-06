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
