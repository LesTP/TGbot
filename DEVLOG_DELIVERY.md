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
