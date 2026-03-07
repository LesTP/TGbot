# ARCH: Delivery

## Purpose
Format a Digest into a Telegram message and send it. Handles message construction, character limit management, Telegram markdown escaping, optional Telegraph publishing for long deep dives, and API interaction. Delivery knows about Telegram and Telegraph; nothing else does.

## Public API

### send_digest
- **Signature:** `send_digest(digest: Digest, channel_id: str, bot_token: str, telegraph_token: str | None = None) -> DeliveryResult`
- **Parameters:**
  - digest: Digest — assembled by Orchestrator
    ```
    Digest:
      deep_dive: SummaryWithRepo   # summary + repo metadata
      quick_hits: list[SummaryWithRepo]  # 1-3 summaries with repo metadata
      ranking_criteria: str
      date: date

    SummaryWithRepo:
      summary_content: str
      repo_name: str
      repo_url: str
      stars: int
      created_at: str
    ```
  - channel_id: str — Telegram channel/chat ID
  - bot_token: str — Telegram bot API token
  - telegraph_token: str | None — Optional Telegraph access token. If provided and deep dive ≥1,000 chars, publishes full analysis to Telegraph and links from Telegram message with an excerpt.
- **Returns:** DeliveryResult with `success` (bool), `message_id` (str|None), `error` (str|None).
- **Errors:**
  - `TelegramAPIError` — Telegram API call failed (auth, network, invalid channel). Includes status and message.
  - `MessageTooLongError` — formatted message exceeds Telegram limits even after truncation. Includes character count.
  - `TelegraphAPIError` — Telegraph API call failed. Non-fatal: caller falls back to truncation. Never surfaces to Orchestrator.

## Inputs
- Digest object (from Orchestrator)
- Telegram bot token (from environment/config)
- Channel ID (from environment/config)
- Telegraph access token (optional, from environment/config)

## Outputs
- DeliveryResult:
  ```
  DeliveryResult:
    success: bool
    message_id: str | None   # Telegram message ID if sent
    error: str | None         # Error description if failed
  ```
- Guarantees: If success is True, the message was accepted by Telegram's API. Message formatting handles the 4,096 character limit — if a Telegraph token is available and the deep dive is ≥1,000 chars, the full analysis is published to Telegraph and the Telegram message contains an excerpt with a link. Otherwise, deep dives are truncated with a "read more" link.

## State
None. Delivery is stateless.

## Usage Example
```python
from delivery import send_digest
from config import TELEGRAM_CHANNEL_ID, TELEGRAM_BOT_TOKEN

result = send_digest(
    digest,
    channel_id=TELEGRAM_CHANNEL_ID,
    bot_token=TELEGRAM_BOT_TOKEN,
    telegraph_token=TELEGRAPH_ACCESS_TOKEN,  # optional
)
if result.success:
    print(f"Posted: message {result.message_id}")
else:
    print(f"Failed: {result.error}")
```
