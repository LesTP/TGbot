"""
Ranking/sorting for discovered repositories.

Sorts raw GitHub API repo dicts by a given RankingCriteria.
Uses GitHub API field names directly (stargazers_count, forks_count, etc.).

"Activity" is defined as ``pushed_at`` — the timestamp of the most
recent push to any branch. This is distinct from ``updated_at``
(which tracks any repo event including issues, wiki edits, etc.)
and is available in GitHub search results without extra API calls.
"""

from discovery.types import RankingCriteria

# Maps RankingCriteria to (dict_key, reverse). All currently descending.
_SORT_KEYS: dict[RankingCriteria, str] = {
    RankingCriteria.STARS: "stargazers_count",
    RankingCriteria.FORKS: "forks_count",
    RankingCriteria.SUBSCRIBERS: "subscribers_count",
    RankingCriteria.RECENCY: "updated_at",
    RankingCriteria.ACTIVITY: "pushed_at",
}

# Default values when a key is missing from a repo dict.
_DEFAULTS: dict[str, object] = {
    "stargazers_count": 0,
    "forks_count": 0,
    "subscribers_count": 0,
    "updated_at": "",
    "pushed_at": "",
}


def sort_repos(repos: list[dict], criteria: RankingCriteria) -> list[dict]:
    """Sort repos by the given ranking criteria (descending).

    Args:
        repos: Raw GitHub API repo dicts.
        criteria: Which metric to sort by.

    Returns:
        New list sorted descending by the criteria. Ties preserve
        original order (stable sort).
    """
    key = _SORT_KEYS[criteria]
    default = _DEFAULTS[key]
    return sorted(repos, key=lambda r: r.get(key, default), reverse=True)
