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
- (none discovered)

## Current Status

**Phase:** 1 — In progress
**Focus:** Step 5 — save_summary and get_summary
**Blocked/Broken:** None

---

## Phase 1: Storage Implementation (Build)

**Regime:** Build — all correctness is verifiable by tests and type checks.

**Outcomes:** A working `src/storage/` package with 6 public API functions, tested against SQLite in-memory. A `schema.sql` ready for MySQL deployment. Error handling via `StorageError`.

### Step 1 — Project structure + types + schema

**What:** Create `src/storage/` package. Define `StorageError`, `RepoRecord`, `SummaryRecord`, `FeatureRecord` dataclasses. Write MySQL/SQLite-compatible table DDL as `src/storage/schema.sql`.

**Files:** `src/storage/__init__.py`, `src/storage/types.py`, `src/storage/schema.sql`

**Schema design:**

```
repos:
  id              INTEGER PRIMARY KEY AUTOINCREMENT
  source          TEXT NOT NULL
  source_id       TEXT NOT NULL
  name            TEXT NOT NULL
  url             TEXT NOT NULL
  description     TEXT
  raw_content     TEXT NOT NULL
  source_metadata TEXT NOT NULL          -- JSON
  discovered_at   TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
  first_featured_at TIMESTAMP
  last_featured_at  TIMESTAMP
  feature_count   INTEGER NOT NULL DEFAULT 0
  UNIQUE(source, source_id)

summaries:
  id              INTEGER PRIMARY KEY AUTOINCREMENT
  repo_id         INTEGER NOT NULL REFERENCES repos(id)
  summary_type    TEXT NOT NULL           -- "deep" | "quick"
  content         TEXT NOT NULL
  model_used      TEXT NOT NULL
  generated_at    TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP

feature_history:
  id              INTEGER PRIMARY KEY AUTOINCREMENT
  repo_id         INTEGER NOT NULL REFERENCES repos(id)
  feature_type    TEXT NOT NULL           -- "deep" | "quick"
  featured_date   DATE NOT NULL
  ranking_criteria TEXT NOT NULL
```

**Test spec** (`tests/storage/test_types.py`):
- RepoRecord has all fields per ARCH_storage.md (id, source, source_id, name, url, description, raw_content, source_metadata, discovered_at, first_featured_at, last_featured_at, feature_count)
- SummaryRecord has all fields (id, repo_id, summary_type, content, model_used, generated_at)
- FeatureRecord has all fields (id, repo_id, feature_type, featured_date, ranking_criteria)
- StorageError is an Exception subclass
- source_metadata round-trips through JSON (dict → json.dumps → json.loads → dict)
- Optional fields (description, first_featured_at, last_featured_at) accept None

### Step 2 — Database connection management

**What:** Create `src/storage/db.py` with `init(config)`, `close()`, and `get_connection()` (internal). Config dict keys: `engine` ("sqlite" | "mysql"), plus engine-specific keys. `init()` auto-runs schema DDL. Expose engine type so upsert helpers can branch.

**Config shapes:**
- SQLite: `{"engine": "sqlite", "database": ":memory:"}` or `{"engine": "sqlite", "database": "path/to/file.db"}`
- MySQL: `{"engine": "mysql", "host": "...", "user": "...", "password": "...", "database": "..."}`

**Files:** `src/storage/db.py`

**Test spec** (`tests/storage/test_db.py`):
- `init()` with SQLite config succeeds and creates all three tables
- After `init()`, tables verified via `SELECT name FROM sqlite_master WHERE type='table'`
- `close()` closes the connection; subsequent operations raise
- `init()` with missing required config keys raises `StorageError`
- `init()` is idempotent — calling twice with same config is safe
- `get_engine()` returns "sqlite" or "mysql"

### Step 3 — `save_repo` and `get_repo`

**What:** Implement `save_repo(repo: DiscoveredRepo) -> RepoRecord` with upsert (insert or update by `source + source_id`). Implement `get_repo(repo_id: int) -> RepoRecord | None`. Engine-aware upsert helper branches on MySQL vs SQLite syntax.

**Files:** `src/storage/repos.py`

