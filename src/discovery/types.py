"""
Discovery module types.

Data types for the Discovery module's public API: configuration,
output shapes, and error types. See ARCH_discovery.md for contracts.
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional


# ---------------------------------------------------------------------------
# Configuration types
# ---------------------------------------------------------------------------


@dataclass
class SeedRepo:
    """A known repo to fetch directly regardless of search results."""

    full_name: str  # "owner/repo"
    name: str  # display name
    reason: str  # why this is seeded


@dataclass
class CategoryConfig:
    """Configuration for a discovery category.

    Defines what to search for (topics, keywords, seeds) and quality
    filters to apply. Expansion topics use a higher min_stars bar
    (min_stars + 50) to compensate for broader, noisier results.
    """

    name: str
    description: str

    topics: list[str] = field(default_factory=list)
    keywords: list[str] = field(default_factory=list)
    expansion_topics: list[str] = field(default_factory=list)
    seed_repos: list[SeedRepo] = field(default_factory=list)

    min_stars: int = 50
    min_readme_length: int = 200
    require_readme: bool = True
    exclude_forks: bool = True
    exclude_archived: bool = True
    languages: Optional[list[str]] = None


class RankingCriteria(Enum):
    """Ranking criteria for sorting discovered repos."""

    STARS = "stars"
    FORKS = "forks"
    SUBSCRIBERS = "subscribers"
    RECENCY = "recency"
    ACTIVITY = "activity"


# ---------------------------------------------------------------------------
# Output types
# ---------------------------------------------------------------------------


@dataclass
class DiscoveredRepo:
    """A repository discovered from a source (currently GitHub only).

    Source-agnostic shape: downstream modules consume this without
    knowing which source produced it.
    """

    source: str  # e.g. "github"
    source_id: str  # source-specific unique ID
    name: str  # "owner/repo"
    url: str  # full URL
    description: Optional[str]
    raw_content: str  # README text, truncated to 50KB
    source_metadata: dict  # stars, forks, subscribers, etc.


# ---------------------------------------------------------------------------
# Error types
# ---------------------------------------------------------------------------


class GitHubAPIError(Exception):
    """GitHub API request failed (rate limit, auth, network)."""

    def __init__(
        self,
        message: str,
        status_code: Optional[int] = None,
        response_body: Optional[str] = None,
    ):
        super().__init__(message)
        self.status_code = status_code
        self.response_body = response_body


class NoResultsError(Exception):
    """Search returned zero repos after filtering."""

    def __init__(self, message: str, query_details: Optional[dict] = None):
        super().__init__(message)
        self.query_details = query_details or {}
