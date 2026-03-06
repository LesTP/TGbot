"""Tests for Delivery markdown escaping, link formatting, and message assembly."""

from datetime import date

import pytest

from delivery.formatting import (
    escape_markdown,
    escape_url,
    format_deep_dive,
    format_digest,
    format_link,
    format_quick_hit,
    truncate_for_telegram,
)
from delivery.types import Digest, SummaryWithRepo
from tests.delivery.conftest import make_summary as _make_summary


class TestEscapeMarkdown:
    """Tests for escape_markdown — MarkdownV2 special char escaping."""

    def test_plain_text_unchanged(self):
        assert escape_markdown("hello world") == "hello world"

    def test_empty_string(self):
        assert escape_markdown("") == ""

    def test_underscore(self):
        assert escape_markdown("hello_world") == "hello\\_world"

    def test_asterisk(self):
        assert escape_markdown("*bold*") == "\\*bold\\*"

    def test_square_brackets(self):
        assert escape_markdown("[link]") == "\\[link\\]"

    def test_parentheses(self):
        assert escape_markdown("(text)") == "\\(text\\)"

    def test_tilde(self):
        assert escape_markdown("~strike~") == "\\~strike\\~"

    def test_backtick(self):
        assert escape_markdown("`code`") == "\\`code\\`"

    def test_greater_than(self):
        assert escape_markdown("> quote") == "\\> quote"

    def test_hash(self):
        assert escape_markdown("# heading") == "\\# heading"

    def test_plus(self):
        assert escape_markdown("+item") == "\\+item"

    def test_minus(self):
        assert escape_markdown("-item") == "\\-item"

    def test_equals(self):
        assert escape_markdown("a=b") == "a\\=b"

    def test_pipe(self):
        assert escape_markdown("a|b") == "a\\|b"

    def test_curly_braces(self):
        assert escape_markdown("{x}") == "\\{x\\}"

    def test_dot(self):
        assert escape_markdown("v1.0") == "v1\\.0"

    def test_exclamation(self):
        assert escape_markdown("Hello!") == "Hello\\!"

    def test_multiple_special_chars(self):
        result = escape_markdown("v1.0 - *new* (beta)")
        assert result == "v1\\.0 \\- \\*new\\* \\(beta\\)"

    def test_all_special_chars_present(self):
        text = "_*[]()~`>#+-=|{}.!"
        result = escape_markdown(text)
        for char in text:
            assert f"\\{char}" in result

    def test_numbers_and_letters_unchanged(self):
        text = "abc123XYZ"
        assert escape_markdown(text) == text

    def test_unicode_unchanged(self):
        assert escape_markdown("⭐ 🔍 émojis") == "⭐ 🔍 émojis"


class TestEscapeUrl:
    """Tests for escape_url — URL escaping for MarkdownV2 inline links."""

    def test_clean_url_unchanged(self):
        url = "https://github.com/org/repo"
        assert escape_url(url) == url

    def test_closing_paren_escaped(self):
        url = "https://en.wikipedia.org/wiki/Thing_(concept)"
        assert escape_url(url) == "https://en.wikipedia.org/wiki/Thing_(concept\\)"

    def test_backslash_escaped(self):
        url = "https://example.com/path\\file"
        assert escape_url(url) == "https://example.com/path\\\\file"

    def test_both_paren_and_backslash(self):
        url = "https://example.com/a\\b(c)"
        assert escape_url(url) == "https://example.com/a\\\\b(c\\)"

    def test_empty_url(self):
        assert escape_url("") == ""

    def test_dots_not_escaped(self):
        url = "https://github.com/org/repo.git"
        assert escape_url(url) == url


class TestFormatLink:
    """Tests for format_link — MarkdownV2 inline link construction."""

    def test_clean_text_and_url(self):
        result = format_link("Click here", "https://example.com")
        assert result == "[Click here](https://example.com)"

    def test_text_with_special_chars_escaped(self):
        result = format_link("v1.0 (beta)", "https://example.com")
        assert result == "[v1\\.0 \\(beta\\)](https://example.com)"

    def test_url_with_parens_escaped(self):
        result = format_link("Link", "https://example.com/a(b)")
        assert result == "[Link](https://example.com/a(b\\))"

    def test_both_text_and_url_escaped(self):
        result = format_link("project.name", "https://example.com/a(b)")
        assert result == "[project\\.name](https://example.com/a(b\\))"

    def test_empty_text(self):
        result = format_link("", "https://example.com")
        assert result == "[](https://example.com)"

    def test_github_repo_link(self):
        result = format_link("View on GitHub", "https://github.com/langchain-ai/langchain")
        assert result == "[View on GitHub](https://github.com/langchain-ai/langchain)"

    def test_text_with_underscore(self):
        result = format_link("my_repo", "https://github.com/org/my_repo")
        assert result == "[my\\_repo](https://github.com/org/my_repo)"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_digest(
    deep_name="deep-repo",
    quick_names=("quick-1", "quick-2", "quick-3"),
    criteria="stars",
    d=date(2026, 3, 6),
):
    deep = _make_summary(name=deep_name, stars=5000, content="Deep dive content here.")
    quicks = [
        _make_summary(name=n, stars=100 * (i + 1), content=f"Quick summary {i + 1}.")
        for i, n in enumerate(quick_names)
    ]
    return Digest(deep_dive=deep, quick_hits=quicks, ranking_criteria=criteria, date=d)


