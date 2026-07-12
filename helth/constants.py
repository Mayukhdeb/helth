"""Apple HealthKit identifier constants and helpers.

Apple exports every metric under a verbose ``HK...TypeIdentifier`` name.
This module centralises the prefixes and provides helpers to convert between
the full identifiers and friendly short names (e.g. ``StepCount``).
"""

from __future__ import annotations

from typing import Final

#: Prefixes Apple uses for the ``type`` attribute of ``<Record>`` elements.
QUANTITY_TYPE_PREFIX: Final = "HKQuantityTypeIdentifier"
CATEGORY_TYPE_PREFIX: Final = "HKCategoryTypeIdentifier"
CHARACTERISTIC_TYPE_PREFIX: Final = "HKCharacteristicTypeIdentifier"
WORKOUT_TYPE_PREFIX: Final = "HKWorkoutActivityType"

#: Every prefix that can appear on a record/workout ``type``-like attribute.
_ALL_PREFIXES: Final = (
    QUANTITY_TYPE_PREFIX,
    CATEGORY_TYPE_PREFIX,
    CHARACTERISTIC_TYPE_PREFIX,
    WORKOUT_TYPE_PREFIX,
)

#: Value prefix used by categorical records such as sleep stages.
CATEGORY_VALUE_PREFIX: Final = "HKCategoryValue"


def short_name(identifier: str) -> str:
    """Strip the ``HK...`` prefix from an identifier.

    >>> short_name("HKQuantityTypeIdentifierStepCount")
    'StepCount'
    >>> short_name("HKCategoryValueSleepAnalysisAsleepDeep")
    'SleepAnalysisAsleepDeep'
    >>> short_name("count")
    'count'
    """
    for prefix in (*_ALL_PREFIXES, CATEGORY_VALUE_PREFIX):
        if identifier.startswith(prefix):
            return identifier[len(prefix) :]
    return identifier


def quantity_type(name: str) -> str:
    """Expand a short name into a full quantity identifier.

    >>> quantity_type("StepCount")
    'HKQuantityTypeIdentifierStepCount'
    """
    if name.startswith(QUANTITY_TYPE_PREFIX):
        return name
    return f"{QUANTITY_TYPE_PREFIX}{name}"


def category_type(name: str) -> str:
    """Expand a short name into a full category identifier."""
    if name.startswith(CATEGORY_TYPE_PREFIX):
        return name
    return f"{CATEGORY_TYPE_PREFIX}{name}"


# ---------------------------------------------------------------------------
# Commonly used identifiers, exposed as constants for autocomplete-friendly use.
# ---------------------------------------------------------------------------
class Quantity:
    """Frequently used ``HKQuantityTypeIdentifier`` values."""

    STEP_COUNT: Final = "HKQuantityTypeIdentifierStepCount"
    DISTANCE_WALKING_RUNNING: Final = "HKQuantityTypeIdentifierDistanceWalkingRunning"
    ACTIVE_ENERGY_BURNED: Final = "HKQuantityTypeIdentifierActiveEnergyBurned"
    BASAL_ENERGY_BURNED: Final = "HKQuantityTypeIdentifierBasalEnergyBurned"
    HEART_RATE: Final = "HKQuantityTypeIdentifierHeartRate"
    RESTING_HEART_RATE: Final = "HKQuantityTypeIdentifierRestingHeartRate"
    WALKING_HEART_RATE_AVERAGE: Final = "HKQuantityTypeIdentifierWalkingHeartRateAverage"
    HEART_RATE_VARIABILITY_SDNN: Final = "HKQuantityTypeIdentifierHeartRateVariabilitySDNN"
    HEART_RATE_RECOVERY: Final = "HKQuantityTypeIdentifierHeartRateRecoveryOneMinute"
    VO2_MAX: Final = "HKQuantityTypeIdentifierVO2Max"
    RESPIRATORY_RATE: Final = "HKQuantityTypeIdentifierRespiratoryRate"
    OXYGEN_SATURATION: Final = "HKQuantityTypeIdentifierOxygenSaturation"
    BODY_MASS: Final = "HKQuantityTypeIdentifierBodyMass"
    BODY_MASS_INDEX: Final = "HKQuantityTypeIdentifierBodyMassIndex"
    BODY_FAT_PERCENTAGE: Final = "HKQuantityTypeIdentifierBodyFatPercentage"
    HEIGHT: Final = "HKQuantityTypeIdentifierHeight"
    EXERCISE_TIME: Final = "HKQuantityTypeIdentifierAppleExerciseTime"
    STAND_TIME: Final = "HKQuantityTypeIdentifierAppleStandTime"
    FLIGHTS_CLIMBED: Final = "HKQuantityTypeIdentifierFlightsClimbed"
    WALKING_SPEED: Final = "HKQuantityTypeIdentifierWalkingSpeed"


class Category:
    """Frequently used ``HKCategoryTypeIdentifier`` values."""

    SLEEP_ANALYSIS: Final = "HKCategoryTypeIdentifierSleepAnalysis"
    STAND_HOUR: Final = "HKCategoryTypeIdentifierAppleStandHour"
    MINDFUL_SESSION: Final = "HKCategoryTypeIdentifierMindfulSession"
