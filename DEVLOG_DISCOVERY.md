# DEVLOG: Discovery

## Step 1 — Project structure + data types
**Date:** 2026-03-05

**What was done:**
- Created `src/discovery/` package with `__init__.py` and `types.py`
- Created `tests/discovery/` package with `test_types.py` (17 tests)
- Added `pytest.ini` with `pythonpath = src` and `testpaths = tests`
- Defined 6 types matching ARCH_discovery contract:
  - `SeedRepo` — dataclass (full_name, name, reason)
  - `CategoryConfig` — dataclass with all richer fields (topics, keywords, expansion_topics, seed_repos, quality filters, languages)
  - `RankingCriteria` — enum with 5 members (stars, forks, subscribers, recency, activity)
  - `DiscoveredRepo` — dataclass (source-agnostic shape)
  - `GitHubAPIError` — exception with status_code, response_body
  - `NoResultsError` — exception with query_details

**Decisions:**
- Query generation methods (`get_all_queries()` etc. from investigation's `category_config.py`) stay out of the config type. They'll be internal helpers in the search client (Step 2).
- `pytest.ini` added to avoid needing manual `$env:PYTHONPATH='src'` — discovered during first test run that PowerShell `set` + `&&` chaining doesn't work for env vars.

**Issues:** None.

## Phase 1 — Completion
**Date:** 2026-03-06

**Summary:** Discovery module complete. 7 of 8 steps implemented, 108 tests passing. All source files in `src/discovery/`, all tests in `tests/discovery/`.

**Deferred:** Step 8 (integration test against real GitHub API) — requires `GITHUB_TOKEN`. Write this before first real pipeline run.

**Contract changes propagated:**
- ARCH_discovery.md: `CategoryConfig` updated to richer shape (topics, keywords, expansion_topics, seed_repos, quality filters). `pushed_at` added to `DiscoveredRepo.source_metadata`.

**DEVLOG learning review:** No trial-and-error patterns to promote to Gotchas. `pytest.ini` solved the PYTHONPATH issue before it could become recurring.

## Step 7 — discover_repos integration
**Date:** 2026-03-06

**What was done:**
- Created `src/discovery/discover.py` with `discover_repos()` — the public API wiring all components
- Pipeline: search → dedup → pre-filter (stars/fork/archived) → fetch READMEs → full filter → fetch seeds → merge → dedup → sort → limit → convert to DiscoveredRepo
- Pre-filter optimization: checks stars/fork/archived before README fetch to avoid unnecessary API calls
- Maps `RankingCriteria` → GitHub search sort parameter for better initial results
- Token falls back to `GITHUB_TOKEN` env var
- Updated `__init__.py` to re-export `discover_repos`
- Created `tests/discovery/test_discover_repos.py` with 18 tests (happy path, dedup, filtering, expansion, seeds, errors, keywords)

**Decisions:**
- Pre-filter before README fetch. At 10-15 queries × 30 results = ~300 raw repos, fetching all READMEs would be wasteful. Pre-filtering by stars/fork/archived first typically cuts this by 30-50%.
- `_is_expansion` tag carried on raw dicts to route expansion repos through higher star bar during filtering, rather than splitting queries into separate pipelines.

### Contract Changes
- **ARCH_discovery.md**: Added `pushed_at: str (ISO 8601)` to `DiscoveredRepo.source_metadata`. Needed for `RankingCriteria.ACTIVITY` sorting.

**Issues:** None.

## Step 6 — Seed repo handling
**Date:** 2026-03-06

**What was done:**
- Added `fetch_repo(full_name, token)` to `github_client.py` — single repo fetch via Repos API, returns `None` on 404
- Extracted `_request_get()` helper to share error handling between `fetch_repo` and `fetch_readme`
- Created `src/discovery/seeds.py` with `fetch_seed_repos(seeds, token)` — fetches each seed's metadata + README, skips 404s, returns raw dicts with `readme_content` key
- Added 4 `fetch_repo` tests to `test_github_client.py`, created `tests/discovery/test_seeds.py` with 7 tests

**Decisions:**
- `fetch_seed_repos` returns raw dicts (not `DiscoveredRepo`) so seeds can be merged, filtered, and sorted uniformly with search results in the integration step.
- Seeds with `None` README are still returned — quality filtering happens downstream.

**Issues:** None.

## Step 5 — Ranking/sorting
**Date:** 2026-03-06

**What was done:**
- Created `src/discovery/ranking.py` with `sort_repos(repos, criteria)`
- Table-driven design: `_SORT_KEYS` maps `RankingCriteria` → GitHub API field name, `_DEFAULTS` handles missing keys
- All criteria sort descending; stable sort preserves original order on ties
- Created `tests/discovery/test_ranking.py` with 10 tests (one per criteria + stable sort + edge cases)

**Decisions:**
- "Activity" = `pushed_at` (most recent push to any branch). Distinct from `updated_at` (any repo event). Already in search results, no extra API call needed. Will need to carry `pushed_at` into `DiscoveredRepo.source_metadata` during Step 7 conversion.

**Issues:** None.

## Step 4 — Quality filtering
**Date:** 2026-03-05

**What was done:**
- Created `src/discovery/filters.py` with `apply_quality_filters(repos, config, is_expansion)`
- Five filter criteria: min stars (with +50 for expansion), fork exclusion, archived exclusion, README presence + min length, language match
- Filters operate on raw GitHub API dicts augmented with `readme_content` key — avoids constructing DiscoveredRepo for repos that will be filtered out
- Case-insensitive language comparison
- Created `tests/discovery/test_filters.py` with 23 tests across 6 classes

**Decisions:**
- `is_expansion` parameter on the filter function controls the +50 star threshold, rather than requiring callers to modify the config object.

**Issues:** None.

## Step 3 — README fetching
**Date:** 2026-03-05

**What was done:**
- Added `fetch_readme(owner, repo, token)` to `src/discovery/github_client.py`
- Uses GitHub Contents API (`GET /repos/{owner}/{repo}/readme`) — auto-resolves branch and filename
- Base64-decodes response, truncates to 50KB (`MAX_README_BYTES`)
- Returns `None` for 404, unknown encoding, or empty content
- Raises `GitHubAPIError` for 401/403/5xx/network/timeout
- Created `tests/discovery/test_readme_fetch.py` with 13 mocked tests

**Decisions:**
- Contents API over raw.githubusercontent.com. Rate limit math: even at hundreds of weekly repos, API budget stays under 12% of 5,000/hr. No branch/filename guessing needed. Revisit if a single run approaches 3,000+ README fetches.

**Issues:** None.

## Step 2 — GitHub search client
**Date:** 2026-03-05

**What was done:**
- Created `src/discovery/github_client.py` with `search_repos()` function
- Handles auth (token → `Authorization: token {token}` header, omitted when no token)
- Handles pagination (iterates pages, stops early when all results collected or partial page)
- Caps `per_page` at 100 (GitHub API max)
- Error mapping: 401→auth, 403→rate limit (with reset timestamp from headers), 422→validation, 5xx→server, ConnectionError/Timeout→network — all raise `GitHubAPIError`
- Returns raw `items` list (dicts) — no domain type conversion at this layer
- Created `tests/discovery/test_github_client.py` with 16 mocked tests (URL construction, auth, pagination, errors, empty results)

**Decisions:**
- Used `urllib.parse.urlencode` for URL construction rather than passing `params` dict to `requests.get`. Explicit URL makes tests easier to assert against.
- Pagination stops on three conditions: all results fetched (`len >= total_count`), partial page returned (`len(items) < per_page`), or `max_pages` reached. No `Link` header parsing needed.

**Issues:** None.
