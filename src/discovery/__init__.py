"""Discovery module — find repos matching category criteria on GitHub."""

from discovery.discover import discover_repos
from discovery.types import (
    CategoryConfig,
    DiscoveredRepo,
    GitHubAPIError,
    NoResultsError,
    RankingCriteria,
    SeedRepo,
)

__all__ = [
    "CategoryConfig",
    "DiscoveredRepo",
    "GitHubAPIError",
    "NoResultsError",
    "RankingCriteria",
    "SeedRepo",
    "discover_repos",
]
