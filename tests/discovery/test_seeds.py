"""Tests for seed repo fetching."""

from unittest.mock import MagicMock, patch

import pytest

from discovery.seeds import fetch_seed_repos
from discovery.types import GitHubAPIError, SeedRepo


def _make_repo_data(full_name: str = "owner/repo", stars: int = 100) -> dict:
    """Create a raw repo dict as returned by the GitHub Repos API."""
    owner, name = full_name.split("/", 1)
    return {
        "id": hash(full_name) % 100000,
        "full_name": full_name,
        "html_url": f"https://github.com/{full_name}",
        "description": f"Description of {name}",
        "stargazers_count": stars,
        "forks_count": 10,
        "subscribers_count": 5,
        "fork": False,
        "archived": False,
        "language": "Python",
        "updated_at": "2025-06-01T00:00:00Z",
        "pushed_at": "2025-06-01T00:00:00Z",
    }


SEEDS = [
    SeedRepo("owner/repo-a", "Repo A", "reason a"),
    SeedRepo("owner/repo-b", "Repo B", "reason b"),
]


class TestFetchSeedReposSuccess:
    @patch("discovery.seeds.fetch_readme")
    @patch("discovery.seeds.fetch_repo")
    def test_fetches_all_seeds(self, mock_fetch_repo, mock_fetch_readme):
        mock_fetch_repo.side_effect = [
            _make_repo_data("owner/repo-a"),
            _make_repo_data("owner/repo-b"),
        ]
        mock_fetch_readme.side_effect = ["# Repo A README", "# Repo B README"]

        result = fetch_seed_repos(SEEDS, token="tok")

        assert len(result) == 2
        assert result[0]["full_name"] == "owner/repo-a"
        assert result[0]["readme_content"] == "# Repo A README"
        assert result[1]["full_name"] == "owner/repo-b"
        assert result[1]["readme_content"] == "# Repo B README"

    @patch("discovery.seeds.fetch_readme")
    @patch("discovery.seeds.fetch_repo")
    def test_passes_token(self, mock_fetch_repo, mock_fetch_readme):
        mock_fetch_repo.return_value = _make_repo_data("owner/repo-a")
        mock_fetch_readme.return_value = "readme"

        fetch_seed_repos([SEEDS[0]], token="my-token")

        mock_fetch_repo.assert_called_once_with("owner/repo-a", token="my-token")
        mock_fetch_readme.assert_called_once_with("owner", "repo-a", token="my-token")

    @patch("discovery.seeds.fetch_readme")
    @patch("discovery.seeds.fetch_repo")
    def test_readme_none_still_included(self, mock_fetch_repo, mock_fetch_readme):
        """Seed with no README is still returned (filtering happens later)."""
        mock_fetch_repo.return_value = _make_repo_data("owner/repo-a")
        mock_fetch_readme.return_value = None

        result = fetch_seed_repos([SEEDS[0]], token="tok")

        assert len(result) == 1
        assert result[0]["readme_content"] is None


class TestFetchSeedRepos404:
    @patch("discovery.seeds.fetch_readme")
    @patch("discovery.seeds.fetch_repo")
    def test_404_skipped(self, mock_fetch_repo, mock_fetch_readme):
        mock_fetch_repo.return_value = None  # 404

        result = fetch_seed_repos([SEEDS[0]], token="tok")

        assert len(result) == 0
        mock_fetch_readme.assert_not_called()

    @patch("discovery.seeds.fetch_readme")
    @patch("discovery.seeds.fetch_repo")
    def test_one_404_others_returned(self, mock_fetch_repo, mock_fetch_readme):
        mock_fetch_repo.side_effect = [
            None,  # repo-a 404
            _make_repo_data("owner/repo-b"),  # repo-b exists
        ]
        mock_fetch_readme.return_value = "readme"

        result = fetch_seed_repos(SEEDS, token="tok")

        assert len(result) == 1
        assert result[0]["full_name"] == "owner/repo-b"


class TestFetchSeedReposErrors:
    @patch("discovery.seeds.fetch_repo")
    def test_api_error_propagates(self, mock_fetch_repo):
        mock_fetch_repo.side_effect = GitHubAPIError("rate limited", status_code=403)

        with pytest.raises(GitHubAPIError):
            fetch_seed_repos([SEEDS[0]], token="tok")


class TestFetchSeedReposEdgeCases:
    def test_empty_seed_list(self):
        result = fetch_seed_repos([], token="tok")
        assert result == []
