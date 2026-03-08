# Deployment & Operations Guide

How to deploy, run, and maintain the GitHub Digest Bot.

---

## Prerequisites

| Requirement | Verified |
|-------------|----------|
| SSH access to s501 | `ssh mikey@s501` |
| Python 3.11 in venv | `/home/mikey/private/tgbot/venv/bin/python` |
| Outbound HTTPS | GitHub, Anthropic, Telegram all reachable |
| Cron scheduler | Web UI (not CLI `crontab`) |
| Bot directory | `/home/mikey/private/tgbot/` |

See `hosting_investigation/HOSTING_CHECKLIST.md` for the full viability report.

### API Keys Required

| Key | Where to get it |
|-----|-----------------|
| `GITHUB_TOKEN` | github.com → Settings → Developer settings → Personal access tokens |
| `ANTHROPIC_API_KEY` | console.anthropic.com → API Keys |
| `TELEGRAM_BOT_TOKEN` | Talk to @BotFather on Telegram → `/newbot` |
| `TELEGRAM_CHANNEL_ID` | Your channel's `@username` or numeric ID (e.g. `@my_digest`) |
| `TELEGRAPH_ACCESS_TOKEN` (optional) | Call the Telegraph API `createAccount` endpoint, or use `telegraph_client.create_account()` |

---

## Step-by-Step Deployment

### 1. Upload the code

From your local machine (PowerShell):

```powershell
scp -r src/ mikey@s501:~/private/tgbot/src/
```

Only `src/` is needed from the repo. The entry-point script (`run_daily.py`) is created on the server in step 4 below. Everything else — `tests/`, `github_search_investigation/`, `hosting_investigation/`, doc files (`ARCH_*.md`, `DEVPLAN_*.md`, `DEVLOG_*.md`), and `demo_pipeline.py` — is development-only and should not be deployed.

### 2. Install dependencies

```bash
ssh mikey@s501
source ~/private/tgbot/venv/bin/activate
pip install requests anthropic python-dotenv
```

`python-dotenv` is needed for `.env` file loading. If `requests` and `anthropic` are already installed from the hosting investigation, only `python-dotenv` is new.

### 3. Create the `.env` file

```bash
cat > ~/private/tgbot/.env << 'EOF'
# Required
GITHUB_TOKEN=ghp_your_token_here
ANTHROPIC_API_KEY=sk-ant-your_key_here
TELEGRAM_BOT_TOKEN=123456:ABC-DEF1234ghIkl-zyx57W2v1u123ew11
TELEGRAM_CHANNEL_ID=@your_channel_name

# Storage
DB_ENGINE=sqlite
DB_PATH=/home/mikey/private/tgbot/data/bot.db

# Optional: Telegraph for long deep dives
# TELEGRAPH_ACCESS_TOKEN=your_telegraph_token

# Optional: Override LLM model defaults
# LLM_DEEP_DIVE_MODEL=claude-sonnet-4-5-20250929
# LLM_QUICK_HIT_MODEL=claude-3-5-haiku-20241022
EOF

chmod 600 ~/private/tgbot/.env
mkdir -p ~/private/tgbot/data
```

**Important:** `chmod 600` ensures only your user can read the secrets.

### 4. Create the production entry-point script

Save this as `~/private/tgbot/run_daily.py`:

```python
#!/usr/bin/env python3
"""Daily pipeline entry point for cron."""

import io
import sys
import logging
from pathlib import Path
from dotenv import load_dotenv

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")
sys.path.insert(0, str(Path(__file__).parent / "src"))

load_dotenv(Path(__file__).parent / ".env")

from discovery.types import CategoryConfig
from orchestrator import run_daily_pipeline, PipelineConfig

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
    handlers=[
        logging.FileHandler(Path(__file__).parent / "data" / "pipeline.log"),
        logging.StreamHandler(),
    ],
)

def main():
    config = PipelineConfig(
        category=CategoryConfig(
            name="agentic-coding",
            description="AI-powered coding tools and agents",
            topics=["ai-coding-agent", "ai-coding-assistant"],
            keywords=["agentic coding"],
            expansion_topics=["llm-agent", "code-generation"],
            min_stars=100,
            min_readme_length=200,
        ),
        channel_id="@your_channel_name",
        discovery_limit=20,
    )

    result = run_daily_pipeline(config)

    if result.success:
        logging.info(
            "Pipeline succeeded: %d repos, %d summaries",
            result.repos_discovered,
            result.summaries_generated,
        )
    else:
        logging.error("Pipeline failed: %s", result.errors)
        sys.exit(1)


if __name__ == "__main__":
    main()
```

