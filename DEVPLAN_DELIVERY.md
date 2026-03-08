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

**Phase:** 2 — Formatting Improvements — COMPLETE; Phase 3 — Production Deployment Fixes — COMPLETE
**Blocked/Broken:** Nothing

---

## Phase 1: Delivery Implementation (Build) — COMPLETE

Steps 1–6 implemented, 123 tests passing. Step 7 (integration test) deferred. See DEVLOG_DELIVERY.md for full details.

**Deferred: Step 7 — Integration test.** Write `tests/delivery/test_integration.py` when TELEGRAM_BOT_TOKEN and TELEGRAM_TEST_CHANNEL are available. Single test sending a real digest to a test channel. Mark `@pytest.mark.skipif(not os.environ.get("TELEGRAM_BOT_TOKEN") or not os.environ.get("TELEGRAM_TEST_CHANNEL"))`.

---

## Phase 2: Formatting Improvements (Build + Refine) — COMPLETE

Steps 1–4 implemented: Telegraph client, quick-hit layout, Telegraph wiring into send_digest, review/cleanup. 67 new tests (190 delivery total), 570 project total. See DEVLOG_DELIVERY.md for full details.

**Decisions:**
- D-5: Telegraph token via env var (`TELEGRAPH_ACCESS_TOKEN`). `api.telegra.ph` blocked on corporate network; all dev/test uses mocked HTTP. Real calls only on deployment server.

**Deferred:** Visual review of Telegram output on production server (Telegraph blocked on dev machine).

---

## Phase 3: Production Deployment Fixes — COMPLETE

Telegraph Node format fix + truncation telegraph_url passthrough. 0 new tests (2 updated), 570 project total. See DEVLOG_DELIVERY.md Phase 3 for full details.

**Decisions:**
- D-6: Telegraph API requires Node array format in `content` field, not HTML strings. The `html_content` form-data parameter does not work in practice. (Closed)
