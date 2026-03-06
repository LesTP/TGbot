# DEVPLAN: Delivery

## Cold Start Summary

**What this is:** Delivery module — formats a Digest into a Telegram message and sends it via the Bot API. Stateless. Handles MarkdownV2 escaping, 4,096 character limit (truncation with "read more" link), and API error handling. Public API: `send_digest(digest, channel_id) → DeliveryResult`.

**Key constraints:**
- Telegram Bot API via HTTP POST to `https://api.telegram.org/bot{token}/sendMessage`.
- MarkdownV2 parse mode — 11 special characters must be escaped: `_ * [ ] ( ) ~ ` > # + - = | { } . !`
- Message limit: 4,096 characters. Deep dive body truncated if exceeded; metadata/links preserved.
- `requests` library for HTTP (already used by Discovery). No new dependencies.
- Bot token from environment/config — passed in, not read inside module.
- Delivery is a pure leaf — no imports from other project modules except types passed by caller.

**Gotchas:**
- (none discovered)

## Current Status

**Phase:** 1 — In Progress
**Focus:** Steps 1-6 complete, ready for Step 7 (Integration Test — deferred)
**Blocked/Broken:** Nothing

---

## Phase 1: Delivery Implementation (Build)

### Step 1: Types

**Files:** `src/delivery/types.py`

**Work:**
- `SummaryWithRepo` dataclass: `summary_content: str`, `repo_name: str`, `repo_url: str`, `stars: int`, `created_at: str`
- `Digest` dataclass: `deep_dive: SummaryWithRepo`, `quick_hits: list[SummaryWithRepo]`, `ranking_criteria: str`, `date: date`
- `DeliveryResult` dataclass: `success: bool`, `message_id: str | None`, `error: str | None`
- `TelegramAPIError(Exception)`: `status_code: int`, `message: str`
- `MessageTooLongError(Exception)`: `length: int`, `max_length: int`

**Tests:** `tests/delivery/test_types.py`
- All types instantiate with expected fields
- Dataclass field types match ARCH contract
- Exceptions carry expected attributes

---

### Step 2: Markdown Escaping

**Files:** `src/delivery/formatting.py`

**Work:**
- `escape_markdown(text: str) -> str` — escapes all 11 MarkdownV2 special characters
- `format_link(text: str, url: str) -> str` — returns `[escaped_text](escaped_url)` safe for MarkdownV2

