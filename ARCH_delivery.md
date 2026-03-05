# ARCH: Delivery

## Purpose
Format a Digest into a Telegram message and send it. Handles message construction, character limit management, Telegram markdown escaping, and API interaction. Delivery knows about Telegram; nothing else does.

## Public API

### send_digest
- **Signature:** `send_digest(digest: Digest, channel_id: str) -> DeliveryResult`
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
- **Returns:** DeliveryResult with `success` (bool), `message_id` (str|None), `error` (str|None).
- **Errors:**
  - `TelegramAPIError` — Telegram API call failed (auth, network, invalid channel). Includes status and message.
  - `MessageTooLongError` — formatted message exceeds Telegram limits even after truncation. Includes character count.

## Inputs
- Digest object (from Orchestrator)
- Telegram bot token (from environment/config)
- Channel ID (from environment/config)

## Outputs
- DeliveryResult:
  ```
  DeliveryResult:
    success: bool
    message_id: str | None   # Telegram message ID if sent
    error: str | None         # Error description if failed
  ```
- Guarantees: If success is True, the message was accepted by Telegram's API. Message formatting handles the 4,096 character limit — deep dives are truncated with a "read more" link if necessary.

## State
None. Delivery is stateless.

## Usage Example
```python
from delivery import send_digest
from config import TELEGRAM_CHANNEL_ID

result = send_digest(digest, channel_id=TELEGRAM_CHANNEL_ID)
if result.success:
    print(f"Posted: message {result.message_id}")
else:
    print(f"Failed: {result.error}")
```
