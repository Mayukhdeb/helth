# helth

![helth banner](assets/banner.jpg)

A small python library for reading **Apple Health** exports
and turning them into insights — activity levels, vitals, and population
percentile rankings.

It's built to handle the real thing: exports are often hundreds of megabytes
with millions of `<Record>` elements, so parsing is fully streaming and stays
memory-light. (A 160 MB / 340k-record export loads in ~7s.)

## Install

```bash
pip install -e .          # runtime dep: pandas
pip install -e ".[dev]"   # + pytest for the test suite
```

## Get your data

On iPhone: **Health app → profile → Export All Health Data**. Unzip it and
you'll get an `apple_health_export/` folder containing `export.xml`. Point
`helth` at that folder.

## Quick start

```python
from helth import HealthExport

health = HealthExport.from_dir("data/apple_health_export")
print(health.summary())

# Query raw records (short names or full HK identifiers both work)
steps = health.records_of_type("StepCount")
latest_weight = health.latest("BodyMass")

# Tidy pandas DataFrames for analysis / plotting
df = health.to_dataframe("HeartRate")
```

## Insights

```python
from helth.insights import (
    activity_profile,
    vitals_summary,
    population_ranking,
)

print(activity_profile(health))    # steps, active energy, exercise band
print(vitals_summary(health))      # resting HR, HRV, SpO2, VO2 max ...
print(population_ranking(health))  # percentile ranks vs the population
```

### Population percentile ranking (instead of a "biological age")

`helth` deliberately does **not** report a single biological-age number.
Any such number from wearable data is dominated by VO2max, which measures
*aerobic* fitness only and badly misrepresents strength-trained people — and
consumer devices simply don't measure the many systems a real biological-age
clock needs.

Instead you get **percentile ranks** across independent domains, so no one
metric dominates. Each answers: *what fraction of adults do you beat?*

```
Population ranking (vs general adult population)
==============================================================
Overall activity: P87 — well above average

Activity
--------------------------------------------------------------
Daily steps            16,330.5 steps     P  98  elite (top 3%)
Exercise minutes           47.2 min/day   P  92  top 8%
Active energy             440.2 kcal/day  P  71  above average

Cardio fitness (aerobic only — not strength)
--------------------------------------------------------------
Resting heart rate         59.8 bpm       P  63  above average
VO2max (aerobic)           43.1 mL/kg/min P  28  below average
```

Reference distributions are drawn from published population data — daily steps
(Paluch et al. 2022 / NHANES), resting heart rate (Health eHeart / NHANES),
exercise minutes (WHO/ACSM guidelines), and VO2max (FRIEND registry, Kaminsky
et al. 2015). They're population-level approximations, not clinical norms, and
the cardio section is explicitly aerobic-only — it says nothing about strength,
which Apple Health does not record.

You can also pull each part directly:

```python
from helth.insights import (
    activity_percentiles,   # [PercentileResult, ...]
    fitness_percentiles,    # aerobic only
    estimate_vo2max,        # VO2max value + provenance (measured vs Nes-estimated)
)
```

## HTML dashboard

Generate a single, self-contained interactive dashboard (Apple Watch Ultra–style
light theme) with population percentiles, long-term trends and time-of-day
patterns:

```bash
python -m helth.dashboard data/apple_health_export -o helth_dashboard.html
```

```python
from helth.dashboard import generate_dashboard
generate_dashboard(health, "helth_dashboard.html")
```

Long-term trend charts (steps/day, resting HR, HRV, calories per strength
session, sleep, …) each have a **time-window selector** (default: last 3
months) and a **smoothing knob** (Raw / 7 / 14 / 30-day rolling mean).

### Normal & athletic reference baselines (cited per field)

Every relevant chart overlays **two shaded reference ranges** — a *normal*
(general adult) band in indigo and an *athletic* (trained/elite) band in green —
each backed by a recent peer-reviewed source and cited in-plot and in the
dashboard footer. Bands are only drawn where the comparison is honest for the
data an Apple Watch records (e.g. short-window SDNN norms for HRV, not 24-hour
Holter SDNN).

