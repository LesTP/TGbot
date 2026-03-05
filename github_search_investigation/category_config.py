"""
Category Configuration for GitHub Digest Bot

Defines search categories with topics, keywords, and seed repos based on
the GitHub search coverage investigation (2026-03-05).

Data sources:
- github_search_investigation.py: Validated 22 search queries
- topic_cooccurrence_analysis.py: Identified 15 high-value expansion topics
- Manual review: Known tools with poor topic tagging
"""

from dataclasses import dataclass, field
from typing import Optional


@dataclass
class SearchQuery:
    """A single search query configuration."""
    query: str
    description: str
    priority: int = 1  # 1=primary, 2=secondary, 3=expansion
    min_stars: int = 50


@dataclass
class SeedRepo:
    """A known repo to include regardless of search results."""
    full_name: str
    name: str
    reason: str  # Why it's seeded (e.g., "Major tool, poor topic tagging")


@dataclass
class CategoryConfig:
    """Configuration for a discovery category."""

    name: str
    description: str

    # Topic-based searches (most reliable)
    topics: list[str] = field(default_factory=list)

    # Keyword searches (broader, may have noise)
    keywords: list[str] = field(default_factory=list)

    # Expansion topics (discovered via co-occurrence analysis)
    expansion_topics: list[str] = field(default_factory=list)

    # Seed repos (known tools that don't appear in search)
    seed_repos: list[SeedRepo] = field(default_factory=list)

    # Quality filters
    min_stars: int = 50
    require_readme: bool = True
    exclude_forks: bool = True
    exclude_archived: bool = True

    # Language filters (None = any language)
    languages: Optional[list[str]] = None

    def get_all_topic_queries(self) -> list[SearchQuery]:
        """Generate search queries for all topics."""
        queries = []

        # Primary topics
        for topic in self.topics:
            queries.append(SearchQuery(
                query=f"topic:{topic}",
                description=f"Topic: {topic}",
                priority=1,
                min_stars=self.min_stars,
            ))

        # Expansion topics (lower priority)
        for topic in self.expansion_topics:
            queries.append(SearchQuery(
                query=f"topic:{topic}",
                description=f"Expansion: {topic}",
                priority=3,
                min_stars=self.min_stars + 50,  # Higher bar for expansion
            ))

        return queries

    def get_keyword_queries(self) -> list[SearchQuery]:
        """Generate search queries for keywords."""
        queries = []
        for keyword in self.keywords:
            queries.append(SearchQuery(
                query=f'"{keyword}" in:description,readme stars:>{self.min_stars}',
                description=f'Keyword: "{keyword}"',
                priority=2,
                min_stars=self.min_stars,
            ))
        return queries

    def get_all_queries(self) -> list[SearchQuery]:
        """Get all search queries, sorted by priority."""
        queries = self.get_all_topic_queries() + self.get_keyword_queries()
        return sorted(queries, key=lambda q: q.priority)


# =============================================================================
# AGENTIC CODING CATEGORY
# Based on investigation results from 2026-03-05
# =============================================================================

