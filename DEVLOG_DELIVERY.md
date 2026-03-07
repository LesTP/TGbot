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

### Phase 1 Completion — Review & Cleanup (2026-03-06)

**Phase result:** 6 of 7 steps implemented. Step 7 (integration test) deferred — requires TELEGRAM_BOT_TOKEN.

**Final stats:** 123 delivery tests, 433 total project tests.

**Review cleanup:**
- Removed unused `_mock_successful_send` from test_send.py
- Removed unused `Optional` import and `logger` from telegram_client.py
- Deduplicated `_make_summary` helper into tests/delivery/conftest.py
- Changed `List[SummaryWithRepo]` → `list[SummaryWithRepo]` in types.py
- Updated ARCH_delivery.md usage example to include bot_token parameter

**Files (final):**
- `src/delivery/types.py` — SummaryWithRepo, Digest, DeliveryResult, TelegramAPIError, MessageTooLongError
- `src/delivery/formatting.py` — escape_markdown, escape_url, format_link, format_deep_dive, format_quick_hit, format_digest, truncate_for_telegram
- `src/delivery/telegram_client.py` — TelegramClient.send_message
- `src/delivery/send.py` — send_digest (public entry point)
- `src/delivery/__init__.py` — public exports

## Phase 2: Formatting Improvements (Build + Refine)

### Step 1 — Telegraph client (2026-03-07)

**What was done:**
- Created `src/delivery/telegraph_client.py` with:
  - `TelegraphClient(access_token)` class with `create_page(title, html_content, author_name, author_url) → page_url`
  - `create_account(short_name, author_name) → access_token` standalone setup utility
  - `text_to_telegraph_html(text)` — converts plain text to Telegraph's HTML subset:
    - Paragraph splitting on blank lines, consecutive lines joined
    - HTML entity escaping (`&`, `<`, `>`)
    - `**bold**` → `<b>bold</b>` conversion
    - Bare URL linkification → `<a>` tags
  - Internal helpers: `_split_paragraphs`, `_escape_html`, `_apply_bold`, `_linkify_urls`
  - HTTP error handling mirrors `TelegramClient` pattern (ConnectionError, Timeout, RequestException → `TelegraphAPIError`)
- Added `TelegraphAPIError` exception to `src/delivery/types.py` (non-fatal — callers fall back to truncation)
- Updated `src/delivery/__init__.py` to export `TelegraphAPIError`
- Created `tests/delivery/test_telegraph_client.py` — 48 tests covering:
  - HTML conversion (14 tests): empty/whitespace, paragraphs, escaping, bold, links, combined
  - Internal helpers (11 tests): paragraph splitting, HTML escaping, bold conversion, URL linkification
  - `create_page` success (7 tests): return value, payload fields, endpoint URL
  - `create_page` API errors (4 tests): ok=false, missing URL, non-JSON, HTTP errors
  - `create_page` network errors (3 tests): connection, timeout, generic
  - `create_account` (6 tests): success, payload, URL, API error, missing token, network error
  - All tests use mocked HTTP (api.telegra.ph blocked on corporate network per D-5)

**Decisions:** None — followed DEVPLAN spec and existing `TelegramClient` patterns.

**Issues:** None.

**Test count:** 48 new, 171 delivery tests, all passing.

### Step 2 — Quick-hit formatting (2026-03-07)

**What was done:**
- Changed `format_quick_hit` in `src/delivery/formatting.py`: removed `— {content}` from header line, placed summary content on its own indented line between header and GitHub link
- Added 2 structural tests in `tests/delivery/test_formatting.py`:
  - `test_content_on_separate_line_from_header` — verifies name and content are on different lines
  - `test_dash_separator_removed` — verifies `—` no longer appears
- All 6 existing quick-hit tests pass unchanged (used `in` assertions, layout-independent)

**Decisions:** None.

**Issues:** None.

**Test count:** 2 new, 77 formatting tests, all passing.

### Step 3 — Wire Telegraph into send_digest (2026-03-07)

**What was done:**
- Added `extract_excerpt(text, max_paragraphs=3)` and `TELEGRAPH_THRESHOLD = 1000` to `src/delivery/formatting.py`
- Rewrote `src/delivery/send.py`:
  - `send_digest` gains optional `telegraph_token: str | None = None` parameter
  - `_try_publish_telegraph(digest, telegraph_token)` — publishes deep dive to Telegraph if content ≥1000 chars; returns page URL or None; never raises
  - `_build_message_with_telegraph(digest, telegraph_url)` — builds Telegram message with excerpt (first 3 paragraphs) + "Read full analysis →" Telegraph link
  - Fallback: if no token, content too short, or Telegraph fails → existing `format_digest` + truncation path
