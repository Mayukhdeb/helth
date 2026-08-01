"""Generate a beautiful, self-contained HTML dashboard from a Health export.

Usage (library)::

    from helth import HealthExport
    from helth.dashboard import generate_dashboard

    health = HealthExport.from_dir("data/apple_health_export")
    generate_dashboard(health, "helth_dashboard.html")

Usage (CLI)::

    python -m helth.dashboard data/apple_health_export -o helth_dashboard.html

The output is a single HTML file with interactive Plotly charts embedded and
Plotly loaded from CDN — open it in any browser, no server needed.
"""

from __future__ import annotations

import sys
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING, List, Optional

import pandas as pd
import plotly.graph_objects as go

from .constants import Quantity
from .insights import activity_profile, population_ranking, vitals_summary
from .insights.athlete_reference import (
    CITATIONS,
    HRV_NOTE,
    MetricBaseline,
    baseline_for,
    short_ref,
)
from .insights.patterns import (
    by_weekday,
    daily_trend,
    heart_rate_by_hour,
    heart_rate_histogram,
    highlights,
    hourly_sum,
    sleep_by_night,
    workout_breakdown,
    workout_metric_series,
)
from .insights.percentiles import PercentileResult

if TYPE_CHECKING:  # pragma: no cover
    from .export import HealthExport

# --- theme: Apple Watch Ultra (light titanium + International Orange) --------
_BG = "#f2f2f5"       # Apple system light grey
_CARD = "#ffffff"     # white cards
_GRID = "#e7e7ec"     # hairline grid / borders
_TEXT = "#1d1d1f"     # near-black ink
_MUTED = "#86868b"    # secondary grey
_ACCENT = "#ff6a00"   # Ultra "International Orange" — primary accent
_ACCENT2 = "#5e5ce6"  # Apple system indigo
_WARN = "#ff9500"     # Apple orange
_HOT = "#fa114f"      # activity-ring red (Move)
_TEAL = "#00c7be"     # activity-ring teal (Stand)
_GREEN = "#34c759"    # Apple system green

_FONT = (
    "-apple-system, BlinkMacSystemFont, 'SF Pro Display', 'SF Pro Text', "
    "'Segoe UI', Roboto, sans-serif"
)
_MONO = "ui-monospace, 'SF Mono', 'SFMono-Regular', Menlo, monospace"

# Long-term trends default to the last 3 months; smoothing "knob" offers these
# rolling windows (in days). 0 = raw. The 7-day window is selected by default.
DEFAULT_WINDOW_DAYS = 90
SMOOTHING_WINDOWS = (7, 14, 30)
DEFAULT_SMOOTHING = 7


def _layout(fig: go.Figure, title: str, height: int = 230) -> go.Figure:
    fig.update_layout(
        title=dict(text=title, font=dict(size=15, color=_TEXT)),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font=dict(family=_FONT, color=_MUTED, size=12),
        height=height,
        margin=dict(l=50, r=24, t=48, b=40),
        showlegend=False,
        hovermode="x unified",
    )
    fig.update_xaxes(gridcolor=_GRID, zeroline=False, linecolor=_GRID)
    fig.update_yaxes(gridcolor=_GRID, zeroline=False, linecolor=_GRID)
    return fig


def _hour_labels() -> List[str]:
    out = []
    for h in range(24):
        suffix = "a" if h < 12 else "p"
        out.append(f"{h % 12 or 12}{suffix}")
    return out


# --- reference baselines (normal + athletic bands, cited) ------------------
_NORMAL_FILL = "rgba(94,92,230,0.09)"   # indigo tint
_ATHLETIC_FILL = "rgba(52,199,89,0.14)"  # green tint
_NORMAL_INK = "#5e5ce6"
_ATHLETIC_INK = "#2a9648"


# Captions sit in the bottom margin, stacked, measured in pixels from the
# bottom of the plotting area so they never depend on the figure's height.
_CAP_TOP_PX = 30    # clearance for the x-axis ticks before the first line
_CAP_LINE_PX = 14
_CAP_PAD_PX = 8


