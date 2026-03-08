# 📡 GitHub Digest Bot

An automated daily digest system that discovers GitHub repositories in configured technical domains, generates AI-powered summaries, and delivers curated content to Telegram. No manual browsing required — repos come to you.

Each daily post contains **one deep-dive analysis** (500–1000 words) and **three quick-hit summaries** (2–3 sentences each). The system tracks history to avoid repetition and rotates ranking criteria to surface diverse repos throughout the week.

---

## What It Looks Like

Every day, your Telegram channel receives a formatted digest:

```
📅 Daily Digest — March 8, 2026
Ranked by: ⭐ Stars

━━━━━━━━━━━━━━━━━━━━━━
🔍 DEEP DIVE
━━━━━━━━━━━━━━━━━━━━━━

[owner/repo-name] ⭐ 4,200
View on GitHub

A 500–1000 word technical analysis covering:
• What problem the tool solves
• How it works (architecture and approach)
• How it compares to alternatives
• Who should consider using it

━━━━━━━━━━━━━━━━━━━━━━
⚡ QUICK HITS
━━━━━━━━━━━━━━━━━━━━━━

1. repo-one ⭐ 1,800
   2–3 sentence summary capturing what it does
   and its key distinguishing feature.

2. repo-two ⭐ 950
   ...

3. repo-three ⭐ 720
   ...
```

Deep dives longer than Telegram's 4,096-char limit are published to [Telegraph](https://telegra.ph/) with an excerpt and "Read full analysis" link in the message.

---

## How It Works

The pipeline runs once daily via cron, executing a 12-step process:

```
┌─────────────┐    ┌─────────────┐    ┌─────────────────┐    ┌──────────────┐
│  Discovery   │ →  │   Storage    │ →  │  Summarization   │ →  │   Delivery    │
│              │    │             │    │                 │    │              │
│ GitHub API   │    │ SQLite/MySQL│    │ Claude (LLM)    │    │ Telegram API │
│ search+fetch │    │ persist+    │    │ deep dive +     │    │ format+send  │
│ filter+rank  │    │ dedup query │    │ quick hits      │    │ Telegraph    │
└─────────────┘    └─────────────┘    └─────────────────┘    └──────────────┘
                         ↑                                          │
                         └──────── feature history recorded ────────┘
```

**Step by step:**

1. **Resolve ranking** — select today's ranking criteria (auto-rotates by day of week)
2. **Discover repos** — search GitHub by topics, keywords, and expansion topics; fetch READMEs
3. **Filter** — apply quality gates (stars, README length, not a fork, not archived)
4. **Persist** — save discovered repos to the database
5. **Dedup** — query feature history; exclude recently featured repos (tiered cooldown)
6. **Select candidates** — pick top-ranked repos for deep dive and quick hits
7. **Summarize** — generate AI summaries via Claude (Anthropic API)
8. **Save summaries** — persist to database for context in future runs
9. **Assemble digest** — compose the Telegram message
10. **Deliver** — send to Telegram (with Telegraph fallback for long content)
11. **Record features** — log which repos were featured, preventing re-featuring

The Orchestrator coordinates all of this. If any step fails, the pipeline captures the error and either falls back (tries the next candidate) or exits cleanly — it never crashes silently.

---

## Discovery: How Repos Are Found

The bot searches GitHub using three query strategies per category:

| Strategy | Query Pattern | Volume | Purpose |
|----------|--------------|--------|---------|
| **Topics** | `topic:{tag} stars:>={min}` | ~60 repos/topic (2 pages) | Primary — repos that self-tag with relevant topics |
| **Keywords** | `"{phrase}" in:description,readme stars:>={min}` | ~30 repos/keyword (1 page) | Catches repos that mention the phrase but lack topic tags |
| **Expansion** | `topic:{broad_tag} stars:>={min+50}` | ~30 repos/topic (1 page) | Casts a wider net with higher quality bar |

Additionally, **seed repos** — known tools that lack proper topic tags — can be listed explicitly and are fetched directly by `owner/repo`.

All results are deduplicated, then passed through quality filters before ranking.

### Quality Filters

Every discovered repo must pass:

| Filter | Default | Configurable? |
|--------|---------|:---:|
| Minimum stars | 50 (100 for expansion topics) | ✅ `min_stars` |
| README present and ≥ N chars | 200 chars | ✅ `min_readme_length` |
| Not a fork | Excluded | ✅ `exclude_forks` |
| Not archived | Excluded | ✅ `exclude_archived` |
| Language match | Any | ✅ `languages` |

Repos that pass all filters are ranked and the top candidates are selected for summarization.

---

## Ranking Criteria

The bot rotates ranking criteria by day of week to surface different kinds of repos:

| Day | Criteria | What It Surfaces |
|-----|----------|-----------------|
| Monday | ⭐ Stars | Most popular repos |
| Tuesday | 📈 Activity | Recently active / maintained |
| Wednesday | 🍴 Forks | Community engagement / adoption |
| Thursday | 🆕 Recency | Newest repos |
| Friday | 👀 Subscribers | Repos people are watching |
| Saturday | ⭐ Stars | (fallback) |
| Sunday | ⭐ Stars | (fallback) |

Ranking can also be fixed to a single criteria via configuration.

---

## Dedup & Cooldown

The system prevents re-featuring repos using a **tiered cooldown**:

| Feature type | Cooldown | Meaning |
|-------------|----------|---------|
| Deep dive | 90 days | A repo deep-dived won't appear in any feature for 90 days |
| Quick hit | 30 days | A quick-hit repo won't appear as a quick hit for 30 days |
| Promotion | 7 days | A quick-hit repo becomes eligible for deep dive after 7 days |

This means a repo quick-hit on day 1 could be deep-dived on day 8 — the "promotion path" — ensuring good repos get progressively deeper coverage.

---

## AI Summaries

Summaries are generated by Claude (Anthropic API) with two specialized prompts:

### Deep Dive (500–1000 words)

The LLM receives the repo's README (truncated to 15,000 chars), metadata (stars, language, creation date, topics), and optionally summaries of recently covered repos for comparison context. The system prompt instructs:

- Cover four sections: **Problem Solved**, **Approach & Architecture**, **Comparison to Alternatives**, **Target Audience**
- Be specific and technical, not vague or promotional
- If the README lacks detail, say so rather than speculating
- Use metadata for context, not as quality signals

### Quick Hit (2–3 sentences)

A briefer prompt: capture what the tool does and its key distinguishing feature. The reader should understand in under 10 seconds whether the repo is worth exploring.

### Model Selection

The bot uses a two-tier model strategy to optimize cost:

| Summary type | Default model | Rationale |
|-------------|---------------|-----------|
| Deep dive | `claude-sonnet-4-5-20250929` | Higher quality for longer analysis |
| Quick hit | `claude-3-5-haiku-20241022` | Fast and cheap for short summaries |

Models are configurable via environment variables.

---

## Project Structure

```
TGbot/
├── src/
│   ├── discovery/        # GitHub search, quality filters, ranking
│   │   ├── types.py          CategoryConfig, DiscoveredRepo, RankingCriteria
│   │   ├── github_client.py  HTTP client for GitHub API
│   │   ├── filters.py        Quality filter functions
│   │   ├── ranking.py        Sort by criteria (stars, activity, etc.)
│   │   ├── seeds.py          Fetch known repos directly
│   │   └── discover.py       Main discovery pipeline
│   │
│   ├── storage/          # Database persistence
│   │   ├── types.py          RepoRecord, SummaryRecord, StorageError
│   │   ├── db.py             Connection management (SQLite + MySQL)
│   │   ├── schema.sql        Table definitions
│   │   ├── repos.py          Repo CRUD operations
│   │   ├── summaries.py      Summary persistence
│   │   ├── features.py       Feature recording
│   │   └── history.py        Feature history queries
│   │
│   ├── summarization/    # LLM-powered summaries
│   │   ├── types.py          LLMConfig, SummaryResult, exceptions
│   │   ├── client.py         LLM provider abstraction (Anthropic)
│   │   ├── prompts.py        Prompt templates for deep/quick summaries
│   │   ├── validation.py     Content and response validation
│   │   └── summarize.py      Public API (generate_deep_dive, generate_quick_hit)
│   │
│   ├── delivery/         # Telegram message formatting and sending
│   │   ├── types.py          Digest, DeliveryResult, SummaryWithRepo
│   │   ├── formatting.py     MarkdownV2 escaping, message layout
│   │   ├── telegram_client.py  Telegram Bot API client
│   │   ├── telegraph_client.py Telegraph API client (for long content)
│   │   └── send.py           Orchestrates format → truncate → send
│   │
│   └── orchestrator/     # Daily pipeline coordination
│       ├── types.py          PipelineConfig, PipelineResult
│       ├── ranking.py        Day-of-week ranking rotation
│       └── pipeline.py       12-step daily pipeline
│
├── tests/                # Mirrors src/ structure; pytest
│   ├── discovery/            108 tests
│   ├── storage/              100+ tests
│   ├── summarization/        80+ tests
│   ├── delivery/             180+ tests
│   └── orchestrator/         114 tests
│
├── demo_pipeline.py      # Standalone demo (bypasses orchestrator)
├── models.json           # Claude model reference
├── DEPLOY.md             # Deployment & operations guide
├── ROADMAP.md            # Customization, known issues, future plans
└── data/                 # SQLite database (created at runtime)
```

---

## Quick Start

### Prerequisites