AGENTIC_CODING = CategoryConfig(
    name="agentic-coding",
    description="AI-powered coding assistants, autonomous coding agents, and LLM-based developer tools",

    # Primary topics (validated - return quality results)
    topics=[
        "agentic-coding",
        "ai-coding-assistant",
        "coding-assistant",
        "code-assistant",
        "ai-pair-programming",
        "code-generation",
        "autonomous-coding",
    ],

    # Keyword searches
    keywords=[
        "agentic coding",
        "ai coding assistant",
        "coding agent",
        "autonomous coding",
        "ai pair programming",
    ],

    # Expansion topics (validated via validate_expansion_topics.py 2026-03-05)
    # Only topics with meaningful overlap with coding-assistant
    expansion_topics=[
        "ai-coding",            # ✅ 6.8% overlap, 161 repos - INCLUDE
        "codegen",              # ❓ 3.5% overlap, 1,293 repos - niche, code generation alias
        "vibe-coding",          # ❓ 2.0% overlap, 2,396 repos - emerging term, worth monitoring
    ],

    # Topics that require higher min_stars filter (broad but some relevance)
    # These are NOT in expansion_topics - handle separately in discovery if needed
    # - claude-code: 8,630 repos, 0.5% overlap (use min_stars: 500+)
    # - agentic-ai: 6,210 repos, 1.0% overlap (use min_stars: 200+)
    # - agents: 5,902 repos, 0.0% overlap (SKIP - no overlap at all)
    #
    # Topics validated and SKIPPED (too broad, <1% overlap):
    # - developer-tools: 15,045 repos, 1.0% overlap
    # - ai-agents: 12,342 repos, 1.0% overlap
    # - mcp: 15,141 repos, 0.5% overlap

    # Seed repos: Known tools that exist but don't appear in topic searches
    # These will be checked directly regardless of search results
    seed_repos=[
        # Major tools with poor/missing topic tagging
        SeedRepo(
            full_name="getcursor/cursor",
            name="Cursor",
            reason="Major AI IDE, exists but not in search results"
        ),
        SeedRepo(
            full_name="Significant-Gravitas/AutoGPT",
            name="AutoGPT",
            reason="Pioneering autonomous agent, poor topic tagging"
        ),
        SeedRepo(
            full_name="All-Hands-AI/OpenHands",
            name="OpenHands",
            reason="Major coding agent (formerly OpenDevin)"
        ),
        SeedRepo(
            full_name="OpenInterpreter/open-interpreter",
            name="Open Interpreter",
            reason="Popular code interpreter, missing from searches"
        ),
        SeedRepo(
            full_name="Codium-ai/pr-agent",
            name="PR Agent",
            reason="AI code review tool, not in topic searches"
        ),
        SeedRepo(
            full_name="stitionai/devika",
            name="Devika",
            reason="AI software engineer, missing from searches"
        ),
        SeedRepo(
            full_name="gpt-engineer-org/gpt-engineer",
            name="GPT Engineer",
            reason="Code generation tool, org path not in results"
        ),
        SeedRepo(
            full_name="smol-ai/developer",
            name="Smol Developer",
            reason="Minimal AI developer, not in topic searches"
        ),
        SeedRepo(
            full_name="e2b-dev/e2b",
            name="E2B",
            reason="Code interpreter sandbox, missing from searches"
        ),
        SeedRepo(
            full_name="sourcegraph/cody",
            name="Cody",
            reason="AI coding assistant by Sourcegraph"
        ),
        SeedRepo(
            full_name="anthropics/anthropic-cookbook",
            name="Anthropic Cookbook",
            reason="Official Claude examples and patterns"
        ),

        # Additional notable tools identified during investigation
        SeedRepo(
            full_name="paul-gauthier/aider",
            name="Aider",
            reason="Alternative path for Aider repo"
        ),
        SeedRepo(
            full_name="AbanteAI/mentat",
            name="Mentat",
            reason="AI coding assistant, correct org path"
        ),
    ],

    # Quality filters
    min_stars=50,
    require_readme=True,
    exclude_forks=True,
    exclude_archived=True,
)


# =============================================================================
# HELPER FUNCTIONS
# =============================================================================

def get_category(name: str) -> Optional[CategoryConfig]:
    """Get a category configuration by name."""
    categories = {
        "agentic-coding": AGENTIC_CODING,
    }
    return categories.get(name)


def list_categories() -> list[str]:
    """List all available category names."""
    return ["agentic-coding"]


# =============================================================================
# USAGE EXAMPLE
# =============================================================================

if __name__ == "__main__":
    import sys
    import io

    if sys.platform == "win32":
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

    config = AGENTIC_CODING

    print(f"Category: {config.name}")
    print(f"Description: {config.description}")
    print()

    print(f"Primary Topics ({len(config.topics)}):")
    for topic in config.topics:
        print(f"  - topic:{topic}")
    print()

    print(f"Keywords ({len(config.keywords)}):")
    for kw in config.keywords:
        print(f"  - \"{kw}\"")
    print()

    print(f"Expansion Topics ({len(config.expansion_topics)}):")
    for topic in config.expansion_topics:
        print(f"  - topic:{topic}")
    print()

    print(f"Seed Repos ({len(config.seed_repos)}):")
    for repo in config.seed_repos:
        print(f"  - {repo.full_name} ({repo.name})")
        print(f"      Reason: {repo.reason}")
    print()

    print(f"All Queries ({len(config.get_all_queries())}):")
    for q in config.get_all_queries():
        print(f"  [P{q.priority}] {q.description}")
