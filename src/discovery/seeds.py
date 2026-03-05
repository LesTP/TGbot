"""
Seed repo fetching for Discovery module.

Fetches repos specified by name in the category's seed list,
regardless of whether they appear in search results. Returns
raw dicts in the same shape as search results (with readme_content
added) so they can be merged, filtered, and sorted uniformly.
"""

import logging
from typing import Optional

from discovery.github_client import fetch_readme, fetch_repo
from discovery.types import SeedRepo

logger = logging.getLogger(__name__)


def fetch_seed_repos(
    seeds: list[SeedRepo],
    token: Optional[str] = None,
) -> list[dict]:
    """Fetch repos from a seed list by full name.

    For each seed, fetches repo metadata via the Repos API and
    README via the Contents API. Skips seeds that 404 (deleted/renamed)
    or whose README fetch fails — logs a warning but does not raise.

    Args:
        seeds: List of SeedRepo with full_name (e.g. "owner/repo").
        token: GitHub personal access token. Optional.

    Returns:
        List of raw repo dicts (same shape as GitHub search results)
        augmented with ``readme_content`` key. Only includes seeds
        that were successfully fetched.

    Raises:
        GitHubAPIError: Only for non-404 API errors (auth, rate limit,
                        server errors). Individual seed 404s are skipped.
    """
    results = []

    for seed in seeds:
        repo_data = fetch_repo(seed.full_name, token=token)
        if repo_data is None:
            logger.warning("Seed repo not found (404): %s", seed.full_name)
            continue

        owner, repo_name = seed.full_name.split("/", 1)
        readme = fetch_readme(owner, repo_name, token=token)
        repo_data["readme_content"] = readme

        results.append(repo_data)

    return results
