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

### Step 3 — Prompt templates (2026-03-06)

**What:** Created `src/summarization/prompts.py` with two prompt builder functions:
- `build_deep_dive_prompt(repo, recent_context=None) -> (system, user)` — includes repo metadata (name, URL, description, stars, forks, language, created_at, topics), truncated README, and optional "Recently Covered Repos" section
- `build_quick_hit_prompt(repo) -> (system, user)` — same metadata + README, no context parameter

**Design choices:**
- Two separate system prompt strings for deep dive (with/without context) rather than conditional string building inside one template. Easier to read and tune independently.
- `_format_repo_metadata` selectively includes fields — omits Description when None, includes topics as comma-separated. Only surfaces what the LLM needs.
- README truncation at `MAX_README_CHARS = 15000` with `[README truncated]` marker appended after the cut.

**Tests:** 24 tests in `tests/summarization/test_prompts.py`. 276 total suite passing.

**Issues:** None.

### Step 5 — Public API / generate functions (2026-03-06)

**What:** Created `src/summarization/summarize.py` with the two public functions:
- `generate_deep_dive(repo, config, recent_context=None) -> SummaryResult`
- `generate_quick_hit(repo, config) -> SummaryResult`

Pipeline: `validate_repo_content` → `build_*_prompt` → `create_provider` → `provider.call` → `parse_llm_response` → `SummaryResult`. Each function is a straight pipeline with no branching — errors propagate naturally.

**Design choices:**
- `DEEP_DIVE_MAX_TOKENS = 2000`, `QUICK_HIT_MAX_TOKENS = 300` as module constants. Sufficient margin for target word counts.
- Provider created per call (no module state). Creation is cheap (stores API key only).
- `model_used` taken from API response (actual model used), not echoed from config.

**Tests:** 15 tests in `tests/summarization/test_summarize.py`. 307 total suite passing.

**Issues:** None.

### Step 4 — Content validation (2026-03-06)

**What:** Created `src/summarization/validation.py` with two functions:
- `validate_repo_content(repo)` — raises `InsufficientContentError` if `raw_content` is empty or below `MIN_CONTENT_LENGTH` (100 chars). Error carries `content_length` for diagnostics.
- `parse_llm_response(raw_response)` — extracts `(content_text, token_usage)` from normalized provider response dict. Raises `LLMResponseError` for missing/empty/whitespace-only content. Defaults missing usage fields to 0 (usage is for cost tracking, not correctness).

**Tests:** 16 tests in `tests/summarization/test_validation.py`. 292 total suite passing.

**Issues:** None.
