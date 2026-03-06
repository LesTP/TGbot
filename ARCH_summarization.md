# ARCH: Summarization

## Purpose
Generate AI-powered summaries for discovered repositories via a provider-agnostic LLM interface. Produces two content types: deep dives (detailed analysis) and quick hits (brief overviews). Manages prompt construction, model selection, and response parsing internally. Currently supports Anthropic (Claude models); new providers require one class + one factory branch.

## Public API

### generate_deep_dive
- **Signature:** `generate_deep_dive(repo: RepoRecord, config: LLMConfig, recent_context: list[dict] | None = None) -> SummaryResult`
- **Parameters:**
  - repo: RepoRecord — must have populated raw_content and source_metadata
  - config: LLMConfig — provider name, API key, and model names (see below)
  - recent_context: optional list of recent summary dicts (`{"repo_name": str, "summary_content": str, "date": str}`). When provided, the prompt includes a "Recently Covered Repos" section for comparison. Passed by Orchestrator; Summarization has no Storage dependency.
- **Returns:** SummaryResult containing the generated text and model used.
- **Errors:**
  - `LLMAPIError` — LLM API call failed (rate limit, auth, network). Includes status and retry info.
  - `LLMResponseError` — API returned successfully but response couldn't be parsed or was empty.
  - `InsufficientContentError` — repo's raw_content is too short or low-quality to produce a meaningful summary.

### generate_quick_hit
- **Signature:** `generate_quick_hit(repo: RepoRecord, config: LLMConfig) -> SummaryResult`
- **Parameters:**
  - repo: RepoRecord — same requirements as deep dive
  - config: LLMConfig — same as deep dive
- **Returns:** SummaryResult containing the generated text and model used.
- **Errors:** Same as generate_deep_dive.

## Inputs
- RepoRecord (from Storage): needs name, url, description, raw_content, source_metadata at minimum
- LLMConfig:
  ```
  LLMConfig:
    provider: str          # e.g. "anthropic"
    api_key: str
    deep_dive_model: str   # e.g. "claude-sonnet-4-5-20250929"
    quick_hit_model: str   # e.g. "claude-3-5-haiku-20241022"
  ```
- recent_context (optional, from Orchestrator): list of dicts with repo_name, summary_content, date

## Outputs
- SummaryResult:
  ```
  SummaryResult:
    content: str       # The generated summary text
    model_used: str    # Model identifier (e.g. "claude-sonnet-4-5-20250929")
    token_usage: dict  # input_tokens (int), output_tokens (int)
  ```
- Guarantees:
  - Deep dive content is 500-1000 words covering: problem solved, approach/architecture, comparison to alternatives, target audience.
  - Quick hit content is 2-3 sentences with key distinguishing feature.
  - model_used always populated. token_usage always populated (for cost tracking).

## Provider Abstraction
- `LLMProvider` ABC — defines `call(model, system_prompt, user_prompt, max_tokens) -> dict`
- `AnthropicProvider` — concrete implementation wrapping the `anthropic` Python SDK
- `create_provider(config: LLMConfig) -> LLMProvider` — factory dispatching on `config.provider`
- Adding a new provider: implement `LLMProvider`, add a branch to `create_provider`

## State
None. Summarization is stateless — each call is independent. Prompt templates are internal constants; model selection comes from LLMConfig.

## Usage Example
```python
from summarization import generate_deep_dive, generate_quick_hit, LLMConfig

config = LLMConfig(
    provider="anthropic",
    api_key="sk-...",
    deep_dive_model="claude-sonnet-4-5-20250929",
    quick_hit_model="claude-3-5-haiku-20241022",
)

# Generate a deep dive for the featured repo
deep = generate_deep_dive(repo_record, config)
print(f"Deep dive ({deep.model_used}): {len(deep.content.split())} words")
print(f"Cost estimate: {deep.token_usage}")

# Generate quick hits for the remaining repos
for repo in quick_hit_repos:
    quick = generate_quick_hit(repo, config)
    print(f"Quick: {repo.name} — {quick.content[:80]}...")
```
