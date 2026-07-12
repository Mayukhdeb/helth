"""Shared fixtures: a tiny synthetic Apple Health export.

Tests run against this in-memory fixture rather than the real (160 MB) export,
so they're fast and hermetic.
"""

from __future__ import annotations

from pathlib import Path

import pytest

# A compact but representative export.xml covering every element the parser
# understands: Me, quantity Records, a category (sleep) Record with metadata,
# a Workout, and an ActivitySummary.
SAMPLE_EXPORT_XML = """<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE HealthData [<!ELEMENT HealthData (Me|Record|Workout|ActivitySummary)*>]>
<HealthData locale="en_GB">
 <ExportDate value="2026-07-12 10:00:00 +0100"/>
 <Me HKCharacteristicTypeIdentifierDateOfBirth="2000-11-09"
     HKCharacteristicTypeIdentifierBiologicalSex="HKBiologicalSexMale"
     HKCharacteristicTypeIdentifierBloodType="HKBloodTypeNotSet"
     HKCharacteristicTypeIdentifierFitzpatrickSkinType="HKFitzpatrickSkinTypeNotSet"/>
 <Record type="HKQuantityTypeIdentifierStepCount" unit="count" sourceName="Watch"
   creationDate="2026-05-01 09:00:00 +0100" startDate="2026-05-01 08:00:00 +0100"
   endDate="2026-05-01 09:00:00 +0100" value="6000"/>
 <Record type="HKQuantityTypeIdentifierStepCount" unit="count" sourceName="Watch"
   creationDate="2026-05-02 09:00:00 +0100" startDate="2026-05-02 08:00:00 +0100"
   endDate="2026-05-02 09:00:00 +0100" value="12000"/>
 <Record type="HKQuantityTypeIdentifierActiveEnergyBurned" unit="kcal" sourceName="Watch"
   startDate="2026-05-01 08:00:00 +0100" endDate="2026-05-01 09:00:00 +0100" value="150.5"/>
 <Record type="HKQuantityTypeIdentifierHeartRate" unit="count/min" sourceName="Watch"
   startDate="2026-05-01 07:00:00 +0100" endDate="2026-05-01 07:00:00 +0100" value="58"/>
 <Record type="HKQuantityTypeIdentifierHeartRate" unit="count/min" sourceName="Watch"
   startDate="2026-05-01 18:00:00 +0100" endDate="2026-05-01 18:00:00 +0100" value="120"/>
 <Record type="HKQuantityTypeIdentifierHeartRate" unit="count/min" sourceName="Watch"
   startDate="2026-05-02 18:00:00 +0100" endDate="2026-05-02 18:00:00 +0100" value="110"/>
 <Record type="HKQuantityTypeIdentifierRestingHeartRate" unit="count/min" sourceName="Watch"
   startDate="2026-05-01 08:00:00 +0100" endDate="2026-05-01 08:00:00 +0100" value="52"/>
 <Record type="HKQuantityTypeIdentifierHeartRateVariabilitySDNN" unit="ms" sourceName="Watch"
   startDate="2026-05-01 08:00:00 +0100" endDate="2026-05-01 08:00:00 +0100" value="70">
   <HeartRateVariabilityMetadataList/>
 </Record>
 <Record type="HKQuantityTypeIdentifierOxygenSaturation" unit="%" sourceName="Watch"
   startDate="2026-05-01 08:00:00 +0100" endDate="2026-05-01 08:00:00 +0100" value="0.98"/>
 <Record type="HKQuantityTypeIdentifierVO2Max" unit="mL/min·kg" sourceName="Watch"
   startDate="2026-05-01 08:00:00 +0100" endDate="2026-05-01 08:00:00 +0100" value="50"/>
 <Record type="HKQuantityTypeIdentifierBodyMassIndex" unit="count" sourceName="Watch"
   startDate="2026-05-01 08:00:00 +0100" endDate="2026-05-01 08:00:00 +0100" value="22"/>
 <Record type="HKCategoryTypeIdentifierSleepAnalysis" sourceName="Watch"
   startDate="2026-05-01 23:00:00 +0100" endDate="2026-05-02 05:00:00 +0100"
   value="HKCategoryValueSleepAnalysisAsleepCore">
   <MetadataEntry key="HKTimeZone" value="Europe/London"/>
 </Record>
 <Workout workoutActivityType="HKWorkoutActivityTypeWalking" duration="22.5"
   durationUnit="min" totalDistance="1.8" totalDistanceUnit="km"
   totalEnergyBurned="95.2" totalEnergyBurnedUnit="kcal" sourceName="Watch"
   startDate="2026-05-01 18:00:00 +0100" endDate="2026-05-01 18:22:30 +0100">
   <WorkoutStatistics type="HKQuantityTypeIdentifierActiveEnergyBurned"
     startDate="2026-05-01 18:00:00 +0100" endDate="2026-05-01 18:22:30 +0100"
     sum="88.4" unit="Cal"/>
 </Workout>
 <ActivitySummary dateComponents="2026-05-01" activeEnergyBurned="281.6"
   activeEnergyBurnedGoal="360" activeEnergyBurnedUnit="Cal" appleMoveTime="0"
   appleExerciseTime="25" appleExerciseTimeGoal="30" appleStandHours="10"
   appleStandHoursGoal="12"/>
</HealthData>
"""


@pytest.fixture()
def export_xml_path(tmp_path: Path) -> Path:
    path = tmp_path / "export.xml"
    path.write_text(SAMPLE_EXPORT_XML, encoding="utf-8")
    return path


@pytest.fixture()
def export_dir(tmp_path: Path) -> Path:
    directory = tmp_path / "apple_health_export"
    directory.mkdir()
    (directory / "export.xml").write_text(SAMPLE_EXPORT_XML, encoding="utf-8")
    return directory


@pytest.fixture()
def health(export_dir: Path):
    from helth import HealthExport

    return HealthExport.from_dir(export_dir, include_metadata=True)
