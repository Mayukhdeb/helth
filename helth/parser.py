"""Streaming parser for Apple Health ``export.xml`` files.

The real export is often hundreds of megabytes with millions of ``<Record>``
elements, so we use :func:`xml.etree.ElementTree.iterparse` and clear each
element after handling it. Peak memory stays proportional to the *result*,
not the file size.
"""

from __future__ import annotations

from pathlib import Path
from typing import IO, Callable, Dict, Iterable, Iterator, List, Optional, Union
from xml.etree.ElementTree import Element, iterparse

from .models import ActivitySummary, Personal, Record, Workout

PathLike = Union[str, Path]

#: Optional callback invoked with ``(elements_seen, records_kept)`` periodically.
ProgressCallback = Callable[[int, int], None]


def _metadata_of(elem: Element) -> Dict[str, str]:
    meta: Dict[str, str] = {}
    for child in elem:
        if child.tag == "MetadataEntry":
            key = child.get("key")
            value = child.get("value")
            if key is not None and value is not None:
                meta[key] = value
    return meta


def _workout_statistics(elem: Element) -> Dict[str, float]:
    """Summed ``<WorkoutStatistics>`` children, keyed by short type name."""
    from .constants import short_name

    stats: Dict[str, float] = {}
    for child in elem:
        if child.tag != "WorkoutStatistics":
            continue
        type_ = child.get("type")
        raw_sum = child.get("sum")
        if type_ is None or raw_sum is None:
            continue
        try:
            stats[short_name(type_)] = float(raw_sum)
        except ValueError:
            continue
    return stats


def iter_records(
    source: Union[PathLike, IO[bytes]],
    *,
    types: Optional[Iterable[str]] = None,
    include_metadata: bool = False,
) -> Iterator[Record]:
    """Yield :class:`~helth.models.Record` objects one at a time.

    Args:
        source: Path to ``export.xml`` (or an open binary file object).
        types: If given, only records whose ``type`` is in this set are yielded.
        include_metadata: Parse nested ``<MetadataEntry>`` children (slower).

    This is the memory-efficient primitive; :class:`HealthExport` builds on it.
    """
    wanted = set(types) if types is not None else None
    # ``start`` events let us see attributes; ``end`` lets us read children.
    events = ("end",) if include_metadata else ("start",)
    for event, elem in iterparse(source, events=events):
        if elem.tag != "Record":
            # Don't clear here: non-Record end events may be MetadataEntry
            # children whose attributes the parent Record still needs.
            continue
        rec_type = elem.get("type")
        if wanted is not None and rec_type not in wanted:
            elem.clear()
            continue
        metadata = _metadata_of(elem) if include_metadata else None
        yield Record.from_attrib(elem.attrib, metadata)
        elem.clear()


class ParsedExport:
    """The fully-materialised contents of a single ``export.xml``."""

    def __init__(
        self,
        personal: Optional[Personal],
        records: List[Record],
        workouts: List[Workout],
        activity_summaries: List[ActivitySummary],
    ) -> None:
        self.personal = personal
        self.records = records
        self.workouts = workouts
        self.activity_summaries = activity_summaries


def parse_export(
    source: Union[PathLike, IO[bytes]],
    *,
    record_types: Optional[Iterable[str]] = None,
    include_metadata: bool = False,
    progress: Optional[ProgressCallback] = None,
    progress_every: int = 250_000,
) -> ParsedExport:
    """Parse an entire export into typed collections in a single pass.

    Args:
        source: Path to ``export.xml`` (or an open binary file object).
        record_types: Restrict parsed ``<Record>`` elements to these types.
        include_metadata: Parse ``<MetadataEntry>`` children of records.
        progress: Optional callback ``(elements_seen, records_kept)``.
        progress_every: How often (in elements) to invoke ``progress``.
    """
    wanted = set(record_types) if record_types is not None else None
    personal: Optional[Personal] = None
    records: List[Record] = []
    workouts: List[Workout] = []
    summaries: List[ActivitySummary] = []

    seen = 0
    for event, elem in iterparse(source, events=("end",)):
        tag = elem.tag
        if tag == "Record":
            seen += 1
            rec_type = elem.get("type")
            if wanted is None or rec_type in wanted:
                metadata = _metadata_of(elem) if include_metadata else None
                records.append(Record.from_attrib(elem.attrib, metadata))
        elif tag == "Workout":
            seen += 1
            workouts.append(
                Workout.from_attrib(elem.attrib, _workout_statistics(elem))
            )
        elif tag == "ActivitySummary":
            seen += 1
            summaries.append(ActivitySummary.from_attrib(elem.attrib))
        elif tag == "Me":
            personal = Personal.from_attrib(elem.attrib)
        else:
            # Child elements (e.g. MetadataEntry) are cleared together with
            # their parent below; clearing them here would drop attributes the
            # parent still needs when include_metadata is True.
            continue

        elem.clear()
        if progress is not None and seen % progress_every == 0:
            progress(seen, len(records))

    if progress is not None:
        progress(seen, len(records))
    return ParsedExport(personal, records, workouts, summaries)
