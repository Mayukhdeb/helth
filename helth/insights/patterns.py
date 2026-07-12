"""Temporal pattern analysis — the "when" behind your health data.

These functions surface *patterns* rather than single numbers: what time of day
your heart rate peaks, which weekdays you move most, how your resting heart rate
trends over months, how you sleep. Each returns a tidy pandas object ready for
plotting (the dashboard consumes these).

All hour-of-day / weekday grouping uses the **local** time recorded in the
export (Apple stores a UTC offset per sample), so "6pm" means 6pm where you were.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, List, Optional

import pandas as pd

from ..constants import Category, Quantity

if TYPE_CHECKING:  # pragma: no cover
    from ..export import HealthExport

_WEEKDAYS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]


def records_frame(export: "HealthExport", type_: str) -> pd.DataFrame:
    """Numeric records of ``type_`` with local-time hour/weekday/date columns."""
    recs = [r for r in export.records_of_type(type_) if r.numeric_value is not None]
    if not recs:
        return pd.DataFrame(columns=["value", "start", "hour", "weekday", "date"])
    frame = pd.DataFrame(
        {
            "value": [r.numeric_value for r in recs],
            "start": [r.start_date for r in recs],
        }
    )
    starts = frame["start"]
    frame["hour"] = starts.map(lambda d: d.hour)
    frame["weekday"] = starts.map(lambda d: d.weekday())
    frame["date"] = starts.map(lambda d: d.date())
    return frame


# --- hour-of-day patterns ---------------------------------------------------
def hourly_average(export: "HealthExport", type_: str) -> pd.Series:
    """Mean value of ``type_`` by hour of day (index 0-23, gaps filled)."""
    frame = records_frame(export, type_)
    if frame.empty:
        return pd.Series(dtype="float64", name=type_)
    series = frame.groupby("hour")["value"].mean().reindex(range(24))
    series.name = type_
    return series


def hourly_sum(export: "HealthExport", type_: str) -> pd.Series:
    """Total value of ``type_`` per hour of day, averaged per active day."""
    frame = records_frame(export, type_)
    if frame.empty:
        return pd.Series(dtype="float64", name=type_)
    per_day_hour = frame.groupby(["date", "hour"])["value"].sum().reset_index()
    series = per_day_hour.groupby("hour")["value"].mean().reindex(range(24)).fillna(0.0)
    series.name = type_
    return series


def heart_rate_by_hour(export: "HealthExport") -> pd.DataFrame:
    """Per-hour heart-rate stats: mean, and the 10th/90th percentile band."""
    frame = records_frame(export, Quantity.HEART_RATE)
    if frame.empty:
        return pd.DataFrame(columns=["mean", "p10", "p90"])
    grouped = frame.groupby("hour")["value"]
    out = pd.DataFrame(
        {
            "mean": grouped.mean(),
            "p10": grouped.quantile(0.10),
            "p90": grouped.quantile(0.90),
        }
    ).reindex(range(24))
    return out


# --- weekday patterns -------------------------------------------------------
def by_weekday(export: "HealthExport", type_: str, *, how: str = "sum") -> pd.Series:
    """Average daily total (or mean) of ``type_`` for each weekday (Mon-Sun)."""
    frame = records_frame(export, type_)
    if frame.empty:
        return pd.Series(dtype="float64", index=_WEEKDAYS, name=type_)
    daily = frame.groupby(["date", "weekday"])["value"]
    daily = daily.sum() if how == "sum" else daily.mean()
    daily = daily.reset_index()
    series = daily.groupby("weekday")["value"].mean().reindex(range(7))
    series.index = _WEEKDAYS
    series.name = type_
    return series


# --- trends over time -------------------------------------------------------
def daily_trend(export: "HealthExport", type_: str, *, how: str = "mean") -> pd.Series:
    """A date-indexed daily series (mean or sum) for ``type_``."""
    frame = records_frame(export, type_)
    if frame.empty:
        return pd.Series(dtype="float64", name=type_)
    grouped = frame.groupby("date")["value"]
    series = grouped.sum() if how == "sum" else grouped.mean()
    series.index = pd.to_datetime(list(series.index))
    series.name = type_
    return series.sort_index()


def heart_rate_histogram(export: "HealthExport", bins: int = 40) -> pd.DataFrame:
    """Distribution of all heart-rate samples as (bin_center, count)."""
    frame = records_frame(export, Quantity.HEART_RATE)
    if frame.empty:
        return pd.DataFrame(columns=["bpm", "count"])
    binned = pd.cut(frame["value"], bins=bins)
    hist = frame.groupby(binned, observed=False).size()
    centers = [(iv.left + iv.right) / 2 for iv in hist.index]
    return pd.DataFrame({"bpm": centers, "count": hist.values})


# --- sleep ------------------------------------------------------------------
def sleep_by_night(export: "HealthExport") -> pd.Series:
    """Hours asleep per night, keyed by the morning's date."""
    recs = [
        r
        for r in export.records_of_type(Category.SLEEP_ANALYSIS)
        if (r.short_value or "").startswith("SleepAnalysisAsleep")
    ]
    if not recs:
        return pd.Series(dtype="float64", name="sleep_hours")
    rows = [
        {"night": r.end_date.date(), "hours": r.duration_seconds / 3600.0}
        for r in recs
    ]
    frame = pd.DataFrame(rows)
    series = frame.groupby("night")["hours"].sum()
    series.index = pd.to_datetime(list(series.index))
    series.name = "sleep_hours"
    return series.sort_index()


