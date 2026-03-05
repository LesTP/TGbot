# GitHub Digest Bot — Architecture

## Component Map

| Component | Responsibility | Dependencies |
|-----------|---------------|--------------|
| Discovery | Find repos via GitHub API, apply quality filters, rank by criteria | none (leaf) |
| Storage | Persist repos, summaries, feature history; answer dedup and candidate queries | none (leaf) |
| Summarization | Generate deep-dive and quick-hit summaries via LLM; extract structured metadata | Storage (read repo content) |
| Delivery | Format a Digest into a Telegram message and send it | none (receives Digest) |
| Orchestrator | Coordinate the daily pipeline: discover → dedup → summarize → assemble → deliver → record | Discovery, Storage, Summarization, Delivery |

## Data Flow

### Core Objects
- **DiscoveredRepo** — source, source_id, name, url, description, raw_content (README), source_metadata (stars/forks/subscribers/language/dates). Source-agnostic shape.
- **RepoRecord** — DiscoveredRepo fields + id, discovered_at, first_featured_at, last_featured_at, feature_count. Persisted in DB.
- **Summary** — repo_id, summary_type (deep/quick), content (text), model_used, generated_at. Persisted in DB.
- **Digest** — deep_dive (Summary), quick_hits (list[Summary]), ranking_criteria, date. Transient, assembled in memory.
- **FeatureRecord** — repo_id, feature_type, featured_date, ranking_criteria. Persisted in DB.

### Flow
```
GitHub API → Discovery → [DiscoveredRepo list]
                              ↓
Orchestrator persists via Storage → [RepoRecord]
Orchestrator queries Storage for feature history → filters candidates
                              ↓
Orchestrator passes candidates to Summarization → [Summary list] → Storage
                              ↓
Orchestrator assembles [Digest] from Summaries
                              ↓
Orchestrator passes Digest to Delivery → Telegram
                              ↓
Orchestrator records [FeatureRecord] via Storage
```

## Implementation Sequence

| Order | Module | Rationale |
|-------|--------|-----------|
| 1 | Discovery | Leaf, no dependencies. Validates GitHub search coverage (must-resolve risk). |
| 2 | Storage | Shared dependency for downstream modules. Start thin: repo persistence + history queries. |
| 3 | Orchestrator (thin) | Wire Discovery → Storage. First working pipeline segment — discover and persist repos. |
| 4 | Summarization | Highest remaining uncertainty (LLM prompts, cost, response parsing). Validates before Delivery. |
| 5 | Delivery | Completes end-to-end path. First user-visible output (Telegram message). |
| 6 | Orchestrator (full) | Complete pipeline: dedup filtering, ranking rotation, digest assembly, feature history recording. |

## Coupling Notes

- Discovery ↔ Storage: **loose** — mediated by Orchestrator. Discovery never imports Storage.
- Summarization ↔ Storage: **loose** — simple read/write, no complex queries.
- Delivery ↔ Summarization: **none** — no direct interaction. Both accessed by Orchestrator.
- Orchestrator ↔ all: **tight by design** — coordinator knows all components. Acceptable.
- Additional discovery sources → affects Discovery (new module) + Orchestrator (new call). Additive change.
- Additional output channels → affects Delivery (new module) + Orchestrator (new call). Additive change.
- Additional categories → configuration change in Discovery + Orchestrator. No structural change.
- Richer metadata → additive to Storage schema + Discovery output. Summarization optionally uses it.

## Key Decisions

D-1: Orchestrator-mediated dedup
Date: 2025-03-04 | Status: Closed
Decision: Orchestrator queries feature history from Storage and filters candidates, rather than Discovery owning dedup.
Rationale: Keeps Discovery as a pure leaf with no Storage dependency. Easier to test, easier to swap for other sources.
Revisit if: Dedup logic becomes complex enough to warrant its own module.

D-2: Single-process pipeline
Date: 2025-03-04 | Status: Closed
Decision: All modules run in a single Python process triggered by cron. No message queue or worker architecture.
Rationale: Solo project, shared host, cron scheduling. Message queue adds infrastructure for no benefit at this scale.
Revisit if: Pipeline needs parallelization or exceeds single-run time budget.

D-3: Transient Digest (no post queue)
Date: 2025-03-04 | Status: Closed
Decision: Digest is assembled in memory and delivered in the same pipeline run. No persisted post queue.
Rationale: Simplest architecture for daily pipeline MVP. Batch/queue is deferred scope.
Revisit if: Batch architecture is promoted from deferred, or if delivery failures require retry with pre-generated content.

## Provisional Contracts

- DiscoveredRepo shape — designed source-agnostic but only tested with GitHub. May need adjustment when a second source is added. Resolve during first non-GitHub source implementation.
- Dedup coordination — Orchestrator currently owns candidate filtering. If filtering rules grow complex (multi-criteria, scoring), may need a dedicated selection module. Watch during Orchestrator full implementation.
