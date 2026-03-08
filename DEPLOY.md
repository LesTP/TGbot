# Deployment & Operations Guide

How to deploy, run, and maintain the GitHub Digest Bot.

---

## Prerequisites

| Requirement | Verified |
|-------------|----------|
| SSH access to s501 | `ssh mikey@s501.sureserver.com` |
| Python 3.11 in venv | `/home/mikey/private/tgbot/venv/bin/python` |
| Outbound HTTPS | GitHub, Anthropic, Telegram all reachable |
| Cron scheduler | Web UI (not CLI `crontab`) |
| Bot directory | `/home/mikey/private/tgbot/` |

See `hosting_investigation/HOSTING_CHECKLIST.md` for the full viability report.

### API Keys Required

| Key | Where to get it |
|-----|-----------------|
| `GITHUB_TOKEN` | github.com → Settings → Developer settings → Personal access tokens (classic) → scope: `public_repo` |
| `ANTHROPIC_API_KEY` | console.anthropic.com → API Keys |
| `TELEGRAM_BOT_TOKEN` | Talk to @BotFather on Telegram → `/newbot` |
| `TELEGRAM_CHANNEL_ID` | Create a channel, add bot as admin → use `@channel_handle` |
| `TELEGRAPH_ACCESS_TOKEN` (optional) | Call the Telegraph API `createAccount` endpoint, or use `telegraph_client.create_account()` |

### Telegram Channel Setup

1. In Telegram, create a new channel (e.g., "GitHub Discovery")
2. Choose **Public** and set a link (e.g., `t.me/github_discovery` → handle is `@github_discovery`)
3. Add your bot as **admin** of the channel with "Post Messages" permission
4. Use the `@handle` (e.g., `@github_discovery`) as your `TELEGRAM_CHANNEL_ID`

---

## Step-by-Step Deployment

### 1. Upload the code

From your local machine (PowerShell). **Use full absolute paths** — Windows OpenSSH does not expand `~` in SCP paths.

```powershell
# Upload src/ and entry-point to the server
scp -r src mikey@s501.sureserver.com:/home/mikey/private/tgbot/
scp run_daily.py mikey@s501.sureserver.com:/home/mikey/private/tgbot/run_daily.py
scp .env mikey@s501.sureserver.com:/home/mikey/private/tgbot/.env
```

> **SCP gotchas on Windows:**
> - Always use `/home/mikey/private/tgbot/` — never `~/private/tgbot/` (Windows OpenSSH doesn't expand `~`)
> - To upload a directory, target the **parent** path: `scp -r src server:/home/.../tgbot/` — not `.../tgbot/src/` (causes `src/src/` nesting)
> - If the target directory doesn't exist, create it first: `ssh mikey@s501.sureserver.com "mkdir -p /home/mikey/private/tgbot/src"`

Only `src/`, `run_daily.py`, and `.env` are needed on the server. Everything else — `tests/`, `github_search_investigation/`, `hosting_investigation/`, doc files, and `demo_pipeline.py` — is development-only and should not be deployed.

After uploading, fix Windows line endings and set permissions on the server:

```bash
ssh mikey@s501.sureserver.com
sed -i 's/\r$//' /home/mikey/private/tgbot/run_daily.py
sed -i 's/\r$//' /home/mikey/private/tgbot/.env
chmod 775 /home/mikey/private/tgbot/run_daily.py
chmod 600 /home/mikey/private/tgbot/.env
```

The `sed` command converts CRLF → LF. Windows-created files have `\r\n` line endings that can corrupt API keys in `.env` and break the shebang in `run_daily.py`.

### 2. Install dependencies

```bash
ssh mikey@s501.sureserver.com
source ~/private/tgbot/venv/bin/activate
pip install requests anthropic python-dotenv
```

`python-dotenv` is needed for `.env` file loading. If `requests` and `anthropic` are already installed from the hosting investigation, only `python-dotenv` is new.

### 3. Configure the `.env` file

The `.env` file is uploaded in step 1. Verify it's locked down and the `data/` directory exists:

```bash
chmod 600 ~/private/tgbot/.env
mkdir -p ~/private/tgbot/data
```

**Required variables:**

```bash
GITHUB_TOKEN=ghp_...
ANTHROPIC_API_KEY=sk-ant-...
TELEGRAM_BOT_TOKEN=123456:ABC...
TELEGRAM_CHANNEL_ID=@github_discovery

# These MUST be uncommented or the DB defaults to in-memory (data lost every run)
DB_ENGINE=sqlite
DB_PATH=/home/mikey/private/tgbot/data/bot.db
```

**Optional variables:**

```bash
TELEGRAPH_ACCESS_TOKEN=...              # For publishing long deep dives
LLM_DEEP_DIVE_MODEL=claude-sonnet-4-5-20250929   # Override default model
LLM_QUICK_HIT_MODEL=claude-haiku-4-5-20251001    # Override default model
```

**Important:** `chmod 600` ensures only your user can read the secrets. `DB_ENGINE` and `DB_PATH` must be uncommented — without them, the database runs in-memory and all history/dedup data is lost between runs.

### 4. Test manually

```bash
ssh mikey@s501.sureserver.com
cd ~/private/tgbot
source venv/bin/activate
python run_daily.py
```

Watch the output. Check your Telegram channel. If the message arrives, you're ready for cron.

### 5. Set up the cron job

Via the **web UI cron scheduler** (not `crontab -e`, which is blocked on s501).

First, create a wrapper shell script on the server (the cron UI expects a single executable script, not a `python script.py` command):

```bash
cat > /home/mikey/private/tgbot/run_cron.sh << 'EOF'
#!/bin/bash
cd /home/mikey/private/tgbot
/home/mikey/private/tgbot/venv/bin/python /home/mikey/private/tgbot/run_daily.py
EOF
chmod 775 /home/mikey/private/tgbot/run_cron.sh
```

Then in the cron UI:

- **Script:** `/home/mikey/private/tgbot/run_cron.sh`
- **Schedule:** `1 6 * * *` (daily at 06:01 server time / 10:01 UTC)

> **Timezone note:** The server runs on **EDT (UTC-4)**. Cron times are in server time. Check "Current server time" in the cron UI to confirm.

> **Hosting panel requirements:**
> - Scripts must have **read and execute permissions**: `chmod 775`
> - Scripts must use **Unix-style line endings** (LF, not CRLF). Files uploaded from Windows need conversion: `sed -i 's/\r$//' filename`
> - Apply the same line-ending fix to `.env` — CRLF can silently corrupt API keys with trailing `\r`

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
scp -r src mikey@s501.sureserver.com:/home/mikey/private/tgbot/
scp run_daily.py mikey@s501.sureserver.com:/home/mikey/private/tgbot/run_daily.py
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
| SCP `realpath ... No such file` | Windows SCP can't expand `~` or target dir missing | Use full absolute paths (`/home/mikey/...`); create target dirs via SSH first |
| SCP creates nested `src/src/` | Destination path includes `src/` and dir already exists | Upload to parent: `scp -r src server:/home/.../tgbot/` (not `.../tgbot/src/`) |