# --- workouts ---------------------------------------------------------------
_WORKOUT_METRICS = {
    "energy": ("energy_burned", "kcal"),
    "duration": ("duration", "min"),
    "distance": ("distance", "km"),
}


def workout_metric_series(
    export: "HealthExport",
    activity: Optional[str] = None,
    *,
    metric: str = "energy",
) -> pd.Series:
    """One point per workout: e.g. calories burned per strength session.

    Args:
        activity: Short activity name (e.g. ``"TraditionalStrengthTraining"``);
            ``None`` includes all workouts.
        metric: ``"energy"`` (kcal), ``"duration"`` (min) or ``"distance"`` (km).

    Returns a datetime-indexed series (workout start time -> value), sorted.
    """
    if metric not in _WORKOUT_METRICS:
        raise ValueError(f"metric must be one of {sorted(_WORKOUT_METRICS)}")
    attr, _unit = _WORKOUT_METRICS[metric]
    points = []
    for w in export.workouts:
        if activity is not None and w.short_type != activity:
            continue
        value = getattr(w, attr)
        if value is None:
            continue
        points.append((w.start_date, float(value)))
    if not points:
        return pd.Series(dtype="float64", name=metric)
    points.sort(key=lambda p: p[0])
    series = pd.Series(
        [v for _, v in points],
        index=pd.to_datetime([d for d, _ in points], utc=True),
        name=metric,
    )
    return series


def workout_breakdown(export: "HealthExport") -> pd.DataFrame:
    """Per-activity workout counts and total minutes."""
    if not export.workouts:
        return pd.DataFrame(columns=["activity", "count", "minutes"])
    rows = [
        {"activity": w.short_type, "minutes": (w.duration or 0.0)}
        for w in export.workouts
    ]
    frame = pd.DataFrame(rows)
    out = frame.groupby("activity").agg(
        count=("minutes", "size"), minutes=("minutes", "sum")
    )
    return out.sort_values("minutes", ascending=False).reset_index()


# --- headline callouts ------------------------------------------------------
@dataclass(frozen=True)
class Highlight:
    """A one-line 'did you know' pattern for the dashboard header."""

    title: str
    detail: str


def highlights(export: "HealthExport") -> List[Highlight]:
    """A handful of automatically-surfaced interesting patterns."""
    out: List[Highlight] = []

    hr = heart_rate_by_hour(export)
    if not hr.empty and hr["mean"].notna().any():
        peak = hr["mean"].idxmax()
        low = hr["mean"].idxmin()
        out.append(
            Highlight(
                "Heart rate peaks around " + _fmt_hour(peak),
                f"avg {hr['mean'].max():.0f} bpm then, vs a low of "
                f"{hr['mean'].min():.0f} bpm around {_fmt_hour(low)}.",
            )
        )

    steps_wd = by_weekday(export, Quantity.STEP_COUNT)
    if not steps_wd.dropna().empty:
        top = steps_wd.idxmax()
        out.append(
            Highlight(
                f"{top} is your most active day",
                f"~{steps_wd.max():,.0f} steps on an average {top}, "
                f"vs {steps_wd.min():,.0f} on {steps_wd.idxmin()}.",
            )
        )

    steps_hr = hourly_sum(export, Quantity.STEP_COUNT)
    if not steps_hr.dropna().empty and steps_hr.max() > 0:
        busy = int(steps_hr.idxmax())
        out.append(
            Highlight(
                "You move most around " + _fmt_hour(busy),
                f"~{steps_hr.max():,.0f} steps in that hour on a typical day.",
            )
        )

    sleep = sleep_by_night(export)
    if not sleep.empty:
        out.append(
            Highlight(
                f"You sleep about {sleep.median():.1f} h a night",
                f"across {len(sleep)} tracked nights "
                f"(range {sleep.min():.1f}–{sleep.max():.1f} h).",
            )
        )

    return out


def _fmt_hour(hour: Optional[int]) -> str:
    if hour is None:
        return "?"
    hour = int(hour)
    suffix = "am" if hour < 12 else "pm"
    display = hour % 12 or 12
    return f"{display}{suffix}"
