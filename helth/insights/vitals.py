"""Cardiovascular / vitals insights."""

from __future__ import annotations

from dataclasses import dataclass
from statistics import mean
from typing import TYPE_CHECKING, List, Optional

from ..constants import Quantity

if TYPE_CHECKING:  # pragma: no cover
    from ..export import HealthExport


def _numeric_values(export: "HealthExport", type_: str) -> List[float]:
    return [
        r.numeric_value
        for r in export.records_of_type(type_)
        if r.numeric_value is not None
    ]


def _recent_mean(
    export: "HealthExport", type_: str, last_n: Optional[int] = None
) -> Optional[float]:
    records = sorted(export.records_of_type(type_), key=lambda r: r.start_date)
    values = [r.numeric_value for r in records if r.numeric_value is not None]
    if not values:
        return None
    if last_n is not None:
        values = values[-last_n:]
    return mean(values)


@dataclass(frozen=True)
class VitalsSummary:
    """Aggregate cardiovascular markers used across insights."""

    resting_heart_rate: Optional[float]
    walking_heart_rate: Optional[float]
    hrv_sdnn: Optional[float]
    respiratory_rate: Optional[float]
    oxygen_saturation: Optional[float]
    vo2_max: Optional[float]

    def __str__(self) -> str:
        def fmt(v: Optional[float], unit: str) -> str:
            return f"{v:.1f} {unit}" if v is not None else "n/a"

        return (
            "Vitals summary\n"
            "--------------\n"
            f"Resting HR:       {fmt(self.resting_heart_rate, 'bpm')}\n"
            f"Walking HR:       {fmt(self.walking_heart_rate, 'bpm')}\n"
            f"HRV (SDNN):       {fmt(self.hrv_sdnn, 'ms')}\n"
            f"Respiratory rate: {fmt(self.respiratory_rate, 'br/min')}\n"
            f"SpO2:             {fmt(self.oxygen_saturation, '')}\n"
            f"VO2 max:          {fmt(self.vo2_max, 'mL/kg/min')}"
        )


def vitals_summary(export: "HealthExport", last_n: int = 30) -> VitalsSummary:
    """Summarise vitals using the mean of the ``last_n`` most recent samples."""
    spo2 = _recent_mean(export, Quantity.OXYGEN_SATURATION, last_n)
    return VitalsSummary(
        resting_heart_rate=_recent_mean(export, Quantity.RESTING_HEART_RATE, last_n),
        walking_heart_rate=_recent_mean(
            export, Quantity.WALKING_HEART_RATE_AVERAGE, last_n
        ),
        hrv_sdnn=_recent_mean(export, Quantity.HEART_RATE_VARIABILITY_SDNN, last_n),
        respiratory_rate=_recent_mean(export, Quantity.RESPIRATORY_RATE, last_n),
        # SpO2 is stored as a fraction (0-1); present it as a percentage.
        oxygen_saturation=spo2 * 100 if spo2 is not None else None,
        vo2_max=_recent_mean(export, Quantity.VO2_MAX, last_n),
    )
