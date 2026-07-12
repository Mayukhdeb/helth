"""Tests for the streaming XML parser and models."""

from __future__ import annotations

from datetime import date, datetime, timezone

from helth import HealthExport, iter_records, parse_export
from helth.constants import Quantity
from helth.models import Record, parse_apple_datetime


def test_parse_apple_datetime_roundtrip() -> None:
    dt = parse_apple_datetime("2026-05-06 05:16:24 +0100")
    assert dt is not None
    assert dt.year == 2026 and dt.hour == 5 and dt.minute == 16
    assert dt.utcoffset().total_seconds() == 3600
    assert parse_apple_datetime(None) is None
    assert parse_apple_datetime("") is None


def test_parse_export_counts(export_xml_path) -> None:
    parsed = parse_export(export_xml_path)
    # 12 <Record> elements in the fixture.
    assert len(parsed.records) == 12
    assert len(parsed.workouts) == 1
    assert len(parsed.activity_summaries) == 1
    assert parsed.personal is not None


def test_personal_parsing(export_xml_path) -> None:
    parsed = parse_export(export_xml_path)
    me = parsed.personal
    assert me is not None
    assert me.date_of_birth == date(2000, 11, 9)
    assert me.biological_sex == "Male"  # prefix stripped
    age = me.age_years(on=date(2026, 11, 9))
    assert age is not None and round(age) == 26


def test_record_type_filter(export_xml_path) -> None:
    parsed = parse_export(export_xml_path, record_types=[Quantity.STEP_COUNT])
    assert len(parsed.records) == 2
    assert all(r.short_type == "StepCount" for r in parsed.records)


def test_iter_records_streaming(export_xml_path) -> None:
    steps = list(iter_records(export_xml_path, types=[Quantity.STEP_COUNT]))
    assert [r.numeric_value for r in steps] == [6000.0, 12000.0]


def test_record_properties() -> None:
    rec = Record.from_attrib(
        {
            "type": "HKQuantityTypeIdentifierStepCount",
            "sourceName": "Watch",
            "startDate": "2026-05-01 08:00:00 +0100",
            "endDate": "2026-05-01 09:00:00 +0100",
            "value": "6000",
            "unit": "count",
        }
    )
    assert rec.short_type == "StepCount"
    assert rec.numeric_value == 6000.0
    assert rec.duration_seconds == 3600.0


def test_category_record_value_and_metadata(export_xml_path) -> None:
    parsed = parse_export(export_xml_path, include_metadata=True)
    sleep = [r for r in parsed.records if r.short_type == "SleepAnalysis"]
    assert len(sleep) == 1
    assert sleep[0].numeric_value is None
    assert sleep[0].short_value == "SleepAnalysisAsleepCore"
    assert sleep[0].metadata["HKTimeZone"] == "Europe/London"


def test_workout_parsing(export_xml_path) -> None:
    parsed = parse_export(export_xml_path)
    w = parsed.workouts[0]
    assert w.short_type == "Walking"
    assert w.duration == 22.5
    assert w.total_distance == 1.8


def test_from_dir_and_missing_file(export_dir, tmp_path) -> None:
    health = HealthExport.from_dir(export_dir)
    assert len(health.records) == 12

    import pytest

    with pytest.raises(FileNotFoundError):
        HealthExport.from_dir(tmp_path / "does_not_exist")


def test_progress_callback(export_xml_path) -> None:
    seen = []
    parse_export(export_xml_path, progress=lambda s, k: seen.append((s, k)))
    assert seen  # called at least once at the end
    assert seen[-1][0] == 14  # 12 records + 1 workout + 1 summary
