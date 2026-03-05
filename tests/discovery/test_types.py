"""Tests for Discovery module types."""

import pytest

from discovery.types import (
    CategoryConfig,
    DiscoveredRepo,
    GitHubAPIError,
    NoResultsError,
    RankingCriteria,
    SeedRepo,
)


class TestSeedRepo:
    def test_construction(self):
        seed = SeedRepo(
            full_name="owner/repo",
            name="Repo",
            reason="Major tool, poor tagging",
        )
        assert seed.full_name == "owner/repo"
        assert seed.name == "Repo"
        assert seed.reason == "Major tool, poor tagging"


class TestCategoryConfig:
    def test_minimal_construction(self):
        config = CategoryConfig(name="test", description="A test category")
        assert config.name == "test"
        assert config.description == "A test category"

    def test_defaults(self):
        config = CategoryConfig(name="test", description="test")
        assert config.topics == []
        assert config.keywords == []
        assert config.expansion_topics == []
        assert config.seed_repos == []
        assert config.min_stars == 50
        assert config.min_readme_length == 200
        assert config.require_readme is True
        assert config.exclude_forks is True
        assert config.exclude_archived is True
        assert config.languages is None

    def test_full_construction(self):
        seed = SeedRepo("owner/repo", "Repo", "reason")
        config = CategoryConfig(
            name="agentic-coding",
            description="AI coding tools",
            topics=["ai-coding", "coding-assistant"],
            keywords=["agentic coding"],
            expansion_topics=["codegen"],
            seed_repos=[seed],
            min_stars=100,
            min_readme_length=500,
            require_readme=True,
            exclude_forks=False,
            exclude_archived=True,
            languages=["Python", "TypeScript"],
        )
        assert config.name == "agentic-coding"
        assert len(config.topics) == 2
        assert len(config.keywords) == 1
        assert len(config.expansion_topics) == 1
        assert len(config.seed_repos) == 1
        assert config.seed_repos[0].full_name == "owner/repo"
        assert config.min_stars == 100
        assert config.min_readme_length == 500
        assert config.exclude_forks is False
        assert config.languages == ["Python", "TypeScript"]

    def test_list_fields_are_independent(self):
        """Verify default list fields aren't shared across instances."""
        config_a = CategoryConfig(name="a", description="a")
        config_b = CategoryConfig(name="b", description="b")
        config_a.topics.append("topic-a")
        assert config_b.topics == []


class TestRankingCriteria:
    def test_has_five_members(self):
        assert len(RankingCriteria) == 5

    def test_members(self):
        assert RankingCriteria.STARS.value == "stars"
        assert RankingCriteria.FORKS.value == "forks"
        assert RankingCriteria.SUBSCRIBERS.value == "subscribers"
        assert RankingCriteria.RECENCY.value == "recency"
        assert RankingCriteria.ACTIVITY.value == "activity"

    def test_from_value(self):
        assert RankingCriteria("stars") is RankingCriteria.STARS

    def test_invalid_value(self):
        with pytest.raises(ValueError):
            RankingCriteria("invalid")


class TestDiscoveredRepo:
    def test_construction(self):
        repo = DiscoveredRepo(
            source="github",
            source_id="12345",
            name="owner/repo",
            url="https://github.com/owner/repo",
            description="A test repo",
            raw_content="# README\nThis is a test.",
            source_metadata={
                "stars": 100,
                "forks": 20,
                "subscribers": 10,
                "primary_language": "Python",
                "created_at": "2024-01-01T00:00:00Z",
                "updated_at": "2025-06-01T00:00:00Z",
                "topics": ["ai-coding"],
            },
        )
        assert repo.source == "github"
        assert repo.source_id == "12345"
        assert repo.name == "owner/repo"
        assert repo.url == "https://github.com/owner/repo"
        assert repo.description == "A test repo"
        assert repo.raw_content.startswith("# README")
        assert repo.source_metadata["stars"] == 100
        assert repo.source_metadata["topics"] == ["ai-coding"]

    def test_description_none(self):
        repo = DiscoveredRepo(
            source="github",
            source_id="1",
            name="owner/repo",
            url="https://github.com/owner/repo",
            description=None,
            raw_content="readme",
            source_metadata={},
        )
        assert repo.description is None


class TestGitHubAPIError:
    def test_with_all_fields(self):
        err = GitHubAPIError("Rate limited", status_code=403, response_body='{"message":"rate limit"}')
        assert str(err) == "Rate limited"
        assert err.status_code == 403
        assert err.response_body == '{"message":"rate limit"}'

    def test_defaults(self):
        err = GitHubAPIError("Network error")
        assert str(err) == "Network error"
        assert err.status_code is None
        assert err.response_body is None

    def test_is_exception(self):
        assert issubclass(GitHubAPIError, Exception)


class TestNoResultsError:
    def test_with_query_details(self):
        details = {"query": "topic:ai-coding", "min_stars": 50}
        err = NoResultsError("No repos found", query_details=details)
        assert str(err) == "No repos found"
        assert err.query_details == details

    def test_defaults(self):
        err = NoResultsError("Empty")
        assert err.query_details == {}

    def test_is_exception(self):
        assert issubclass(NoResultsError, Exception)
