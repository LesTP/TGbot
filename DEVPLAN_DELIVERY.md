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

**Phase:** 1 — Complete
**Focus:** Phase complete — 6 steps implemented, 123 delivery tests, 433 total passing
**Blocked/Broken:** Step 7 (integration test) deferred — requires TELEGRAM_BOT_TOKEN and TELEGRAM_TEST_CHANNEL

---

## Phase 1: Delivery Implementation (Build) — COMPLETE

Steps 1–6 implemented, 123 tests passing. Step 7 (integration test) deferred. See DEVLOG_DELIVERY.md for full details.

**Deferred: Step 7 — Integration test.** Write `tests/delivery/test_integration.py` when TELEGRAM_BOT_TOKEN and TELEGRAM_TEST_CHANNEL are available. Single test sending a real digest to a test channel. Mark `@pytest.mark.skipif(not os.environ.get("TELEGRAM_BOT_TOKEN") or not os.environ.get("TELEGRAM_TEST_CHANNEL"))`.
