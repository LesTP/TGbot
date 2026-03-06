# DEVPLAN: Summarization

## Cold Start Summary

**What this is:** Summarization module — generates AI-powered repo summaries via Anthropic API. Two public functions (`generate_deep_dive`, `generate_quick_hit`), stateless. Pure leaf — no imports from other project modules except shared types passed in by caller.

**Key constraints:**
- Provider-agnostic LLM client: `LLMProvider` ABC with `AnthropicProvider` as the only implementation for now. New providers require one class + one factory branch.
- `LLMConfig` dataclass carries provider name, API key, and per-tier model names. Passed into generate functions — no env var reads inside the module.
- `anthropic` Python SDK required for the Anthropic provider (must be installed in venv).
- Two-tier model strategy: expensive model for deep dives, cheap for quick hits. Model names live in `LLMConfig`, not hardcoded.
- Deep dive: 500-1000 words covering problem solved, approach/architecture, comparison to alternatives, target audience.
- Quick hit: 2-3 sentences, key distinguishing feature.
- Input is `RepoRecord` (from Storage types) — needs `name`, `url`, `description`, `raw_content`, `source_metadata`.
- README truncation: Discovery truncates to 50KB at fetch time. Summarization applies its own truncation (~15K chars) to fit LLM context budget.
- `recent_context` parameter on `generate_deep_dive` is accepted but not exercised until Orchestrator Full. Type is `list[dict] | None` — no import of Storage types. Dict shape: `{"repo_name": str, "summary_content": str, "date": str}`. Orchestrator converts `SummaryRecord` → dict at the boundary.

**Gotchas:**
- (none yet)

## Current Status

**Phase:** 1 — In progress
**Focus:** Step 3 — Prompt templates
**Blocked/Broken:** Nothing

---

## Phase 1: Summarization Implementation (Build)

### Step 1 — Types and errors

File: `src/summarization/types.py`

Define:
- `LLMConfig` dataclass: `provider` (str, e.g. "anthropic"), `api_key` (str), `deep_dive_model` (str), `quick_hit_model` (str)
- `SummaryResult` dataclass: `content` (str), `model_used` (str), `token_usage` (dict with `input_tokens`, `output_tokens`)
- `LLMAPIError(Exception)`: `message`, `status_code` (int|None), `retry_after` (float|None)
- `LLMResponseError(Exception)`: `message`
- `InsufficientContentError(Exception)`: `message`, `content_length` (int)

Tests: `tests/summarization/test_types.py`
- `LLMConfig` construction and field access
- `LLMConfig` carries all four fields (provider, api_key, deep_dive_model, quick_hit_model)
- `SummaryResult` construction and field access
- `token_usage` dict has `input_tokens` and `output_tokens` keys
- Each error type is an Exception subclass with expected fields
- `LLMAPIError` defaults: `status_code=None`, `retry_after=None`
- `InsufficientContentError` carries `content_length`

### Step 2 — Provider abstraction and Anthropic implementation

File: `src/summarization/client.py`

Provider protocol (ABC):
```python
class LLMProvider(ABC):
    def call(self, model: str, system_prompt: str, user_prompt: str, max_tokens: int) -> dict: ...
```

Returns normalized response dict: `{"content": str, "model": str, "usage": {"input_tokens": int, "output_tokens": int}}`

Concrete implementation: `AnthropicProvider(LLMProvider)` — wraps `anthropic` Python SDK. Translates SDK exceptions → `LLMAPIError`.

Factory: `create_provider(config: LLMConfig) -> LLMProvider` — dispatches on `config.provider`. Currently supports `"anthropic"`. Raises `ValueError` for unknown providers.

Tests: `tests/summarization/test_client.py`
- `AnthropicProvider.call` returns expected dict shape (mock `anthropic.Anthropic`)
- Rate limit error (status 429) → `LLMAPIError` with status_code and retry_after
- Auth error (status 401) → `LLMAPIError`
- Network/connection error → `LLMAPIError`
- Empty response content → `LLMResponseError`
- `create_provider` with `provider="anthropic"` returns `AnthropicProvider`
- `create_provider` with unknown provider raises `ValueError`
- `LLMProvider` ABC cannot be instantiated directly

### Step 3 — Prompt templates

