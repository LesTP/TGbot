"""Shared test fixtures for Delivery module tests."""

from delivery.types import SummaryWithRepo


def make_summary(
    name="test-repo",
    url="https://github.com/org/test-repo",
    stars=1234,
    content="A great tool for testing.",
    created_at="2024-06-15",
):
    """Create a SummaryWithRepo for testing."""
    return SummaryWithRepo(
        summary_content=content,
        repo_name=name,
        repo_url=url,
        stars=stars,
        created_at=created_at,
    )
