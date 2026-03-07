# DEVPLAN: Delivery

## Cold Start Summary

**What this is:** Delivery module — formats a Digest into a Telegram message and sends it via the Bot API. Stateless. Handles MarkdownV2 escaping, 4,096 character limit (truncation with "read more" link), and API error handling. Public API: `send_digest(digest, channel_id, bot_token) → DeliveryResult`.

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

**Phase:** 2 — Formatting Improvements (Build + Refine)
**Focus:** Step 1 — Telegraph client
**Blocked/Broken:** Nothing

---

## Phase 1: Delivery Implementation (Build) — COMPLETE

Steps 1–6 implemented, 123 tests passing. Step 7 (integration test) deferred. See DEVLOG_DELIVERY.md for full details.

**Deferred: Step 7 — Integration test.** Write `tests/delivery/test_integration.py` when TELEGRAM_BOT_TOKEN and TELEGRAM_TEST_CHANNEL are available. Single test sending a real digest to a test channel. Mark `@pytest.mark.skipif(not os.environ.get("TELEGRAM_BOT_TOKEN") or not os.environ.get("TELEGRAM_TEST_CHANNEL"))`.

---

## Phase 2: Formatting Improvements (Build + Refine)

Observed issues from production digest output. Two formatting fixes and one new feature (Telegraph integration) to avoid losing deep-dive content to truncation.

### Context

Deep-dive summaries are 500-1000 words. Telegram's 4,096 character limit means most deep dives are truncated. The current truncation appends `[Read more](repo_url)` — but this links to the GitHub repo, not to the rest of the summary. The full LLM-generated analysis is lost. Quick hits are rendered as a single dense line, making multi-sentence summaries hard to scan.

### Decisions

D-5: Telegraph token management
Date: 2026-03-07 | Status: Closed
Decision: Env var (`TELEGRAPH_ACCESS_TOKEN`), consistent with other tokens. Token created, verified working on server.
Note: `api.telegra.ph` is blocked by corporate network (TLS handshake failure). All dev/test work uses mocked HTTP. Real Telegraph calls only happen on the deployment server.
Revisit if: Token rotation or multi-instance deployment needed.

### Step 1 — Telegraph client (Build)

New `src/delivery/telegraph_client.py` — HTTP client for Telegraph API.

- `create_account(short_name, author_name) → access_token` (utility for initial setup)
- `create_page(access_token, title, html_content, author_name, author_url) → page_url`
- Convert plain text to Telegraph's simplified HTML (`<p>`, `<b>`, `<a>`)
- Telegraph API: `https://api.telegra.ph/createPage`, POST with JSON body
- Tests: mock HTTP layer, verify request shape, error handling, HTML conversion
- Error type: `TelegraphAPIError` (non-fatal — caller falls back to truncation)
- Dev constraint: `api.telegra.ph` blocked on corporate network — all tests use mocked HTTP, no live API calls

### Step 2 — Quick-hit formatting (Build, then Refine visually)

Change `format_quick_hit` layout from single dense line to separated header + body:

Before:
```
1. *name* ⭐ 74,787 — Entire summary on one line with no breaks.
   GitHub
```

After:
```
1. *name* ⭐ 74,787
   Summary content on its own line...
   GitHub
```

- Update `format_quick_hit` in `src/delivery/formatting.py`
- Update tests in `tests/delivery/test_formatting.py` for new shape
- Verify truncation logic still works (quick hits are in the preserved tail)

### Step 3 — Wire Telegraph into send_digest (Build)

Modify `send_digest` to optionally publish deep dives to Telegraph.

- Add optional `telegraph_token: str | None = None` parameter to `send_digest`
- If `telegraph_token` provided and deep-dive content exceeds ~1,000 chars:
  - Publish full deep dive to Telegraph via `create_page`
  - Replace deep-dive body in Telegram message with excerpt (first 2-3 paragraphs) + `[Read full analysis →](telegraph_url)`
- If `telegraph_token` is None, Telegraph publish fails, or Telegraph is unreachable:
  - Fall back to current truncation with corrected label (`"View full repo on GitHub →"`)
  - Log warning on Telegraph failure, never crash the pipeline
- Update `truncate_for_telegram` to support both paths
- Orchestrator change: read `TELEGRAPH_ACCESS_TOKEN` from env, pass to `send_digest`
- Tests: mock Telegraph client, verify both paths (success → Telegraph link, failure → GitHub fallback)

### Step 4 — Review and cleanup

- Update ARCH_delivery.md: add Telegraph dependency, updated `send_digest` signature
- Update ARCH_orchestrator.md: `send_digest` call gains `telegraph_token` parameter
- Run full test suite, verify no regressions
- Visual review of Telegram output (Refine — must test on server, Telegraph blocked on dev machine)