- Python 3.9+
- [GitHub personal access token](https://github.com/settings/tokens) (for 5,000 req/hour rate limit)
- [Anthropic API key](https://console.anthropic.com/)
- [Telegram bot token](https://t.me/BotFather) and a channel where the bot is an admin

### Setup

```bash
# Clone and set up
git clone <repo-url>
cd TGbot
python -m venv venv
source venv/bin/activate          # Linux/Mac
# venv\Scripts\activate           # Windows
pip install requests anthropic python-dotenv

# Configure
cp .env.example .env              # Then fill in your API keys
mkdir -p data
```

### Environment Variables

Create a `.env` file in the project root:

```bash
# Required
GITHUB_TOKEN=ghp_...
ANTHROPIC_API_KEY=sk-ant-...
TELEGRAM_BOT_TOKEN=123456:ABC-...
TELEGRAM_CHANNEL_ID=@your_channel

# Storage (defaults to in-memory SQLite if omitted)
DB_ENGINE=sqlite
DB_PATH=./data/bot.db

# Optional
TELEGRAPH_ACCESS_TOKEN=...           # For long deep dives
LLM_DEEP_DIVE_MODEL=claude-sonnet-4-5-20250929
LLM_QUICK_HIT_MODEL=claude-3-5-haiku-20241022
```

### Run

```bash
# Full pipeline (with dedup, cooldown, history)
python run_daily.py

# Or: standalone demo (no dedup/history, good for testing)
python demo_pipeline.py
```

### Tests

```bash
py -m pytest                    # Run all tests
py -m pytest tests/discovery/   # Run one module's tests
py -m pytest -v                 # Verbose output
```

---

## Configuration

All customization is done through two dataclasses — no code changes needed for common scenarios.

### Defining a Category

```python
from discovery.types import CategoryConfig, SeedRepo

category = CategoryConfig(
    name="agentic-coding",
    description="AI-powered coding tools and agents",

    # Primary search: GitHub topic tags
    topics=["ai-coding-agent", "ai-coding-assistant"],

    # Secondary search: keyword phrases in descriptions/READMEs
    keywords=["agentic coding"],

    # Broader search with higher star threshold (+50)
    expansion_topics=["llm-agent", "code-generation"],

    # Known repos that lack proper tags
    seed_repos=[
        SeedRepo("paul-gauthier/aider", "Aider", "Popular CLI coding assistant"),
    ],

    # Quality filters
    min_stars=100,
    min_readme_length=200,
    languages=None,        # None = any language; ["Python", "Rust"] = filter
)
```

### Pipeline Settings

```python
from orchestrator import PipelineConfig

config = PipelineConfig(
    category=category,
    channel_id="@your_channel",

    ranking_criteria=None,     # None = auto-rotate by day of week
    deep_dive_count=1,         # Deep dives per digest
    quick_hit_count=3,         # Quick hits per digest
    discovery_limit=20,        # Max repos to discover per run
    cooldown_days=90,          # Deep-dive cooldown
    quick_hit_cooldown_days=30,
    promotion_gap_days=7,      # Quick→deep promotion gap
)
```

See [ROADMAP.md](ROADMAP.md) for detailed customization scenarios (multiple categories, language filtering, seed repos, model selection, ranking changes).

---

## Architecture

Five modules with clean dependency boundaries:

```
Discovery ──→ Orchestrator ←── Storage
                  ↓   ↑
          Summarization
                  ↓
              Delivery
```

- **Discovery** and **Storage** are leaf modules with no dependencies on each other
- **Summarization** reads repo content from Storage
- **Delivery** receives a finished Digest — no upstream knowledge
- **Orchestrator** coordinates everything; the only module that imports all others

Modules communicate through typed dataclasses (`DiscoveredRepo`, `RepoRecord`, `SummaryResult`, `Digest`). Each module defines its own exception types with semantic context (status codes, retry hints, content lengths).

See [ARCHITECTURE.md](ARCHITECTURE.md) for the full component map, data flow, and design decisions.

---

## Cost

| Resource | Per-run usage | Cost |
|----------|--------------|------|
| GitHub API | ~200 calls | Free (within 5,000/hr token limit) |
| Anthropic (deep dive) | ~5,500 tokens | ~$0.02–0.10 |
| Anthropic (quick hits ×3) | ~2,300 tokens each | ~$0.01–0.05 |
| Telegram / Telegraph | 1–2 calls | Free |
| **Daily total** | | **~$0.05–0.40** |
| **Monthly total** | | **~$2–12** |

---

## Documentation

| File | Contents |
|------|----------|
| [DEPLOY.md](DEPLOY.md) | Step-by-step deployment, operations, monitoring, troubleshooting |
| [ROADMAP.md](ROADMAP.md) | Customization guide, known issues, future enhancements |
| [ARCHITECTURE.md](ARCHITECTURE.md) | Component map, data flow, design decisions |
| [PROJECT.md](PROJECT.md) | Scope, audience, constraints, success criteria |

Per-module architecture specs: `ARCH_discovery.md`, `ARCH_storage.md`, `ARCH_summarization.md`, `ARCH_delivery.md`, `ARCH_orchestrator.md`

---

## License

Private project. Not currently licensed for redistribution.
