"""
GitHub API client for Discovery module.

Handles search queries, README fetching, pagination, auth, and
error mapping. All functions return raw data (dicts/lists/strings);
conversion to domain types happens in the caller.
"""

import base64
import logging
from typing import Optional
from urllib.parse import urlencode

import requests

from discovery.types import GitHubAPIError

logger = logging.getLogger(__name__)

GITHUB_API_BASE = "https://api.github.com"
DEFAULT_PER_PAGE = 30
MAX_PER_PAGE = 100
MAX_README_BYTES = 50 * 1024  # 50KB


def _build_headers(token: Optional[str] = None) -> dict:
    headers = {"Accept": "application/vnd.github.v3+json"}
    if token:
        headers["Authorization"] = f"token {token}"
    return headers


def _raise_for_github_error(response: requests.Response) -> None:
    """Map GitHub HTTP errors to GitHubAPIError."""
    status = response.status_code
    try:
        body = response.text
    except Exception:
        body = None

    if status == 401:
        raise GitHubAPIError(
            "GitHub authentication failed. Check your token.",
            status_code=401,
            response_body=body,
        )
    if status == 403:
        # Check for rate limiting
        remaining = response.headers.get("X-RateLimit-Remaining")
        reset = response.headers.get("X-RateLimit-Reset")
        msg = "GitHub API rate limit exceeded." if remaining == "0" else "GitHub API forbidden (403)."
        if reset:
            msg += f" Resets at timestamp {reset}."
        raise GitHubAPIError(msg, status_code=403, response_body=body)
    if status == 422:
        raise GitHubAPIError(
            f"GitHub API validation error: {body}",
            status_code=422,
            response_body=body,
        )
    if status >= 500:
        raise GitHubAPIError(
            f"GitHub server error ({status}).",
            status_code=status,
            response_body=body,
        )
    if status >= 400:
        raise GitHubAPIError(
            f"GitHub API error ({status}): {body}",
            status_code=status,
            response_body=body,
        )


def search_repos(
    query: str,
    token: Optional[str] = None,
    sort: str = "stars",
    order: str = "desc",
    per_page: int = DEFAULT_PER_PAGE,
    max_pages: int = 1,
) -> list[dict]:
    """Search GitHub repositories and return raw item dicts.

    Args:
        query: GitHub search query string (e.g. "topic:ai-coding").
        token: GitHub personal access token. Optional but recommended
               (unauthenticated: 10 requests/min; authenticated: 30/min).
        sort: Sort field — "stars", "forks", or "updated".
        order: Sort order — "desc" or "asc".
        per_page: Results per page (1-100, default 30).
        max_pages: Maximum pages to fetch (default 1).

    Returns:
        List of raw repository dicts from the GitHub API ``items`` array.

    Raises:
        GitHubAPIError: On auth failure, rate limiting, server errors,
                        or network errors.
    """
    per_page = min(per_page, MAX_PER_PAGE)
    headers = _build_headers(token)
    all_items: list[dict] = []

    for page in range(1, max_pages + 1):
        params = urlencode({
            "q": query,
            "sort": sort,
            "order": order,
            "per_page": per_page,
            "page": page,
        })
        url = f"{GITHUB_API_BASE}/search/repositories?{params}"

        try:
            response = requests.get(url, headers=headers, timeout=30)
        except requests.ConnectionError as exc:
            raise GitHubAPIError(f"Network error connecting to GitHub: {exc}") from exc
        except requests.Timeout as exc:
            raise GitHubAPIError("GitHub API request timed out.") from exc
        except requests.RequestException as exc:
            raise GitHubAPIError(f"GitHub API request failed: {exc}") from exc

        if response.status_code != 200:
            _raise_for_github_error(response)

        data = response.json()
        items = data.get("items", [])
        all_items.extend(items)

        # Stop if we've received all results
        total_count = data.get("total_count", 0)
        if len(all_items) >= total_count:
            break
        if len(items) < per_page:
            break

    return all_items


def fetch_readme(
    owner: str,
    repo: str,
    token: Optional[str] = None,
) -> Optional[str]:
    """Fetch README content for a repository via the Contents API.

    Uses ``GET /repos/{owner}/{repo}/readme`` which automatically
    resolves the correct README file regardless of name casing or
    default branch.

    Args:
        owner: Repository owner (e.g. "anthropics").
        repo: Repository name (e.g. "anthropic-cookbook").
        token: GitHub personal access token. Optional.

    Returns:
        Decoded README text truncated to 50KB, or None if the repo
        has no README or the content is not decodable as UTF-8.

    Raises:
        GitHubAPIError: On auth failure, rate limiting, server errors,
                        or network errors. Does NOT raise on 404
                        (returns None instead).
    """
    url = f"{GITHUB_API_BASE}/repos/{owner}/{repo}/readme"
    headers = _build_headers(token)

    try:
        response = requests.get(url, headers=headers, timeout=30)
    except requests.ConnectionError as exc:
        raise GitHubAPIError(f"Network error connecting to GitHub: {exc}") from exc
    except requests.Timeout as exc:
        raise GitHubAPIError("GitHub API request timed out.") from exc
    except requests.RequestException as exc:
        raise GitHubAPIError(f"GitHub API request failed: {exc}") from exc

    if response.status_code == 404:
        return None

    if response.status_code != 200:
        _raise_for_github_error(response)

    data = response.json()
    encoding = data.get("encoding", "")
    content = data.get("content", "")

    if encoding == "base64":
        try:
            decoded = base64.b64decode(content).decode("utf-8", errors="replace")
        except Exception:
            return None
    elif encoding == "none" or encoding == "":
        # Content might be empty or unavailable
        if not content:
            return None
        decoded = content
    else:
        return None

    if len(decoded) > MAX_README_BYTES:
        decoded = decoded[:MAX_README_BYTES]

    return decoded
