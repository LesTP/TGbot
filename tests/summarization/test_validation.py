"""Tests for content validation."""

import pytest

from datetime import datetime
from storage.types import RepoRecord
from summarization.validation import (
    MIN_CONTENT_LENGTH,
    validate_repo_content,
)
from summarization.types import InsufficientContentError


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_repo(raw_content="# Test Repo\n\nThis is a test repository with sufficient content for validation. " * 3) -> RepoRecord:
    return RepoRecord(
        id=1,
        source="github",
        source_id="12345",
        name="owner/test-repo",
        url="https://github.com/owner/test-repo",
        description="A test repo",
        raw_content=raw_content,
        source_metadata={"stars": 100},
        discovered_at=datetime(2026, 3, 1),
    )


# ---------------------------------------------------------------------------
# validate_repo_content
# ---------------------------------------------------------------------------


class TestValidateRepoContent:
    def test_adequate_content_passes(self):
        repo = _make_repo(raw_content="x" * MIN_CONTENT_LENGTH)
        validate_repo_content(repo)  # should not raise

    def test_long_content_passes(self):
        repo = _make_repo(raw_content="x" * 50000)
        validate_repo_content(repo)  # should not raise

    def test_empty_content_raises(self):
        repo = _make_repo(raw_content="")
        with pytest.raises(InsufficientContentError) as exc_info:
            validate_repo_content(repo)
        assert exc_info.value.content_length == 0

    def test_none_like_empty_string_raises(self):
        repo = _make_repo(raw_content="")
        with pytest.raises(InsufficientContentError):
            validate_repo_content(repo)

    def test_short_content_raises(self):
        repo = _make_repo(raw_content="Short")
        with pytest.raises(InsufficientContentError) as exc_info:
            validate_repo_content(repo)
        assert exc_info.value.content_length == 5

    def test_one_below_minimum_raises(self):
        repo = _make_repo(raw_content="x" * (MIN_CONTENT_LENGTH - 1))
        with pytest.raises(InsufficientContentError) as exc_info:
            validate_repo_content(repo)
        assert exc_info.value.content_length == MIN_CONTENT_LENGTH - 1

    def test_exactly_minimum_passes(self):
        repo = _make_repo(raw_content="x" * MIN_CONTENT_LENGTH)
        validate_repo_content(repo)  # should not raise

    def test_error_message_includes_length(self):
        repo = _make_repo(raw_content="x" * 42)
        with pytest.raises(InsufficientContentError, match="42"):
            validate_repo_content(repo)
