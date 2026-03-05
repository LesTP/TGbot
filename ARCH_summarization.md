# ARCH: Summarization

## Purpose
Generate AI-powered summaries for discovered repositories using the Anthropic API. Produces two content types: deep dives (detailed analysis) and quick hits (brief overviews). Manages prompt construction, model selection, and response parsing internally.

## Public API

### generate_deep_dive
- **Signature:** `generate_deep_dive(repo: RepoRecord) -> SummaryResult`
- **Parameters:** repo: RepoRecord — must have populated raw_content and source_metadata
- **Returns:** SummaryResult containing the generated text and model used.
- **Errors:**
  - `LLMAPIError` — Anthropic API call failed (rate limit, auth, network). Includes status and retry info.
  - `LLMResponseError` — API returned successfully but response couldn't be parsed or was empty.
  - `InsufficientContentError` — repo's raw_content is too short or low-quality to produce a meaningful summary.

### generate_quick_hit
- **Signature:** `generate_quick_hit(repo: RepoRecord) -> SummaryResult`
- **Parameters:** repo: RepoRecord — same requirements as deep dive
- **Returns:** SummaryResult containing the generated text and model used.
- **Errors:** Same as generate_deep_dive.

## Inputs
- RepoRecord (from Storage): needs name, url, description, raw_content, source_metadata at minimum
- Anthropic API key (from environment/config)

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

## State
None. Summarization is stateless — each call is independent. Prompt templates and model configuration are internal constants.

## Usage Example
```python
from summarization import generate_deep_dive, generate_quick_hit

# Generate a deep dive for the featured repo
deep = generate_deep_dive(repo_record)
print(f"Deep dive ({deep.model_used}): {len(deep.content.split())} words")
print(f"Cost estimate: {deep.token_usage}")

# Generate quick hits for the remaining repos
for repo in quick_hit_repos:
    quick = generate_quick_hit(repo)
    print(f"Quick: {repo.name} — {quick.content[:80]}...")
```
