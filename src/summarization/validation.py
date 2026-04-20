"""
Content validation for summarization.

Validates that repo content is sufficient for summarization.
"""

from storage.types import RepoRecord
from summarization.types import InsufficientContentError

MIN_CONTENT_LENGTH = 100


def validate_repo_content(repo: RepoRecord) -> None:
    """Validate that a repo has sufficient content for summarization.

    Raises:
        InsufficientContentError: If raw_content is empty or below
            MIN_CONTENT_LENGTH characters.
    """
    content_length = len(repo.raw_content) if repo.raw_content else 0

    if content_length == 0:
        raise InsufficientContentError(
            "Repo has no README content",
            content_length=0,
        )

    if content_length < MIN_CONTENT_LENGTH:
        raise InsufficientContentError(
            f"Repo README too short ({content_length} chars, "
            f"minimum {MIN_CONTENT_LENGTH})",
            content_length=content_length,
        )
