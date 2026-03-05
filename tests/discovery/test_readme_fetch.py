"""Tests for README fetching via GitHub Contents API."""

import base64
from unittest.mock import MagicMock, patch

import pytest

from discovery.github_client import fetch_readme, MAX_README_BYTES
from discovery.types import GitHubAPIError


def _make_readme_response(
    content_text: str = "# Hello\nThis is a README.",
    encoding: str = "base64",
    status_code: int = 200,
):
    """Create a mock response for the Contents API readme endpoint."""
    resp = MagicMock()
    resp.status_code = status_code

    if encoding == "base64" and status_code == 200:
        encoded = base64.b64encode(content_text.encode("utf-8")).decode("ascii")
        resp.json.return_value = {"content": encoded, "encoding": "base64"}
    elif status_code == 200:
        resp.json.return_value = {"content": content_text, "encoding": encoding}
    else:
        resp.text = content_text
        resp.headers = {}
        resp.json.return_value = {}

    return resp


class TestFetchReadmeSuccess:
    @patch("discovery.github_client.requests.get")
    def test_basic_fetch(self, mock_get):
        mock_get.return_value = _make_readme_response("# My Project\nA great tool.")
        result = fetch_readme("owner", "repo", token="tok")

        assert result == "# My Project\nA great tool."
        url = mock_get.call_args[0][0]
        assert "/repos/owner/repo/readme" in url

    @patch("discovery.github_client.requests.get")
    def test_auth_header_passed(self, mock_get):
        mock_get.return_value = _make_readme_response("readme")
        fetch_readme("owner", "repo", token="my-token")

        headers = mock_get.call_args[1]["headers"]
        assert headers["Authorization"] == "token my-token"

    @patch("discovery.github_client.requests.get")
    def test_no_auth_header_without_token(self, mock_get):
        mock_get.return_value = _make_readme_response("readme")
        fetch_readme("owner", "repo", token=None)

        headers = mock_get.call_args[1]["headers"]
        assert "Authorization" not in headers


class TestFetchReadmeReturnsNone:
    @patch("discovery.github_client.requests.get")
    def test_404_returns_none(self, mock_get):
        resp = MagicMock()
        resp.status_code = 404
        mock_get.return_value = resp

        result = fetch_readme("owner", "nonexistent")
        assert result is None

    @patch("discovery.github_client.requests.get")
    def test_unknown_encoding_returns_none(self, mock_get):
        resp = MagicMock()
        resp.status_code = 200
        resp.json.return_value = {"content": "stuff", "encoding": "utf-32"}
        mock_get.return_value = resp

        result = fetch_readme("owner", "repo")
        assert result is None

    @patch("discovery.github_client.requests.get")
    def test_empty_content_returns_none(self, mock_get):
        resp = MagicMock()
        resp.status_code = 200
        resp.json.return_value = {"content": "", "encoding": "none"}
        mock_get.return_value = resp

        result = fetch_readme("owner", "repo")
        assert result is None


class TestFetchReadmeTruncation:
    @patch("discovery.github_client.requests.get")
    def test_truncates_at_50kb(self, mock_get):
        large_content = "x" * (MAX_README_BYTES + 10_000)
        mock_get.return_value = _make_readme_response(large_content)

        result = fetch_readme("owner", "repo")
        assert result is not None
        assert len(result) == MAX_README_BYTES

    @patch("discovery.github_client.requests.get")
    def test_under_limit_not_truncated(self, mock_get):
        content = "x" * 1000
        mock_get.return_value = _make_readme_response(content)

        result = fetch_readme("owner", "repo")
        assert result is not None
        assert len(result) == 1000


class TestFetchReadmeErrors:
    @patch("discovery.github_client.requests.get")
    def test_401_raises(self, mock_get):
        resp = MagicMock()
        resp.status_code = 401
        resp.text = "Bad credentials"
        resp.headers = {}
        mock_get.return_value = resp

        with pytest.raises(GitHubAPIError) as exc_info:
            fetch_readme("owner", "repo", token="bad")
        assert exc_info.value.status_code == 401

    @patch("discovery.github_client.requests.get")
    def test_403_rate_limit_raises(self, mock_get):
        resp = MagicMock()
        resp.status_code = 403
        resp.text = "rate limit exceeded"
        resp.headers = {"X-RateLimit-Remaining": "0", "X-RateLimit-Reset": "9999999999"}
        mock_get.return_value = resp

        with pytest.raises(GitHubAPIError) as exc_info:
            fetch_readme("owner", "repo")
        assert exc_info.value.status_code == 403

    @patch("discovery.github_client.requests.get")
    def test_500_raises(self, mock_get):
        resp = MagicMock()
        resp.status_code = 500
        resp.text = "Internal Server Error"
        resp.headers = {}
        mock_get.return_value = resp

        with pytest.raises(GitHubAPIError) as exc_info:
            fetch_readme("owner", "repo")
        assert exc_info.value.status_code == 500

    @patch("discovery.github_client.requests.get")
    def test_network_error_raises(self, mock_get):
        import requests as req
        mock_get.side_effect = req.ConnectionError("refused")

        with pytest.raises(GitHubAPIError):
            fetch_readme("owner", "repo")

    @patch("discovery.github_client.requests.get")
    def test_timeout_raises(self, mock_get):
        import requests as req
        mock_get.side_effect = req.Timeout("timed out")

        with pytest.raises(GitHubAPIError):
            fetch_readme("owner", "repo")