**Test spec** (`tests/storage/test_repos.py`):
- Insert new repo → returns RepoRecord with id > 0 and discovered_at set
- Insert same repo again (same source + source_id) → returns same id, updates metadata fields
- Upsert preserves original discovered_at
- Upsert updates source_metadata (e.g., star count changes)
- get_repo with valid id → returns correct RepoRecord
- get_repo with nonexistent id → returns None
- source_metadata stored as JSON, retrieved as dict with correct values
- raw_content round-trips correctly (including content near 50KB)
- description=None stored and retrieved as None
- New repo has feature_count=0, first_featured_at=None, last_featured_at=None

### Step 4 — `get_featured_repo_ids`

**What:** Implement `get_featured_repo_ids(since_days: int = 90) -> set[int]`. Queries feature_history for repos featured within the lookback window.

**Files:** `src/storage/history.py`

**Test spec** (`tests/storage/test_history.py`):
- No feature records → returns empty set
- Repo featured 30 days ago, since_days=90 → included in set
- Repo featured 100 days ago, since_days=90 → excluded from set
- Repo featured exactly 90 days ago → included (boundary: >= cutoff)
- Multiple repos featured within window → all IDs returned
- Same repo featured twice within window → ID appears once (it's a set)
- Default since_days is 90

Note: These tests require `save_repo` and `record_feature` to set up fixture data. Step 4 tests depend on steps 3 and 6 being functional. If implementing sequentially, use direct SQL inserts for test fixtures until step 6 is complete.

### Step 5 — `save_summary` and `get_summary`

**What:** Implement `save_summary(repo_id, summary_type, content, model_used) -> SummaryRecord` and `get_summary(summary_id) -> SummaryRecord | None`.

**Files:** `src/storage/summaries.py`

**Test spec** (`tests/storage/test_summaries.py`):
- Save summary with valid repo_id → returns SummaryRecord with id > 0 and generated_at set
- Save summary with nonexistent repo_id → raises ValueError
- summary_type must be "deep" or "quick" → invalid value raises ValueError
- get_summary with valid id → returns correct SummaryRecord
- get_summary with nonexistent id → returns None
- Content round-trips correctly (long text, special characters, unicode, newlines)
- Multiple summaries for same repo → each gets unique id

### Step 6 — `record_feature`

**What:** Implement `record_feature(repo_id, feature_type, ranking_criteria) -> FeatureRecord`. Inserts into feature_history, updates repo's `last_featured_at` (to today), increments `feature_count`. On first feature, also sets `first_featured_at`.

**Files:** `src/storage/features.py`

**Test spec** (`tests/storage/test_features.py`):
- Record feature → returns FeatureRecord with featured_date = today
- After record_feature, get_repo shows updated last_featured_at
- After record_feature, get_repo shows feature_count incremented by 1
- First feature sets first_featured_at; second feature does not overwrite first_featured_at
- feature_type must be "deep" or "quick" → invalid value raises ValueError
- Recording feature for nonexistent repo_id → raises ValueError

### Step 7 — Public API wiring + integration test

**What:** Update `src/storage/__init__.py` to re-export `init`, `close`, and all 6 public functions. Write integration test exercising the full lifecycle.

**Files:** `src/storage/__init__.py` (update), `tests/storage/test_integration.py`

**Test spec** (`tests/storage/test_integration.py`):
- Full lifecycle: save_repo → save_summary → record_feature → get_featured_repo_ids (repo appears) → get_repo (feature_count=1, first/last_featured_at set)
- Two repos: feature repo A, verify repo B not in featured set
- Upsert + feature interaction: save_repo, feature it, save_repo again (simulating re-discovery with updated metadata), verify feature_count preserved, metadata updated
- get_summary retrieves summary saved during lifecycle
- Cooldown boundary: feature repo, advance time past window, verify repo no longer in featured set

### Deferred: MySQL integration test

Write `tests/storage/test_mysql_integration.py` when MySQL credentials are available. Single test running full lifecycle against real MySQL. Mark `@pytest.mark.skipif(not os.environ.get("DB_HOST"))`. Validate before first server deployment.
