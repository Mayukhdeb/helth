"""The :class:`HealthExport` — the primary entry point of the library."""

from __future__ import annotations

from collections import Counter
from pathlib import Path
from typing import (
    TYPE_CHECKING,
    Iterable,
    List,
    Optional,
    Sequence,
    Union,
)

from .constants import quantity_type
from .models import ActivitySummary, Personal, Record, Workout
from .parser import ParsedExport, PathLike, ProgressCallback, parse_export

if TYPE_CHECKING:  # pragma: no cover - typing only
    import pandas as pd

#: Default filename Apple uses inside the export directory.
EXPORT_FILENAME = "export.xml"


class HealthExport:
    """An in-memory, queryable view over an Apple Health export.

    Construct via :meth:`from_dir` (pointing at the ``apple_health_export``
    folder) or :meth:`from_xml` (pointing at ``export.xml`` directly).

    Example:
        >>> health = HealthExport.from_dir("data/apple_health_export")  # doctest: +SKIP
        >>> health.record_types()[:3]  # doctest: +SKIP
        ['ActiveEnergyBurned', 'BasalEnergyBurned', 'HeartRate']
    """

    def __init__(
        self,
        personal: Optional[Personal],
        records: Sequence[Record],
        workouts: Sequence[Workout],
        activity_summaries: Sequence[ActivitySummary],
        *,
        source_path: Optional[Path] = None,
    ) -> None:
        self.personal = personal
        self.records: List[Record] = list(records)
        self.workouts: List[Workout] = list(workouts)
        self.activity_summaries: List[ActivitySummary] = list(activity_summaries)
        self.source_path = source_path

    # -- constructors -------------------------------------------------------
    @classmethod
    def from_parsed(
        cls, parsed: ParsedExport, *, source_path: Optional[Path] = None
    ) -> "HealthExport":
        return cls(
            parsed.personal,
            parsed.records,
            parsed.workouts,
            parsed.activity_summaries,
            source_path=source_path,
        )

    @classmethod
    def from_xml(
        cls,
        path: Union[PathLike, "object"],
        *,
        record_types: Optional[Iterable[str]] = None,
        include_metadata: bool = False,
        progress: Optional[ProgressCallback] = None,
    ) -> "HealthExport":
        """Load from a specific ``export.xml`` file (or open binary stream)."""
        source_path = Path(path) if isinstance(path, (str, Path)) else None
        parsed = parse_export(
            path,  # type: ignore[arg-type]
            record_types=record_types,
            include_metadata=include_metadata,
            progress=progress,
        )
        return cls.from_parsed(parsed, source_path=source_path)

    @classmethod
    def from_dir(
        cls,
        directory: PathLike,
        *,
        record_types: Optional[Iterable[str]] = None,
        include_metadata: bool = False,
        progress: Optional[ProgressCallback] = None,
    ) -> "HealthExport":
        """Load from an ``apple_health_export`` directory containing ``export.xml``."""
        directory = Path(directory)
        xml_path = directory / EXPORT_FILENAME
        if not xml_path.exists():
            raise FileNotFoundError(
                f"No '{EXPORT_FILENAME}' found in {directory!s}. "
                "Point this at the unzipped 'apple_health_export' folder."
            )
        return cls.from_xml(
            xml_path,
            record_types=record_types,
            include_metadata=include_metadata,
            progress=progress,
        )

    # -- queries ------------------------------------------------------------
    def records_of_type(self, type_: str) -> List[Record]:
        """All records of a type. Accepts full identifiers or short names.

        >>> health.records_of_type("StepCount")  # doctest: +SKIP
        """
        full = quantity_type(type_) if not type_.startswith("HK") else type_
        # Also allow matching by short name for category types etc.
        return [
            r
            for r in self.records
            if r.type == full or r.type == type_ or r.short_type == type_
        ]

    def record_types(self) -> List[str]:
        """Sorted list of distinct short record-type names present."""
        return sorted({r.short_type for r in self.records})

    def type_counts(self) -> "Counter[str]":
        """A ``Counter`` of short record-type name -> number of samples."""
        return Counter(r.short_type for r in self.records)

    def workout_types(self) -> List[str]:
        return sorted({w.short_type for w in self.workouts})

    def latest(self, type_: str) -> Optional[Record]:
        """The most recent record of ``type_`` by start date, if any."""
        matches = self.records_of_type(type_)
        if not matches:
            return None
        return max(matches, key=lambda r: r.start_date)

    # -- dataframes ---------------------------------------------------------
    def to_dataframe(self, type_: Optional[str] = None) -> "pd.DataFrame":
        """Return records as a tidy :class:`pandas.DataFrame`.

        Columns: ``type, value, unit, start_date, end_date, source_name``.
        If ``type_`` is given, only those records are included and ``value`` is
        coerced to numeric where possible.
        """
        import pandas as pd

        source = self.records_of_type(type_) if type_ is not None else self.records
        frame = pd.DataFrame(
            {
                "type": [r.short_type for r in source],
                "value": [r.numeric_value if r.numeric_value is not None else r.value for r in source],
                "unit": [r.unit for r in source],
                "start_date": [r.start_date for r in source],
                "end_date": [r.end_date for r in source],
                "source_name": [r.source_name for r in source],
            }
        )
        if not frame.empty:
            frame["start_date"] = pd.to_datetime(frame["start_date"], utc=True)
            frame["end_date"] = pd.to_datetime(frame["end_date"], utc=True)
        return frame

    def activity_summary_dataframe(self) -> "pd.DataFrame":
        """Activity-ring summaries as a DataFrame indexed by date."""
        import pandas as pd

        rows = [
            {
                "date": s.date,
                "active_energy_burned": s.active_energy_burned,
                "exercise_time": s.exercise_time,
                "stand_hours": s.stand_hours,
                "move_time": s.move_time,
            }
            for s in self.activity_summaries
        ]
        frame = pd.DataFrame(rows)
        if not frame.empty:
            frame = frame.set_index(pd.to_datetime(frame.pop("date"))).sort_index()
        return frame

    # -- niceties -----------------------------------------------------------
    def date_range(self) -> Optional["tuple[object, object]"]:
        """(earliest, latest) start date across all records, or ``None``."""
        if not self.records:
            return None
        starts = [r.start_date for r in self.records]
        return (min(starts), max(starts))

    def summary(self) -> str:
        """A human-readable overview of what the export contains."""
        lines = ["Apple Health export summary", "=" * 30]
        if self.personal is not None:
            age = self.personal.age_years()
            age_str = f"{age:.0f}y" if age is not None else "unknown age"
            lines.append(
                f"Subject: {self.personal.biological_sex or '?'}, {age_str}"
            )
        span = self.date_range()
        if span is not None:
            lines.append(f"Date range: {span[0].date()} to {span[1].date()}")
        lines.append(f"Records: {len(self.records):,}")
        lines.append(f"Workouts: {len(self.workouts):,}")
        lines.append(f"Activity summaries: {len(self.activity_summaries):,}")
        top = self.type_counts().most_common(8)
        if top:
            lines.append("Top record types:")
            for name, count in top:
                lines.append(f"  {name:<32} {count:>10,}")
        return "\n".join(lines)

    def __repr__(self) -> str:  # pragma: no cover - cosmetic
        return (
            f"HealthExport(records={len(self.records)}, "
            f"workouts={len(self.workouts)}, "
            f"activity_summaries={len(self.activity_summaries)})"
        )