def _add_caption(fig: go.Figure, text: str) -> None:
    """Add a small grey caption below the plot, stacked under any earlier one.

    The figure grows by exactly the space the caption needs, so captions never
    eat into the plotting area. Must be called *after* the figure's layout is
    set, since ``_layout`` resets both height and margins.
    """
    lines = sum(
        1 for a in (fig.layout.annotations or ()) if a.name == "helth-caption"
    )
    fig.add_annotation(
        name="helth-caption", text=text,
        x=0, xref="paper", xanchor="left",
        y=0, yref="paper", yanchor="top",
        yshift=-(_CAP_TOP_PX + lines * _CAP_LINE_PX),
        showarrow=False, align="left",
        font=dict(size=9, color=_MUTED),
    )
    needed = _CAP_TOP_PX + (lines + 1) * _CAP_LINE_PX + _CAP_PAD_PX
    current = fig.layout.margin.b or 0
    if needed > current:
        fig.update_layout(
            margin_b=needed, height=(fig.layout.height or 230) + needed - current
        )


def _data_max(fig: go.Figure, axis: str) -> Optional[float]:
    """Largest plotted value on ``axis`` ("x" or "y"), ignoring non-numerics."""
    best: Optional[float] = None
    for trace in fig.data:
        values = getattr(trace, axis, None)
        if values is None:
            continue
        for v in values:
            try:
                f = float(v)
            except (TypeError, ValueError):
                continue
            if f == f and (best is None or f > best):  # f == f skips NaN
                best = f
    return best


def _add_baselines(
    fig: go.Figure, baseline: "MetricBaseline", *, axis: Optional[str] = None
) -> None:
    """Shade the normal (indigo) and athletic (green) reference ranges.

    The ranges and their sources are named in a caption *below* the plot rather
    than inside it — in-plot labels collided with the data (bars especially).
    """
    axis = axis or baseline.axis
    specs = [
        ("Normal", baseline.normal, _NORMAL_FILL, _NORMAL_INK),
        ("Athlete", baseline.athletic, _ATHLETIC_FILL, _ATHLETIC_INK),
    ]
    # Shapes count towards axis autorange, so an open-ended band ("≥10,000
    # steps") must stop at the data — otherwise it stretches the axis and
    # squashes the actual bars into the bottom of the plot.
    top = _data_max(fig, axis)
    keys: List[str] = []
    for name, band, fill, ink in specs:
        if band.high is not None:
            high = band.high
        else:
            high = max(top, band.low * 1.05) if top is not None else band.low * 4
        common = dict(fillcolor=fill, line_width=0, layer="below")
        if axis == "x":
            fig.add_vrect(x0=band.low, x1=high, **common)
        else:
            fig.add_hrect(y0=band.low, y1=high, **common)
        keys.append(
            f'<span style="color:{ink}">▮</span> '
            f"{band.label(name, baseline.unit)} · {short_ref(band.citation_key)}"
        )
    _add_caption(fig, "&nbsp;&nbsp;&nbsp;".join(keys))


def _ref_note(fig: go.Figure, text: str) -> None:
    """Add a small grey citation caption under a chart."""
    _add_caption(fig, text)


# --- long-term trend figure (time-window + smoothing controls) -------------
def _rolling(series: pd.Series, window_days: int) -> pd.Series:
    """Time-based rolling mean; tolerates irregular (per-event) spacing."""
    if window_days <= 0:
        return series
    return series.rolling(f"{window_days}D", min_periods=1).mean()