# ---------------------------------------------------------------------------
# format_deep_dive, format_quick_hit, format_digest
# ---------------------------------------------------------------------------


class TestFormatDeepDive:
    def test_contains_repo_name_bold(self):
        result = format_deep_dive(_make_summary(name="langchain"))
        assert "*langchain*" in result

    def test_contains_stars_with_comma(self):
        result = format_deep_dive(_make_summary(stars=12345))
        assert "12,345" in result

    def test_contains_github_link(self):
        url = "https://github.com/org/repo"
        result = format_deep_dive(_make_summary(url=url))
        assert f"[View on GitHub]({url})" in result

    def test_contains_summary_content(self):
        result = format_deep_dive(_make_summary(content="Does amazing things"))
        assert "Does amazing things" in result

    def test_special_chars_in_name_escaped(self):
        result = format_deep_dive(_make_summary(name="my_repo.js"))
        assert "*my\\_repo\\.js*" in result

    def test_special_chars_in_content_escaped(self):
        result = format_deep_dive(_make_summary(content="Use `pip install` (v1.0)"))
        assert "\\`pip install\\`" in result
        assert "\\(v1\\.0\\)" in result


class TestFormatQuickHit:
    def test_contains_index(self):
        result = format_quick_hit(_make_summary(), 1)
        assert result.startswith("1\\.")

    def test_contains_repo_name_bold(self):
        result = format_quick_hit(_make_summary(name="fastapi"), 1)
        assert "*fastapi*" in result

    def test_contains_stars(self):
        result = format_quick_hit(_make_summary(stars=567), 1)
        assert "567" in result

    def test_contains_summary_content(self):
        result = format_quick_hit(_make_summary(content="A web framework"), 2)
        assert "A web framework" in result

    def test_contains_github_link(self):
        url = "https://github.com/org/repo"
        result = format_quick_hit(_make_summary(url=url), 1)
        assert f"[GitHub]({url})" in result

    def test_index_two_digits(self):
        result = format_quick_hit(_make_summary(), 10)
        assert "10\\." in result


class TestFormatDigest:
    def test_contains_date(self):
        result = format_digest(_make_digest(d=date(2026, 3, 6)))
        assert "March 6, 2026" in result

    def test_contains_daily_digest_header(self):
        result = format_digest(_make_digest())
        assert "Daily Digest" in result

    def test_contains_ranking_criteria(self):
        result = format_digest(_make_digest(criteria="stars"))
        assert "Stars" in result

    def test_stars_emoji(self):
        result = format_digest(_make_digest(criteria="stars"))
        assert "⭐" in result

    def test_forks_emoji(self):
        result = format_digest(_make_digest(criteria="forks"))
        assert "🍴" in result

    def test_activity_emoji(self):
        result = format_digest(_make_digest(criteria="activity"))
        assert "📈" in result

    def test_recency_emoji(self):
        result = format_digest(_make_digest(criteria="recency"))
        assert "🆕" in result

    def test_subscribers_emoji(self):
        result = format_digest(_make_digest(criteria="subscribers"))
        assert "👀" in result

    def test_unknown_criteria_fallback_emoji(self):
        result = format_digest(_make_digest(criteria="unknown"))
        assert "📊" in result

    def test_contains_deep_dive_section(self):
        result = format_digest(_make_digest())
        assert "DEEP DIVE" in result

    def test_contains_quick_hits_section(self):
        result = format_digest(_make_digest())
        assert "QUICK HITS" in result

    def test_contains_deep_dive_repo_name(self):
        result = format_digest(_make_digest(deep_name="awesome-tool"))
        assert "awesome\\-tool" in result

    def test_contains_all_quick_hit_names(self):
        result = format_digest(_make_digest(quick_names=("alpha", "beta", "gamma")))
        assert "alpha" in result
        assert "beta" in result
        assert "gamma" in result

    def test_quick_hits_numbered_sequentially(self):
        result = format_digest(_make_digest(quick_names=("a", "b", "c")))
        assert "1\\." in result
        assert "2\\." in result
        assert "3\\." in result

    def test_empty_quick_hits_omits_section(self):
        digest = Digest(
            deep_dive=_make_summary(),
            quick_hits=[],
            ranking_criteria="stars",
            date=date(2026, 1, 1),
        )
        result = format_digest(digest)
        assert "DEEP DIVE" in result
        assert "QUICK HITS" not in result

    def test_single_quick_hit(self):
        digest = Digest(
            deep_dive=_make_summary(),
            quick_hits=[_make_summary(name="solo")],
            ranking_criteria="stars",
            date=date(2026, 1, 1),
        )
        result = format_digest(digest)
        assert "QUICK HITS" in result
        assert "solo" in result

    def test_contains_section_separators(self):
        result = format_digest(_make_digest())
        assert "━" in result

    def test_date_no_leading_zero(self):
        result = format_digest(_make_digest(d=date(2026, 1, 5)))
        assert "January 5, 2026" in result
        assert "January 05" not in result


