# DEVPLAN: Discovery

## Cold Start Summary

**What this is:** Discovery module — finds GitHub repos matching a category's search criteria, applies quality filters, ranks results, and returns `list[DiscoveredRepo]`. Pure leaf, no dependencies on other modules.

**Key constraints:**
- GitHub REST API v3 (not GraphQL). 5,000 requests/hour with token, 60 without.
- Search API returns max 1,000 results per query, 100 per page, 30 per page default.
- README fetched separately per repo (Contents API or raw.githubusercontent.com).
- Must work on Python 3.11, host has no special packages — stick to `requests` + stdlib.
- CategoryConfig is richer than original ARCH spec: includes expansion_topics (higher star bar), seed_repos (direct fetch by name), exclude_forks, exclude_archived. See ARCH_discovery.md for full contract.

**Gotchas:**
- (none yet — first phase)

## Current Status

**Phase:** 1 — Discovery implementation
**Focus:** Not yet started. Pending approval of phase plan.
**Blocked/Broken:** Nothing.

---

## Phase 1: Discovery Implementation (Build)

### Step 1: Project structure + data types

**Outcome:** Importable Python types matching the ARCH_discovery contract.

**Files:**
- `src/discovery/__init__.py` — public API surface (`discover_repos`)
- `src/discovery/types.py` — `DiscoveredRepo`, `CategoryConfig`, `SeedRepo`, `RankingCriteria`, error types
- `tests/discovery/__init__.py`
- `tests/discovery/test_types.py`

**Work:**
- Define `DiscoveredRepo` as a dataclass
- Define `CategoryConfig` as a dataclass (adapt from `github_search_investigation/category_config.py`, reconcile with ARCH contract)
- Define `SeedRepo` as a dataclass
- Define `RankingCriteria` as an enum (stars, forks, subscribers, recency, activity)
- Define `GitHubAPIError(Exception)` and `NoResultsError(Exception)`

**Tests:**
- Each type is constructible with required fields
- `CategoryConfig` defaults are correct (min_stars=50, require_readme=True, etc.)
- `RankingCriteria` has exactly 5 members
- Error types carry expected attributes (status_code, query_details)

**Decision:** Adopt the investigation's `CategoryConfig` fields. Drop `SearchQuery` (internal to discovery, not part of public types — may reuse as a private helper). `get_all_queries()` logic moves to the search client, not the config type.

---

### Step 2: GitHub search client

**Outcome:** Function that executes GitHub search queries and returns raw API responses.

**Files:**
- `src/discovery/github_client.py` — `search_repos(query, token, per_page, max_pages)` → raw result list
- `tests/discovery/test_github_client.py`

**Work:**
- Build search URL: `https://api.github.com/search/repositories?q={query}&sort={sort}&per_page={per_page}`
- Set auth header: `Authorization: token {token}`
- Handle pagination: follow `Link` header or iterate pages until results exhausted or max_pages reached
- Map HTTP errors: 403 rate limit → `GitHubAPIError` with clear message, 401 → auth error, 5xx → transient error
- Parse `items` array from response

**Tests (mocked with `unittest.mock.patch` on `requests.get`):**
- Correct URL construction for topic query, keyword query
- Auth header included when token provided, omitted when not
- Single page response returns all items
- Multi-page response (2 pages) follows pagination correctly
- 403 response → `GitHubAPIError` with rate limit info
- 401 response → `GitHubAPIError` with auth message
- Network error (ConnectionError) → `GitHubAPIError`
- Empty `items` array → returns empty list (not an error at this layer)

---

### Step 3: README fetching

**Outcome:** Function that fetches and returns README text for a repo.

**Files:**
- Add `fetch_readme(owner, repo, token)` to `github_client.py`
- `tests/discovery/test_readme_fetch.py`

**Work:**
- Use GitHub Contents API: `GET /repos/{owner}/{repo}/readme` (returns base64 content)
- Or use `raw.githubusercontent.com/{owner}/{repo}/main/README.md` (returns raw text, simpler). Try `main`, fall back to `master`, fall back to API.
- Truncate to 50KB
- Return `None` for 404 or non-decodable content

**Decision to make during implementation:** Which README fetch strategy is more reliable / rate-limit-friendly. The Contents API counts against the 5,000/hr limit. raw.githubusercontent.com does not count against API limits but requires guessing the default branch.

**Tests (mocked):**
- Successful fetch returns decoded text
- 404 → returns `None`
- Binary/non-UTF8 content → returns `None`
- Content over 50KB → truncated to exactly 50KB
- Network error → `GitHubAPIError`

---

### Step 4: Quality filtering

**Outcome:** Function that filters a list of raw repo dicts by quality criteria.

**Files:**
- `src/discovery/filters.py` — `apply_quality_filters(repos, config) -> list`
- `tests/discovery/test_filters.py`

