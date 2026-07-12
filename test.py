"""Manual smoke test against the real Apple Health export in ./data/.

Run with:

    python test.py

Unlike the pytest suite (which uses a tiny synthetic fixture), this loads the
full export from ``data/apple_health_export`` and prints a set of insights.
"""

from __future__ import annotations

import time
from pathlib import Path

from helth import HealthExport
from helth.insights import (
    activity_profile,
    population_ranking,
    vitals_summary,
)

EXPORT_DIR = Path(__file__).parent / "data" / "apple_health_export"


def main() -> None:
    if not (EXPORT_DIR / "export.xml").exists():
        raise SystemExit(f"No export found at {EXPORT_DIR}")

    print(f"Loading {EXPORT_DIR}/export.xml ...")
    start = time.perf_counter()

    def progress(seen: int, kept: int) -> None:
        print(f"  parsed {seen:,} elements ({kept:,} records kept)", end="\r")

    health = HealthExport.from_dir(EXPORT_DIR, progress=progress)
    print()  # newline after the progress line
    print(f"Loaded in {time.perf_counter() - start:.1f}s\n")

    print(health.summary())
    print()
    print(activity_profile(health))
    print()
    print(vitals_summary(health))
    print()
    print(population_ranking(health))


if __name__ == "__main__":
    main()
