"""Tests for quality filtering."""

import pytest

from discovery.filters import apply_quality_filters
from discovery.types import CategoryConfig


def _make_repo(
    stars: int = 100,
    fork: bool = False,
    archived: bool = False,
    language: str | None = "Python",
    readme_content: str | None = "x" * 500,
) -> dict:
    """Create a minimal repo dict for filter testing."""
    return {
        "id": 1,
        "full_name": "owner/repo",
        "stargazers_count": stars,
        "fork": fork,
        "archived": archived,
        "language": language,
        "readme_content": readme_content,
    }


def _default_config(**overrides) -> CategoryConfig:
    """Create a CategoryConfig with sensible defaults, allowing overrides."""
    kwargs = dict(
        name="test",
        description="test",
        min_stars=50,
        min_readme_length=200,
        require_readme=True,
        exclude_forks=True,
        exclude_archived=True,
        languages=None,
    )
    kwargs.update(overrides)
    return CategoryConfig(**kwargs)


class TestStarFilter:
    def test_at_threshold_passes(self):
        repo = _make_repo(stars=50)
        result = apply_quality_filters([repo], _default_config(min_stars=50))
        assert len(result) == 1

    def test_below_threshold_fails(self):
        repo = _make_repo(stars=49)
        result = apply_quality_filters([repo], _default_config(min_stars=50))
        assert len(result) == 0

    def test_above_threshold_passes(self):
        repo = _make_repo(stars=500)
        result = apply_quality_filters([repo], _default_config(min_stars=50))
        assert len(result) == 1

    def test_expansion_uses_higher_threshold(self):
        repo = _make_repo(stars=80)
        config = _default_config(min_stars=50)
        # Normal: 80 >= 50 → passes
        assert len(apply_quality_filters([repo], config, is_expansion=False)) == 1
        # Expansion: 80 < 100 (50+50) → fails
        assert len(apply_quality_filters([repo], config, is_expansion=True)) == 0

    def test_expansion_at_threshold_passes(self):
        repo = _make_repo(stars=100)
        config = _default_config(min_stars=50)
        assert len(apply_quality_filters([repo], config, is_expansion=True)) == 1


class TestForkFilter:
    def test_fork_excluded_when_enabled(self):
        repo = _make_repo(fork=True)
        result = apply_quality_filters([repo], _default_config(exclude_forks=True))
        assert len(result) == 0

    def test_fork_included_when_disabled(self):
        repo = _make_repo(fork=True)
        result = apply_quality_filters([repo], _default_config(exclude_forks=False))
        assert len(result) == 1

    def test_non_fork_passes(self):
        repo = _make_repo(fork=False)
        result = apply_quality_filters([repo], _default_config(exclude_forks=True))
        assert len(result) == 1


class TestArchivedFilter:
    def test_archived_excluded_when_enabled(self):
        repo = _make_repo(archived=True)
        result = apply_quality_filters([repo], _default_config(exclude_archived=True))
        assert len(result) == 0

    def test_archived_included_when_disabled(self):
        repo = _make_repo(archived=True)
        result = apply_quality_filters([repo], _default_config(exclude_archived=False))
        assert len(result) == 1

    def test_non_archived_passes(self):
        repo = _make_repo(archived=False)
        result = apply_quality_filters([repo], _default_config(exclude_archived=True))
        assert len(result) == 1


class TestReadmeFilter:
    def test_at_min_length_passes(self):
        repo = _make_repo(readme_content="x" * 200)
        result = apply_quality_filters([repo], _default_config(min_readme_length=200))
        assert len(result) == 1

    def test_below_min_length_fails(self):
        repo = _make_repo(readme_content="x" * 199)
        result = apply_quality_filters([repo], _default_config(min_readme_length=200))
        assert len(result) == 0

    def test_none_readme_fails(self):
        repo = _make_repo(readme_content=None)
        result = apply_quality_filters([repo], _default_config(require_readme=True))
        assert len(result) == 0

    def test_none_readme_passes_when_not_required(self):
        repo = _make_repo(readme_content=None)
        result = apply_quality_filters([repo], _default_config(require_readme=False))
        assert len(result) == 1


class TestLanguageFilter:
    def test_matching_language_passes(self):
        repo = _make_repo(language="Python")
        result = apply_quality_filters([repo], _default_config(languages=["Python", "TypeScript"]))
        assert len(result) == 1

    def test_non_matching_language_fails(self):
        repo = _make_repo(language="Java")
        result = apply_quality_filters([repo], _default_config(languages=["Python", "TypeScript"]))
        assert len(result) == 0

    def test_none_languages_passes_all(self):
        repo = _make_repo(language="Rust")
        result = apply_quality_filters([repo], _default_config(languages=None))
        assert len(result) == 1

    def test_none_repo_language_fails(self):
        repo = _make_repo(language=None)
        result = apply_quality_filters([repo], _default_config(languages=["Python"]))
        assert len(result) == 0

    def test_case_insensitive(self):
        repo = _make_repo(language="python")
        result = apply_quality_filters([repo], _default_config(languages=["Python"]))
        assert len(result) == 1


class TestEdgeCases:
    def test_empty_input(self):
        result = apply_quality_filters([], _default_config())
        assert result == []

    def test_all_filtered_out(self):
        repos = [_make_repo(stars=1), _make_repo(stars=2), _make_repo(stars=3)]
        result = apply_quality_filters(repos, _default_config(min_stars=50))
        assert result == []

    def test_multiple_repos_mixed(self):
        repos = [
            _make_repo(stars=100),  # passes
            _make_repo(stars=10),   # fails stars
            _make_repo(stars=200, fork=True),  # fails fork
            _make_repo(stars=150),  # passes
        ]
        result = apply_quality_filters(repos, _default_config())
        assert len(result) == 2