**Work:**
- Filter: `stars >= config.min_stars` (expansion topics use `min_stars + 50`)
- Filter: README present and `len(readme) >= config.min_readme_length`
- Filter: `fork == False` when `config.exclude_forks`
- Filter: `archived == False` when `config.exclude_archived`
- Filter: `language in config.languages` when languages is not None

**Tests:**
- Repo with stars = min_stars passes; stars = min_stars - 1 fails
- Repo with README length = min_readme_length passes; length - 1 fails
- Fork excluded when exclude_forks=True; included when False
- Archived excluded when exclude_archived=True; included when False
- Language filter: matches pass, non-matches fail, None languages → all pass
- Empty input → empty output
- All filtered out → empty output (no error at this layer)

---

### Step 5: Ranking/sorting

**Outcome:** Function that sorts repos by a given `RankingCriteria`.

**Files:**
- `src/discovery/ranking.py` — `sort_repos(repos, criteria) -> list`
- `tests/discovery/test_ranking.py`

**Work:**
- `stars` → descending by `source_metadata['stars']`
- `forks` → descending by `source_metadata['forks']`
- `subscribers` → descending by `source_metadata['subscribers']`
- `recency` → descending by `source_metadata['updated_at']` (ISO string sort works)
- `activity` → descending by `pushed_at` from GitHub API (most recent push). May need to carry `pushed_at` in source_metadata or compute a proxy.

**Tests:**
- Each criteria produces correct order (3+ items, distinct values)
- Ties are stable (original order preserved)
- Single-item list → unchanged
- Empty list → empty list

**Decision to make:** What "activity" means. Options: `pushed_at` (last push date), recent commit count (requires extra API call), or `updated_at` (already have it, but overlaps with recency). Recommendation: use `pushed_at` — it's in the search response already and is distinct from `updated_at`.

---

### Step 6: Seed repo handling

**Outcome:** Function that fetches seed repos by name and merges them into search results.

**Files:**
- Add `fetch_repo(full_name, token)` to `github_client.py` — single repo fetch via `GET /repos/{owner}/{repo}`
- `src/discovery/seeds.py` — `fetch_seed_repos(seeds, token) -> list[DiscoveredRepo]`
- `tests/discovery/test_seeds.py`

**Work:**
- For each `SeedRepo`, call `fetch_repo()` to get metadata, then `fetch_readme()` to get README
- Convert to `DiscoveredRepo` format
- Skip seeds that 404 (repo deleted/renamed) — log warning, don't fail
- Skip seeds that fail quality filters (same filters as search results)
- Return list of `DiscoveredRepo` from seeds

**Tests (mocked):**
- Seed repo fetched successfully → appears in output as `DiscoveredRepo`
- Seed repo 404 → skipped, no error
- Seed repo exists but fails quality filter (too few stars) → excluded
- Multiple seeds, one fails → others still returned

---

### Step 7: `discover_repos` integration

**Outcome:** The public API function wired end-to-end.

**Files:**
- `src/discovery/__init__.py` — implement `discover_repos()`
- `tests/discovery/test_discover_repos.py`

**Work:**
- Generate search queries from `CategoryConfig` (topics → `topic:{t}`, keywords → keyword searches, expansion topics → `topic:{t}` with higher star bar)
- Execute each query via search client
- Fetch README for each result
- Apply quality filters
- Fetch seed repos
- Merge seeds into results
- Deduplicate by `source_id`
- Sort by ranking criteria
- Truncate to `limit`
- If result is empty after all filtering → raise `NoResultsError`

**Tests (all mocked):**
- Happy path: 2 topic queries + 1 keyword + 2 seeds → deduplicated, filtered, ranked, limited
- Dedup: same repo from two queries appears once
- Seed that also appears in search → not duplicated
- All repos filtered out → `NoResultsError`
- GitHub API failure → `GitHubAPIError` propagated
- `limit` respected: 30 candidates, limit=10 → returns 10
- Expansion topics use higher min_stars bar

---

### Step 8: Integration test (skippable)

**Outcome:** One test that validates assumptions against the real GitHub API.

**Files:**
- `tests/discovery/test_integration.py`

**Work:**
- Use a small, known category (e.g., single topic "agentic-coding", min_stars=1000, limit=5)
- Call `discover_repos()` against real API
- Assert: returns non-empty list, all items are `DiscoveredRepo`, all have populated fields

**Tests:**
- Marked `@pytest.mark.skipif(not os.environ.get("GITHUB_TOKEN"))` — only runs when token is available
- Asserts structural correctness, not specific repos (results change over time)

---

## Contract Changes to Track

At phase completion, verify these against upstream docs:
- ARCH_discovery.md — already updated to reflect richer CategoryConfig (decision B)
- ARCHITECTURE.md — may need a note that Discovery's CategoryConfig is richer than the original sketch
- If `pushed_at` is added to source_metadata for the activity ranking, update the DiscoveredRepo shape in ARCH_discovery.md
