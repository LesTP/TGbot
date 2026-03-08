"""Tests for Telegraph API client."""

from unittest.mock import MagicMock, patch

import pytest

from delivery.telegraph_client import (
    TELEGRAPH_API_BASE,
    TelegraphClient,
    create_account,
    text_to_telegraph_html,
    _split_paragraphs,
    _escape_html,
    _apply_bold,
    _linkify_urls,
)
from delivery.types import TelegraphAPIError


# ───────────────────────────────────────────────────────────────────
# text_to_telegraph_html
# ───────────────────────────────────────────────────────────────────


class TestTextToTelegraphHtml:
    def test_empty_string(self):
        assert text_to_telegraph_html("") == "<p></p>"

    def test_whitespace_only(self):
        assert text_to_telegraph_html("   \n  ") == "<p></p>"

    def test_single_paragraph(self):
        result = text_to_telegraph_html("Hello world.")
        assert result == "<p>Hello world.</p>"

    def test_two_paragraphs(self):
        result = text_to_telegraph_html("First paragraph.\n\nSecond paragraph.")
        assert result == "<p>First paragraph.</p><p>Second paragraph.</p>"

    def test_consecutive_lines_join_into_paragraph(self):
        result = text_to_telegraph_html("Line one.\nLine two.\nLine three.")
        assert result == "<p>Line one. Line two. Line three.</p>"

    def test_multiple_blank_lines_treated_as_one_separator(self):
        result = text_to_telegraph_html("First.\n\n\n\nSecond.")
        assert result == "<p>First.</p><p>Second.</p>"

    def test_html_characters_escaped(self):
        result = text_to_telegraph_html("Use <b> tags & \"quotes\".")
        assert "&lt;b&gt;" in result
        assert "&amp;" in result

    def test_bold_markers_converted(self):
        result = text_to_telegraph_html("This is **important** text.")
        assert "<b>important</b>" in result
        assert "**" not in result

    def test_multiple_bold_in_one_paragraph(self):
        result = text_to_telegraph_html("Both **first** and **second** are bold.")
        assert "<b>first</b>" in result
        assert "<b>second</b>" in result

    def test_urls_linkified(self):
        result = text_to_telegraph_html("See https://example.com for details.")
        assert '<a href="https://example.com">https://example.com</a>' in result

    def test_http_url_linkified(self):
        result = text_to_telegraph_html("See http://example.com for details.")
        assert '<a href="http://example.com">http://example.com</a>' in result

    def test_url_with_path_linkified(self):
        result = text_to_telegraph_html("Check https://github.com/org/repo/issues")
        assert 'href="https://github.com/org/repo/issues"' in result

    def test_bold_and_links_combined(self):
        text = "**Tool:** Visit https://example.com for more."
        result = text_to_telegraph_html(text)
        assert "<b>Tool:</b>" in result
        assert '<a href="https://example.com">' in result

    def test_leading_trailing_whitespace_stripped_from_lines(self):
        result = text_to_telegraph_html("  hello  \n  world  ")
        assert result == "<p>hello world</p>"


# ───────────────────────────────────────────────────────────────────
# Internal helpers
# ───────────────────────────────────────────────────────────────────


class TestSplitParagraphs:
    def test_single_line(self):
        assert _split_paragraphs("hello") == ["hello"]

    def test_blank_line_separates(self):
        assert _split_paragraphs("a\n\nb") == ["a", "b"]

    def test_empty_input(self):
        assert _split_paragraphs("") == [""]

    def test_trailing_newlines(self):
        assert _split_paragraphs("a\n\n") == ["a"]


class TestEscapeHtml:
    def test_ampersand(self):
        assert _escape_html("A & B") == "A &amp; B"

    def test_angle_brackets(self):
        assert _escape_html("<div>") == "&lt;div&gt;"

    def test_no_special_chars(self):
        assert _escape_html("plain text") == "plain text"


class TestApplyBold:
    def test_basic_bold(self):
        assert _apply_bold("**bold**") == "<b>bold</b>"

    def test_no_bold(self):
        assert _apply_bold("plain text") == "plain text"

    def test_single_stars_not_converted(self):
        assert _apply_bold("*italic*") == "*italic*"

    def test_multiple_bold(self):
        result = _apply_bold("**a** and **b**")
        assert result == "<b>a</b> and <b>b</b>"