def trend_figure(
    series: pd.Series,
    title: str,
    unit: str,
    *,
    kind: str = "markers",
    color: str = _ACCENT,
    height: int = 260,
    baseline: "Optional[MetricBaseline]" = None,
    note: Optional[str] = None,
) -> Optional[go.Figure]:
    """A long-term time series with range-selector, range-slider and a
    smoothing knob (Raw / 7 / 14 / 30-day rolling mean).

    ``series`` must be datetime-indexed and numeric. ``kind`` controls the raw
    layer: ``"markers"``, ``"bars"`` or ``"line"``. Opens on the last
    ``DEFAULT_WINDOW_DAYS`` days with the default smoothing applied.

    ``baseline`` overlays cited normal + athletic reference bands; ``note`` adds
    a small caption (defaults to the baseline's citations when given).
    """
    series = series.dropna()
    if series.empty:
        return None
    series = series.sort_index()

    fig = go.Figure()

    # Raw layer, kept faint so the smoothed line reads clearly on top.
    if kind == "bars":
        fig.add_trace(
            go.Bar(x=series.index, y=series.values, marker_color=color, opacity=0.35,
                   name="raw", hovertemplate="%{x|%b %d, %Y} · %{y:,.1f}<extra></extra>")
        )
    else:
        fig.add_trace(
            go.Scatter(
                x=series.index, y=series.values,
                mode="markers" if kind == "markers" else "lines",
                marker=dict(size=4, color=color),
                line=dict(color=color, width=1),
                opacity=0.35, name="raw",
                hovertemplate="%{x|%b %d, %Y} · %{y:,.1f}<extra></extra>",
            )
        )

    # One smoothed trace per window; visibility toggled by the smoothing knob.
    for w in SMOOTHING_WINDOWS:
        roll = _rolling(series, w)
        fig.add_trace(
            go.Scatter(
                x=roll.index, y=roll.values, mode="lines",
                line=dict(color=color, width=3, shape="spline"),
                name=f"{w}-day", visible=(w == DEFAULT_SMOOTHING),
                hovertemplate="%{x|%b %d, %Y} · %{y:,.1f} " + unit + "<extra></extra>",
            )
        )

    # Smoothing knob: each button sets which smoothed trace is visible.
    n_smooth = len(SMOOTHING_WINDOWS)

    def _vis(active: int) -> List[bool]:
        # index 0 is the always-on raw layer.
        return [True] + [i == active for i in range(n_smooth)]

    buttons = [
        dict(label="Smooth: Raw", method="update",
             args=[{"visible": [True] + [False] * n_smooth}])
    ]
    for i, w in enumerate(SMOOTHING_WINDOWS):
        buttons.append(
            dict(label=f"Smooth: {w}d", method="update", args=[{"visible": _vis(i)}])
        )
    default_active = 1 + list(SMOOTHING_WINDOWS).index(DEFAULT_SMOOTHING)

    # Default visible window: last DEFAULT_WINDOW_DAYS days.
    xmax = series.index.max()
    xmin = xmax - pd.Timedelta(days=DEFAULT_WINDOW_DAYS)

    _layout(fig, title, height=height)
    # Compact header: title (left) and the two control groups share one band
    # just above the plot, so there's no dead space between title and chart.
    fig.update_layout(
        title=dict(
            x=0, xanchor="left", y=0.99, yref="container", yanchor="top",
            font=dict(size=14, color=_TEXT),
        ),
        margin=dict(l=48, r=18, t=72, b=28),
        updatemenus=[
            dict(
                type="dropdown", direction="down", showactive=True,
                active=default_active, x=1, xanchor="right", y=1.03,
                yanchor="bottom",  # grows upward into the margin, never the plot
                pad=dict(r=2, t=2), bgcolor="#ececf0", bordercolor=_GRID,
                font=dict(color=_TEXT, size=10), buttons=buttons,
            )
        ],
    )
    # Reference bands go on after the layout, which resets height and margins.
    if baseline is not None:
        _add_baselines(fig, baseline)
    if note:
        _add_caption(fig, note)
    # Range-selector buttons only (no slider — the buttons + drag-zoom are
    # enough, and dropping the slider removes a chunk of vertical clutter).
    fig.update_xaxes(
        range=[xmin, xmax],
        rangeselector=dict(
            buttons=[
                dict(count=1, label="1m", step="month", stepmode="backward"),
                dict(count=3, label="3m", step="month", stepmode="backward"),
                dict(count=6, label="6m", step="month", stepmode="backward"),
                dict(count=1, label="1y", step="year", stepmode="backward"),
                dict(step="all", label="All"),
            ],
            bgcolor="#ececf0", activecolor=_ACCENT, bordercolor=_GRID,
            font=dict(color=_TEXT, size=10), x=0, xanchor="left",
            y=1.03, yanchor="bottom",
        ),
    )
    fig.update_yaxes(title_text=unit)
    return fig