- Updated `src/orchestrator/pipeline.py`: reads `TELEGRAPH_ACCESS_TOKEN` from env, passes `telegraph_token=` to `send_digest()`
- Added 17 new tests in `tests/delivery/test_send.py`:
  - `TestExtractExcerpt` (6 tests): single/multi paragraph, custom max, blank line handling
  - `TestSendDigestTelegraph` (11 tests): no-token skip, None-token skip, short-content skip, success with link, success with excerpt, excerpt excludes later paragraphs, failure fallback, unexpected error resilience, preserves quick hits, preserves header, passes repo name as title

**Decisions:** None — followed DEVPLAN spec.

**Issues:**
- Initial test `test_telegraph_success_does_not_contain_full_content` used 10 short paragraphs (268 chars total) — below TELEGRAPH_THRESHOLD, so Telegraph was skipped and full content appeared. Fixed by using 20 longer paragraphs to exceed threshold.

**Test count:** 17 new (send) + 2 new (formatting), 570 total project tests, all passing.

### Contract Changes (Steps 3 & 4)
- **ARCH_delivery.md:** `send_digest` signature updated from `(digest, channel_id, bot_token)` to `(digest, channel_id, bot_token, telegraph_token=None)`. Added `TelegraphAPIError` to errors. Updated purpose, guarantees, inputs, and usage example for Telegraph support. Propagated in Step 4.
- **ARCH_orchestrator.md:** Pipeline step 11 updated to include `telegraph_token` parameter read from `TELEGRAPH_ACCESS_TOKEN` env var. Propagated in Step 4.

### Step 4 — Review and cleanup (2026-03-07)

**What was done:**
- Propagated contract changes to upstream documents:
  - `ARCH_delivery.md`: updated `send_digest` signature, added `telegraph_token` parameter docs, added `TelegraphAPIError` to errors, updated purpose/guarantees/inputs/usage example
  - `ARCH_orchestrator.md`: updated pipeline step 11 to show `telegraph_token` parameter
- Updated `DEVPLAN_DELIVERY.md` current status to Step 4 / phase completion
- Full test suite: 570 passed, 0 regressions
- No code changes — doc-only step

**Decisions:** None.

**Issues:**
- Visual review of Telegram output deferred — requires server deployment (Telegraph API blocked on corporate network per D-5). This is the Refine portion of Phase 2; Build portion is complete.

### Phase 2 Review & Cleanup (2026-03-07)

**Code review findings fixed:**

Must-fix:
- `_build_message_with_telegraph` in `send.py` duplicated `format_digest` layout logic and imported private symbols (`_CRITERIA_EMOJI`, `_SECTION_SEPARATOR`) from `formatting.py`. Refactored: added `_format_deep_dive_with_excerpt` to `formatting.py`, extended `format_digest` to accept optional `telegraph_url` parameter, removed `_build_message_with_telegraph` from `send.py` entirely.
- `create_page` content handling had a dead code branch (`"<" not in html_content` was never true since `text_to_telegraph_html` always produces HTML). Removed the branching; content is now always passed as an HTML string.

Should-fix:
- `create_account` duplicated `TelegraphClient._post` HTTP/error handling (28 lines). Extracted `_telegraph_post` as a module-level function reused by both.
- `TELEGRAPH_THRESHOLD` moved from `formatting.py` to `send.py` (delivery-policy constant, not a formatting concept).
- Removed dead `_mock_telegram_success` helper and unused `MagicMock`/`SummaryWithRepo` imports from `test_send.py`.

**Phase result:** 4 steps completed. Visual review deferred to server deployment.

**Final stats:** 190 delivery tests (67 new in Phase 2), 570 total project tests.

**Files (final, Phase 2 additions/changes marked with *):**
- `src/delivery/types.py` — +TelegraphAPIError*
- `src/delivery/formatting.py` — +extract_excerpt*, +_format_deep_dive_with_excerpt*, format_digest gains telegraph_url param*, format_quick_hit layout changed*
- `src/delivery/telegraph_client.py`* — TelegraphClient.create_page, create_account, text_to_telegraph_html, _telegraph_post
- `src/delivery/send.py` — +telegraph_token param*, +_try_publish_telegraph*, Telegraph→format_digest wiring*
- `src/delivery/telegram_client.py` — unchanged
- `src/delivery/__init__.py` — +TelegraphAPIError export*
- `src/orchestrator/pipeline.py` — +TELEGRAPH_ACCESS_TOKEN env read*
