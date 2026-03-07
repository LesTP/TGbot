"""
Telegraph API client.

Publishes long-form content to Telegraph (telegra.ph) so deep-dive
summaries can be read in full instead of being truncated in Telegram.
"""

import re

import requests

from delivery.types import TelegraphAPIError

TELEGRAPH_API_BASE = "https://api.telegra.ph"


def text_to_telegraph_html(text: str) -> str:
    """Convert plain text to Telegraph's simplified HTML.

    Telegraph supports a limited subset of HTML: <p>, <b>, <i>, <a>,
    <br>, <blockquote>, <h3>, <h4>, and a few others.

    Conversion rules:
    - Consecutive non-blank lines become a single <p> paragraph.
    - Blank lines separate paragraphs.
    - Lines starting with **text** become <b>text</b> within their paragraph.
    - Bare URLs (https://...) become clickable <a> links.
    - HTML special characters (&, <, >) are escaped.
    """
    if not text or not text.strip():
        return "<p></p>"

    paragraphs = _split_paragraphs(text)
    html_parts = []

    for para in paragraphs:
        escaped = _escape_html(para)
        styled = _apply_bold(escaped)
        linked = _linkify_urls(styled)
        html_parts.append(f"<p>{linked}</p>")

    return "".join(html_parts)


def _split_paragraphs(text: str) -> list[str]:
    """Split text into paragraphs on blank lines.

    Consecutive non-blank lines are joined with a space.
    """
    lines = text.split("\n")
    paragraphs = []
    current = []

    for line in lines:
        if line.strip() == "":
            if current:
                paragraphs.append(" ".join(current))
                current = []
        else:
            current.append(line.strip())

    if current:
        paragraphs.append(" ".join(current))

    return paragraphs if paragraphs else [""]


def _escape_html(text: str) -> str:
    """Escape HTML special characters."""
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def _apply_bold(text: str) -> str:
    """Convert **text** markers to <b>text</b>."""
    return re.sub(r'\*\*(.+?)\*\*', r'<b>\1</b>', text)


def _linkify_urls(text: str) -> str:
    """Convert bare https:// URLs into <a> tags."""
    return re.sub(
        r'(https?://[^\s<>&]+)',
        r'<a href="\1">\1</a>',
        text,
    )


def _telegraph_post(url: str, payload: dict) -> dict:
    """Make a POST request to the Telegraph API.

    Shared by TelegraphClient and create_account.

    Returns:
        Parsed JSON response dict.

    Raises:
        TelegraphAPIError: On any failure.
    """
    try:
        response = requests.post(url, json=payload, timeout=30)
    except requests.ConnectionError as exc:
        raise TelegraphAPIError(
            f"Network error connecting to Telegraph: {exc}"
        ) from exc
    except requests.Timeout as exc:
        raise TelegraphAPIError(
            "Telegraph API request timed out."
        ) from exc
    except requests.RequestException as exc:
        raise TelegraphAPIError(
            f"Telegraph API request failed: {exc}"
        ) from exc

    try:
        data = response.json()
    except ValueError:
        raise TelegraphAPIError(
            f"Telegraph returned non-JSON response (HTTP {response.status_code})",
            status_code=response.status_code,
        )

    if response.status_code != 200 or not data.get("ok"):
        error = data.get("error", response.text)
        raise TelegraphAPIError(
            f"Telegraph API error: {error}",
            status_code=response.status_code,
        )

    return data


class TelegraphClient:
    """Minimal Telegraph API client for publishing pages."""

    def __init__(self, access_token: str):
        self._access_token = access_token

    def create_page(
        self,
        title: str,
        html_content: str,
        author_name: str = "",
        author_url: str = "",
    ) -> str:
        """Publish an HTML page to Telegraph.

        Args:
            title: Page title (1-256 characters).
            html_content: Page body in Telegraph's HTML subset.
            author_name: Author name displayed on the page.
            author_url: URL opened when the author name is clicked.

        Returns:
            The URL of the published page.

        Raises:
            TelegraphAPIError: On API errors, HTTP errors, or network failures.
        """
        url = f"{TELEGRAPH_API_BASE}/createPage"
        payload = {
            "access_token": self._access_token,
            "title": title,
            "content": html_content,
            "author_name": author_name,
            "author_url": author_url,
            "return_content": False,
        }

        response_data = _telegraph_post(url, payload)

        try:
            return response_data["result"]["url"]
        except (KeyError, TypeError) as exc:
            raise TelegraphAPIError(
                f"Unexpected Telegraph response: missing 'result.url' in {response_data}"
            ) from exc


def create_account(short_name: str, author_name: str = "") -> str:
    """Create a Telegraph account and return the access token.

    Utility for initial setup. Call once, then store the token.

    Args:
        short_name: Account name (1-32 characters).
        author_name: Default author name for pages.

    Returns:
        Access token string for use with TelegraphClient.

    Raises:
        TelegraphAPIError: On API or network failure.
    """
    url = f"{TELEGRAPH_API_BASE}/createAccount"
    payload = {
        "short_name": short_name,
        "author_name": author_name,
    }

    data = _telegraph_post(url, payload)

    try:
        return data["result"]["access_token"]
    except (KeyError, TypeError) as exc:
        raise TelegraphAPIError(
            f"Unexpected Telegraph response: missing 'result.access_token'"
        ) from exc
