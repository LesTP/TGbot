"""Tests for get_todays_ranking — day-of-week rotation."""

from datetime import date

import pytest

from discovery.types import RankingCriteria
from orchestrator.ranking import get_todays_ranking


@pytest.mark.parametrize(
    "day, expected",
    [
        (date(2026, 3, 2), RankingCriteria.STARS),        # Monday
        (date(2026, 3, 3), RankingCriteria.ACTIVITY),     # Tuesday
        (date(2026, 3, 4), RankingCriteria.FORKS),        # Wednesday
        (date(2026, 3, 5), RankingCriteria.RECENCY),      # Thursday
        (date(2026, 3, 6), RankingCriteria.SUBSCRIBERS),  # Friday
        (date(2026, 3, 7), RankingCriteria.STARS),        # Saturday
        (date(2026, 3, 8), RankingCriteria.STARS),        # Sunday
    ],
    ids=["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"],
)
def test_day_of_week_rotation(day, expected):
    assert get_todays_ranking(day) == expected
