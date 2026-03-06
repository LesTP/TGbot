"""
Main discovery function — wires all components together.

Pipeline: search → pre-filter → fetch READMEs → full filter →
          fetch seeds → merge → dedup → sort → limit → convert
"""

import logging
import os
from typing import Optional

from discovery.filters import apply_quality_filters
from discovery.github_client import fetch_readme, search_repos
from discovery.ranking import sort_repos
from discovery.seeds import fetch_seed_repos
from discovery.types import (
    CategoryConfig,
    DiscoveredRepo,
    NoResultsError,
    RankingCriteria,
)

logger = logging.getLogger(__name__)

# GitHub search API sort options mapped from RankingCriteria.
_GITHUB_SORT: dict[RankingCriteria, str] = {
    RankingCriteria.STARS: "stars",
    RankingCriteria.FORKS: "forks",
    RankingCriteria.SUBSCRIBERS: "stars",  # no GitHub equivalent
    RankingCriteria.RECENCY: "updated",
    RankingCriteria.ACTIVITY: "updated",
}


def discover_repos(
    category: CategoryConfig,
    ranking: RankingCriteria,
    limit: int = 20,
    token: Optional[str] = None,
) -> list[DiscoveredRepo]:
    """Discover GitHub repos matching category criteria.

    Args:
        category: What to search for (topics, keywords, seeds, filters).
        ranking: How to sort results.
        limit: Max repos to return (default 20, max 100).
        token: GitHub API token. Falls back to GITHUB_TOKEN env var.

    Returns:
        list[DiscoveredRepo] sorted by ranking criteria, all passing
        quality filters. May return fewer than limit.

    Raises:
        GitHubAPIError: On API failures (auth, rate limit, network).
        NoResultsError: When zero repos remain after filtering.
    """
    limit = min(limit, 100)
    token = token or os.environ.get("GITHUB_TOKEN")
    github_sort = _GITHUB_SORT[ranking]

    # --- 1. Run search queries ---
    all_repos: list[dict] = []

    for topic in category.topics:
        query = f"topic:{topic} stars:>={category.min_stars}"
        results = search_repos(query, token=token, sort=github_sort, per_page=30, max_pages=2)
        all_repos.extend(results)

    for keyword in category.keywords:
        query = f'"{keyword}" in:description,readme stars:>={category.min_stars}'
        results = search_repos(query, token=token, sort=github_sort, per_page=30, max_pages=1)
        all_repos.extend(results)

    for topic in category.expansion_topics:
        exp_min_stars = category.min_stars + 50
        query = f"topic:{topic} stars:>={exp_min_stars}"
        results = search_repos(query, token=token, sort=github_sort, per_page=30, max_pages=1)
        for repo in results:
            repo["_is_expansion"] = True
        all_repos.extend(results)

    logger.info("Search returned %d raw results", len(all_repos))

    # --- 2. Dedup raw results (before README fetch) ---
    all_repos = _dedup_by_id(all_repos)
    logger.info("After dedup: %d unique repos", len(all_repos))

    # --- 3. Pre-filter (stars, fork, archived — no README needed) ---
    pre_filtered = _pre_filter(all_repos, category)
    logger.info("After pre-filter: %d repos", len(pre_filtered))

    # --- 4. Fetch READMEs ---
    for repo in pre_filtered:
        owner, repo_name = repo["full_name"].split("/", 1)
        repo["readme_content"] = fetch_readme(owner, repo_name, token=token)

    # --- 5. Full quality filter (including README length) ---
    regular = [r for r in pre_filtered if not r.get("_is_expansion")]
    expansion = [r for r in pre_filtered if r.get("_is_expansion")]

    filtered = apply_quality_filters(regular, category, is_expansion=False)
    filtered += apply_quality_filters(expansion, category, is_expansion=True)
    logger.info("After quality filter: %d repos", len(filtered))

    # --- 6. Fetch seed repos and merge ---
    if category.seed_repos:
        seed_results = fetch_seed_repos(category.seed_repos, token=token)
        seed_results = apply_quality_filters(seed_results, category, is_expansion=False)
        filtered.extend(seed_results)
        logger.info("After adding seeds: %d repos", len(filtered))

    # --- 7. Final dedup (seeds may overlap with search) ---
    filtered = _dedup_by_id(filtered)

    # --- 8. Sort ---
    sorted_repos = sort_repos(filtered, ranking)

    # --- 9. Limit ---
    sorted_repos = sorted_repos[:limit]

    # --- 10. Convert to DiscoveredRepo ---
    if not sorted_repos:
        raise NoResultsError(
            "No repos found after filtering",
            query_details={
                "category": category.name,
                "topics": category.topics,
                "keywords": category.keywords,
                "min_stars": category.min_stars,
            },
        )

    return [_to_discovered_repo(r) for r in sorted_repos]


def _dedup_by_id(repos: list[dict]) -> list[dict]:
    """Remove duplicate repos by GitHub ID, keeping first occurrence."""
    seen: set[int] = set()
    result = []
    for repo in repos:
        repo_id = repo.get("id")
        if repo_id is not None and repo_id in seen:
            continue
        if repo_id is not None:
            seen.add(repo_id)
        result.append(repo)
    return result


def _pre_filter(repos: list[dict], config: CategoryConfig) -> list[dict]:
    """Quick filter before README fetch — uses only fields from search results."""
    result = []
    for repo in repos:
        stars = repo.get("stargazers_count", 0)
        min_stars = config.min_stars + 50 if repo.get("_is_expansion") else config.min_stars
        if stars < min_stars:
            continue
        if config.exclude_forks and repo.get("fork", False):
            continue
        if config.exclude_archived and repo.get("archived", False):
            continue
        if config.languages:
            lang = repo.get("language")
            if lang is None or lang.lower() not in [l.lower() for l in config.languages]:
                continue
        result.append(repo)
    return result


def _to_discovered_repo(repo: dict) -> DiscoveredRepo:
    """Convert a raw GitHub API dict to a DiscoveredRepo."""
    return DiscoveredRepo(
        source="github",
        source_id=str(repo.get("id", "")),
        name=repo.get("full_name", ""),
        url=repo.get("html_url", ""),
        description=repo.get("description"),
        raw_content=repo.get("readme_content", ""),
        source_metadata={
            "stars": repo.get("stargazers_count", 0),
            "forks": repo.get("forks_count", 0),
            "subscribers": repo.get("subscribers_count", 0),
            "primary_language": repo.get("language"),
            "created_at": repo.get("created_at", ""),
            "updated_at": repo.get("updated_at", ""),
            "pushed_at": repo.get("pushed_at", ""),
            "topics": repo.get("topics", []),
        },
    )
