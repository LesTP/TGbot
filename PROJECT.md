# GitHub Digest Bot

## Spark
> Staying current with emerging tools in technical domains (agentic coding, dev utilities) means manually browsing GitHub — easy to forget, time-consuming, and existing solutions like GitHub Trending are too broad and lack context.

## What This Is
An automated daily digest system that discovers GitHub repositories in configured categories, generates AI-powered summaries, and delivers curated content to Telegram. Each daily post contains one deep-dive analysis and three quick-hit summaries. The system tracks history to avoid repetition and rotates ranking criteria to surface diverse repos.

## Audience
Technical professionals actively working in specific domains who want passive discovery of new tools without manual research overhead. Primary persona: a developer working with agentic coding tools who wants to know what alternatives exist and what approaches are emerging, without spending 30 minutes a day browsing GitHub.

## Scope

### Core
- Discover GitHub repos matching category criteria (topics, keywords) with quality filtering (minimum stars, README presence)
- Generate AI summaries: deep dive (500-1000 words, analysis/comparison/use cases) and quick hits (2-3 sentences)
- Deliver daily digest to Telegram: 1 deep dive + 3 quick summaries with repo links and metadata
- Track feature history to prevent re-featuring repos within a cooldown window
- Persist discovered repos and generated content in a database

### Flexible
- [in] Ranking rotation by day of week (stars, activity, forks, recency, subscribers)
- [in] Two-tier LLM model strategy (expensive model for deep dives, cheap for quick hits)
- [in] Major-update refeaturing logic (README change >30%, high commit activity, version bump, star growth)
- [in] 90-day cooldown window (specific duration is tunable)
- [deferred] Batch/queue architecture — weekly pre-generation with daily posting from queue. MVP can use a simpler daily pipeline; batch is an optimization for cost and reliability
- [deferred] Trend detection and weekend trend posts — requires 4-6 weeks of accumulated data
- [deferred] Multi-category support with separate channels or rotation
- [deferred] User commands (/history, /search, /categories)
- [deferred] Email delivery option

### Exclusions
- Web dashboard or archive UI
- User accounts, personalization, or preference profiles
- Community features (public channels, user-submitted categories, collaborative filtering)
- Interactive Telegram features (reaction buttons, voting)
- Code quality metrics, security scanning, dependency analysis
- Real-time / breaking-news discovery

## Constraints
- **Language:** Python 3.9+
- **APIs:** GitHub REST API v3, Anthropic API (Claude models), Telegram Bot API
- **Database:** MySQL/MariaDB
- **Hosting:** Existing paid host (WordPress server, s501) — Python 3.11 verified, virtual environment required (PEP 668), cron via web UI scheduler. Bot location: `/home/mikey/private/tgbot/`
- **Cost:** Monthly LLM budget <$15 (estimated $0.15-0.40/day for 1 deep + 3 quick)
- **Rate limits:** GitHub API 5,000 requests/hour with token; Anthropic API per-plan limits
- **Scheduling:** Cron-based; no long-running daemon process
- **Single instance:** No horizontal scaling, sequential processing

## Prior Art
- **GitHub Trending** — surfaces popular repos but too broad, no domain focus, no summaries or comparison context
- **GitHub Explore** — curated but infrequent, not personalized to specific technical domains
- **Newsletter services (TLDR, etc.)** — human-curated, cover broad tech news, not focused on repo-level discovery in niche domains

## Success Criteria
- A user receives a Telegram message every day at the scheduled time containing 1 deep dive + 3 quick hits
- The system does not re-feature the same repo within the cooldown window
- Deep-dive summaries provide actionable insight: what the tool does, how it compares, who should use it
- Quick-hit summaries are concise enough to scan in under 10 seconds each
- The system recovers gracefully from API failures without missing posts
- A user can click repo links in the digest and land on the correct GitHub page
- Monthly LLM costs stay under $15

