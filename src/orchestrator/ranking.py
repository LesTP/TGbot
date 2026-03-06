"""
Day-of-week ranking rotation.

Maps each day to a RankingCriteria so the pipeline surfaces
diverse repos across the week. See ARCH_orchestrator.md.
"""

from datetime import date

from discovery.types import RankingCriteria

_DAY_TO_RANKING: dict[int, RankingCriteria] = {
    0: RankingCriteria.STARS,        # Monday
    1: RankingCriteria.ACTIVITY,     # Tuesday
    2: RankingCriteria.FORKS,        # Wednesday
    3: RankingCriteria.RECENCY,      # Thursday
    4: RankingCriteria.SUBSCRIBERS,  # Friday
    5: RankingCriteria.STARS,        # Saturday (fallback)
    6: RankingCriteria.STARS,        # Sunday (fallback)
}


def get_todays_ranking(today: date) -> RankingCriteria:
    """Return the ranking criteria for a given date based on day-of-week rotation."""
    return _DAY_TO_RANKING[today.weekday()]
