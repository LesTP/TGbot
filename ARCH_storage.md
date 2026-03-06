# ARCH: Storage

## Purpose
Persist and query all durable data: discovered repos, generated summaries, and feature history. Provides a data access layer that isolates the rest of the system from database implementation details (schema, SQL, connection management).

## Public API

### save_repo
- **Signature:** `save_repo(repo: DiscoveredRepo) -> RepoRecord`
- **Parameters:** DiscoveredRepo (as defined in ARCH_discovery)
- **Returns:** RepoRecord with assigned `id` and `discovered_at`. If the repo already exists (matched by source + source_id), updates metadata and returns the existing record.
- **Errors:** `StorageError` — database write failed.

### get_repo
- **Signature:** `get_repo(repo_id: int) -> RepoRecord | None`
- **Parameters:** repo_id (internal ID)
- **Returns:** RepoRecord or None if not found.
- **Errors:** `StorageError` — database read failed.

### get_featured_repo_ids
- **Signature:** `get_featured_repo_ids(since_days: int = 90) -> set[int]`
- **Parameters:** since_days — lookback window for feature history (default 90)
- **Returns:** Set of repo IDs featured within the lookback window.
- **Errors:** `StorageError` — database read failed.

### save_summary
- **Signature:** `save_summary(repo_id: int, summary_type: str, content: str, model_used: str) -> SummaryRecord`
- **Parameters:**
  - repo_id: int — must reference an existing repo
  - summary_type: "deep" | "quick"
  - content: str — the generated summary text
  - model_used: str — model identifier
- **Returns:** SummaryRecord with assigned `id` and `generated_at`.
- **Errors:** `StorageError` — write failed. `ValueError` — repo_id doesn't exist.

### get_summary
- **Signature:** `get_summary(summary_id: int) -> SummaryRecord | None`
- **Parameters:** summary_id (internal ID)
- **Returns:** SummaryRecord or None.
- **Errors:** `StorageError` — read failed.

### get_recent_summaries
- **Signature:** `get_recent_summaries(since_days: int = 14) -> list[SummaryRecord]`
- **Parameters:** since_days — lookback window (default 14)
- **Returns:** List of SummaryRecords generated within the lookback window, ordered by `generated_at` descending (newest first). Empty list if none found.
- **Errors:** `StorageError` — database read failed.

### record_feature
- **Signature:** `record_feature(repo_id: int, feature_type: str, ranking_criteria: str) -> FeatureRecord`
- **Parameters:**
  - repo_id: int
  - feature_type: "deep" | "quick"
  - ranking_criteria: str — which ranking was used
- **Returns:** FeatureRecord with `featured_date` set to today. Also updates the repo's `last_featured_at` and increments `feature_count`.
- **Errors:** `StorageError` — write failed.

## Inputs
- Database connection config (host, user, password, database — from environment)
- DiscoveredRepo objects (from Discovery via Orchestrator)
- Summary content (from Summarization)

## Outputs
- RepoRecord: DiscoveredRepo fields + id (int), discovered_at (datetime), first_featured_at (datetime|None), last_featured_at (datetime|None), feature_count (int)
- SummaryRecord: id (int), repo_id (int), summary_type (str), content (str), model_used (str), generated_at (datetime)
- FeatureRecord: id (int), repo_id (int), feature_type (str), featured_date (date), ranking_criteria (str)

## State
MySQL/MariaDB database with tables for repos, summaries, and feature history. Storage owns all database state — no other module writes to the database directly.

## Usage Example
```python
from storage import save_repo, get_featured_repo_ids, save_summary, record_feature

# Persist a discovered repo
record = save_repo(discovered_repo)

# Check what's been featured recently
featured = get_featured_repo_ids(since_days=90)
if record.id not in featured:
    # This repo is eligible for featuring
    ...

# Save a generated summary
summary = save_summary(record.id, "deep", content="...", model_used="claude-sonnet-4-5")

# Record that this repo was featured
record_feature(record.id, "deep", "stars")
```
