"""Smoke test — all public names importable from orchestrator."""

from orchestrator import (
    PipelineConfig,
    PipelineResult,
    get_todays_ranking,
    run_daily_pipeline,
)


def test_all_exports_importable():
    assert callable(run_daily_pipeline)
    assert callable(get_todays_ranking)
    assert PipelineConfig is not None
    assert PipelineResult is not None
