"""VO2max estimation and cardiorespiratory-fitness reference norms.

We deliberately do **not** collapse fitness into a single "biological age"
number: VO2max only captures *aerobic* capacity and badly misrepresents
strength-trained people, and consumer-wearable data can't measure the many
systems a true biological-age clock needs. Instead this module exposes VO2max
(with provenance) and the population norms used elsewhere for percentile ranks.

VO2max sources:
    * Preferred: the value your Apple Watch estimates
      (``HKQuantityTypeIdentifierVO2Max``).
    * Fallback: the **Nes et al. (2011) HUNT non-exercise model** from age,
      sex, resting heart rate, body composition and physical activity.

Reference norms (population mean/SD of VO2max by age & sex) come from the
**FRIEND registry** (Kaminsky et al., 2015), the standard US CRF reference.

References:
    * Nes BM et al. Med Sci Sports Exerc. 2011;43(11):2024-30.
    * Kaminsky LA et al. Mayo Clin Proc. 2015;90(11):1515-23.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Dict, Optional

from ..constants import Quantity
from .vitals import _recent_mean

if TYPE_CHECKING:  # pragma: no cover
    from ..export import HealthExport


# --- FRIEND registry (Kaminsky 2015) VO2max norms, linearised by age -------
# Population mean VO2max ≈ intercept - slope * age; sd is roughly constant.
@dataclass(frozen=True)
class CrfNorm:
    intercept: float
    slope: float  # ml/kg/min lost per year in the reference population
    sd: float

    def mean_vo2max(self, age: float) -> float:
        return self.intercept - self.slope * age


CRF_NORMS: Dict[str, CrfNorm] = {
    "male": CrfNorm(intercept=59.8, slope=0.472, sd=8.0),
    "female": CrfNorm(intercept=45.5, slope=0.314, sd=7.0),
}

# --- Nes et al. (2011) HUNT non-exercise VO2max model (waist-based) ---------
@dataclass(frozen=True)
class _NesModel:
    c0: float
    c_age: float
    c_pa: float
    c_wc: float
    c_rhr: float

    def vo2max(self, age: float, pa_index: float, waist_cm: float, rhr: float) -> float:
        return (
            self.c0
            - self.c_age * age
            + self.c_pa * pa_index
            - self.c_wc * waist_cm
            - self.c_rhr * rhr
        )


_NES: Dict[str, _NesModel] = {
    "male": _NesModel(c0=100.27, c_age=0.296, c_pa=0.226, c_wc=0.369, c_rhr=0.155),
    "female": _NesModel(c0=74.736, c_age=0.247, c_pa=0.198, c_wc=0.259, c_rhr=0.114),
}

# HUNT PA index runs 0 (inactive) .. ~15 (highly active).
_DEFAULT_PA_INDEX = 5.0


def normalise_sex(raw: Optional[str]) -> Optional[str]:
    if raw is None:
        return None
    low = raw.lower()
    if low.startswith("male") or low == "m":
        return "male"
    if low.startswith("female") or low == "f":
        return "female"
    return None


def _estimate_waist_from_bmi(bmi: float, sex: str) -> float:
    """Rough waist (cm) proxy from BMI, for the non-exercise fallback only."""
    if sex == "male":
        return 2.2 * bmi + 41.0
    return 2.3 * bmi + 33.0


@dataclass
class Vo2MaxEstimate:
    """VO2max value plus provenance."""

    value: Optional[float]
    source: str  # "measured" | "estimated_nes_2011" | "unavailable"
    details: Dict[str, float] = field(default_factory=dict)

    def __str__(self) -> str:
        if self.value is None:
            return "VO2max: unavailable"
        label = {
            "measured": "Apple Watch measured",
            "estimated_nes_2011": "estimated (Nes 2011 non-exercise model)",
        }.get(self.source, self.source)
        return f"VO2max: {self.value:.1f} mL/kg/min [{label}]"


def estimate_vo2max(
    export: "HealthExport",
    *,
    last_n: int = 30,
    pa_index: Optional[float] = None,
    waist_cm: Optional[float] = None,
) -> Vo2MaxEstimate:
    """Return the best available VO2max for the subject.

    Uses the Apple Watch measured value when present, otherwise falls back to
    the Nes (2011) HUNT non-exercise model.
    """
    measured = _recent_mean(export, Quantity.VO2_MAX, last_n)
    if measured is not None:
        return Vo2MaxEstimate(value=measured, source="measured", details={})

    personal = export.personal
    sex = normalise_sex(personal.biological_sex if personal else None)
    age = personal.age_years() if personal else None
    rhr = _recent_mean(export, Quantity.RESTING_HEART_RATE, last_n)
    if sex is None or age is None or rhr is None:
        return Vo2MaxEstimate(value=None, source="unavailable", details={})

    if waist_cm is None:
        bmi = _recent_mean(export, Quantity.BODY_MASS_INDEX, last_n)
        if bmi is not None:
            waist_cm = _estimate_waist_from_bmi(bmi, sex)
    if waist_cm is None:
        return Vo2MaxEstimate(value=None, source="unavailable", details={})

    pa = _DEFAULT_PA_INDEX if pa_index is None else pa_index
    value = _NES[sex].vo2max(age=age, pa_index=pa, waist_cm=waist_cm, rhr=rhr)
    return Vo2MaxEstimate(
        value=value,
        source="estimated_nes_2011",
        details={"age": age, "pa_index": pa, "waist_cm": waist_cm, "resting_hr": rhr},
    )
