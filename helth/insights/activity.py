"""Activity-level insights derived from an Apple Health export."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Optional

from ..constants import Quantity

if TYPE_CHECKING:  # pragma: no cover
    import pandas as pd

    from ..export import HealthExport


@dataclass(frozen=True)
class ActivityProfile:
    """Summary statistics describing habitual activity levels."""

    avg_daily_steps: Optional[float]
    avg_daily_active_energy: Optional[float]
    avg_daily_exercise_minutes: Optional[float]
    active_days: int
    activity_level: str

    def __str__(self) -> str:
        def fmt(v: Optional[float], unit: str) -> str:
            return f"{v:,.0f} {unit}" if v is not None else "n/a"

        return (
            "Activity profile\n"
            "----------------\n"
            f"Level:            {self.activity_level}\n"
            f"Avg steps/day:    {fmt(self.avg_daily_steps, 'steps')}\n"
            f"Avg active kcal:  {fmt(self.avg_daily_active_energy, 'kcal')}\n"
            f"Avg exercise:     {fmt(self.avg_daily_exercise_minutes, 'min/day')}\n"
            f"Days tracked:     {self.active_days:,}"
        )


def _classify(avg_steps: Optional[float]) -> str:
    """Map average daily steps to a widely-used activity band."""
    if avg_steps is None:
        return "unknown"
    if avg_steps < 5000:
        return "sedentary"
    if avg_steps < 7500:
        return "low active"
    if avg_steps < 10000:
        return "somewhat active"
    if avg_steps < 12500:
        return "active"
    return "highly active"


def _daily_sum(export: "HealthExport", type_: str) -> "Optional[pd.Series]":
    frame = export.to_dataframe(type_)
    if frame.empty:
        return None
    numeric = frame[frame["value"].map(lambda v: isinstance(v, (int, float)))]
    if numeric.empty:
        return None
    return (
        numeric.assign(day=numeric["start_date"].dt.date)
        .groupby("day")["value"]
        .sum()
    )


def activity_profile(export: "HealthExport") -> ActivityProfile:
    """Compute an :class:`ActivityProfile` from step, energy and exercise data."""
    steps = _daily_sum(export, Quantity.STEP_COUNT)
    energy = _daily_sum(export, Quantity.ACTIVE_ENERGY_BURNED)
    exercise = _daily_sum(export, Quantity.EXERCISE_TIME)

    avg_steps = float(steps.mean()) if steps is not None and len(steps) else None
    avg_energy = float(energy.mean()) if energy is not None and len(energy) else None
    avg_exercise = (
        float(exercise.mean()) if exercise is not None and len(exercise) else None
    )
    active_days = len(steps) if steps is not None else 0

    return ActivityProfile(
        avg_daily_steps=avg_steps,
        avg_daily_active_energy=avg_energy,
        avg_daily_exercise_minutes=avg_exercise,
        active_days=active_days,
        activity_level=_classify(avg_steps),
    )


def daily_steps(export: "HealthExport") -> "pd.Series":
    """A date-indexed series of total steps per day (empty if unavailable)."""
    import pandas as pd

    series = _daily_sum(export, Quantity.STEP_COUNT)
    if series is None:
        return pd.Series(dtype="float64", name="steps")
    series.index = pd.to_datetime(list(series.index))
    series.name = "steps"
    return series.sort_index()