File: `src/summarization/prompts.py`

Two functions:
- `build_deep_dive_prompt(repo: RepoRecord, recent_context: list[dict] | None = None) -> tuple[str, str]` (system, user)
- `build_quick_hit_prompt(repo: RepoRecord) -> tuple[str, str]` (system, user)

Deep dive prompt instructs: problem solved, approach/architecture, comparison to alternatives, target audience, 500-1000 words. Quick hit prompt instructs: 2-3 sentences, key distinguishing feature.

README truncation: content exceeding `MAX_README_CHARS` (default 15000) is truncated with a `[README truncated]` marker.

`recent_context` accepted in deep dive prompt. When provided, adds a "Recently Covered Repos" section. When None or empty, section is omitted.

Tests: `tests/summarization/test_prompts.py`
- Deep dive prompt includes repo name, description, README content, stars, language
- Quick hit prompt includes repo name, description, README content
- README truncation applied when content exceeds limit; marker present
- Content under limit is not truncated
- `recent_context=None` → no "Recently Covered" section in prompt
- `recent_context` with entries → "Recently Covered" section present with repo names and summaries
- Return type is `tuple[str, str]`

### Step 4 — Content validation

File: `src/summarization/validation.py`

Two functions:
- `validate_repo_content(repo: RepoRecord) -> None` — raises `InsufficientContentError` if `raw_content` is empty or below `MIN_CONTENT_LENGTH` (default 100 chars)
- `parse_llm_response(raw_response: dict) -> tuple[str, dict]` — extracts `(content_text, token_usage)` from raw API response dict. Raises `LLMResponseError` if content missing or empty.

Tests: `tests/summarization/test_validation.py`
- Empty `raw_content` → `InsufficientContentError` with `content_length=0`
- Very short `raw_content` (below threshold) → `InsufficientContentError`
- Adequate `raw_content` → no error
- Valid response dict → `(content_str, {"input_tokens": int, "output_tokens": int})`
- Response missing `content` key → `LLMResponseError`
- Response with empty content → `LLMResponseError`

### Step 5 — Public API (generate functions)

File: `src/summarization/summarize.py`

Two functions:
- `generate_deep_dive(repo: RepoRecord, config: LLMConfig, recent_context: list[dict] | None = None) -> SummaryResult`
- `generate_quick_hit(repo: RepoRecord, config: LLMConfig) -> SummaryResult`

Pipeline: validate content → build prompt → create provider from config → call LLM with appropriate model (`config.deep_dive_model` or `config.quick_hit_model`) → parse response → return `SummaryResult`.

No module-level state. Config and provider created per call (provider creation is cheap — just stores API key). Deep dive uses higher `max_tokens`.

Tests: `tests/summarization/test_summarize.py`
- Full pipeline with mocked provider: repo + config in → `SummaryResult` out with correct fields
- Deep dive calls provider with `config.deep_dive_model`, quick hit with `config.quick_hit_model`
- `InsufficientContentError` raised when content too short (propagated from validation)
- `LLMAPIError` raised when API fails (propagated from client)
- `LLMResponseError` raised when response is unparseable (propagated from parse)
- `token_usage` populated in result
- `recent_context` passed through to prompt builder (verify prompt builder called with context)

### Step 6 — Module init and exports

File: `src/summarization/__init__.py`

Exports: `generate_deep_dive`, `generate_quick_hit`, `LLMConfig`, `SummaryResult`, `LLMAPIError`, `LLMResponseError`, `InsufficientContentError`, `LLMProvider`, `create_provider`

Tests: `tests/summarization/test_init.py`
- All 9 public names importable from `summarization`
- No unexpected exports beyond `__all__`

### Step 7 — Integration test (deferred)

File: `tests/summarization/test_integration.py`

Single test calling real Anthropic API with a synthetic `RepoRecord` containing a known README.

Guard: `@pytest.mark.skipif(not os.environ.get("ANTHROPIC_API_KEY"))`

Validates:
- Response is non-empty string
- `token_usage` has both keys populated with positive integers
- Deep dive word count in 500-1000 range
- Quick hit is 1-3 sentences
- `model_used` matches expected model constant

Deferred until `ANTHROPIC_API_KEY` is available.
