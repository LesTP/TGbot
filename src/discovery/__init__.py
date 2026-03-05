"""Discovery module — find repos matching category criteria on GitHub."""

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
]
