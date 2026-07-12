"""Tests for the HealthExport query surface and dataframe helpers."""

from __future__ import annotations


def test_records_of_type_accepts_short_and_full(health) -> None:
    assert len(health.records_of_type("StepCount")) == 2
    assert len(health.records_of_type("HKQuantityTypeIdentifierStepCount")) == 2


def test_record_types_and_counts(health) -> None:
    types = health.record_types()
    assert "StepCount" in types and "SleepAnalysis" in types
    counts = health.type_counts()
    assert counts["StepCount"] == 2


def test_latest(health) -> None:
    latest_steps = health.latest("StepCount")
    assert latest_steps is not None
    assert latest_steps.numeric_value == 12000.0


def test_workout_types(health) -> None:
    assert health.workout_types() == ["Walking"]


def test_to_dataframe(health) -> None:
    frame = health.to_dataframe("StepCount")
    assert list(frame["value"]) == [6000.0, 12000.0]
    assert set(frame.columns) == {
        "type",
        "value",
        "unit",
        "start_date",
        "end_date",
        "source_name",
    }


def test_activity_summary_dataframe(health) -> None:
    frame = health.activity_summary_dataframe()
    assert len(frame) == 1
    assert frame["exercise_time"].iloc[0] == 25


def test_date_range_and_summary(health) -> None:
    span = health.date_range()
    assert span is not None
    text = health.summary()
    assert "Records: 12" in text
    assert "Workouts: 1" in text
