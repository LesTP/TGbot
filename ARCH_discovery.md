# ARCH: Discovery

## Purpose
Find repositories on GitHub that match a category's search criteria, apply quality filters, and return ranked candidates. Discovery is a pure leaf — it talks to the GitHub API and returns results. It has no knowledge of feature history, summarization, or delivery.

## Public API

### discover_repos
- **Signature:** `discover_repos(category: CategoryConfig, ranking: RankingCriteria, limit: int = 20) -> list[DiscoveredRepo]`
- **Parameters:**
  - `category`: CategoryConfig — full category definition including topics, keywords, expansion topics, seed repos, and quality filters (see Types below)
  - `ranking`: RankingCriteria — one of: stars, forks, subscribers, recency, activity
  - `limit`: int — max repos to return (default 20, max 100)
- **Returns:** list[DiscoveredRepo], sorted by ranking criteria, all passing quality filters. May return fewer than `limit` if insufficient candidates.
- **Errors:**
  - `GitHubAPIError` — API request failed (rate limit, auth, network). Includes HTTP status and message.
  - `NoResultsError` — query returned zero repos after filtering. Includes query details for debugging.

## Types

### CategoryConfig
```python
CategoryConfig:
  name: str                          # category identifier (e.g. "agentic-coding")
  description: str                   # human-readable description
  topics: list[str]                  # primary topic searches (highest priority)
  keywords: list[str]               # keyword searches (broader, may have noise)
  expansion_topics: list[str]        # secondary topics (higher min_stars bar)
  seed_repos: list[SeedRepo]        # known repos to fetch directly regardless of search
  min_stars: int                     # default 50; expansion topics use min_stars + 50
  min_readme_length: int             # default 200 characters
  require_readme: bool               # default True
  exclude_forks: bool                # default True
  exclude_archived: bool             # default True
  languages: list[str] | None       # language filter (None = any)
```

### SeedRepo
```python
SeedRepo:
  full_name: str    # "owner/repo"
  name: str         # display name
  reason: str       # why this is seeded
```

### RankingCriteria
Enum: `stars`, `forks`, `subscribers`, `recency`, `activity`

### DiscoveredRepo
```
DiscoveredRepo:
  source: str ("github")
  source_id: str (GitHub repo ID as string)
  name: str (repo name, e.g. "owner/repo")
  url: str (full GitHub URL)
  description: str | None
  raw_content: str (README text, truncated to 50KB)
  source_metadata: dict
    stars: int
    forks: int
    subscribers: int
    primary_language: str | None
    created_at: str (ISO 8601)
    updated_at: str (ISO 8601)
    pushed_at: str (ISO 8601)
    topics: list[str]
```

### Errors
- `GitHubAPIError(message: str, status_code: int | None, response_body: str | None)`
- `NoResultsError(message: str, query_details: dict)`

## Inputs
- GitHub API token (from environment/config)
- CategoryConfig: defines what to search for
- RankingCriteria: defines sort order

## Outputs
- list[DiscoveredRepo]:
  - Guarantees: all returned repos pass quality filters (min stars, README present and above min length, not forked, not archived). raw_content is always populated (repos without readable READMEs are excluded).
  - Deduplication: repos appearing in multiple search queries or as both a search result and a seed repo are deduplicated (by source_id). Seed repos are merged into search results before dedup.

## State
None. Discovery is stateless — every call is independent.

## Usage Example
```python
from discovery import discover_repos
from discovery.types import CategoryConfig, SeedRepo, RankingCriteria

category = CategoryConfig(
    name="agentic-coding",
    description="AI-powered coding assistants and autonomous coding agents",
    topics=["agentic-coding", "ai-coding-assistant", "coding-assistant"],
    keywords=["agentic coding", "AI developer tool"],
    expansion_topics=["ai-coding", "codegen"],
    seed_repos=[
        SeedRepo("getcursor/cursor", "Cursor", "Major AI IDE, poor topic tagging"),
    ],
    min_stars=50,
    min_readme_length=500,
)

repos = discover_repos(category, ranking=RankingCriteria.STARS, limit=20)
for repo in repos:
    print(f"{repo.name} — {repo.source_metadata['stars']} stars")
```
