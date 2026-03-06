"""
Orchestrator module types.

Data types for the Orchestrator module's public API: pipeline
configuration and result shapes. See ARCH_orchestrator.md for contracts.
"""

from dataclasses import dataclass, field
from typing import Any, Optional

from discovery.types import CategoryConfig, RankingCriteria


@dataclass
class PipelineConfig:
    """Configuration for a daily pipeline run.

    category and channel_id are required. All other fields have defaults.
    ranking_criteria=None triggers automatic day-of-week rotation.
    """

    category: CategoryConfig
    channel_id: str
    ranking_criteria: Optional[RankingCriteria] = None
    deep_dive_count: int = 1
    quick_hit_count: int = 3
    discovery_limit: int = 20
    cooldown_days: int = 90
    context_lookback_days: int = 14


@dataclass
class PipelineResult:
    """Result of a daily pipeline run.

    success=False when the pipeline cannot complete. All errors
    are captured in the errors list — the pipeline never raises.
    """

    success: bool
    repos_discovered: int
    repos_after_dedup: int
    summaries_generated: int
    delivery_result: Any = None  # DeliveryResult, defined in ARCH_delivery
    errors: list[str] = field(default_factory=list)
