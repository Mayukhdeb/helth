"""Typed, immutable data models for Apple Health export entities.

Every model maps to one kind of element in ``export.xml``. Models are frozen
dataclasses so a parsed export can be shared freely without risk of mutation.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Dict, Mapping, Optional

from .constants import short_name

# Apple encodes every timestamp like ``2026-05-06 05:16:24 +0100``.
_APPLE_DT_FORMAT = "%Y-%m-%d %H:%M:%S %z"


def parse_apple_datetime(raw: Optional[str]) -> Optional[datetime]:
    """Parse an Apple Health timestamp, tolerating ``None``/empty values."""
    if not raw:
        return None
    return datetime.strptime(raw, _APPLE_DT_FORMAT)


def _to_float(raw: Optional[str]) -> Optional[float]:
    if raw is None or raw == "":
        return None
    try:
        return float(raw)
    except ValueError:
        return None


@dataclass(frozen=True)
class Personal:
    """The ``<Me>`` element: characteristics that rarely change."""

    date_of_birth: Optional[date]
    biological_sex: Optional[str]
    blood_type: Optional[str]
    fitzpatrick_skin_type: Optional[str]

    @classmethod
    def from_attrib(cls, attrib: Mapping[str, str]) -> "Personal":
        dob_raw = attrib.get("HKCharacteristicTypeIdentifierDateOfBirth")
        dob = date.fromisoformat(dob_raw) if dob_raw else None
        return cls(
            date_of_birth=dob,
            biological_sex=_clean_enum(
                attrib.get("HKCharacteristicTypeIdentifierBiologicalSex"),
                "HKBiologicalSex",
            ),
            blood_type=_clean_enum(
                attrib.get("HKCharacteristicTypeIdentifierBloodType"), "HKBloodType"
            ),
            fitzpatrick_skin_type=_clean_enum(
                attrib.get("HKCharacteristicTypeIdentifierFitzpatrickSkinType"),
                "HKFitzpatrickSkinType",
            ),
        )

    def age_years(self, on: Optional[date] = None) -> Optional[float]:
        """Chronological age in years on ``on`` (default: today)."""
        if self.date_of_birth is None:
            return None
        on = on or date.today()
        return (on - self.date_of_birth).days / 365.25


def _clean_enum(raw: Optional[str], prefix: str) -> Optional[str]:
    if not raw:
        return None
    value = raw[len(prefix) :] if raw.startswith(prefix) else raw
    return value or None


@dataclass(frozen=True)
class Record:
    """A single ``<Record>`` sample (quantity or category)."""

    type: str
    source_name: str
    start_date: datetime
    end_date: datetime
    creation_date: Optional[datetime] = None
    value: Optional[str] = None
    unit: Optional[str] = None
    device: Optional[str] = None
    metadata: Mapping[str, str] = field(default_factory=dict)

    @classmethod
    def from_attrib(
        cls, attrib: Mapping[str, str], metadata: Optional[Dict[str, str]] = None
    ) -> "Record":
        return cls(
            type=attrib["type"],
            source_name=attrib.get("sourceName", ""),
            start_date=parse_apple_datetime(attrib["startDate"]),  # type: ignore[arg-type]
            end_date=parse_apple_datetime(attrib.get("endDate", attrib["startDate"])),  # type: ignore[arg-type]
            creation_date=parse_apple_datetime(attrib.get("creationDate")),
            value=attrib.get("value"),
            unit=attrib.get("unit"),
            device=attrib.get("device"),
            metadata=metadata or {},
        )

    @property
    def short_type(self) -> str:
        """The identifier without its ``HK...`` prefix."""
        return short_name(self.type)

    @property
    def numeric_value(self) -> Optional[float]:
        """The value as a float, or ``None`` for categorical records."""
        return _to_float(self.value)

    @property
    def short_value(self) -> Optional[str]:
        """Categorical value without its ``HKCategoryValue`` prefix."""
        return short_name(self.value) if self.value is not None else None

    @property
    def duration_seconds(self) -> float:
        return (self.end_date - self.start_date).total_seconds()


@dataclass(frozen=True)
class Workout:
    """A ``<Workout>`` element."""

    activity_type: str
    source_name: str
    start_date: datetime
    end_date: datetime
    duration: Optional[float] = None
    duration_unit: Optional[str] = None
    total_distance: Optional[float] = None
    total_distance_unit: Optional[str] = None
    total_energy_burned: Optional[float] = None
    total_energy_burned_unit: Optional[str] = None
    creation_date: Optional[datetime] = None
    device: Optional[str] = None
    #: Summed ``<WorkoutStatistics>`` by short type, e.g.
    #: ``{"ActiveEnergyBurned": 169.6, "DistanceWalkingRunning": 1.8}``.
    #: Newer HealthKit exports put per-workout energy/distance here rather
    #: than on the top-level ``total*`` attributes.
    statistics: Mapping[str, float] = field(default_factory=dict)

    @classmethod
    def from_attrib(
        cls,
        attrib: Mapping[str, str],
        statistics: Optional[Dict[str, float]] = None,
    ) -> "Workout":
        return cls(
            activity_type=attrib["workoutActivityType"],
            source_name=attrib.get("sourceName", ""),
            start_date=parse_apple_datetime(attrib["startDate"]),  # type: ignore[arg-type]
            end_date=parse_apple_datetime(attrib.get("endDate", attrib["startDate"])),  # type: ignore[arg-type]
            duration=_to_float(attrib.get("duration")),
            duration_unit=attrib.get("durationUnit"),
            total_distance=_to_float(attrib.get("totalDistance")),
            total_distance_unit=attrib.get("totalDistanceUnit"),
            total_energy_burned=_to_float(attrib.get("totalEnergyBurned")),
            total_energy_burned_unit=attrib.get("totalEnergyBurnedUnit"),
            creation_date=parse_apple_datetime(attrib.get("creationDate")),
            device=attrib.get("device"),
            statistics=statistics or {},
        )

    @property
    def short_type(self) -> str:
        return short_name(self.activity_type)

    @property
    def energy_burned(self) -> Optional[float]:
        """Calories burned — from the top-level attribute or WorkoutStatistics."""
        if self.total_energy_burned is not None:
            return self.total_energy_burned
        return self.statistics.get("ActiveEnergyBurned")

    @property
    def distance(self) -> Optional[float]:
        """Distance covered — from the top-level attribute or WorkoutStatistics."""
        if self.total_distance is not None:
            return self.total_distance
        for key in ("DistanceWalkingRunning", "DistanceCycling", "DistanceSwimming"):
            if key in self.statistics:
                return self.statistics[key]
        return None


@dataclass(frozen=True)
class ActivitySummary:
    """An ``<ActivitySummary>`` element: one Apple activity-ring day."""

    date: date
    active_energy_burned: Optional[float] = None
    active_energy_burned_goal: Optional[float] = None
    active_energy_burned_unit: Optional[str] = None
    move_time: Optional[float] = None
    move_time_goal: Optional[float] = None
    exercise_time: Optional[float] = None
    exercise_time_goal: Optional[float] = None
    stand_hours: Optional[float] = None
    stand_hours_goal: Optional[float] = None

    @classmethod
    def from_attrib(cls, attrib: Mapping[str, str]) -> "ActivitySummary":
        return cls(
            date=date.fromisoformat(attrib["dateComponents"]),
            active_energy_burned=_to_float(attrib.get("activeEnergyBurned")),
            active_energy_burned_goal=_to_float(attrib.get("activeEnergyBurnedGoal")),
            active_energy_burned_unit=attrib.get("activeEnergyBurnedUnit"),
            move_time=_to_float(attrib.get("appleMoveTime")),
            move_time_goal=_to_float(attrib.get("appleMoveTimeGoal")),
            exercise_time=_to_float(attrib.get("appleExerciseTime")),
            exercise_time_goal=_to_float(attrib.get("appleExerciseTimeGoal")),
            stand_hours=_to_float(attrib.get("appleStandHours")),
            stand_hours_goal=_to_float(attrib.get("appleStandHoursGoal")),
        )
