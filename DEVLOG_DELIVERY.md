# DEVLOG: Delivery

## Phase 1: Delivery Implementation (Build)

### Step 1 — Types (2026-03-06)

**What was done:**
- Created `src/delivery/types.py` with all 5 types from ARCH_delivery.md:
  - `SummaryWithRepo` dataclass (summary_content, repo_name, repo_url, stars, created_at)
  - `Digest` dataclass (deep_dive, quick_hits, ranking_criteria, date)
  - `DeliveryResult` dataclass (success, message_id, error)
  - `TelegramAPIError` exception (message, status_code)
  - `MessageTooLongError` exception (length, max_length)
- Created `src/delivery/__init__.py` module stub
- Created `tests/delivery/test_types.py` — 20 tests, all passing
- Created `DEVPLAN_DELIVERY.md` with full phase plan (7 steps)

**Decisions:** None — types follow ARCH_delivery.md contract directly.

**Issues:** None.

**Test count:** 20 new, 330 total passing.

### Step 2 — Markdown Escaping (2026-03-06)

**What was done:**
- Created `src/delivery/formatting.py` with three functions:
  - `escape_markdown(text)` — escapes all 18 MarkdownV2 special characters
  - `escape_url(url)` — escapes only `)` and `\` for inline URL context
  - `format_link(text, url)` — builds `[escaped_text](escaped_url)`
- Created `tests/delivery/test_formatting.py` — 34 tests, all passing

**Decisions:**
- Separated `escape_url` from `escape_markdown` — Telegram MarkdownV2 has different escaping rules inside `(...)` URL context (only `)` and `\` are structural). Keeping them as distinct functions makes the spec difference explicit and avoids over-escaping URLs.

**Issues:** None.

**Test count:** 34 new, 364 total passing.

### Step 3 — Message Formatting (2026-03-06)

**What was done:**
- Added `format_deep_dive(summary)`, `format_quick_hit(summary, index)`, `format_digest(digest)` to `src/delivery/formatting.py`
- Added `_CRITERIA_EMOJI` mapping (stars→⭐, forks→🍴, activity→📈, recency→🆕, subscribers→👀) with 📊 fallback
- Added `_SECTION_SEPARATOR` constant for visual dividers
- Extended `tests/delivery/test_formatting.py` with 30 new tests (64 total)

**Decisions:**
- Emoji mapping via plain dict, not by importing `RankingCriteria` enum — preserves Delivery as a pure leaf with no cross-module imports. Orchestrator passes `ranking_criteria` as a string.
- Cross-platform date formatting: `strftime("%B %d, %Y").replace(" 0", " ")` avoids platform-specific `%-d` vs `%#d`.

**Issues:**
- Test `test_contains_stars_with_comma` initially asserted `"12\\,345"` but comma is not a MarkdownV2 special char — actual output is `"12,345"`. Fixed assertion.

**Test count:** 30 new, 394 total passing.

### Step 4 — Truncation (2026-03-06)

**What was done:**
- Added `truncate_for_telegram(message, repo_url, max_length=4096)` to `src/delivery/formatting.py`
- Added `_truncate_at_boundary(text, max_chars)` internal helper (sentence → word → hard cut)
- Extended `tests/delivery/test_formatting.py` with 11 new tests (75 total in file)

**Decisions:**
- Truncation targets the deep dive body only — header, repo metadata, and quick hits preserved. Located by "View on GitHub" link marker.
- Sentence boundary detection uses `"\\. "` since text is already MarkdownV2-escaped at truncation time.
- Three-tier fallback: sentence boundary → word boundary → hard cut.

**Issues:** None.

**Test count:** 11 new, 405 total passing.

### Step 5 — Telegram Client (2026-03-06)

**What was done:**
- Created `src/delivery/telegram_client.py` with `TelegramClient` class
  - `__init__(bot_token)` — stores token, builds base URL
  - `send_message(chat_id, text, parse_mode)` — POST to `/bot{token}/sendMessage`
  - Error handling: `ok=False` response, HTTP 4xx/5xx, non-JSON response, network errors → all raise `TelegramAPIError`
- Created `tests/delivery/test_telegram_client.py` — 17 tests, all passing

**Decisions:**
- Followed `github_client.py` pattern: `requests` library, 30s timeout, exception mapping.
- Single `send_message` method — only endpoint Delivery needs.

**Issues:** None.

**Test count:** 17 new, 422 total passing.

### Step 6 — send_digest (2026-03-06)

**What was done:**
- Created `src/delivery/send.py` with `send_digest(digest, channel_id, bot_token) -> DeliveryResult`
  - Wires format_digest → truncate_for_telegram → TelegramClient.send_message → DeliveryResult
  - TelegramAPIError caught and converted to DeliveryResult(success=False) — never raises on API errors
  - MessageTooLongError raised only for pathological input that can't fit after truncation
- Updated `src/delivery/__init__.py` with public exports: send_digest, all types, all errors
- Created `tests/delivery/test_send.py` — 11 tests, all passing

**Decisions:**
- Added `bot_token` as third parameter to `send_digest` — not in original ARCH contract but necessary. Keeps module stateless, consistent with how LLMConfig is passed into Summarization. Updated ARCH_delivery.md.

**Issues:** None.

**Test count:** 11 new, 433 total passing.

### Contract Changes
- **ARCH_delivery.md:** `send_digest` signature updated from `(digest, channel_id)` to `(digest, channel_id, bot_token)`. Bot token passed in by caller rather than read from environment.