# --- individual charts ------------------------------------------------------
def _fig_hr_by_hour(export: "HealthExport") -> Optional[go.Figure]:
    hr = heart_rate_by_hour(export)
    if hr.empty or hr["mean"].notna().sum() == 0:
        return None
    x = list(range(24))
    fig = go.Figure()
    # p10-p90 band
    fig.add_trace(
        go.Scatter(
            x=x + x[::-1],
            y=list(hr["p90"]) + list(hr["p10"])[::-1],
            fill="toself",
            fillcolor="rgba(250,17,79,0.10)",
            line=dict(color="rgba(0,0,0,0)"),
            hoverinfo="skip",
        )
    )
    fig.add_trace(
        go.Scatter(
            x=x,
            y=hr["mean"],
            mode="lines+markers",
            line=dict(color=_HOT, width=3, shape="spline"),
            marker=dict(size=5, color=_HOT),
            name="avg bpm",
        )
    )
    peak = int(hr["mean"].idxmax())
    fig.add_trace(
        go.Scatter(
            x=[peak],
            y=[hr["mean"].max()],
            mode="markers+text",
            marker=dict(size=13, color=_ACCENT, symbol="star"),
            text=[f" peak {hr['mean'].max():.0f}"],
            textposition="top center",
            textfont=dict(color=_ACCENT),
        )
    )
    fig.update_xaxes(tickmode="array", tickvals=x, ticktext=_hour_labels())
    _layout(fig, "Heart rate by time of day  ·  avg with 10–90% band")
    rhr = baseline_for("resting_heart_rate")
    if rhr is not None:
        _add_baselines(fig, rhr)  # resting-HR bands anchor the overnight lows
    return fig


def _fig_steps_by_hour(export: "HealthExport") -> Optional[go.Figure]:
    steps = hourly_sum(export, Quantity.STEP_COUNT)
    if steps.dropna().empty or steps.max() == 0:
        return None
    fig = go.Figure(
        go.Bar(
            x=list(range(24)),
            y=steps.values,
            marker=dict(color=steps.values, colorscale=[[0, _GRID], [1, _ACCENT2]]),
            hovertemplate="%{y:,.0f} steps<extra></extra>",
        )
    )
    fig.update_xaxes(tickmode="array", tickvals=list(range(24)), ticktext=_hour_labels())
    _layout(fig, "When you move  ·  average steps per hour of day")
    _ref_note(fig, "Per-hour steps; daily-total baselines shown on “Steps per day”.")
    return fig


def _fig_weekday(export: "HealthExport") -> Optional[go.Figure]:
    steps = by_weekday(export, Quantity.STEP_COUNT)
    if steps.dropna().empty:
        return None
    colors = [_ACCENT if v == steps.max() else _ACCENT2 for v in steps.values]
    fig = go.Figure(
        go.Bar(
            x=list(steps.index),
            y=steps.values,
            marker_color=colors,
            hovertemplate="%{y:,.0f} steps<extra></extra>",
        )
    )
    _layout(fig, "Which weekdays you move most  ·  avg steps", height=230)
    steps_bl = baseline_for("steps")
    if steps_bl is not None:
        _add_baselines(fig, steps_bl)
    return fig


def _fig_hr_hist(export: "HealthExport") -> Optional[go.Figure]:
    hist = heart_rate_histogram(export)
    if hist.empty:
        return None
    fig = go.Figure(
        go.Bar(
            x=hist["bpm"],
            y=hist["count"],
            marker_color=_HOT,
            hovertemplate="%{x:.0f} bpm · %{y:,} samples<extra></extra>",
        )
    )
    _layout(fig, "Heart rate distribution  ·  all samples", height=230)
    rhr = baseline_for("resting_heart_rate")
    if rhr is not None:
        _add_baselines(fig, rhr, axis="x")  # bpm on the x-axis here
    return fig