**Tests:** `tests/delivery/test_formatting.py`
- Each of 11 special chars (`_`, `*`, `[`, `]`, `(`, `)`, `~`, `` ` ``, `>`, `#`, `+`, `-`, `=`, `|`, `{`, `}`, `.`, `!`) escaped correctly
- Text with multiple special chars fully escaped
- `format_link` with clean text/URL produces valid link
- `format_link` with special chars in text escapes them
- `format_link` with special chars in URL escapes them

---

### Step 3: Message Formatting

**Files:** `src/delivery/formatting.py` (extend)

**Work:**
- `format_deep_dive(summary: SummaryWithRepo) -> str` — formats repo name (bold), stars, link, content
- `format_quick_hit(summary: SummaryWithRepo, index: int) -> str` — formats numbered entry with name, stars, summary, link
- `format_digest(digest: Digest) -> str` — assembles full message:
  ```
  📅 Daily Digest — {date}
  Ranked by: {criteria_emoji} {criteria}

  ━━━━━━━━━━━━━━━━━━
  🔍 DEEP DIVE
  ━━━━━━━━━━━━━━━━━━

  **{repo_name}** ⭐ {stars:,}
  [View on GitHub]({url})

  {summary_content}

  ━━━━━━━━━━━━━━━━━━
  ⚡ QUICK HITS
  ━━━━━━━━━━━━━━━━━━

  1. **{repo_name}** ⭐ {stars:,} — {summary}
     [GitHub]({url})

  2. ...
  ```

**Tests:** `tests/delivery/test_formatting.py` (extend)
- `format_deep_dive` output contains repo name, stars with comma formatting, link, content
- `format_quick_hit` output contains index, repo name, stars, summary, link
- `format_digest` output contains header with date and ranking criteria
- `format_digest` output contains deep dive section with separator
- `format_digest` output contains quick hits section with all entries numbered
- Empty quick_hits list produces digest with only deep dive
- Ranking criteria maps to appropriate emoji (stars→⭐, forks→🍴, activity→📈, recency→🆕, subscribers→👀)

---

### Step 4: Truncation

**Files:** `src/delivery/formatting.py` (extend)

**Work:**
- `truncate_for_telegram(message: str, repo_url: str, max_length: int = 4096) -> str`
  - If message ≤ max_length, return unchanged
  - Otherwise, find the deep dive content section and truncate it
  - Cut at last sentence boundary (`. `) before limit, or last word boundary if no sentence
  - Append `…\n\n[Read more]({repo_url})`
  - Recalculate to ensure final length ≤ max_length

**Tests:** `tests/delivery/test_formatting.py` (extend)
- Message under limit returned unchanged
- Message at exactly limit returned unchanged
- Message over limit truncated to ≤ max_length
- Truncated message ends with "…\n\n[Read more](url)"
- Truncation prefers sentence boundary when available
- Truncation falls back to word boundary if no sentence boundary
- Very long message with no spaces handled gracefully (hard cut)

---

### Step 5: Telegram Client

**Files:** `src/delivery/telegram_client.py`

**Work:**
- `TelegramClient` class:
  - `__init__(self, bot_token: str)`
  - `send_message(self, chat_id: str, text: str, parse_mode: str = "MarkdownV2") -> dict`
    - POST to `https://api.telegram.org/bot{token}/sendMessage`
    - Body: `{"chat_id": chat_id, "text": text, "parse_mode": parse_mode}`
    - On 200 with `ok=True`: return response JSON
    - On 200 with `ok=False`: raise `TelegramAPIError` with description
    - On 4xx/5xx: raise `TelegramAPIError` with status and body
    - On network error: raise `TelegramAPIError` with message

**Tests:** `tests/delivery/test_telegram_client.py`
- Mock successful response: returns dict with `message_id`
- Mock `ok=False` response: raises `TelegramAPIError` with description
- Mock 400 response: raises `TelegramAPIError` with status 400
- Mock 500 response: raises `TelegramAPIError` with status 500
- Mock network timeout: raises `TelegramAPIError`
- Mock connection error: raises `TelegramAPIError`
- Verify request URL includes bot token
- Verify request body contains chat_id, text, parse_mode

---

### Step 6: send_digest

**Files:** `src/delivery/send.py`, `src/delivery/__init__.py`

**Work:**
- `send_digest(digest: Digest, channel_id: str, bot_token: str) -> DeliveryResult`
  1. Format digest with `format_digest()`
  2. Truncate if needed with `truncate_for_telegram()` using deep dive repo URL
  3. If still > 4096 after truncation, raise `MessageTooLongError`
  4. Create `TelegramClient(bot_token)`
  5. Call `client.send_message(channel_id, message)`
  6. On success: return `DeliveryResult(success=True, message_id=..., error=None)`
  7. On `TelegramAPIError`: return `DeliveryResult(success=False, message_id=None, error=str(e))`
- Export `send_digest`, types, and errors from `__init__.py`

**Tests:** `tests/delivery/test_send.py`
- Success case: mock client returns message_id, result has `success=True`
- API error case: mock client raises `TelegramAPIError`, result has `success=False` with error message
- Truncation applied: digest with very long deep dive is truncated before sending
- MessageTooLongError: pathological input that can't fit even after truncation raises exception
- Verify `format_digest` called with correct digest
- Verify `truncate_for_telegram` called with correct URL

---

### Step 7: Integration Test (Deferred)

**Files:** `tests/delivery/test_integration.py`

**Work:**
- Single test with `@pytest.mark.skipif(not os.environ.get("TELEGRAM_BOT_TOKEN") or not os.environ.get("TELEGRAM_TEST_CHANNEL"))`
- Create a minimal Digest with synthetic data
- Call `send_digest()` with real token and test channel
- Assert `result.success is True` and `result.message_id` is not None

**Deferred until:** `TELEGRAM_BOT_TOKEN` and `TELEGRAM_TEST_CHANNEL` environment variables available.

---

## Test Summary

| Step | Test File | Expected Test Count |
|------|-----------|---------------------|
| 1 | `test_types.py` | ~8 |
| 2 | `test_formatting.py` | ~10 |
| 3 | `test_formatting.py` | ~10 (cumulative ~20) |
| 4 | `test_formatting.py` | ~7 (cumulative ~27) |
| 5 | `test_telegram_client.py` | ~10 |
| 6 | `test_send.py` | ~8 |
| 7 | `test_integration.py` | 1 (skipped without token) |

**Total:** ~45-50 tests