| Field | Normal | Athletic | Sources |
|---|---|---|---|
| Resting heart rate | 60–100 bpm | 40–55 bpm | Avram 2019; Reimers 2018 |
| HRV (short-window SDNN) | 30–70 ms | 70–110 ms | Nunan 2010; Ziadia 2023 |
| Sleep per night | 7–9 h | 8–10 h | Hirshkowitz 2015; Mah 2011 |
| Steps per day | 5,000–7,500 | ≥10,000 | Tudor-Locke 2004; Paluch 2022 |
| Workout volume | — | ≥150 min/wk mod. | Bull 2020 (WHO) |

References:

- Avram R, Tison GH, Aschbacher K, et al. *Real-world heart rate norms in the
  Health eHeart study.* NPJ Digit Med. 2019;2:58.
  <https://pmc.ncbi.nlm.nih.gov/articles/PMC6592896/>
- Reimers AK, Knapp G, Reimers CD. *Effects of exercise on the resting heart
  rate: a systematic review & meta-analysis.* J Clin Med. 2018;7(12):503.
  <https://pubmed.ncbi.nlm.nih.gov/30513777/>
- Nunan D, Sandercock GRH, Brodie DA. *A quantitative systematic review of normal
  values for short-term heart rate variability in healthy adults.* Pacing Clin
  Electrophysiol. 2010;33(11):1407-1417.
  <https://pubmed.ncbi.nlm.nih.gov/20663071/>
- Ziadia H, Sassi I, Trudeau F, Fait P. *Normative values of resting heart rate
  variability in young male contact sport athletes.* Front Sports Act Living.
  2023;4:730401.
  <https://www.frontiersin.org/journals/sports-and-active-living/articles/10.3389/fspor.2022.730401/full>
- Hirshkowitz M, Whiton K, Albert SM, et al. *National Sleep Foundation's updated
  sleep duration recommendations.* Sleep Health. 2015;1(4):233-243.
  <https://www.sleephealthjournal.org/article/S2352-7218(15)00160-6/abstract>
- Mah CD, Mah KE, Kezirian EJ, Dement WC. *The effects of sleep extension on the
  athletic performance of collegiate basketball players.* Sleep.
  2011;34(7):943-950. <https://pubmed.ncbi.nlm.nih.gov/21731144/>
- Watson AM. *Sleep and athletic performance.* Curr Sports Med Rep.
  2017;16(6):413-418. <https://pubmed.ncbi.nlm.nih.gov/29135639/>
- Tudor-Locke C, Bassett DR Jr. *How many steps/day are enough? Preliminary
  pedometer indices for public health.* Sports Med. 2004;34(1):1-8.
  <https://pubmed.ncbi.nlm.nih.gov/14715035/>
- Paluch AE, Bajpai S, Bassett DR, et al. *Daily steps and all-cause mortality: a
  meta-analysis of 15 international cohorts.* Lancet Public Health.
  2022;7(3):e219-e228. <https://pmc.ncbi.nlm.nih.gov/articles/PMC9289978/>
- Bull FC, Al-Ansari SS, Biddle S, et al. *World Health Organization 2020
  guidelines on physical activity and sedentary behaviour.* Br J Sports Med.
  2020;54(24):1451-1462. <https://pubmed.ncbi.nlm.nih.gov/33239350/>

## Streaming huge files

`parse_export` materialises everything in one pass, but if you only need one
metric — or want constant memory — iterate:

```python
from helth import iter_records
from helth.constants import Quantity

for rec in iter_records("data/apple_health_export/export.xml",
                        types=[Quantity.HEART_RATE]):
    ...  # one Record at a time, nothing else held in memory
```

## Layout

```
helth/
  constants.py            # HK identifier helpers + friendly constants
  models.py               # frozen dataclasses: Record, Workout, Personal, ...
  parser.py               # streaming iterparse-based reader
  export.py               # HealthExport — the main entry point
  dashboard.py            # generate_dashboard — interactive HTML report
  insights/
    activity.py           # activity_profile, daily_steps
    vitals.py             # vitals_summary
    fitness.py            # estimate_vo2max (+ population CRF norms)
    percentiles.py        # population_ranking, activity/fitness percentiles
    patterns.py           # time-of-day / weekday / long-term trend analysis
    athlete_reference.py  # cited athlete baseline bands (HR, sleep)
```

## Tests

The pytest suite runs against a tiny synthetic fixture (fast, hermetic):

```bash
pytest -vvx tests
```

`test.py` is a manual smoke test that loads the full real export from `./data/`
and prints every insight:

```bash
python test.py
```
