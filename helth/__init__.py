"""helth — read Apple Health exports and turn them into insights.

Quick start::

    from helth import HealthExport

    health = HealthExport.from_dir("data/apple_health_export")
    print(health.summary())

    from helth.insights import population_ranking
    print(population_ranking(health))
"""

from .constants import Category, Quantity
from .export import HealthExport
from .models import ActivitySummary, Personal, Record, Workout
from .parser import iter_records, parse_export

__version__ = "0.1.0"

__all__ = [
    "HealthExport",
    "Record",
    "Workout",
    "ActivitySummary",
    "Personal",
    "Quantity",
    "Category",
    "iter_records",
    "parse_export",
    "__version__",
]
