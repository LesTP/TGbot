# WordPress Hosting Viability — VERIFIED ✅

**Host:** s501 (SSH: `mikey@s501`)
**Tested:** March 5, 2026
**Result:** Fully viable for Python bot hosting

---

## Results Summary

| Check | Status | Details |
|-------|--------|---------|
| SSH Access | ✅ | `ssh mikey@s501` |
| Python 3.9+ | ✅ | Python 3.11 |
| Virtual environment | ✅ | Required (PEP 668) |
| Package install | ✅ | pip works inside venv |
| Outbound HTTPS (GitHub) | ✅ | 200 response |
| Outbound HTTPS (Anthropic) | ✅ | 404 response (expected, no auth) |
| Outbound HTTPS (Telegram) | ✅ | 200 response |
| Cron jobs | ✅ | Web UI scheduler (not CLI crontab) |

---

## Your Setup

| Item | Path |
|------|------|
| Bot directory | `/home/mikey/private/tgbot/` |
| Python interpreter | `/home/mikey/private/tgbot/venv/bin/python` |
| Activate venv | `source /home/mikey/private/tgbot/venv/bin/activate` |

### Cron Command Format
```
/home/mikey/private/tgbot/venv/bin/python /home/mikey/private/tgbot/your_script.py
```

---

## Quick Reference: Common Commands

### SSH into host
```bash
ssh mikey@s501
```

### Activate virtual environment
```bash
cd ~/private/tgbot
source venv/bin/activate
```

### Install a new package
```bash
source ~/private/tgbot/venv/bin/activate
pip install package_name
```

### Run a script manually
```bash
~/private/tgbot/venv/bin/python ~/private/tgbot/your_script.py
```

---

## Host Restrictions (What Doesn't Work)

| Restriction | Workaround |
|-------------|------------|
| Cannot create directories in `~/` | Use `~/private/` instead |
| `pip install --user` fails (PEP 668) | Use virtual environment |
| `crontab -e` permission denied | Use web UI cron scheduler in control panel |

---

## Initial Setup (Already Done)

These steps were completed during investigation. Documenting for reference.

### 1. Create bot directory
```bash
mkdir -p ~/private/tgbot
cd ~/private/tgbot
```

### 2. Create virtual environment
```bash
python3 -m venv venv
source venv/bin/activate
```

### 3. Install dependencies
```bash
pip install requests anthropic mysql-connector-python
```

### 4. Verify connectivity
```bash
python -c "import requests; r = requests.get('https://api.github.com/rate_limit'); print(f'GitHub: {r.status_code}')"
python -c "import requests; r = requests.get('https://api.telegram.org/'); print(f'Telegram: {r.status_code}')"
```

### 5. Set up cron job
- Go to hosting control panel → Cron Jobs
- Command: `/home/mikey/private/tgbot/venv/bin/python /home/mikey/private/tgbot/your_script.py`
- Set desired schedule

---

## Cleanup

Remove test files when no longer needed:
```bash
rm ~/private/tgbot/test_cron.py ~/private/tgbot/cron_timestamp.txt
```

Remove test cron job from web UI.