# ---------------------------------------------------------------------------
# truncate_for_telegram
# ---------------------------------------------------------------------------


class TestTruncateForTelegram:
    def _make_long_digest(self, content_length=5000):
        """Build a formatted digest message with a deep dive body of roughly content_length chars."""
        sentence = "This is a test sentence about a great tool\\. "
        repeat_count = content_length // len(sentence) + 1
        long_content = sentence * repeat_count
        deep = _make_summary(content=long_content[:content_length])
        digest = Digest(
            deep_dive=deep,
            quick_hits=[_make_summary(name="quick-1")],
            ranking_criteria="stars",
            date=date(2026, 3, 6),
        )
        return format_digest(digest)

    def test_under_limit_unchanged(self):
        short_msg = format_digest(_make_digest())
        result = truncate_for_telegram(short_msg, "https://github.com/org/repo")
        assert result == short_msg

    def test_at_limit_unchanged(self):
        msg = "x" * 4096
        result = truncate_for_telegram(msg, "https://github.com/org/repo", max_length=4096)
        assert result == msg

    def test_over_limit_truncated(self):
        msg = self._make_long_digest(5000)
        assert len(msg) > 4096
        result = truncate_for_telegram(msg, "https://github.com/org/repo")
        assert len(result) <= 4096

    def test_truncated_contains_read_more(self):
        msg = self._make_long_digest(5000)
        url = "https://github.com/org/repo"
        result = truncate_for_telegram(msg, url)
        assert "[Read more]" in result
        assert url in result

    def test_truncated_contains_ellipsis(self):
        msg = self._make_long_digest(5000)
        result = truncate_for_telegram(msg, "https://github.com/org/repo")
        assert "…" in result

    def test_truncated_preserves_header(self):
        msg = self._make_long_digest(5000)
        result = truncate_for_telegram(msg, "https://github.com/org/repo")
        assert "Daily Digest" in result
        assert "DEEP DIVE" in result

    def test_truncated_preserves_quick_hits(self):
        msg = self._make_long_digest(5000)
        result = truncate_for_telegram(msg, "https://github.com/org/repo")
        assert "QUICK HITS" in result

    def test_prefers_sentence_boundary(self):
        msg = self._make_long_digest(5000)
        result = truncate_for_telegram(msg, "https://github.com/org/repo")
        # Should end with a sentence (escaped period before ellipsis)
        ellipsis_pos = result.find("…")
        before_ellipsis = result[:ellipsis_pos].rstrip()
        assert before_ellipsis.endswith("\\.") or before_ellipsis.endswith(" ")

    def test_custom_max_length(self):
        msg = self._make_long_digest(3000)
        result = truncate_for_telegram(msg, "https://github.com/org/repo", max_length=2000)
        assert len(result) <= 2000

    def test_url_with_special_chars_escaped_in_read_more(self):
        msg = self._make_long_digest(5000)
        url = "https://github.com/org/repo_(v2)"
        result = truncate_for_telegram(msg, url)
        assert "(v2\\)" in result

    def test_no_structure_hard_truncates(self):
        msg = "a" * 5000
        result = truncate_for_telegram(msg, "https://example.com", max_length=200)
        assert len(result) <= 200
        assert "[Read more]" in result