This uses the full orchestrator pipeline with dedup, tiered cooldown, ranking rotation, and feature history. See `ROADMAP.md` for how to configure the `CategoryConfig` and `PipelineConfig`.

### 5. Test manually

```bash
ssh mikey@s501
cd ~/private/tgbot
source venv/bin/activate
python run_daily.py
```

Watch the output. Check your Telegram channel. If the message arrives, you're ready for cron.

### 6. Set up the cron job

Via the **web UI cron scheduler** (not `crontab -e`, which is blocked on s501):

- **Command:** `/home/mikey/private/tgbot/venv/bin/python /home/mikey/private/tgbot/run_daily.py`
- **Schedule:** Once daily (e.g., 09:00 UTC)

Full absolute paths are required — the web UI cron doesn't source `.bashrc`.

---

## SQLite vs MySQL

The code supports both. For a single-instance cron job, **SQLite is simpler and recommended**:

| Factor | SQLite | MySQL |
|--------|--------|-------|
| Setup | Zero — just a file path | Needs DB server, credentials, schema init |
| Backup | Copy one file (`data/bot.db`) | `mysqldump` or equivalent |
| Performance | Fine for ~1,500 rows/year | Overkill at this scale |
| Remote access | No (local file) | Yes (query from other apps) |
| Concurrency | Single-writer | Multi-writer |

Use MySQL only if you need to query the data from another application (e.g., a web dashboard) or want remote access.

To switch to MySQL, update `.env`:

```bash
DB_ENGINE=mysql
DB_HOST=localhost
DB_USER=your_user
DB_PASSWORD=your_password
DB_NAME=tgbot
```

The schema is auto-created on first run (`CREATE TABLE IF NOT EXISTS`).

---

## Operations

### Logs

The entry-point script writes to `data/pipeline.log` and stderr. Check logs:

```bash
tail -50 ~/private/tgbot/data/pipeline.log
```

Grep for errors:

```bash
grep ERROR ~/private/tgbot/data/pipeline.log | tail -20
```

### Cost Monitoring

The pipeline logs token usage. Check LLM costs:

```bash
grep "tokens" ~/private/tgbot/data/pipeline.log | tail -10
```

Estimated costs at current rates: ~$0.15–0.40/day ≈ $5–12/month. Well within the $15/month budget.

### Backups

The only state is the SQLite database. Periodically copy it:

```bash
cp ~/private/tgbot/data/bot.db ~/private/tgbot/data/bot.db.bak
```

### Updating Code

Upload new files via `scp` and the next cron run picks them up:

```powershell
scp -r src/ mikey@s501:~/private/tgbot/src/
```

No restart needed — each cron invocation starts a fresh Python process.

### Failure Behavior

The pipeline **never raises** — all errors are captured in `PipelineResult.errors`. The entry-point script calls `sys.exit(1)` on failure, so cron will report the non-zero exit code.

| Failure | Pipeline behavior |
|---------|-------------------|
| GitHub API down | Pipeline fails early, no message sent |
| Anthropic API down | Tries fallback candidates, fails if all exhausted |
| Telegram API down | Summaries saved to DB, delivery fails, `sys.exit(1)` |
| One quick-hit fails | Skipped, other summaries still delivered |
| Storage init fails | Pipeline fails early, `sys.exit(1)` |
| All repos already featured | Pipeline fails (cooldown exhaustion), `sys.exit(1)` |

### Database Schema

Three tables, auto-created on first run:

```
repos            — discovered repos with metadata and README content
summaries        — generated summaries (deep/quick) linked to repos
feature_history  — when each repo was featured, by type and ranking
```

See `src/storage/schema.sql` for the full DDL.

---

## Troubleshooting

| Symptom | Cause | Fix |
|---------|-------|-----|
| `ModuleNotFoundError: No module named 'discovery'` | `sys.path` doesn't include `src/` | Ensure entry-point script has `sys.path.insert(0, ...)` pointing to `src/` |
| `KeyError: 'ANTHROPIC_API_KEY'` | Missing env var | Check `.env` file exists and `load_dotenv()` runs before imports |
| Rate limit errors (403) | GitHub token missing or expired | Check `GITHUB_TOKEN` in `.env`; regenerate if expired |
| Empty digest / "No repos found" | Category too narrow or all repos in cooldown | Broaden topics/keywords, lower `min_stars`, or wait for cooldown to expire |
| Telegram "Bad Request: can't parse entities" | Markdown escaping bug | Check `data/pipeline.log` for the message content; report as a bug |
| `permission denied` on cron | Wrong paths or missing venv | Use full absolute paths in cron command; verify venv exists |
| `UnicodeEncodeError` | Console encoding on Windows | Already handled in entry-point (`io.TextIOWrapper`); shouldn't occur on Linux |
