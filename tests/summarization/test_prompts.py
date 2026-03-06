"""Tests for prompt template construction."""

import pytest

from storage.types import RepoRecord
from summarization.prompts import (
    MAX_README_CHARS,
    _TRUNCATION_MARKER,
    build_deep_dive_prompt,
    build_quick_hit_prompt,
)

from datetime import datetime


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_repo(
    name="owner/test-repo",
    url="https://github.com/owner/test-repo",
    description="A test repository for unit testing",
    raw_content="# Test Repo\n\nThis is a test repository with enough content to pass validation.",
    stars=500,
    forks=50,
    language="Python",
    created_at="2024-06-01T00:00:00Z",
    topics=None,
) -> RepoRecord:
    """Create a RepoRecord for testing."""
    return RepoRecord(
        id=1,
        source="github",
        source_id="12345",
        name=name,
        url=url,
        description=description,
        raw_content=raw_content,
        source_metadata={
            "stars": stars,
            "forks": forks,
            "primary_language": language,
            "created_at": created_at,
            "topics": topics or ["ai-coding", "tool"],
        },
        discovered_at=datetime(2026, 3, 1),
    )


# ---------------------------------------------------------------------------
# Deep dive prompt
# ---------------------------------------------------------------------------


class TestBuildDeepDivePrompt:
    def test_returns_tuple_of_two_strings(self):
        repo = _make_repo()
        result = build_deep_dive_prompt(repo)
        assert isinstance(result, tuple)
        assert len(result) == 2
        assert isinstance(result[0], str)
        assert isinstance(result[1], str)

    def test_includes_repo_name(self):
        repo = _make_repo(name="anthropics/claude-code")
        _, user = build_deep_dive_prompt(repo)
        assert "anthropics/claude-code" in user

    def test_includes_description(self):
        repo = _make_repo(description="An agentic coding assistant")
        _, user = build_deep_dive_prompt(repo)
        assert "An agentic coding assistant" in user

    def test_includes_readme_content(self):
        repo = _make_repo(raw_content="# My Tool\n\nThis tool does amazing things with code.")
        _, user = build_deep_dive_prompt(repo)
        assert "This tool does amazing things with code." in user

    def test_includes_stars(self):
        repo = _make_repo(stars=12345)
        _, user = build_deep_dive_prompt(repo)
        assert "12345" in user

    def test_includes_language(self):
        repo = _make_repo(language="TypeScript")
        _, user = build_deep_dive_prompt(repo)
        assert "TypeScript" in user

    def test_system_prompt_mentions_deep_dive_requirements(self):
        repo = _make_repo()
        system, _ = build_deep_dive_prompt(repo)
        assert "Problem Solved" in system
        assert "Approach" in system
        assert "Comparison" in system or "Alternatives" in system
        assert "Target Audience" in system
        assert "500-1000 words" in system

    def test_no_context_omits_recently_covered_section(self):
        repo = _make_repo()
        _, user = build_deep_dive_prompt(repo, recent_context=None)
        assert "Recently Covered" not in user

    def test_empty_context_omits_recently_covered_section(self):
        repo = _make_repo()
        _, user = build_deep_dive_prompt(repo, recent_context=[])
        assert "Recently Covered" not in user

    def test_recent_context_adds_section(self):
        repo = _make_repo()
        context = [
            {
                "repo_name": "cursor-ai/cursor",
                "summary_content": "Cursor is an AI-powered code editor.",
                "date": "2026-03-04",
            },
            {
                "repo_name": "openai/codex",
                "summary_content": "Codex is a code generation model.",
                "date": "2026-03-03",
            },
        ]
        _, user = build_deep_dive_prompt(repo, recent_context=context)
        assert "Recently Covered" in user
        assert "cursor-ai/cursor" in user
        assert "Cursor is an AI-powered code editor." in user
        assert "openai/codex" in user
        assert "2026-03-04" in user

    def test_context_changes_system_prompt(self):
        repo = _make_repo()
        system_no_ctx, _ = build_deep_dive_prompt(repo)
        system_with_ctx, _ = build_deep_dive_prompt(repo, recent_context=[
            {"repo_name": "test/repo", "summary_content": "A test.", "date": "2026-03-01"},
        ])
        assert "recently covered" in system_with_ctx.lower()
        assert system_no_ctx != system_with_ctx

    def test_description_none_handled(self):
        repo = _make_repo(description=None)
        _, user = build_deep_dive_prompt(repo)
        assert "Description:" not in user
        assert repo.name in user

    def test_includes_topics(self):
        repo = _make_repo(topics=["machine-learning", "llm"])
        _, user = build_deep_dive_prompt(repo)
        assert "machine-learning" in user
        assert "llm" in user


# ---------------------------------------------------------------------------
# Quick hit prompt
# ---------------------------------------------------------------------------


class TestBuildQuickHitPrompt:
    def test_returns_tuple_of_two_strings(self):
        repo = _make_repo()
        result = build_quick_hit_prompt(repo)
        assert isinstance(result, tuple)
        assert len(result) == 2
        assert isinstance(result[0], str)
        assert isinstance(result[1], str)

    def test_includes_repo_name(self):
        repo = _make_repo(name="facebook/react")
        _, user = build_quick_hit_prompt(repo)
        assert "facebook/react" in user

    def test_includes_description(self):
        repo = _make_repo(description="A JavaScript library for building UIs")
        _, user = build_quick_hit_prompt(repo)
        assert "A JavaScript library for building UIs" in user

    def test_includes_readme_content(self):
        repo = _make_repo(raw_content="# React\n\nDeclarative component-based UI library.")
        _, user = build_quick_hit_prompt(repo)
        assert "Declarative component-based UI library." in user

    def test_system_prompt_mentions_brevity(self):
        repo = _make_repo()
        system, _ = build_quick_hit_prompt(repo)
        assert "2-3 sentences" in system

    def test_system_prompt_mentions_distinguishing_feature(self):
        repo = _make_repo()
        system, _ = build_quick_hit_prompt(repo)
        assert "distinguishing" in system.lower()


# ---------------------------------------------------------------------------
# README truncation
# ---------------------------------------------------------------------------


class TestReadmeTruncation:
    def test_short_content_not_truncated(self):
        repo = _make_repo(raw_content="Short README content")
        _, user = build_deep_dive_prompt(repo)
        assert "Short README content" in user
        assert "[README truncated]" not in user

    def test_exact_limit_not_truncated(self):
        content = "x" * MAX_README_CHARS
        repo = _make_repo(raw_content=content)
        _, user = build_deep_dive_prompt(repo)
        assert "[README truncated]" not in user

    def test_over_limit_truncated_with_marker(self):
        content = "x" * (MAX_README_CHARS + 1000)
        repo = _make_repo(raw_content=content)
        _, user = build_deep_dive_prompt(repo)
        assert "[README truncated]" in user

    def test_truncated_content_length(self):
        content = "a" * (MAX_README_CHARS + 5000)
        repo = _make_repo(raw_content=content)
        _, user = build_deep_dive_prompt(repo)
        # The truncated README in the user prompt should contain
        # MAX_README_CHARS of original content + the marker
        assert content[:MAX_README_CHARS] in user
        assert content[:MAX_README_CHARS + 1] not in user

    def test_truncation_applies_to_quick_hit_too(self):
        content = "y" * (MAX_README_CHARS + 1000)
        repo = _make_repo(raw_content=content)
        _, user = build_quick_hit_prompt(repo)
        assert "[README truncated]" in user
