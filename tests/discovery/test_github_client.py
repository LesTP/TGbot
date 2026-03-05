"""Tests for GitHub search client."""

from unittest.mock import MagicMock, patch

import pytest

from discovery.github_client import fetch_repo, search_repos
from discovery.types import GitHubAPIError


def _make_response(
    status_code: int = 200,
    json_data: dict | None = None,
    headers: dict | None = None,
    text: str = "",
):
    """Create a mock requests.Response."""
    resp = MagicMock()
    resp.status_code = status_code
    resp.json.return_value = json_data or {"items": [], "total_count": 0}
    resp.headers = headers or {}
    resp.text = text
    return resp


def _make_items(count: int) -> list[dict]:
    """Create a list of fake repo dicts."""
    return [
        {
            "id": i,
            "full_name": f"owner/repo-{i}",
            "html_url": f"https://github.com/owner/repo-{i}",
            "description": f"Repo {i}",
            "stargazers_count": 100 - i,
            "forks_count": 10,
        }
        for i in range(count)
    ]


class TestSearchReposURLConstruction:
    @patch("discovery.github_client.requests.get")
    def test_topic_query_url(self, mock_get):
        mock_get.return_value = _make_response(json_data={"items": [], "total_count": 0})
        search_repos("topic:ai-coding", token="test-token")

        call_args = mock_get.call_args
        url = call_args[0][0]
        assert "api.github.com/search/repositories" in url
        assert "q=topic%3Aai-coding" in url

    @patch("discovery.github_client.requests.get")
    def test_keyword_query_url(self, mock_get):
        mock_get.return_value = _make_response(json_data={"items": [], "total_count": 0})
        search_repos('"agentic coding" in:description', token="test-token")

        url = mock_get.call_args[0][0]
        assert "api.github.com/search/repositories" in url
        assert "agentic+coding" in url or "agentic%20coding" in url

    @patch("discovery.github_client.requests.get")
    def test_sort_and_order_in_url(self, mock_get):
        mock_get.return_value = _make_response(json_data={"items": [], "total_count": 0})
        search_repos("topic:test", sort="forks", order="asc")

        url = mock_get.call_args[0][0]
        assert "sort=forks" in url
        assert "order=asc" in url


class TestSearchReposAuth:
    @patch("discovery.github_client.requests.get")
    def test_auth_header_with_token(self, mock_get):
        mock_get.return_value = _make_response(json_data={"items": [], "total_count": 0})
        search_repos("topic:test", token="my-token-123")

        headers = mock_get.call_args[1]["headers"]
        assert headers["Authorization"] == "token my-token-123"

    @patch("discovery.github_client.requests.get")
    def test_no_auth_header_without_token(self, mock_get):
        mock_get.return_value = _make_response(json_data={"items": [], "total_count": 0})
        search_repos("topic:test", token=None)

        headers = mock_get.call_args[1]["headers"]
        assert "Authorization" not in headers


class TestSearchReposPagination:
    @patch("discovery.github_client.requests.get")
    def test_single_page(self, mock_get):
        items = _make_items(5)
        mock_get.return_value = _make_response(
            json_data={"items": items, "total_count": 5}
        )

        result = search_repos("topic:test", per_page=30, max_pages=1)
        assert len(result) == 5
        assert mock_get.call_count == 1

    @patch("discovery.github_client.requests.get")
    def test_multi_page(self, mock_get):
        page1_items = _make_items(10)
        page2_items = _make_items(5)
        mock_get.side_effect = [
            _make_response(json_data={"items": page1_items, "total_count": 15}),
            _make_response(json_data={"items": page2_items, "total_count": 15}),
        ]

        result = search_repos("topic:test", per_page=10, max_pages=3)
        assert len(result) == 15
        assert mock_get.call_count == 2

    @patch("discovery.github_client.requests.get")
    def test_stops_when_all_results_fetched(self, mock_get):
        """Stops paginating when all results have been collected."""
        items = _make_items(8)
        mock_get.return_value = _make_response(
            json_data={"items": items, "total_count": 8}
        )

        result = search_repos("topic:test", per_page=10, max_pages=5)
        assert len(result) == 8
        assert mock_get.call_count == 1

    @patch("discovery.github_client.requests.get")
    def test_stops_at_max_pages(self, mock_get):
        """Respects max_pages even if more results exist."""
        items = _make_items(10)
        mock_get.return_value = _make_response(
            json_data={"items": items, "total_count": 100}
        )

        result = search_repos("topic:test", per_page=10, max_pages=2)
        assert len(result) == 20
        assert mock_get.call_count == 2

    @patch("discovery.github_client.requests.get")
    def test_per_page_capped_at_100(self, mock_get):
        mock_get.return_value = _make_response(json_data={"items": [], "total_count": 0})
        search_repos("topic:test", per_page=200)

        url = mock_get.call_args[0][0]
        assert "per_page=100" in url


