"""Rank a person's activity & fitness against the general adult population.

Instead of a single (misleading) "biological age", this reports **percentile
ranks** across several independent domains, so no one metric dominates. Each
rank answers: *what fraction of adults do you beat on this metric?*

All reference distributions are drawn from published population data and are
documented on each :class:`PercentileResult` via ``reference``. They are
population-level approximations, not per-individual clinical norms.

Sources:
    * Steps — Paluch et al., meta-analysis of 15 cohorts (Lancet Public
      Health 2022) quartile step counts; NHANES normative step data.
    * Resting heart rate — Health eHeart study / NHANES adult RHR norms.
    * Exercise minutes — WHO/ACSM physical-activity guideline distributions.
    * VO2max — FRIEND registry (Kaminsky et al., 2015), age/sex specific.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import TYPE_CHECKING, List, Optional, Sequence, Tuple

from ..constants import Quantity
from .activity import _daily_sum
from .fitness import CRF_NORMS, estimate_vo2max, normalise_sex
from .vitals import _recent_mean

if TYPE_CHECKING:  # pragma: no cover
    from ..export import HealthExport

# An anchor curve: ascending (value, percentile-of-population-below-value).
Anchors = Sequence[Tuple[float, float]]


def _interp_percentile(value: float, anchors: Anchors) -> float:
    """Percentile of the population *below* ``value`` via linear interpolation."""
    lo_v, lo_p = anchors[0]
    hi_v, hi_p = anchors[-1]
    if value <= lo_v:
        return lo_p
    if value >= hi_v:
        return hi_p
    for (v0, p0), (v1, p1) in zip(anchors, anchors[1:]):
        if v0 <= value <= v1:
            frac = (value - v0) / (v1 - v0) if v1 != v0 else 0.0
            return p0 + frac * (p1 - p0)
    return hi_p  # pragma: no cover


def _normal_percentile(value: float, mean: float, sd: float) -> float:
    """Percentile of the population below ``value`` under a normal model."""
    z = (value - mean) / sd
    return 100.0 * 0.5 * (1.0 + math.erf(z / math.sqrt(2.0)))


def _band(pct: float) -> str:
    if pct >= 97:
        return "elite (top 3%)"
    if pct >= 90:
        return f"top {round(100 - pct)}%"
    if pct >= 75:
        return "well above average"
    if pct >= 55:
        return "above average"
    if pct >= 45:
        return "about average"
    if pct >= 25:
        return "below average"
    return "well below average"


@dataclass(frozen=True)
class PercentileResult:
    """Where a single metric places the subject vs the adult population."""

    metric: str
    value: float
    unit: str
    percentile: float  # 0-100, already oriented so higher = fitter/more active
    reference: str
    higher_is_better: bool = True

    @property
    def band(self) -> str:
        return _band(self.percentile)

    def __str__(self) -> str:
        return (
            f"{self.metric:<22} {self.value:>8,.1f} {self.unit:<9} "
            f"P{self.percentile:>4.0f}  {self.band}"
        )


# --- Population reference distributions -------------------------------------
# Ascending (value, % of adults below). Percentiles chosen to match published
# quartiles/means; treat as approximate.
_STEPS_ANCHORS: Anchors = (
    (1000, 2),
    (2500, 10),
    (4000, 25),
    (5800, 45),
    (7000, 60),
    (8500, 75),
    (10900, 88),
    (13000, 95),
    (18000, 99),
)
_STEPS_REF = "adult daily steps, Paluch 2022 / NHANES (median ~6k, 75th ~8.5k)"

_EXERCISE_ANCHORS: Anchors = (
    (0, 12),
    (5, 30),
    (11, 50),
    (21, 72),  # ~WHO minimum of 150 min/week
    (35, 86),
    (50, 93),
    (75, 98),
    (120, 99.5),
)
_EXERCISE_REF = "moderate/vigorous exercise min/day vs WHO/ACSM guideline norms"

_ACTIVE_ENERGY_ANCHORS: Anchors = (
    (100, 15),
    (200, 35),
    (300, 52),
    (450, 72),
    (600, 86),
    (800, 95),
    (1100, 99),
)
_ACTIVE_ENERGY_REF = "active energy kcal/day (Apple activity-ring population range)"

# Resting heart rate: lower is fitter. Anchors are % of adults with RHR *below*.
_RHR_ANCHORS: Anchors = (
    (48, 3),
    (52, 10),
    (56, 22),
    (60, 38),
    (65, 58),
    (70, 74),
    (75, 86),
    (82, 95),
    (95, 99),
)
_RHR_REF = "adult resting heart rate, Health eHeart/NHANES (mean ~70 bpm)"


def _oriented(pct_below: float, higher_is_better: bool) -> float:
    """Convert 'percent below value' into a fitness/activity rank (higher=better)."""
    return pct_below if higher_is_better else (100.0 - pct_below)


def activity_percentiles(export: "HealthExport", *, last_n: int = 30) -> List[PercentileResult]:
    """Percentile ranks for habitual **activity** vs the adult population."""
    results: List[PercentileResult] = []

    steps = _daily_sum(export, Quantity.STEP_COUNT)
    if steps is not None and len(steps):
        v = float(steps.mean())
        results.append(
            PercentileResult(
                "Daily steps", v, "steps",
                _interp_percentile(v, _STEPS_ANCHORS), _STEPS_REF,
            )
        )

    exercise = _daily_sum(export, Quantity.EXERCISE_TIME)
    if exercise is not None and len(exercise):
        v = float(exercise.mean())
        results.append(
            PercentileResult(
                "Exercise minutes", v, "min/day",
                _interp_percentile(v, _EXERCISE_ANCHORS), _EXERCISE_REF,
            )
        )

    energy = _daily_sum(export, Quantity.ACTIVE_ENERGY_BURNED)
    if energy is not None and len(energy):
        v = float(energy.mean())
        results.append(
            PercentileResult(
                "Active energy", v, "kcal/day",
                _interp_percentile(v, _ACTIVE_ENERGY_ANCHORS), _ACTIVE_ENERGY_REF,
            )
        )

    return results


def fitness_percentiles(export: "HealthExport", *, last_n: int = 30) -> List[PercentileResult]:
    """Percentile ranks for **cardiovascular fitness** vs the adult population.

    Note: these capture *aerobic/cardio* fitness only — they say nothing about
    muscular strength, which Apple Health does not measure.
    """
    results: List[PercentileResult] = []

    rhr = _recent_mean(export, Quantity.RESTING_HEART_RATE, last_n)
    if rhr is not None:
        pct = _oriented(_interp_percentile(rhr, _RHR_ANCHORS), higher_is_better=False)
        results.append(
            PercentileResult(
                "Resting heart rate", rhr, "bpm", pct, _RHR_REF,
                higher_is_better=False,
            )
        )

    vo2 = estimate_vo2max(export, last_n=last_n)
    personal = export.personal
    sex = normalise_sex(personal.biological_sex if personal else None)
    age = personal.age_years() if personal else None
    if vo2.value is not None and sex is not None and age is not None:
        norm = CRF_NORMS[sex]
        pct = _normal_percentile(vo2.value, norm.mean_vo2max(age), norm.sd)
        ref = (
            f"VO2max vs FRIEND registry, {sex} age {age:.0f} "
            f"(aerobic only; source: {vo2.source})"
        )
        results.append(
            PercentileResult("VO2max (aerobic)", vo2.value, "mL/kg/min", pct, ref)
        )

    return results


@dataclass(frozen=True)
class PopulationRanking:
    """A full percentile report across activity and fitness domains."""

    activity: List[PercentileResult]
    fitness: List[PercentileResult]

    @property
    def overall_activity_percentile(self) -> Optional[float]:
        """Mean activity percentile — a single 'how active' summary."""
        if not self.activity:
            return None
        return sum(r.percentile for r in self.activity) / len(self.activity)

    def __str__(self) -> str:
        lines = ["Population ranking (vs general adult population)", "=" * 62]
        overall = self.overall_activity_percentile
        if overall is not None:
            lines.append(
                f"Overall activity: P{overall:.0f} — {_band(overall)}\n"
            )
        if self.activity:
            lines.append("Activity")
            lines.append("-" * 62)
            lines.extend(str(r) for r in self.activity)
        if self.fitness:
            lines.append("")
            lines.append("Cardio fitness (aerobic only — not strength)")
            lines.append("-" * 62)
            lines.extend(str(r) for r in self.fitness)
        return "\n".join(lines)


def population_ranking(export: "HealthExport", *, last_n: int = 30) -> PopulationRanking:
    """Full activity + fitness percentile report vs the adult population."""
    return PopulationRanking(
        activity=activity_percentiles(export, last_n=last_n),
        fitness=fitness_percentiles(export, last_n=last_n),
    )
