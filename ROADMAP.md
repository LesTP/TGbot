# Roadmap — Customization, Known Issues, and Future Enhancements

Forward-looking reference for the GitHub Digest Bot. Covers how to customize the bot's behavior without code changes, what improvements are known but not yet implemented, and what extensions are anticipated.

---

## Table of Contents

1. [Customization Guide](#customization-guide)
2. [How Discovery Queries Work](#how-discovery-queries-work)
3. [Known Issues & Improvements](#known-issues--improvements)
4. [Future Enhancements](#future-enhancements)

---

## Customization Guide

Most configuration is done through two dataclasses passed to the pipeline. No code changes are needed for common scenarios.

### CategoryConfig — What Repos to Find

Defined in `src/discovery/types.py`:

```python
@dataclass
class CategoryConfig:
    name: str                          # Category label (shown in logs)
    description: str                   # Human description

    topics: list[str]                  # GitHub topic tags (primary search)
    keywords: list[str]               # Keyword phrases (secondary search)
    expansion_topics: list[str]       # Broader topics (higher star threshold)
    seed_repos: list[SeedRepo]        # Known repos to always include

    min_stars: int = 50               # Minimum star threshold
    min_readme_length: int = 200      # Minimum README length (chars)
    require_readme: bool = True       # Reject repos without README
    exclude_forks: bool = True        # Reject forked repos
    exclude_archived: bool = True     # Reject archived repos
    languages: Optional[list[str]] = None  # Filter by language (None = any)
```

### PipelineConfig — How the Pipeline Behaves

Defined in `src/orchestrator/types.py`:

```python
@dataclass
class PipelineConfig:
    category: CategoryConfig          # What to search for
    channel_id: str                   # Where to deliver

    ranking_criteria: Optional[RankingCriteria] = None  # None = auto-rotate
    deep_dive_count: int = 1          # Deep dives per digest
    quick_hit_count: int = 3          # Quick hits per digest
    discovery_limit: int = 20         # Max repos to discover per run
    cooldown_days: int = 90           # Deep-dive cooldown window
    quick_hit_cooldown_days: int = 30 # Quick-hit cooldown window
    promotion_gap_days: int = 7       # Quick→deep promotion gap
    context_lookback_days: int = 14   # Recent summaries for LLM context
```

### Common Scenarios

#### Change the topic / category

Change only the `CategoryConfig` in your entry-point script. Zero code changes.

```python
# Example: Rust CLI tools instead of agentic coding
config = PipelineConfig(
    category=CategoryConfig(
        name="rust-cli",
        description="Command-line tools written in Rust",
        topics=["rust-cli", "command-line-tool"],
        keywords=["rust cli tool"],
        expansion_topics=["rust", "terminal-app"],
        min_stars=200,
        languages=["Rust"],
    ),
    channel_id="@rust_cli_digest",
)
```

#### Add seed repos (known tools that search misses)

Many well-known tools lack proper GitHub topic tags. Seeds fetch them directly by `owner/repo`, bypass search, but still go through quality filters and dedup.

```python
from discovery.types import SeedRepo

category = CategoryConfig(
    name="agentic-coding",
    topics=["ai-coding-agent"],
    keywords=["agentic coding"],
    seed_repos=[
        SeedRepo("Significant-Gravitas/AutoGPT", "AutoGPT",
                 "Major agent framework, missing topic tags"),
        SeedRepo("OpenInterpreter/open-interpreter", "Open Interpreter",
                 "Popular but poorly tagged"),
        SeedRepo("paul-gauthier/aider", "Aider",
                 "Leading CLI coding assistant"),
    ],
    min_stars=100,
)
```

#### Run multiple categories

The pipeline runs one category per invocation. For multiple categories:

**Option A: Multiple cron jobs (recommended — isolated failures):**

```python
# run_daily.py --category agentic-coding
# run_daily.py --category rust-cli

import argparse

CATEGORIES = {
    "agentic-coding": CategoryConfig(
        name="agentic-coding",
        topics=["ai-coding-agent", "ai-coding-assistant"],
        keywords=["agentic coding"],
        min_stars=100,
    ),
    "rust-cli": CategoryConfig(
        name="rust-cli",
        topics=["rust-cli", "command-line-tool"],
        keywords=["rust cli tool"],
        languages=["Rust"],
        min_stars=200,
    ),
}

CHANNEL_IDS = {
    "agentic-coding": "@agentic_digest",
    "rust-cli": "@rust_cli_digest",
}

parser = argparse.ArgumentParser()
parser.add_argument("--category", required=True, choices=CATEGORIES.keys())
args = parser.parse_args()

config = PipelineConfig(
    category=CATEGORIES[args.category],
    channel_id=CHANNEL_IDS[args.category],
)
result = run_daily_pipeline(config)
```

Set up two cron jobs, staggered by 5–10 minutes to avoid API rate-limit overlap:

```
09:00  .../python run_daily.py --category agentic-coding
09:10  .../python run_daily.py --category rust-cli
```

**Option B: Loop in one script:**

```python
for name, cat in CATEGORIES.items():
    config = PipelineConfig(category=cat, channel_id=CHANNEL_IDS[name])
    result = run_daily_pipeline(config)
    storage.close()  # reset DB state between runs
```

Simpler (one cron job), but a failure in category 1 may prevent category 2 from running.

#### Tune discovery quality

| Goal | Config change |
|------|---------------|
| More repos per digest | Increase `discovery_limit` (e.g., 30) and `quick_hit_count` (e.g., 5) |
| Higher quality only | Increase `min_stars` (e.g., 500) |
| Longer/shorter cooldown | Adjust `cooldown_days` (default 90), `quick_hit_cooldown_days` (default 30) |
| Only Python repos | Set `languages=["Python"]` in `CategoryConfig` |
| Broader search | Add more `expansion_topics` (higher star bar applied automatically) |
| Fixed ranking | Set `ranking_criteria=RankingCriteria.STARS` instead of `None` (auto-rotate) |

#### Change LLM models

Override via environment variables (no code change):

```bash
# In .env:
LLM_DEEP_DIVE_MODEL=claude-sonnet-4-5-20250929
LLM_QUICK_HIT_MODEL=claude-haiku-4-5-20251001
```

Or set them directly in `LLMConfig` if using `demo_pipeline.py`.

#### Change the ranking rotation

Edit the `_DAY_TO_RANKING` dict in `src/orchestrator/ranking.py`:

```python
_DAY_TO_RANKING = {
    0: RankingCriteria.STARS,        # Monday
    1: RankingCriteria.ACTIVITY,     # Tuesday
    2: RankingCriteria.FORKS,        # Wednesday
    3: RankingCriteria.RECENCY,      # Thursday
    4: RankingCriteria.SUBSCRIBERS,  # Friday
    5: RankingCriteria.STARS,        # Saturday
    6: RankingCriteria.STARS,        # Sunday
}
```

Or bypass entirely by setting `ranking_criteria` explicitly in `PipelineConfig`.

### What Requires Code Changes

| Enhancement | Code change? | Where |
|-------------|:---:|-------|
| Different tags/topics/keywords | ❌ | Entry-point script config |
| Different star thresholds | ❌ | Entry-point script config |
| Language filter | ❌ | Entry-point script config |
| Seed repos | ❌ | Entry-point script config |
| Multiple categories | ❌ | Entry-point script + cron |
| Different LLM models | ❌ | `.env` file |
| Cooldown period tuning | ❌ | Entry-point script config |
| Ranking rotation schedule | ⚠️ Tiny | `ranking.py` dict |
| New ranking criteria | ✅ | `RankingCriteria` enum + `ranking.py` + `github_client.py` sort mapping |
| New discovery source (not GitHub) | ✅ | New discovery module + orchestrator wiring |
| New delivery channel (not Telegram) | ✅ | New delivery module + orchestrator wiring |
| Richer metadata in summaries | ✅ | `prompts.py` system/user prompts |
| Different summary format/length | ✅ | `prompts.py` + possibly `formatting.py` |

---

## How Discovery Queries Work

Understanding the query construction helps you choose effective tags. The pipeline in `src/discovery/discover.py` builds three types of GitHub Search API queries:

### Query types

| Type | Query template | Volume | Pages |
|------|---------------|--------|-------|
| **Topics** (primary) | `topic:{tag} stars:>={min_stars}` | ~60 repos per topic | 2 × 30 |
| **Keywords** (secondary) | `"{keyword}" in:description,readme stars:>={min_stars}` | ~30 repos per keyword | 1 × 30 |
| **Expansion topics** (broader) | `topic:{tag} stars:>={min_stars + 50}` | ~30 repos per topic | 1 × 30 |

Total raw results per category: ~120–200 repos. After filtering: ~20–50 quality candidates. This is comfortable headroom.

### Tips for effective tag selection

- **Topics** should be specific GitHub topic tags that repos self-apply (e.g., `ai-coding-agent`, not `AI`). Browse [github.com/topics](https://github.com/topics) to find real ones.
- **Keywords** search in descriptions and READMEs — useful for phrases like `"agentic coding"` that repos mention but don't tag.
- **Expansion topics** cast a wider net (e.g., `llm-agent` is broader than `ai-coding-agent`) but use a `min_stars + 50` threshold to filter noise.
- All results are **deduplicated** before filtering, so overlap between queries is harmless — don't worry about the same repo appearing in multiple queries.
- **Seed repos** are fetched directly by `owner/repo`. Use them for well-known tools that lack proper topic tags.

### Checking available topics

To see what GitHub topics exist for a domain, browse:

```
https://github.com/topics/{topic-name}
```

Or search on GitHub and look at the topic tags on repos you consider high-quality. Good topics have 50+ repos using them.

---

## Known Issues & Improvements

Issues identified during the full codebase review. Organized by priority.

### High Priority — Before Production

| # | Issue | Module | Status |
|---|-------|--------|--------|
| 1 | Missing database indexes | Storage | Open — no performance issues at current scale (<100 repos), but add indexes before data grows significantly |
| 2 | No MySQL integration tests | Storage | Open — not urgent since production uses SQLite. Only relevant if MySQL is adopted |
| 3 | Deferred Discovery integration test | Discovery | Open — `@pytest.mark.skipif` test not yet written |
| 4 | `storage.close()` not called in pipeline | Orchestrator | Open — minor (SQLite auto-closes on process exit in cron) |

> **Post-deployment note (2026-03-08):** The pipeline is running successfully in production with SQLite. Items 1–4 are now lower priority since: (1) data volume is small (~20 repos/day), (2) MySQL is not in use, (3) the real GitHub API is exercised by daily cron, and (4) cron processes exit cleanly. These remain valid improvements but are no longer blocking.

### Medium Priority — Soon After Shipping

| # | Issue | Module | Description |
|---|-------|--------|-------------|
| 5 | SQL placeholder duplication | Storage | Each module (`repos.py`, `summaries.py`, `features.py`, `history.py`) has its own SQLite-vs-MySQL branching (~40+ duplicated lines). Extract a `_execute()` helper. |
| 6 | Pre-filter logic duplication | Discovery | `_pre_filter()` in `discover.py` mirrors `apply_quality_filters()` in `filters.py`. Changes must be made in two places. Extract a shared validator or add a sync comment. |
| 7 | Broad `except Exception` | Storage | All DB modules catch `Exception` broadly, which can mask unexpected errors. Catch `(sqlite3.Error, mysql.connector.Error)` specifically. |
| 8 | Datetime handling duplication | Storage | Two identical `_parse_datetime()` functions in `repos.py` and `summaries.py`. Consolidate into shared utility. Also, `datetime.now()` is naive (no timezone). Consider UTC-aware datetimes. |
| 9 | Missing token warning | Discovery | If `GITHUB_TOKEN` is not set, the pipeline silently falls to 60 req/hour. Add a `logger.warning()`. |
| 10 | Missing docstrings on helpers | Orchestrator | `_build_storage_config`, `_build_llm_config`, `_generate_quick_hits`, `_build_summary_with_repo`, `_assemble_digest` lack docstrings. |

### Low Priority — Polish

| # | Issue | Module | Description |
|---|-------|--------|-------------|
| 11 | `_is_expansion` tag via dict key | Discovery | Fragile private-key convention on raw dicts. Could use a wrapper dataclass instead. |
| 12 | `SeedRepo.full_name` not validated | Discovery | `split("/")` on malformed input raises `ValueError` at runtime instead of config time. Add validation in `__post_init__`. |
| 13 | Untyped `dict` returns | Summarization | `token_usage: dict` could be a `TypedDict` for better IDE support and static analysis. |
| 14 | No `since_days` validation | Storage | Negative or zero values produce semantically undefined queries. Add `if since_days <= 0: raise ValueError(...)`. |
| 15 | `models.json` not integrated | Orchestrator | Model versions are hardcoded in `pipeline.py`. The JSON file exists but isn't consumed. Either integrate it or document it as reference-only. **Deployment note (2026-03-08):** The old default `claude-3-5-haiku-20241022` returned 404 — it was unavailable on the production account. `models.json` was used to identify `claude-haiku-4-5-20251001` as the correct replacement. Integrating `models.json` at runtime would prevent this class of issue. |

---

## Future Enhancements

Anticipated extensions from `PROJECT.md` and architectural observations. None are currently planned — this section captures intent for when the time comes.

### Additional Discovery Sources

**What:** Reddit, Hacker News, Product Hunt, RSS feeds as alternative/supplementary repo discovery sources.

**Architecture impact:** Additive. Each new source is a new module that produces `DiscoveredRepo` objects. The Orchestrator calls the new discovery module alongside (or instead of) the GitHub one. `DiscoveredRepo` was designed source-agnostic — `source` field distinguishes origin.

**Estimated scope:** New module per source + orchestrator wiring. No changes to Storage, Summarization, or Delivery.

### Additional Delivery Channels

**What:** Email digest, web archive page, RSS feed output.

**Architecture impact:** Additive. Each new channel is a new delivery module that accepts a `Digest` and returns a result. The `Digest` type is format-agnostic.

**Estimated scope:** New module per channel + orchestrator wiring. No changes to Discovery, Storage, or Summarization.

### Multi-Category Support

**What:** Multiple categories with separate channels or rotation.

**Architecture impact:** Configuration-only if using the multi-cron-job approach (see [Customization Guide](#run-multiple-categories) above). If categories share a database and need cross-category dedup, the Storage schema would need a `category` column on `feature_history`.

**Estimated scope:** Minimal for isolated categories. Moderate if cross-category coordination is needed.

### Trend Detection

**What:** Weekend "trend summary" posts that analyze patterns across the week's discoveries.

**Architecture impact:** Requires accumulated data (4–6 weeks minimum). New analysis module that queries Storage for historical patterns. New Summarization prompt type. New Delivery format.

**Estimated scope:** New module + new prompts + orchestrator changes. Moderate.

### Major-Update Refeaturing

**What:** Re-feature a repo when it has changed significantly (README change >30%, version bump, star growth spike).

**Architecture impact:** Storage already tracks `raw_content` (README) and metadata (stars). A comparison function could detect meaningful changes. The cooldown system would need a "bypass" path for major updates.

**Estimated scope:** New comparison logic in Orchestrator + cooldown override. Moderate.

### Batch/Queue Architecture

**What:** Weekly pre-generation of summaries with daily posting from a queue. Decouples generation from delivery for cost optimization and reliability.

**Architecture impact:** Adds a "post queue" table to Storage. Orchestrator splits into a generator (weekly) and a poster (daily). Summary generation and delivery become independent pipeline stages.

**Estimated scope:** Significant refactor of Orchestrator. Storage schema change. Currently deferred per `PROJECT.md`.

### User Commands

**What:** Telegram bot commands like `/history`, `/search`, `/categories`.

**Architecture impact:** Requires a long-running bot process (not cron) or a webhook handler. Adds a new interaction layer between Telegram and Storage.

**Estimated scope:** Significant — changes the deployment model from cron to daemon or webhook.

---

## Cost Reference

Current estimated costs per pipeline run:

| Resource | Usage | Cost |
|----------|-------|------|
| GitHub API | ~200 calls (well within 5,000/hr free tier) | Free |
| Anthropic (deep dive) | ~4,000 input + ~1,500 output tokens | ~$0.02–0.10 |
| Anthropic (quick hits ×3) | ~2,000 input + ~300 output tokens each | ~$0.01–0.05 |
| Telegram API | 1–2 calls | Free |
| Telegraph API (optional) | 0–1 calls | Free |
| **Daily total** | | **~$0.05–0.40** |
| **Monthly total** | | **~$2–12** |

Budget ceiling from `PROJECT.md`: $15/month. Current estimates are well within budget.