# --- long-term trend builders (full width, with controls) ------------------
def _long_term_figures(export: "HealthExport") -> List[go.Figure]:
    """Every long-term trend that has data, each with window + smoothing knobs."""
    figs: List[go.Figure] = []

    def add(series: pd.Series, title: str, unit: str, **kw) -> None:
        fig = trend_figure(series, title, unit, **kw)
        if fig is not None:
            figs.append(fig)

    add(
        daily_trend(export, Quantity.STEP_COUNT, how="sum"),
        "Steps per day", "steps", kind="bars", color=_ACCENT2,
        baseline=baseline_for("steps"),
    )
    add(
        daily_trend(export, Quantity.RESTING_HEART_RATE, how="mean"),
        "Resting heart rate", "bpm", kind="markers", color=_HOT,
        baseline=baseline_for("resting_heart_rate"),
    )
    add(
        daily_trend(export, Quantity.HEART_RATE_VARIABILITY_SDNN, how="mean"),
        "Heart rate variability (SDNN)", "ms", kind="markers", color=_TEAL,
        baseline=baseline_for("hrv_sdnn"), note=HRV_NOTE,
    )
    add(
        daily_trend(export, Quantity.ACTIVE_ENERGY_BURNED, how="sum"),
        "Active energy per day", "kcal", kind="bars", color=_ACCENT,
        note="No standard population baseline for active-energy kcal.",
    )
    add(
        workout_metric_series(export, "TraditionalStrengthTraining", metric="energy"),
        "Calories per strength-training session", "kcal",
        kind="markers", color=_ACCENT,
        note="Per-session energy; no population reference band.",
    )
    add(
        workout_metric_series(export, "Walking", metric="energy"),
        "Calories per walking workout", "kcal", kind="markers", color=_TEAL,
        note="Per-workout energy; no population reference band.",
    )
    add(
        sleep_by_night(export), "Sleep per night", "hours", kind="bars",
        color=_ACCENT2, baseline=baseline_for("sleep_hours"),
    )
    add(
        daily_trend(export, Quantity.BODY_MASS, how="mean"),
        "Body mass", "kg", kind="markers", color=_MUTED,
        note="Healthy weight is height-dependent (BMI 18.5–24.9); no fixed kg band.",
    )
    return figs


def _fig_workouts(export: "HealthExport") -> Optional[go.Figure]:
    wk = workout_breakdown(export)
    if wk.empty:
        return None
    fig = go.Figure(
        go.Bar(
            x=wk["minutes"], y=wk["activity"], orientation="h",
            marker_color=_ACCENT2,
            text=[f"{c} sessions" for c in wk["count"]],
            textposition="auto",
            hovertemplate="%{y} · %{x:,.0f} min<extra></extra>",
        )
    )
    fig.update_yaxes(autorange="reversed")
    _layout(fig, "Workouts  ·  total minutes by activity", height=230)
    _ref_note(
        fig,
        "WHO adults: ≥150 min/week moderate or ≥75 min vigorous activity "
        "(Bull 2020, Br J Sports Med).",
    )
    return fig


# --- HTML assembly ----------------------------------------------------------
@dataclass
class _Section:
    fig: go.Figure
    span: int  # grid columns (1 or 2)


def _percentile_bar_html(r: PercentileResult) -> str:
    pct = r.percentile
    color = _GREEN if pct >= 70 else _WARN if pct >= 45 else _HOT
    val = f"{r.value:,.0f}" if r.value >= 100 else f"{r.value:,.1f}"
    return f"""
    <div class="prow">
      <div class="pmeta"><span class="pname">{r.metric}</span>
        <span class="pval">{val} {r.unit}</span></div>
      <div class="ptrack"><div class="pfill" style="width:{pct:.0f}%;background:{color}"></div>
        <div class="pmarker"></div></div>
      <div class="ppct" style="color:{color}">P{pct:.0f} · {r.band}</div>
    </div>"""


