# DEVLOG: Summarization

## Phase 1: Summarization Implementation (Build)

### Step 1 — Types and errors (2026-03-06)

**What:** Created `src/summarization/types.py` with all five types from the DEVPLAN spec:
- `LLMConfig` — provider-agnostic config (provider, api_key, deep_dive_model, quick_hit_model)
- `SummaryResult` — generation output (content, model_used, token_usage)
- `LLMAPIError` — API call failures with optional status_code and retry_after
- `LLMResponseError` — unparseable or empty API responses
- `InsufficientContentError` — repo content too short, carries content_length

**Tests:** 20 tests in `tests/summarization/test_types.py`. 235 total suite passing.

**Issues:** `write_to_file` couldn't create `tests/summarization/__init__.py` when the directory didn't exist yet. Used PowerShell `New-Item -Force` instead. Minor tooling quirk.

### Step 2 — Provider abstraction and Anthropic implementation (2026-03-06)

**What:** Created `src/summarization/client.py` with provider-agnostic LLM abstraction:
- `LLMProvider` ABC — defines `call(model, system_prompt, user_prompt, max_tokens) -> dict` contract
- `AnthropicProvider` — wraps `anthropic` Python SDK (v0.84.0), translates SDK exceptions to `LLMAPIError`/`LLMResponseError`
- `create_provider(config: LLMConfig) -> LLMProvider` — factory dispatching on `config.provider`
- Normalized response dict: `{"content": str, "model": str, "usage": {"input_tokens": int, "output_tokens": int}}`

**Error mapping:** `RateLimitError` → `LLMAPIError(status_code=429, retry_after=<from header>)`. `AuthenticationError`/`InternalServerError` → `LLMAPIError(status_code=N)`. `APIConnectionError` → `LLMAPIError(status_code=None)`. Empty response content → `LLMResponseError`.

**Tests:** 17 tests in `tests/summarization/test_client.py`. 252 total suite passing.

**Issues:** None. Installed `anthropic` package during step (wasn't in environment yet).
