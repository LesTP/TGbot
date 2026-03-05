"""
Quality filters for discovered repositories.

Filters operate on raw GitHub API repo dicts augmented with a
``readme_content`` key (str or None). The integration layer adds
this key after fetching READMEs and before calling filters.

GitHub API dict fields used:
- stargazers_count (int)
- fork (bool)
- archived (bool)
- language (str | None)
- readme_content (str | None) — added by caller, not from GitHub API
"""

import logging
from typing import Optional

from discovery.types import CategoryConfig

logger = logging.getLogger(__name__)


def apply_quality_filters(
    repos: list[dict],
    config: CategoryConfig,
    is_expansion: bool = False,
) -> list[dict]:
    """Filter repos by quality criteria from CategoryConfig.

    Args:
        repos: Raw GitHub API repo dicts, each augmented with a
               ``readme_content`` key (str or None).
        config: Category configuration with filter thresholds.
        is_expansion: If True, uses a higher star threshold
                      (min_stars + 50) for expansion topic results.

    Returns:
        Filtered list of repo dicts that pass all quality checks.
    """
    min_stars = config.min_stars + 50 if is_expansion else config.min_stars
    result = []

    for repo in repos:
        if not _passes_star_filter(repo, min_stars):
            continue
        if config.exclude_forks and _is_fork(repo):
            continue
        if config.exclude_archived and _is_archived(repo):
            continue
        if config.require_readme and not _has_readme(repo, config.min_readme_length):
            continue
        if config.languages and not _matches_language(repo, config.languages):
            continue
        result.append(repo)

    return result


def _passes_star_filter(repo: dict, min_stars: int) -> bool:
    return repo.get("stargazers_count", 0) >= min_stars


def _is_fork(repo: dict) -> bool:
    return repo.get("fork", False)


def _is_archived(repo: dict) -> bool:
    return repo.get("archived", False)


def _has_readme(repo: dict, min_length: int) -> bool:
    content = repo.get("readme_content")
    if content is None:
        return False
    return len(content) >= min_length


def _matches_language(repo: dict, languages: list[str]) -> bool:
    repo_lang = repo.get("language")
    if repo_lang is None:
        return False
    return repo_lang.lower() in [lang.lower() for lang in languages]