class TestSearchReposErrors:
    @patch("discovery.github_client.requests.get")
    def test_403_rate_limit(self, mock_get):
        mock_get.return_value = _make_response(
            status_code=403,
            headers={"X-RateLimit-Remaining": "0", "X-RateLimit-Reset": "1700000000"},
            text='{"message":"API rate limit exceeded"}',
        )

        with pytest.raises(GitHubAPIError) as exc_info:
            search_repos("topic:test")

        assert exc_info.value.status_code == 403
        assert "rate limit" in str(exc_info.value).lower()

    @patch("discovery.github_client.requests.get")
    def test_401_auth_error(self, mock_get):
        mock_get.return_value = _make_response(
            status_code=401,
            text='{"message":"Bad credentials"}',
        )

        with pytest.raises(GitHubAPIError) as exc_info:
            search_repos("topic:test", token="bad-token")

        assert exc_info.value.status_code == 401
        assert "authentication" in str(exc_info.value).lower()

    @patch("discovery.github_client.requests.get")
    def test_500_server_error(self, mock_get):
        mock_get.return_value = _make_response(status_code=500, text="Internal Server Error")

        with pytest.raises(GitHubAPIError) as exc_info:
            search_repos("topic:test")

        assert exc_info.value.status_code == 500

    @patch("discovery.github_client.requests.get")
    def test_network_error(self, mock_get):
        import requests as req
        mock_get.side_effect = req.ConnectionError("Connection refused")

        with pytest.raises(GitHubAPIError) as exc_info:
            search_repos("topic:test")

        assert "network error" in str(exc_info.value).lower()

    @patch("discovery.github_client.requests.get")
    def test_timeout_error(self, mock_get):
        import requests as req
        mock_get.side_effect = req.Timeout("Request timed out")

        with pytest.raises(GitHubAPIError) as exc_info:
            search_repos("topic:test")

        assert "timed out" in str(exc_info.value).lower()


class TestSearchReposEmptyResults:
    @patch("discovery.github_client.requests.get")
    def test_empty_items_returns_empty_list(self, mock_get):
        mock_get.return_value = _make_response(
            json_data={"items": [], "total_count": 0}
        )

        result = search_repos("topic:nonexistent")
        assert result == []


class TestFetchRepo:
    @patch("discovery.github_client.requests.get")
    def test_success(self, mock_get):
        repo_data = {"id": 123, "full_name": "owner/repo", "stargazers_count": 100}
        mock_get.return_value = _make_response(json_data=repo_data)

        result = fetch_repo("owner/repo", token="tok")
        assert result["full_name"] == "owner/repo"

        url = mock_get.call_args[0][0]
        assert "/repos/owner/repo" in url
        assert "search" not in url

    @patch("discovery.github_client.requests.get")
    def test_404_returns_none(self, mock_get):
        mock_get.return_value = _make_response(status_code=404)

        result = fetch_repo("owner/nonexistent", token="tok")
        assert result is None

    @patch("discovery.github_client.requests.get")
    def test_auth_header(self, mock_get):
        mock_get.return_value = _make_response(json_data={"id": 1})

        fetch_repo("owner/repo", token="my-token")
        headers = mock_get.call_args[1]["headers"]
        assert headers["Authorization"] == "token my-token"

    @patch("discovery.github_client.requests.get")
    def test_api_error_raises(self, mock_get):
        mock_get.return_value = _make_response(status_code=403, text="rate limited",
                                                headers={"X-RateLimit-Remaining": "0"})

        with pytest.raises(GitHubAPIError) as exc_info:
            fetch_repo("owner/repo")
        assert exc_info.value.status_code == 403