def _render_html(
    export: "HealthExport",
    trend_figures: List[go.Figure],
    pattern_sections: List[_Section],
) -> str:
    personal = export.personal
    span = export.date_range()
    sub_bits: List[str] = []
    if personal is not None:
        if personal.biological_sex:
            sub_bits.append(personal.biological_sex)
        age = personal.age_years()
        if age is not None:
            sub_bits.append(f"{age:.0f} years")
    if span is not None:
        sub_bits.append(f"{span[0].date()} → {span[1].date()}")
    subtitle = "  ·  ".join(sub_bits)

    hl_html = "".join(
        f'<div class="hl"><div class="hlt">{h.title}</div>'
        f'<div class="hld">{h.detail}</div></div>'
        for h in highlights(export)
    )

    ranking = population_ranking(export)
    act_html = "".join(_percentile_bar_html(r) for r in ranking.activity)
    fit_html = "".join(_percentile_bar_html(r) for r in ranking.fitness)

    profile = activity_profile(export)
    vitals = vitals_summary(export)
    stat_cards = _stat_cards(export, profile, vitals)

    # Plotly JS is embedded once (on the very first figure), then reused.
    embed = _FigureEmbedder()
    trend_html = "".join(f'<div class="card">{embed(f)}</div>' for f in trend_figures)
    fig_html = "".join(
        f'<div class="card">{embed(s.fig)}</div>' for s in pattern_sections
    )

    citations_html = "".join(
        f'<li><a href="{c.url}" target="_blank" rel="noopener">{c.text}</a></li>'
        for c in CITATIONS
    )

    generated = datetime.now().strftime("%Y-%m-%d %H:%M")
    return _TEMPLATE.format(
        css=_CSS,
        subtitle=subtitle,
        highlights=hl_html,
        stat_cards=stat_cards,
        activity_bars=act_html,
        fitness_bars=fit_html,
        trend_figures=trend_html,
        figures=fig_html,
        citations=citations_html,
        generated=generated,
    )


class _FigureEmbedder:
    """Embeds Plotly figures, loading plotly.js from CDN only once."""

    def __init__(self) -> None:
        self._loaded = False

    def __call__(self, fig: go.Figure) -> str:
        include = "cdn" if not self._loaded else False
        self._loaded = True
        return fig.to_html(
            full_html=False, include_plotlyjs=include,
            config={"displayModeBar": False},
        )


def _stat_cards(export, profile, vitals) -> str:
    cards = []

    def card(label: str, value: str) -> str:
        return f'<div class="stat"><div class="sv">{value}</div><div class="sl">{label}</div></div>'

    if profile.avg_daily_steps is not None:
        cards.append(card("avg steps / day", f"{profile.avg_daily_steps:,.0f}"))
    if vitals.resting_heart_rate is not None:
        cards.append(card("resting HR", f"{vitals.resting_heart_rate:.0f} bpm"))
    if vitals.hrv_sdnn is not None:
        cards.append(card("HRV (SDNN)", f"{vitals.hrv_sdnn:.0f} ms"))
    if vitals.vo2_max is not None:
        cards.append(card("VO₂ max", f"{vitals.vo2_max:.1f}"))
    cards.append(card("records", f"{len(export.records):,}"))
    cards.append(card("workouts", f"{len(export.workouts):,}"))
    return "".join(cards)


def generate_dashboard(
    export: "HealthExport", output_path: str = "helth_dashboard.html"
) -> Path:
    """Build the HTML dashboard for ``export`` and write it to ``output_path``.

    Returns the path to the written file. Charts with no underlying data are
    silently skipped, so the dashboard adapts to whatever the export contains.
    """
    trend_figures = _long_term_figures(export)

    builders = [
        _fig_hr_by_hour,
        _fig_steps_by_hour,
        _fig_weekday,
        _fig_hr_hist,
        _fig_workouts,
    ]
    sections: List[_Section] = []
    for build in builders:
        fig = build(export)
        if fig is not None:
            sections.append(_Section(fig=fig, span=1))

    html = _render_html(export, trend_figures, sections)
    path = Path(output_path)
    path.write_text(html, encoding="utf-8")
    return path


