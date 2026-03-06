"""
Delivery message formatting.

Telegram MarkdownV2 escaping, link formatting, and digest message assembly.
"""

from delivery.types import Digest, SummaryWithRepo

# MarkdownV2 special characters that must be escaped with '\'
_SPECIAL_CHARS = set(r'_*[]()~`>#+-=|{}.!')

# Emoji mapping for ranking criteria
_CRITERIA_EMOJI = {
    "stars": "⭐",
    "forks": "🍴",
    "activity": "📈",
    "recency": "🆕",
    "subscribers": "👀",
}

_SECTION_SEPARATOR = "━━━━━━━━━━━━━━━━━━"


def escape_markdown(text: str) -> str:
    """Escape all MarkdownV2 special characters in text.

    Every character in Telegram's MarkdownV2 special set is prefixed
    with a backslash so it renders as a literal character.
    """
    result = []
    for char in text:
        if char in _SPECIAL_CHARS:
            result.append('\\')
        result.append(char)
    return ''.join(result)


def escape_url(url: str) -> str:
    """Escape characters that would break a MarkdownV2 inline URL.

    Inside (...) only ')' and '\\' are structural and need escaping.
    """
    return url.replace('\\', '\\\\').replace(')', '\\)')


def format_link(text: str, url: str) -> str:
    """Build a MarkdownV2 inline link: [escaped_text](escaped_url).

    Text gets full MarkdownV2 escaping; URL only escapes ')' and '\\'.
    """
    return f"[{escape_markdown(text)}]({escape_url(url)})"


def format_deep_dive(summary: SummaryWithRepo) -> str:
    """Format the deep dive section of a digest message."""
    stars_str = escape_markdown(f"{summary.stars:,}")
    name = escape_markdown(summary.repo_name)
    link = format_link("View on GitHub", summary.repo_url)
    content = escape_markdown(summary.summary_content)

    return (
        f"*{name}* ⭐ {stars_str}\n"
        f"{link}\n"
        f"\n"
        f"{content}"
    )


def format_quick_hit(summary: SummaryWithRepo, index: int) -> str:
    """Format a single quick hit entry with its index number."""
    stars_str = escape_markdown(f"{summary.stars:,}")
    name = escape_markdown(summary.repo_name)
    content = escape_markdown(summary.summary_content)
    link = format_link("GitHub", summary.repo_url)

    return (
        f"{index}\\. *{name}* ⭐ {stars_str} — {content}\n"
        f"   {link}"
    )


def format_digest(digest: Digest) -> str:
    """Format a complete digest into a MarkdownV2 Telegram message.

    Layout:
      Header (date + ranking criteria)
      Separator
      Deep Dive section
      Separator
      Quick Hits section (if any)
    """
    emoji = _CRITERIA_EMOJI.get(digest.ranking_criteria, "📊")
    criteria_label = escape_markdown(digest.ranking_criteria.capitalize())
    date_str = escape_markdown(digest.date.strftime("%B %d, %Y").replace(" 0", " "))

    sep = escape_markdown(_SECTION_SEPARATOR)

    header = f"📅 *Daily Digest* — {date_str}\nRanked by: {emoji} {criteria_label}"

    deep = format_deep_dive(digest.deep_dive)
    deep_section = f"{sep}\n🔍 *DEEP DIVE*\n{sep}\n\n{deep}"

    parts = [header, "", deep_section]

    if digest.quick_hits:
        hits = "\n\n".join(
            format_quick_hit(s, i + 1)
            for i, s in enumerate(digest.quick_hits)
        )
        quick_section = f"{sep}\n⚡ *QUICK HITS*\n{sep}\n\n{hits}"
        parts.extend(["", quick_section])

    return "\n".join(parts)