class TestLinkifyUrls:
    def test_https_url(self):
        result = _linkify_urls("Visit https://example.com today.")
        assert '<a href="https://example.com">https://example.com</a>' in result

    def test_no_urls(self):
        assert _linkify_urls("no links here") == "no links here"

    def test_url_not_greedy_into_html(self):
        # URL should stop at < or > or & which are HTML entities
        result = _linkify_urls("https://example.com&amp;more")
        assert 'href="https://example.com"' in result


# ───────────────────────────────────────────────────────────────────
# TelegraphClient.create_page — success
# ───────────────────────────────────────────────────────────────────


@pytest.fixture
def client():
    return TelegraphClient(access_token="test-token-123")


class TestCreatePageSuccess:
    def test_returns_page_url(self, client):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "ok": True,
            "result": {
                "path": "Test-Page-03-07",
                "url": "https://telegra.ph/Test-Page-03-07",
                "title": "Test Page",
            },
        }
        with patch("delivery.telegraph_client.requests.post", return_value=mock_response):
            url = client.create_page("Test Page", "<p>Content here</p>")
        assert url == "https://telegra.ph/Test-Page-03-07"

    def test_sends_access_token(self, client):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "ok": True,
            "result": {"url": "https://telegra.ph/x"},
        }
        with patch("delivery.telegraph_client.requests.post", return_value=mock_response) as mock_post:
            client.create_page("Title", "<p>Body</p>")
        payload = mock_post.call_args[1]["json"]
        assert payload["access_token"] == "test-token-123"

    def test_sends_title(self, client):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "ok": True,
            "result": {"url": "https://telegra.ph/x"},
        }
        with patch("delivery.telegraph_client.requests.post", return_value=mock_response) as mock_post:
            client.create_page("My Title", "<p>Body</p>")
        payload = mock_post.call_args[1]["json"]
        assert payload["title"] == "My Title"

    def test_sends_content_as_node_array(self, client):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "ok": True,
            "result": {"url": "https://telegra.ph/x"},
        }
        with patch("delivery.telegraph_client.requests.post", return_value=mock_response) as mock_post:
            client.create_page("Title", "<p>HTML content</p>")
        payload = mock_post.call_args[1]["json"]
        assert payload["content"] == [{"tag": "p", "children": ["HTML content"]}]

    def test_sends_author_name(self, client):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "ok": True,
            "result": {"url": "https://telegra.ph/x"},
        }
        with patch("delivery.telegraph_client.requests.post", return_value=mock_response) as mock_post:
            client.create_page("Title", "<p>Body</p>", author_name="Bot")
        payload = mock_post.call_args[1]["json"]
        assert payload["author_name"] == "Bot"

    def test_sends_author_url(self, client):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "ok": True,
            "result": {"url": "https://telegra.ph/x"},
        }
        with patch("delivery.telegraph_client.requests.post", return_value=mock_response) as mock_post:
            client.create_page("Title", "<p>Body</p>", author_url="https://t.me/bot")
        payload = mock_post.call_args[1]["json"]
        assert payload["author_url"] == "https://t.me/bot"

    def test_posts_to_correct_url(self, client):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "ok": True,
            "result": {"url": "https://telegra.ph/x"},
        }
        with patch("delivery.telegraph_client.requests.post", return_value=mock_response) as mock_post:
            client.create_page("Title", "<p>Body</p>")
        call_url = mock_post.call_args[0][0]
        assert call_url == f"{TELEGRAPH_API_BASE}/createPage"


# ───────────────────────────────────────────────────────────────────
# TelegraphClient.create_page — API errors
# ───────────────────────────────────────────────────────────────────


class TestCreatePageAPIErrors:
    def test_ok_false_raises(self, client):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "ok": False,
            "error": "CONTENT_TEXT_REQUIRED",
        }
        mock_response.text = '{"ok":false,"error":"CONTENT_TEXT_REQUIRED"}'
        with patch("delivery.telegraph_client.requests.post", return_value=mock_response):
            with pytest.raises(TelegraphAPIError) as exc_info:
                client.create_page("Title", "")
        assert "CONTENT_TEXT_REQUIRED" in str(exc_info.value)

    def test_missing_url_in_result_raises(self, client):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "ok": True,
            "result": {"path": "some-path"},
        }
        with patch("delivery.telegraph_client.requests.post", return_value=mock_response):
            with pytest.raises(TelegraphAPIError) as exc_info:
                client.create_page("Title", "<p>Body</p>")
        assert "missing 'result.url'" in str(exc_info.value)

    def test_non_json_response_raises(self, client):
        mock_response = MagicMock()
        mock_response.status_code = 502
        mock_response.json.side_effect = ValueError("No JSON")
        mock_response.text = "<html>Bad Gateway</html>"
        with patch("delivery.telegraph_client.requests.post", return_value=mock_response):
            with pytest.raises(TelegraphAPIError) as exc_info:
                client.create_page("Title", "<p>Body</p>")
        assert exc_info.value.status_code == 502
        assert "non-JSON" in str(exc_info.value)

    def test_http_error_status_raises(self, client):
        mock_response = MagicMock()
        mock_response.status_code = 500
        mock_response.json.return_value = {
            "ok": False,
            "error": "Internal Server Error",
        }
        mock_response.text = "Internal Server Error"
        with patch("delivery.telegraph_client.requests.post", return_value=mock_response):
            with pytest.raises(TelegraphAPIError) as exc_info:
                client.create_page("Title", "<p>Body</p>")
        assert exc_info.value.status_code == 500