# --- static assets ----------------------------------------------------------
_CSS = """
* { box-sizing: border-box; }
:root {
  --bg:#f2f2f5; --card:#ffffff; --ink:#1d1d1f; --muted:#86868b;
  --line:#e7e7ec; --orange:#ff6a00; --indigo:#5e5ce6; --track:#ececf0;
}
body { margin:0; color:var(--ink); font-family:__FONT__;
  background:
    radial-gradient(1200px 500px at 100% -10%, rgba(255,106,0,0.06), transparent 60%),
    radial-gradient(900px 500px at -10% 0%, rgba(94,92,230,0.05), transparent 55%),
    var(--bg);
  -webkit-font-smoothing:antialiased; }
.wrap { max-width:1320px; margin:0 auto; padding:18px 18px 40px; }

/* Compact Ultra-style titanium hero */
.hero { position:relative; border-radius:18px; padding:14px 20px;
  background:linear-gradient(135deg,#fbfbfd 0%,#ececed 45%,#e2e2e6 100%);
  border:1px solid #dedee3;
  box-shadow:0 1px 0 #ffffff inset, 0 6px 18px rgba(0,0,0,0.05);
  margin-bottom:14px; overflow:hidden;
  display:flex; align-items:baseline; gap:14px; flex-wrap:wrap; }
.hero::before { content:""; position:absolute; left:0; top:0; bottom:0; width:5px;
  background:linear-gradient(180deg,#ff8a00,var(--orange)); }
.hero h1 { font-size:22px; margin:0; letter-spacing:-0.5px; font-weight:800; }
.hero .sub { color:var(--muted); font-size:13px; font-weight:500; }
.tag { font-size:10px; font-weight:800; letter-spacing:2px; text-transform:uppercase;
  color:var(--orange); font-family:__MONO__; }

/* highlights as slim pills */
.hlgrid { display:flex; flex-wrap:wrap; gap:10px; margin-bottom:14px; }
.hl { background:var(--card); border:1px solid var(--line); border-radius:12px;
  padding:8px 12px 8px 14px; position:relative; flex:1 1 240px;
  box-shadow:0 3px 10px rgba(0,0,0,0.03); }
.hl::before { content:""; position:absolute; left:0; top:9px; bottom:9px; width:3px;
  border-radius:3px; background:var(--orange); }
.hlt { color:var(--ink); font-weight:700; font-size:13px; }
.hld { color:var(--muted); font-size:11.5px; line-height:1.35; }

.stats { display:grid; grid-template-columns:repeat(auto-fit,minmax(110px,1fr));
  gap:10px; margin-bottom:16px; }
.stat { background:var(--card); border:1px solid var(--line); border-radius:12px;
  padding:10px 13px; box-shadow:0 3px 10px rgba(0,0,0,0.03); }
.sv { font-size:21px; font-weight:800; color:var(--ink); font-family:__MONO__;
  letter-spacing:-1px; font-variant-numeric:tabular-nums; }
.sl { font-size:9.5px; color:var(--muted); text-transform:uppercase;
  letter-spacing:0.8px; margin-top:2px; font-weight:600; }

.section-title.big { font-size:15px; color:var(--ink); margin:18px 0 10px;
  letter-spacing:-0.2px; font-weight:800; }
.section-title .hint { font-size:11.5px; color:var(--muted); font-weight:500;
  letter-spacing:0; }

.panel { display:grid; grid-template-columns:1fr 1fr; gap:6px 28px;
  background:var(--card); border:1px solid var(--line); border-radius:16px;
  padding:14px 18px; margin-bottom:8px; box-shadow:0 5px 18px rgba(0,0,0,0.04); }
.panel .col-title { font-size:11px; text-transform:uppercase;
  letter-spacing:1px; color:var(--muted); font-weight:700; margin:0 0 4px; }
.prow { display:grid; grid-template-columns:150px 1fr 128px; align-items:center;
  gap:12px; padding:5px 0; }
.pmeta { display:flex; flex-direction:column; }
.pname { font-weight:700; font-size:12.5px; }
.pval { color:var(--muted); font-size:11px; font-family:__MONO__;
  font-variant-numeric:tabular-nums; }
.ptrack { position:relative; height:8px; background:var(--track); border-radius:5px; }
.pfill { position:absolute; height:100%; border-radius:5px; }
.pmarker { position:absolute; left:50%; top:-3px; width:2px; height:14px;
  background:#c7c7cc; border-radius:2px; }
.ppct { font-size:11.5px; font-weight:700; text-align:right; font-family:__MONO__;
  font-variant-numeric:tabular-nums; }

.grid { display:grid; grid-template-columns:1fr 1fr; gap:12px; }
.grid.grid3 { grid-template-columns:repeat(3,1fr); }
.card { background:var(--card); border:1px solid var(--line); border-radius:14px;
  padding:4px 8px; overflow:hidden; box-shadow:0 5px 18px rgba(0,0,0,0.04);
  transition:box-shadow .2s ease, transform .2s ease; }
.card:hover { box-shadow:0 8px 24px rgba(0,0,0,0.07); transform:translateY(-1px); }
.span2 { grid-column:1 / -1; }

.refs { margin-top:18px; background:var(--card); border:1px solid var(--line);
  border-radius:14px; padding:12px 18px; box-shadow:0 3px 10px rgba(0,0,0,0.03); }
.refs-title { font-size:11px; text-transform:uppercase; letter-spacing:1px;
  color:var(--ink); font-weight:800; margin-bottom:6px; }
.refs ul { margin:0 0 6px; padding-left:18px; }
.refs li { font-size:11px; color:var(--muted); line-height:1.5; margin-bottom:2px; }
.refs a { color:var(--indigo); text-decoration:none; }
.refs a:hover { text-decoration:underline; }
.refs-note { font-size:10.5px; color:var(--muted); line-height:1.5; }
@media (max-width:900px){ .grid.grid3{grid-template-columns:1fr 1fr;} }
@media (max-width:760px){ .grid,.grid.grid3{grid-template-columns:1fr;}
  .panel{grid-template-columns:1fr;} .prow{grid-template-columns:130px 1fr 96px;} }
""".replace("__FONT__", _FONT).replace("__MONO__", _MONO)

