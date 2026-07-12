"""Insight generators built on top of a parsed :class:`~helth.export.HealthExport`."""

from .activity import ActivityProfile, activity_profile, daily_steps
from .fitness import Vo2MaxEstimate, estimate_vo2max
from .patterns import (
    Highlight,
    by_weekday,
    daily_trend,
    heart_rate_by_hour,
    heart_rate_histogram,
    highlights,
    hourly_average,
    hourly_sum,
    sleep_by_night,
    workout_breakdown,
    workout_metric_series,
)
from .percentiles import (
    PercentileResult,
    PopulationRanking,
    activity_percentiles,
    fitness_percentiles,
    population_ranking,
)
from .vitals import VitalsSummary, vitals_summary

__all__ = [
    "ActivityProfile",
    "activity_profile",
    "daily_steps",
    "VitalsSummary",
    "vitals_summary",
    "Vo2MaxEstimate",
    "estimate_vo2max",
    "PercentileResult",
    "PopulationRanking",
    "activity_percentiles",
    "fitness_percentiles",
    "population_ranking",
    "Highlight",
    "highlights",
    "heart_rate_by_hour",
    "heart_rate_histogram",
    "hourly_average",
    "hourly_sum",
    "by_weekday",
    "daily_trend",
    "sleep_by_night",
    "workout_breakdown",
    "workout_metric_series",
]
