"""Tests for temporal pattern analysis and the HTML dashboard."""

from __future__ import annotations

from pathlib import Path

from helth.insights.patterns import (
    by_weekday,
    heart_rate_by_hour,
    highlights,
    hourly_sum,
    sleep_by_night,
    workout_breakdown,
)


def test_heart_rate_by_hour_uses_local_hour(health) -> None:
    hr = heart_rate_by_hour(health)
    # Fixture HR: 58 bpm at 07:00, 120 & 110 bpm at 18:00 (local +0100).
    assert hr.loc[7, "mean"] == 58.0
    assert hr.loc[18, "mean"] == 115.0
    # 18:00 is the peak hour.
    assert hr["mean"].idxmax() == 18


def test_hourly_sum_steps(health) -> None:
    steps = hourly_sum(health, "StepCount")
    # Both step records fall in the 08:00 hour (local).
    assert steps.loc[8] == 9000.0  # mean of 6000 and 12000 across two days
    assert steps.index.tolist() == list(range(24))


def test_by_weekday(health) -> None:
    steps = by_weekday(health, "StepCount")
    assert list(steps.index) == ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
    # 2026-05-01 is a Friday, 2026-05-02 a Saturday.
    assert steps["Fri"] == 6000.0
    assert steps["Sat"] == 12000.0


def test_sleep_by_night(health) -> None:
    sleep = sleep_by_night(health)
    assert len(sleep) == 1
    # 23:00 -> 05:00 next morning = 6 hours, keyed to the morning (May 2).
    assert round(float(sleep.iloc[0]), 1) == 6.0


def test_workout_statistics_parsed(health) -> None:
    from helth.insights.patterns import workout_metric_series

    w = health.workouts[0]
    assert w.statistics["ActiveEnergyBurned"] == 88.4
    # Top-level attribute wins when present; falls back to statistics otherwise.
    assert w.energy_burned == 95.2
    energy = workout_metric_series(health, "Walking", metric="energy")
    assert len(energy) == 1
    assert float(energy.iloc[0]) == 95.2


def test_workout_breakdown(health) -> None:
    wk = workout_breakdown(health)
    assert wk.iloc[0]["activity"] == "Walking"
    assert wk.iloc[0]["count"] == 1
    assert round(wk.iloc[0]["minutes"], 1) == 22.5


def test_highlights_surface_hr_peak(health) -> None:
    hl = highlights(health)
    titles = " ".join(h.title for h in hl)
    assert "Heart rate peaks" in titles
    assert "6pm" in titles  # 18:00 local


def test_generate_dashboard_writes_html(health, tmp_path: Path) -> None:
    from helth.dashboard import generate_dashboard

    out = tmp_path / "dash.html"
    path = generate_dashboard(health, str(out))
    assert path.exists()
    html = path.read_text(encoding="utf-8")
    assert "helth dashboard" in html
    # Plotly is embedded once and charts are present.
    assert "plotly-graph-div" in html
    assert "Heart rate by time of day" in html
    # Population percentile section is included.
    assert "vs general adult population" in html
    # The aerobic-only caveat must be present.
    assert "not strength" in html.lower()
    # Normal + athletic reference bands and their citations must be embedded.
    assert "Normal" in html and "Athlete" in html
    assert "Reimers" in html and "Nunan" in html  # in-plot citation captions
    assert "Tudor-Locke" in html  # footer citation


def test_baselines_have_normal_and_athletic_bands() -> None:
    from helth.insights.athlete_reference import (
        BASELINES,
        baseline_for,
        citation_for_key,
    )

    for metric in ("resting_heart_rate", "hrv_sdnn", "sleep_hours", "steps"):
        bl = baseline_for(metric)
        assert bl is not None
        # Both a normal and athletic band, each with a resolvable citation URL.
        assert citation_for_key(bl.normal.citation_key).url.startswith("http")
        assert citation_for_key(bl.athletic.citation_key).url.startswith("http")

    # Resting HR: athletic band sits below the normal band (lower = fitter).
    rhr = BASELINES["resting_heart_rate"]
    assert rhr.athletic.high <= rhr.normal.high
    # Steps: athletic band is open-ended (≥ threshold).
    assert BASELINES["steps"].athletic.high is None
    assert baseline_for("nonexistent") is None
