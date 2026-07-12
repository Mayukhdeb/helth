"""Tests for the insight generators."""

from __future__ import annotations

from helth.insights import (
    activity_percentiles,
    activity_profile,
    daily_steps,
    estimate_vo2max,
    fitness_percentiles,
    population_ranking,
    vitals_summary,
)


def test_activity_profile(health) -> None:
    profile = activity_profile(health)
    # Two days: 6000 and 12000 steps -> mean 9000.
    assert profile.avg_daily_steps == 9000.0
    assert profile.active_days == 2
    assert profile.activity_level == "somewhat active"
    assert "Activity profile" in str(profile)


def test_daily_steps_series(health) -> None:
    series = daily_steps(health)
    assert len(series) == 2
    assert series.sum() == 18000.0


def test_vitals_summary(health) -> None:
    vitals = vitals_summary(health)
    assert vitals.resting_heart_rate == 52.0
    assert vitals.hrv_sdnn == 70.0
    # SpO2 stored as fraction 0.98 -> presented as 98%.
    assert round(vitals.oxygen_saturation, 1) == 98.0
    assert vitals.vo2_max == 50.0  # measured value in fixture


def test_estimate_vo2max_prefers_measured(health) -> None:
    est = estimate_vo2max(health)
    assert est.source == "measured"
    assert est.value == 50.0


def test_estimate_vo2max_falls_back_to_nes(export_dir) -> None:
    from helth import HealthExport

    # Load everything except the measured VO2max to force the Nes fallback.
    full = HealthExport.from_dir(export_dir)
    without_vo2 = HealthExport(
        personal=full.personal,
        records=[r for r in full.records if r.short_type != "VO2Max"],
        workouts=full.workouts,
        activity_summaries=full.activity_summaries,
    )
    est = estimate_vo2max(without_vo2)
    assert est.source == "estimated_nes_2011"
    # Sanity: Nes model yields a plausible VO2max for a fit young male.
    assert 30 < est.value < 70


def test_activity_percentiles(health) -> None:
    results = {r.metric: r for r in activity_percentiles(health)}
    steps = results["Daily steps"]
    # Fixture mean is 9000 steps/day -> comfortably above the ~6k median.
    assert steps.value == 9000.0
    assert 75 < steps.percentile < 90
    assert steps.higher_is_better is True
    assert steps.band in {"well above average", "top 20%"} or steps.percentile >= 75


def test_percentile_orientation_is_higher_is_better(health) -> None:
    # More steps must never rank lower than fewer steps.
    from helth.insights.percentiles import _STEPS_ANCHORS, _interp_percentile

    assert _interp_percentile(12000, _STEPS_ANCHORS) > _interp_percentile(
        4000, _STEPS_ANCHORS
    )


def test_fitness_percentiles_rhr_lower_is_better(health) -> None:
    results = {r.metric: r for r in fitness_percentiles(health)}
    rhr = results["Resting heart rate"]
    assert rhr.value == 52.0
    assert rhr.higher_is_better is False
    # A low RHR of 52 bpm should rank in the fitter (high) percentiles.
    assert rhr.percentile > 80


def test_fitness_percentiles_vo2max_labeled_aerobic(health) -> None:
    results = {r.metric: r for r in fitness_percentiles(health)}
    vo2 = results["VO2max (aerobic)"]
    assert vo2.value == 50.0
    assert "aerobic" in vo2.metric.lower()
    assert 0 <= vo2.percentile <= 100


def test_population_ranking_report(health) -> None:
    ranking = population_ranking(health)
    assert ranking.overall_activity_percentile is not None
    text = str(ranking)
    assert "Population ranking" in text
    # Must flag that cardio fitness is aerobic-only, not strength.
    assert "not strength" in text.lower()


def test_percentiles_without_sex_skips_vo2max(export_dir) -> None:
    from helth import HealthExport

    full = HealthExport.from_dir(export_dir)
    object.__setattr__(full.personal, "biological_sex", None)
    metrics = {r.metric for r in fitness_percentiles(full)}
    # VO2max norm is sex-specific, so it's omitted; RHR still ranks.
    assert "VO2max (aerobic)" not in metrics
    assert "Resting heart rate" in metrics
