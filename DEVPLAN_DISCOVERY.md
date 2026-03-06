# DEVPLAN: Discovery

## Cold Start Summary

**What this is:** Discovery module — finds GitHub repos matching a category's search criteria, applies quality filters, ranks results, and returns `list[DiscoveredRepo]`. Pure leaf, no dependencies on other modules.

**Key constraints:**
- GitHub REST API v3 (not GraphQL). 5,000 requests/hour with token, 60 without.
- Search API returns max 1,000 results per query, 100 per page, 30 per page default.
- README fetched via Contents API (auto-resolves branch/filename). Truncated to 50KB.
- Must work on Python 3.11, host has no special packages — stick to `requests` + stdlib.
- CategoryConfig includes expansion_topics (higher star bar), seed_repos (direct fetch by name), exclude_forks, exclude_archived. See ARCH_discovery.md for full contract.
- "Activity" ranking uses `pushed_at` (most recent push), distinct from `updated_at`.

**Gotchas:**
- (none discovered)

## Current Status

**Phase:** 1 — Complete
**Blocked/Broken:** Step 8 (integration test) deferred — requires GITHUB_TOKEN not currently available.

---

## Phase 1: Discovery Implementation (Build) — COMPLETE

Steps 1–7 implemented, 108 tests passing. Step 8 (integration test) deferred. See DEVLOG_DISCOVERY.md for full details.

**Deferred: Step 8 — Integration test.** Write `tests/discovery/test_integration.py` when GITHUB_TOKEN is available. Single test calling real API with known query (topic "agentic-coding", min_stars=1000, limit=5). Mark `@pytest.mark.skipif(not os.environ.get("GITHUB_TOKEN"))`.