## Risks and Open Questions
- [resolved] **Hosting viability:** ✅ Verified 2026-03-05. Python 3.11 available, virtual environment works, pip installs succeed, outbound HTTPS to GitHub/Anthropic/Telegram confirmed, cron jobs work via web UI (CLI crontab blocked). Constraints: cannot write to `~/` (use `~/private/`), must use venv (PEP 668). See `hosting_investigation/HOSTING_CHECKLIST.md` for details.
- [resolved] **GitHub search coverage:** ✅ Verified 2026-03-05. Found 1,373 unique repos across 22 search queries. 853 high-quality repos (100+ stars), 62 medium-quality (50-99 stars). Volume far exceeds the 150-200 needed. Known tools coverage: 8/23 (34%) — many major tools (Cursor, AutoGPT, OpenHands, Open Interpreter) exist but don't appear in topic/keyword searches, suggesting a curated seed list may improve recall. See `github_search_investigation/github_search_results.json` for full data.
- [implementation] **LLM cost validation:** The $0.15-0.40/day estimate assumes specific prompt/response sizes. Validate with real runs during summarization implementation.
- [implementation] **Telegram message length:** 4,096 character limit may require splitting deep dives. Need a formatting strategy.
- [implementation] **README quality variance:** Repos with minimal or non-English READMEs will produce weak summaries. Need a fallback or skip strategy.
- [watch] **Content staleness:** If batch architecture is adopted, content can be up to 7 days old. Monitor whether this matters for the "stay current" goal.
- [watch] **Category exhaustion:** A single narrow category may run out of quality repos to feature. Monitor discovery yield over the first few weeks.

## Extension Points
- **Additional discovery sources** (Reddit, Hacker News, Product Hunt, RSS) are likely. The boundary between discovery and downstream processing should be source-agnostic — discovery modules produce a normalized "discovered item" shape that summarization and posting consume without knowing the source.
- **Additional output channels** beyond Telegram (email, web archive, RSS feed) are plausible. The boundary between content generation and delivery should be format-agnostic.
- **Additional categories** are anticipated. Category configuration should be data-driven, not hard-coded.
- **Richer metadata and analysis** (code quality, dependency graphs, license tracking) may be added to discovery. The metadata model should be extensible.

## Size Estimate
Multi-module. Discovery (GitHub API integration + filtering), summarization (LLM interaction + prompt management), delivery (Telegram formatting + posting), and data persistence are genuinely separate concerns with different change reasons and different external dependencies.

---

## Setup Gotchas

Lessons learned during environment investigation. Reference these when setting up or troubleshooting.

### Host Environment (s501)

| Issue | Solution |
|-------|----------|
| Cannot create directories in `~/` | Home dir owned by root. Use `~/private/` instead (owned by mikey) |
| `pip install` fails with "externally-managed-environment" | PEP 668 on modern Debian/Ubuntu. Use virtual environment: `python3 -m venv venv && source venv/bin/activate` |
| `crontab -e` permission denied | CLI crontab blocked. Use web UI cron scheduler in hosting control panel |
| Cron job "command not found" | Web UI needs full absolute paths: `/home/mikey/private/tgbot/venv/bin/python /home/mikey/private/tgbot/script.py` |

### Local Development (Windows)

| Issue | Solution |
|-------|----------|
| `pip` not recognized | Use `py -m pip install package` instead |
| `python -m pytest` fails (no module named pytest) | Use `py -m pytest` — the `py` launcher finds the Python that has pytest installed |
| Unicode/emoji print errors (cp1252 codec) | Add at top of script: `sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')` |

### GitHub API

| Issue | Solution |
|-------|----------|
| Rate limited (60 requests/hour) | Use personal access token for 5,000/hour: `--token YOUR_TOKEN` or `GITHUB_TOKEN` env var |
| Known tools missing from search results | Many repos lack proper topic tags. Supplement search with curated seed list |

---

## Change History
| Date | What Changed | Why |
|------|-------------|-----|
| 2025-03-04 | Initial extraction from SPEC.md | Retrofitting existing spec into framework. Batch/queue moved to deferred flexible scope. Hosting flagged as must-resolve. Source-agnostic extension point added. |
| 2026-03-05 | Hosting viability verified | SSH tested, Python 3.11 confirmed, venv/pip work, outbound HTTPS works, cron via web UI works. Risk resolved. |
| 2026-03-05 | GitHub search coverage verified | 1,373 unique repos found, 853 high-quality. Volume exceeds requirements. Seed list recommended for known tools with poor tagging. Risk resolved. |
| 2026-03-05 | Added Setup Gotchas section | Documented environment-specific issues and workarounds discovered during investigation. |
