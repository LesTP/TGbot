"""
Prompt templates for LLM summarization.

Builds system and user prompts for deep-dive and quick-hit summaries.
Handles README truncation and optional recent-context injection.
"""

from typing import Optional

from storage.types import RepoRecord

MAX_README_CHARS = 15000
_TRUNCATION_MARKER = "\n\n[README truncated]"


def _truncate_readme(raw_content: str, max_chars: int = MAX_README_CHARS) -> str:
    """Truncate README content if it exceeds max_chars."""
    if len(raw_content) <= max_chars:
        return raw_content
    return raw_content[:max_chars] + _TRUNCATION_MARKER


def _format_repo_metadata(repo: RepoRecord) -> str:
    """Format repo metadata into a readable block for the prompt."""
    meta = repo.source_metadata or {}
    lines = [
        f"Repository: {repo.name}",
        f"URL: {repo.url}",
    ]
    if repo.description:
        lines.append(f"Description: {repo.description}")
    if meta.get("stars") is not None:
        lines.append(f"Stars: {meta['stars']}")
    if meta.get("forks") is not None:
        lines.append(f"Forks: {meta['forks']}")
    if meta.get("primary_language"):
        lines.append(f"Language: {meta['primary_language']}")
    if meta.get("created_at"):
        lines.append(f"Created: {meta['created_at']}")
    if meta.get("topics"):
        lines.append(f"Topics: {', '.join(meta['topics'])}")
    return "\n".join(lines)


def _format_recent_context(recent_context: list[dict]) -> str:
    """Format recent summaries into a context section for the prompt."""
    lines = ["## Recently Covered Repos", ""]
    for entry in recent_context:
        lines.append(f"### {entry.get('repo_name', 'Unknown')}")
        if entry.get("date"):
            lines.append(f"Date: {entry['date']}")
        lines.append(entry.get("summary_content", ""))
        lines.append("")
    return "\n".join(lines)


_DEEP_DIVE_SYSTEM = """\
You are a technical analyst writing for developers who actively work with \
coding tools and want to stay current with emerging alternatives. Your \
audience is experienced — skip basic explanations and focus on what makes \
this tool distinctive.

Write a deep-dive analysis of the given GitHub repository. Your analysis \
must cover:
1. **Problem Solved** — What specific problem does this tool address?
2. **Approach & Architecture** — How does it work? What's the technical approach?
3. **Comparison to Alternatives** — How does it differ from similar tools?
4. **Target Audience** — Who should consider using this, and when?

Guidelines:
- Length: 500-1000 words
- Be specific and technical, not vague or promotional
- If the README lacks detail on a topic, say so rather than speculating
- Use the repo metadata (stars, language, creation date) for context, not as quality signals\
"""

_DEEP_DIVE_SYSTEM_WITH_CONTEXT = """\
You are a technical analyst writing for developers who actively work with \
coding tools and want to stay current with emerging alternatives. Your \
audience is experienced — skip basic explanations and focus on what makes \
this tool distinctive.

Write a deep-dive analysis of the given GitHub repository. Your analysis \
must cover:
1. **Problem Solved** — What specific problem does this tool address?
2. **Approach & Architecture** — How does it work? What's the technical approach?
3. **Comparison to Alternatives** — How does it differ from similar tools?
4. **Target Audience** — Who should consider using this, and when?

You are also provided with summaries of recently covered repositories. \
Reference them where a direct comparison adds value for the reader, but \
do not force comparisons. The focus is on the current repository.

Guidelines:
- Length: 500-1000 words
- Be specific and technical, not vague or promotional
- If the README lacks detail on a topic, say so rather than speculating
- Use the repo metadata (stars, language, creation date) for context, not as quality signals\
"""

_QUICK_HIT_SYSTEM = """\
You are a technical writer creating brief summaries of GitHub repositories \
for a developer audience. Be concise and specific.

Write a quick-hit summary: 2-3 sentences that capture what this tool does \
and its key distinguishing feature. The reader should understand in under \
10 seconds whether this repo is worth exploring.\
"""


def build_deep_dive_prompt(
    repo: RepoRecord,
    recent_context: Optional[list[dict]] = None,
) -> tuple[str, str]:
    """Build system and user prompts for a deep-dive summary.

    Args:
        repo: The repository to summarize.
        recent_context: Optional list of recent summary dicts with keys
            "repo_name", "summary_content", "date". When provided, adds
            a context section and adjusts the system prompt.

    Returns:
        (system_prompt, user_prompt) tuple.
    """
    readme = _truncate_readme(repo.raw_content)
    metadata = _format_repo_metadata(repo)

    user_parts = [metadata, "", "## README", "", readme]

    if recent_context:
        system = _DEEP_DIVE_SYSTEM_WITH_CONTEXT
        user_parts.extend(["", _format_recent_context(recent_context)])
    else:
        system = _DEEP_DIVE_SYSTEM

    return system, "\n".join(user_parts)


def build_quick_hit_prompt(repo: RepoRecord) -> tuple[str, str]:
    """Build system and user prompts for a quick-hit summary.

    Args:
        repo: The repository to summarize.

    Returns:
        (system_prompt, user_prompt) tuple.
    """
    readme = _truncate_readme(repo.raw_content)
    metadata = _format_repo_metadata(repo)

    user_prompt = "\n".join([metadata, "", "## README", "", readme])

    return _QUICK_HIT_SYSTEM, user_prompt