# ───────────────────────────────────────────────────────────────────
# TelegraphClient.create_page — network errors
# ───────────────────────────────────────────────────────────────────


class TestCreatePageNetworkErrors:
    def test_connection_error_raises(self, client):
        import requests as req
        with patch(
            "delivery.telegraph_client.requests.post",
            side_effect=req.ConnectionError("Connection refused"),
        ):
            with pytest.raises(TelegraphAPIError) as exc_info:
                client.create_page("Title", "<p>Body</p>")
        assert "Network error" in str(exc_info.value)
        assert exc_info.value.status_code is None

    def test_timeout_raises(self, client):
        import requests as req
        with patch(
            "delivery.telegraph_client.requests.post",
            side_effect=req.Timeout("timed out"),
        ):
            with pytest.raises(TelegraphAPIError) as exc_info:
                client.create_page("Title", "<p>Body</p>")
        assert "timed out" in str(exc_info.value)
        assert exc_info.value.status_code is None

    def test_generic_request_exception_raises(self, client):
        import requests as req
        with patch(
            "delivery.telegraph_client.requests.post",
            side_effect=req.RequestException("something broke"),
        ):
            with pytest.raises(TelegraphAPIError) as exc_info:
                client.create_page("Title", "<p>Body</p>")
        assert "request failed" in str(exc_info.value)
        assert exc_info.value.status_code is None


# ───────────────────────────────────────────────────────────────────
# create_account
# ───────────────────────────────────────────────────────────────────


class TestCreateAccount:
    def test_returns_access_token(self):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "ok": True,
            "result": {
                "short_name": "mybot",
                "access_token": "abc123token",
            },
        }
        with patch("delivery.telegraph_client.requests.post", return_value=mock_response):
            token = create_account("mybot", author_name="My Bot")
        assert token == "abc123token"

    def test_sends_correct_payload(self):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "ok": True,
            "result": {"access_token": "tok"},
        }
        with patch("delivery.telegraph_client.requests.post", return_value=mock_response) as mock_post:
            create_account("mybot", author_name="Author")
        payload = mock_post.call_args[1]["json"]
        assert payload["short_name"] == "mybot"
        assert payload["author_name"] == "Author"

    def test_posts_to_correct_url(self):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "ok": True,
            "result": {"access_token": "tok"},
        }
        with patch("delivery.telegraph_client.requests.post", return_value=mock_response) as mock_post:
            create_account("mybot")
        call_url = mock_post.call_args[0][0]
        assert call_url == f"{TELEGRAPH_API_BASE}/createAccount"

    def test_api_error_raises(self):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "ok": False,
            "error": "SHORT_NAME_REQUIRED",
        }
        mock_response.text = '{"ok":false,"error":"SHORT_NAME_REQUIRED"}'
        with patch("delivery.telegraph_client.requests.post", return_value=mock_response):
            with pytest.raises(TelegraphAPIError) as exc_info:
                create_account("")
        assert "SHORT_NAME_REQUIRED" in str(exc_info.value)

    def test_missing_token_in_result_raises(self):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "ok": True,
            "result": {"short_name": "mybot"},
        }
        with patch("delivery.telegraph_client.requests.post", return_value=mock_response):
            with pytest.raises(TelegraphAPIError) as exc_info:
                create_account("mybot")
        assert "missing 'result.access_token'" in str(exc_info.value)

    def test_connection_error_raises(self):
        import requests as req
        with patch(
            "delivery.telegraph_client.requests.post",
            side_effect=req.ConnectionError("Connection refused"),
        ):
            with pytest.raises(TelegraphAPIError) as exc_info:
                create_account("mybot")
        assert "Network error" in str(exc_info.value)
