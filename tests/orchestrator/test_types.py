"""Tests for orchestrator types — PipelineConfig and PipelineResult."""

import pytest

from discovery.types import CategoryConfig, RankingCriteria
from orchestrator.types import PipelineConfig, PipelineResult


# ---------------------------------------------------------------------------
# PipelineConfig
# ---------------------------------------------------------------------------


class TestPipelineConfigDefaults:
    """PipelineConfig has sensible defaults for optional fields."""

    def setup_method(self):
        self.category = CategoryConfig(
            name="test", description="test category"
        )

    def test_defaults(self):
        config = PipelineConfig(category=self.category, channel_id="@test")
        assert config.deep_dive_count == 1
        assert config.quick_hit_count == 3
        assert config.discovery_limit == 20
        assert config.cooldown_days == 90

    def test_ranking_criteria_defaults_to_none(self):
        config = PipelineConfig(category=self.category, channel_id="@test")
        assert config.ranking_criteria is None

    def test_ranking_criteria_accepts_enum(self):
        config = PipelineConfig(
            category=self.category,
            channel_id="@test",
            ranking_criteria=RankingCriteria.FORKS,
        )
        assert config.ranking_criteria == RankingCriteria.FORKS

    def test_category_is_required(self):
        with pytest.raises(TypeError):
            PipelineConfig(channel_id="@test")  # type: ignore[call-arg]

    def test_channel_id_is_required(self):
        with pytest.raises(TypeError):
            PipelineConfig(category=self.category)  # type: ignore[call-arg]

    def test_overrides(self):
        config = PipelineConfig(
            category=self.category,
            channel_id="@test",
            deep_dive_count=2,
            quick_hit_count=5,
            discovery_limit=50,
            cooldown_days=30,
        )
        assert config.deep_dive_count == 2
        assert config.quick_hit_count == 5
        assert config.discovery_limit == 50
        assert config.cooldown_days == 30


# ---------------------------------------------------------------------------
# PipelineResult
# ---------------------------------------------------------------------------


class TestPipelineResult:
    """PipelineResult captures pipeline outcome."""

    def test_success_result(self):
        result = PipelineResult(
            success=True,
            repos_discovered=10,
            repos_after_dedup=8,
            summaries_generated=4,
        )
        assert result.success is True
        assert result.repos_discovered == 10
        assert result.repos_after_dedup == 8
        assert result.summaries_generated == 4
        assert result.delivery_result is None
        assert result.errors == []

    def test_failure_result_with_errors(self):
        result = PipelineResult(
            success=False,
            repos_discovered=0,
            repos_after_dedup=0,
            summaries_generated=0,
            errors=["GitHub API rate limited", "Fallback also failed"],
        )
        assert result.success is False
        assert len(result.errors) == 2
        assert "GitHub API rate limited" in result.errors

    def test_delivery_result_accepts_any(self):
        result = PipelineResult(
            success=True,
            repos_discovered=5,
            repos_after_dedup=4,
            summaries_generated=4,
            delivery_result={"message_id": 123, "ok": True},
        )
        assert result.delivery_result == {"message_id": 123, "ok": True}

    def test_errors_default_to_empty_list(self):
        result = PipelineResult(
            success=True,
            repos_discovered=0,
            repos_after_dedup=0,
            summaries_generated=0,
        )
        assert result.errors == []

    def test_errors_list_is_independent(self):
        """Each PipelineResult gets its own errors list (no shared mutable default)."""
        r1 = PipelineResult(success=True, repos_discovered=0, repos_after_dedup=0, summaries_generated=0)
        r2 = PipelineResult(success=True, repos_discovered=0, repos_after_dedup=0, summaries_generated=0)
        r1.errors.append("oops")
        assert r2.errors == []
