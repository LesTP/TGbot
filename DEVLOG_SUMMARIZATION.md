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
- `_format_repo_metadata` selectively includes fields — omits Description when None, includes topics as comma-separated. Only surfaces what the LLM needs.
- README truncation at `MAX_README_CHARS = 15000` with `[README truncated]` marker appended after the cut.

**Tests:** 24 tests in `tests/summarization/test_prompts.py`. 276 total suite passing.

**Issues:** None.

### Step 4 — Content validation (2026-03-06)

**What:** Created `src/summarization/validation.py` with two functions:
- `validate_repo_content(repo)` — raises `InsufficientContentError` if `raw_content` is empty or below `MIN_CONTENT_LENGTH` (100 chars). Error carries `content_length` for diagnostics.
- `parse_llm_response(raw_response)` — extracts `(content_text, token_usage)` from normalized provider response dict. Raises `LLMResponseError` for missing/empty/whitespace-only content. Defaults missing usage fields to 0 (usage is for cost tracking, not correctness).

**Tests:** 16 tests in `tests/summarization/test_validation.py`. 292 total suite passing.

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

### Step 6 — Module init and exports (2026-03-06)

**What:** Updated `src/summarization/__init__.py` with all 9 public exports: `generate_deep_dive`, `generate_quick_hit`, `LLMConfig`, `SummaryResult`, `LLMAPIError`, `LLMResponseError`, `InsufficientContentError`, `LLMProvider`, `create_provider`.

**Tests:** 3 tests in `tests/summarization/test_init.py`. 310 total suite passing.

**Issues:** None.

### Step 7 — Integration test (deferred)

Deferred until `ANTHROPIC_API_KEY` is available. Same pattern as Discovery and Storage deferred integration tests.

### Phase Review (2026-03-06)

**Review findings and fixes:**
- ARCH_summarization.md was stale — signatures missing `LLMConfig`, `recent_context`, provider-agnostic design. Updated to match implementation.
- Duplicate system prompt strings in `prompts.py` consolidated into shared template with `{context_instruction}` placeholder.
- Dead `_mock_provider_call` helper and unused `_, kwargs` unpacking removed from `test_summarize.py`.

### Contract Changes

- **ARCH_summarization.md**: Updated `generate_deep_dive` signature to include `config: LLMConfig` and `recent_context: list[dict] | None`. Updated `generate_quick_hit` signature to include `config: LLMConfig`. Added `LLMConfig` spec under Inputs. Added Provider Abstraction section. Updated Usage Example. Changed Purpose from "Anthropic API" to "provider-agnostic LLM interface".
- **ARCH_orchestrator.md** (updated during planning, before Phase 1): Added `context_lookback_days` to `PipelineConfig`, added pipeline step 6 (query recent summaries), noted `get_recent_summaries` as new Storage dependency.

### Phase 1 Complete (2026-03-06)

**Summary:** Summarization module fully implemented (Steps 1-6), Step 7 deferred. 95 module tests, 310 total suite passing. Provider-agnostic LLM client with Anthropic implementation. Recent-context parameter wired into API and prompt templates, ready for Orchestrator Full to exercise.

**Files:**
- `src/summarization/types.py` — LLMConfig, SummaryResult, 3 error types
- `src/summarization/client.py` — LLMProvider ABC, AnthropicProvider, create_provider factory
- `src/summarization/prompts.py` — prompt builders with README truncation and recent-context
- `src/summarization/validation.py` — content validation and response parsing
- `src/summarization/summarize.py` — generate_deep_dive, generate_quick_hit
- `src/summarization/__init__.py` — 9 public exports
