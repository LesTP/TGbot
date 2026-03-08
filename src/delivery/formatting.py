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


def extract_excerpt(text: str, max_paragraphs: int = 3) -> str:
    """Extract the first few paragraphs of text for use as an excerpt.

    Splits on double-newlines (blank lines) and returns the first
    max_paragraphs paragraphs joined by double-newlines.
    Operates on raw text (before MarkdownV2 escaping).
    """
    paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()]
    selected = paragraphs[:max_paragraphs]
    return "\n\n".join(selected)


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


def _format_deep_dive_with_excerpt(
    summary: SummaryWithRepo, telegraph_url: str
) -> str:
    """Format the deep dive section with an excerpt and Telegraph link.

    Replaces the full body with the first few paragraphs plus a
    "Read full analysis" link to the Telegraph page.
    """
    stars_str = escape_markdown(f"{summary.stars:,}")
    name = escape_markdown(summary.repo_name)
    github_link = format_link("View on GitHub", summary.repo_url)
    excerpt = escape_markdown(extract_excerpt(summary.summary_content))
    read_full = f"[Read full analysis →]({escape_url(telegraph_url)})"

    return (
        f"*{name}* ⭐ {stars_str}\n"
        f"{github_link}\n"
        f"\n"
        f"{excerpt}\n"
        f"\n"
        f"{read_full}"
    )


def format_quick_hit(summary: SummaryWithRepo, index: int) -> str:
    """Format a single quick hit entry with its index number."""
    stars_str = escape_markdown(f"{summary.stars:,}")
    name = escape_markdown(summary.repo_name)
    content = escape_markdown(summary.summary_content)
    link = format_link("GitHub", summary.repo_url)

    return (
        f"{index}\\. *{name}* ⭐ {stars_str}\n"
        f"   {content}\n"
        f"   {link}"
    )


def format_digest(digest: Digest, telegraph_url: str | None = None) -> str:
    """Format a complete digest into a MarkdownV2 Telegram message.

    Layout:
      Header (date + ranking criteria)
      Separator
      Deep Dive section
      Separator
      Quick Hits section (if any)

    If telegraph_url is provided, the deep dive uses an excerpt with
    a link to the full analysis on Telegraph instead of the full body.
    """
    emoji = _CRITERIA_EMOJI.get(digest.ranking_criteria, "📊")
    criteria_label = escape_markdown(digest.ranking_criteria.capitalize())
    date_str = escape_markdown(digest.date.strftime("%B %d, %Y").replace(" 0", " "))

    sep = escape_markdown(_SECTION_SEPARATOR)

    header = f"📅 *Daily Digest* — {date_str}\nRanked by: {emoji} {criteria_label}"

    if telegraph_url:
        deep = _format_deep_dive_with_excerpt(digest.deep_dive, telegraph_url)
    else:
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


def truncate_for_telegram(
    message: str, repo_url: str, max_length: int = 4096,
    telegraph_url: str | None = None,
) -> str:
    """Truncate a formatted message to fit Telegram's character limit.

    If message is within max_length, returns it unchanged. Otherwise,
    finds the deep dive content and truncates it at a sentence boundary
    (or word boundary if no sentence break), appending a "Read more" link.

    The truncation target is the deep dive body — the text after the
    "View on GitHub" link line inside the DEEP DIVE section. Header,
    metadata, and quick hits are preserved intact.

    If telegraph_url is provided, the "Read more" link points to the
    Telegraph article instead of the GitHub repo.
    """
    if len(message) <= max_length:
        return message

    read_more_target = telegraph_url or repo_url
    read_more = f"\n\n[Read more]({escape_url(read_more_target)})"
    read_more_len = len(read_more)

    # Find the deep dive content boundary: the blank line after the
    # "View on GitHub" link, which starts the summary body.
    link_marker = "View on GitHub]("
    link_pos = message.find(link_marker)
    if link_pos == -1:
        # No recognizable structure — hard truncate
        cut = max_length - read_more_len - 1
        return message[:cut] + "…" + read_more

    # Find the blank line after the link line (content starts after it)
    newline_after_link = message.find("\n", link_pos)
    if newline_after_link == -1:
        return message
    content_start = newline_after_link + 1
    # Skip the blank line separator
    if message[content_start:content_start + 1] == "\n":
        content_start += 1

    # Everything after the deep dive content (quick hits section, if any)
    quick_hits_marker = escape_markdown(_SECTION_SEPARATOR) + "\n⚡"
    tail_start = message.find(quick_hits_marker, content_start)

    if tail_start != -1:
        # Preserve the gap before quick hits
        tail = "\n\n" + message[tail_start:]
        prefix = message[:content_start]
        body = message[content_start:tail_start].rstrip("\n")
    else:
        tail = ""
        prefix = message[:content_start]
        body = message[content_start:].rstrip("\n")

    budget = max_length - len(prefix) - len("…") - read_more_len - len(tail)

    if budget <= 0:
        # Extreme case: even without body we're over limit
        cut = max_length - read_more_len - 1
        return message[:cut] + "…" + read_more

    truncated_body = _truncate_at_boundary(body, budget)

    return prefix + truncated_body + "…" + read_more + tail


def _truncate_at_boundary(text: str, max_chars: int) -> str:
    """Truncate text at the last sentence or word boundary within budget.

    Prefers sentence boundaries ('. ' followed by a space or newline).
    Falls back to word boundaries (space). Last resort: hard cut.
    """
    if len(text) <= max_chars:
        return text

    region = text[:max_chars]

    # Try sentence boundary: last '. ' within budget
    # In escaped markdown, a period is '\\.' so look for '\\. '
    sentence_end = region.rfind("\\. ")
    if sentence_end != -1:
        return region[:sentence_end + 2].rstrip()

    # Try word boundary
    space_pos = region.rfind(" ")
    if space_pos > 0:
        return region[:space_pos].rstrip()

    # Hard cut
    return region
