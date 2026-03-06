# DEVPLAN: Summarization

## Cold Start Summary

**What this is:** Summarization module — generates AI-powered repo summaries via a provider-agnostic LLM interface. Two public functions (`generate_deep_dive`, `generate_quick_hit`), stateless. Pure leaf — no imports from other project modules except shared types passed in by caller.

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
- (none discovered)

## Current Status

**Phase:** 1 — Complete
**Focus:** Phase complete — 6 steps implemented, 95 module tests, 310 total passing
**Blocked/Broken:** Step 7 (integration test) deferred — requires ANTHROPIC_API_KEY

---

## Phase 1: Summarization Implementation (Build) — COMPLETE

Steps 1–6 implemented, 95 tests passing. Step 7 (integration test) deferred. See DEVLOG_SUMMARIZATION.md for full details.

**Deferred: Step 7 — Integration test.** Write `tests/summarization/test_integration.py` when ANTHROPIC_API_KEY is available. Single test calling real API with synthetic RepoRecord. Mark `@pytest.mark.skipif(not os.environ.get("ANTHROPIC_API_KEY"))`.