_TEMPLATE = """<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>helth dashboard</title>
<style>{css}</style></head>
<body><div class="wrap">
  <div class="hero">
    <div class="tag">HELTH · ULTRA</div>
    <h1>Health Dashboard</h1>
    <div class="sub">{subtitle}</div>
  </div>

  <div class="hlgrid">{highlights}</div>
  <div class="stats">{stat_cards}</div>

  <div class="panel">
    <div class="pcol">
      <div class="col-title">Activity · vs general adult population</div>
      {activity_bars}
    </div>
    <div class="pcol">
      <div class="col-title">Cardio fitness · aerobic only, not strength</div>
      {fitness_bars}
    </div>
  </div>

  <div class="section-title big">Long-term trends
    <span class="hint">· window (default 3 mo) + smoothing · green band = athlete baseline</span>
  </div>
  <div class="grid">{trend_figures}</div>

  <div class="section-title big">Patterns · time of day &amp; weekly rhythm</div>
  <div class="grid grid3">{figures}</div>

  <div class="refs">
    <div class="refs-title">Athlete baselines &amp; references</div>
    <ul>{citations}</ul>
    <div class="refs-note">
      Green bands mark trained/elite-athlete ranges: resting HR ≈ 40–55 bpm
      (Reimers 2018) and sleep ≈ 8–10 h/night (Mah 2011, Watson 2017). HRV note
      per Kiss 2016. Percentile bars compare you to the general adult population
      (steps: Paluch 2022/NHANES · resting HR: Health eHeart/NHANES · exercise:
      WHO/ACSM · VO₂max: FRIEND registry). Cardio fitness is aerobic-only and
      says nothing about strength. Times in your local recorded timezone.
      Informational only — not medical advice. · Generated {generated} by helth.
    </div>
  </div>
</div></body></html>"""


def _main(argv: Optional[List[str]] = None) -> None:
    import argparse

    from .export import HealthExport

    parser = argparse.ArgumentParser(description="Generate an HTML health dashboard.")
    parser.add_argument(
        "export_dir",
        nargs="?",
        default="data/apple_health_export",
        help="Path to the apple_health_export directory.",
    )
    parser.add_argument(
        "-o", "--output", default="helth_dashboard.html", help="Output HTML path."
    )
    args = parser.parse_args(argv)

    print(f"Loading {args.export_dir} …", file=sys.stderr)
    health = HealthExport.from_dir(args.export_dir)
    path = generate_dashboard(health, args.output)
    print(f"✅ Wrote {path.resolve()}", file=sys.stderr)


if __name__ == "__main__":
    _main()
