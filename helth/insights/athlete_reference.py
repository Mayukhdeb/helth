"""Peer-reviewed reference baselines — normal and athletic — for each metric.

For every metric the dashboard plots, we attach two shaded reference ranges:

* a **normal** (general adult) band, and
* an **athletic** (trained / elite) band,

each backed by a recent peer-reviewed source. Bands are only defined where the
comparison is honest for the data an Apple Watch actually records (e.g. we use
*short-window* SDNN norms for HRV, not 24-hour Holter SDNN).

Every band references a :class:`Citation`; the dashboard renders these in-plot
and in its sources footer, and the README lists them.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple


@dataclass(frozen=True)
class Citation:
    key: str
    text: str
    url: str


@dataclass(frozen=True)
class Band:
    """A reference range. ``high=None`` means open-ended (``≥ low``)."""

    low: float
    high: Optional[float]
    citation_key: str

    def label(self, prefix: str, unit: str) -> str:
        u = f" {unit}" if unit else ""
        if self.high is None:
            return f"{prefix} ≥{self.low:g}{u}"
        return f"{prefix} {self.low:g}–{self.high:g}{u}"


@dataclass(frozen=True)
class MetricBaseline:
    """Normal + athletic reference bands for one metric, with orientation."""

    metric: str
    unit: str
    normal: Band
    athletic: Band
    #: "y" -> horizontal bands (value on y-axis); "x" -> vertical (value on x).
    axis: str = "y"

    def citation_keys(self) -> Tuple[str, ...]:
        return (self.normal.citation_key, self.athletic.citation_key)


# --- citations (latest peer-reviewed sources per field) ---------------------
CITATIONS: List[Citation] = [
    Citation(
        "Avram2019",
        "Avram R, Tison GH, Aschbacher K, et al. Real-world heart rate norms in "
        "the Health eHeart study. NPJ Digit Med. 2019;2:58.",
        "https://pmc.ncbi.nlm.nih.gov/articles/PMC6592896/",
    ),
    Citation(
        "Reimers2018",
        "Reimers AK, Knapp G, Reimers CD. Effects of exercise on the resting "
        "heart rate: a systematic review & meta-analysis. J Clin Med. "
        "2018;7(12):503.",
        "https://pubmed.ncbi.nlm.nih.gov/30513777/",
    ),
    Citation(
        "Nunan2010",
        "Nunan D, Sandercock GRH, Brodie DA. A quantitative systematic review of "
        "normal values for short-term heart rate variability in healthy adults. "
        "Pacing Clin Electrophysiol. 2010;33(11):1407-1417.",
        "https://pubmed.ncbi.nlm.nih.gov/20663071/",
    ),
    Citation(
        "Ziadia2023",
        "Ziadia H, Sassi I, Trudeau F, Fait P. Normative values of resting heart "
        "rate variability in young male contact sport athletes. Front Sports Act "
        "Living. 2023;4:730401.",
        "https://www.frontiersin.org/journals/sports-and-active-living/articles/10.3389/fspor.2022.730401/full",
    ),
    Citation(
        "Hirshkowitz2015",
        "Hirshkowitz M, Whiton K, Albert SM, et al. National Sleep Foundation's "
        "updated sleep duration recommendations. Sleep Health. 2015;1(4):233-243.",
        "https://www.sleephealthjournal.org/article/S2352-7218(15)00160-6/abstract",
    ),
    Citation(
        "Mah2011",
        "Mah CD, Mah KE, Kezirian EJ, Dement WC. The effects of sleep extension "
        "on the athletic performance of collegiate basketball players. Sleep. "
        "2011;34(7):943-950.",
        "https://pubmed.ncbi.nlm.nih.gov/21731144/",
    ),
    Citation(
        "Watson2017",
        "Watson AM. Sleep and athletic performance. Curr Sports Med Rep. "
        "2017;16(6):413-418.",
        "https://pubmed.ncbi.nlm.nih.gov/29135639/",
    ),
    Citation(
        "TudorLocke2004",
        "Tudor-Locke C, Bassett DR Jr. How many steps/day are enough? Preliminary "
        "pedometer indices for public health. Sports Med. 2004;34(1):1-8.",
        "https://pubmed.ncbi.nlm.nih.gov/14715035/",
    ),
    Citation(
        "Paluch2022",
        "Paluch AE, Bajpai S, Bassett DR, et al. Daily steps and all-cause "
        "mortality: a meta-analysis of 15 international cohorts. Lancet Public "
        "Health. 2022;7(3):e219-e228.",
        "https://pmc.ncbi.nlm.nih.gov/articles/PMC9289978/",
    ),
    Citation(
        "Bull2020",
        "Bull FC, Al-Ansari SS, Biddle S, et al. World Health Organization 2020 "
        "guidelines on physical activity and sedentary behaviour. Br J Sports "
        "Med. 2020;54(24):1451-1462.",
        "https://pubmed.ncbi.nlm.nih.gov/33239350/",
    ),
]

CITATIONS_BY_KEY: Dict[str, Citation] = {c.key: c for c in CITATIONS}


# --- per-metric baselines ---------------------------------------------------
BASELINES: Dict[str, MetricBaseline] = {
    # Resting HR: normal adult 60-100 bpm (Health eHeart real-world norms);
    # endurance-trained ~40-55 bpm (exercise lowers RHR, Reimers meta-analysis).
    "resting_heart_rate": MetricBaseline(
        metric="resting_heart_rate", unit="bpm",
        normal=Band(60, 100, "Avram2019"),
        athletic=Band(40, 55, "Reimers2018"),
    ),
    # Short-window SDNN: healthy-adult 5-min norm ≈ 50 ms, ~30-70 range
    # (Nunan meta-analysis); trained athletes elevated, ~70-110 ms (Ziadia).
    "hrv_sdnn": MetricBaseline(
        metric="hrv_sdnn", unit="ms",
        normal=Band(30, 70, "Nunan2010"),
        athletic=Band(70, 110, "Ziadia2023"),
    ),
    # Sleep: general adult recommendation 7-9 h (NSF); elite-athlete 8-10 h,
    # with performance gains on extension toward ~10 h (Mah).
    "sleep_hours": MetricBaseline(
        metric="sleep_hours", unit="h",
        normal=Band(7, 9, "Hirshkowitz2015"),
        athletic=Band(8, 10, "Mah2011"),
    ),
    # Steps/day: "somewhat active" ~5,000-7,500 (Tudor-Locke indices); "active"
    # to "highly active" ≥10,000 (mortality benefit plateaus ~8-10k, Paluch).
    "steps": MetricBaseline(
        metric="steps", unit="",
        normal=Band(5000, 7500, "TudorLocke2004"),
        athletic=Band(10000, None, "Paluch2022"),
    ),
}

# HRV window caveat surfaced next to the HRV chart.
HRV_NOTE = (
    "Apple records short-window SDNN; bands use short-term norms (Nunan 2010) "
    "and young-athlete data (Ziadia 2023). Treat as directional — higher is "
    "generally better."
)


def baseline_for(metric: str) -> Optional[MetricBaseline]:
    return BASELINES.get(metric)


def citation_for_key(key: str) -> Citation:
    return CITATIONS_BY_KEY[key]


def note_for(baseline: MetricBaseline) -> str:
    """Short in-plot caption naming the two sources behind the bands."""
    keys = []
    for key in baseline.citation_keys():
        if key not in keys:
            keys.append(key)
    refs = " · ".join(_short_ref(CITATIONS_BY_KEY[k]) for k in keys)
    return f"Baselines — {refs}"


def short_ref(key: str) -> str:
    """e.g. 'Reimers 2018' for citation key ``Reimers2018``."""
    return _short_ref(CITATIONS_BY_KEY[key])


def _short_ref(c: Citation) -> str:
    """e.g. 'Reimers 2018'."""
    author = c.text.split(" ")[0].rstrip(",")
    year = "".join(ch for ch in c.key if ch.isdigit())
    return f"{author} {year}"
