"""
Orchestrator module — coordinates the daily digest pipeline.

Public API: run_daily_pipeline, get_todays_ranking, PipelineConfig, PipelineResult.
See ARCH_orchestrator.md for contracts.
"""

from orchestrator.pipeline import run_daily_pipeline
from orchestrator.ranking import get_todays_ranking
from orchestrator.types import PipelineConfig, PipelineResult

__all__ = [
    "run_daily_pipeline",
    "get_todays_ranking",
    "PipelineConfig",
    "PipelineResult",
]
