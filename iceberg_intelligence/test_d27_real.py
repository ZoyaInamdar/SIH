"""
test_d27_real.py

End-to-end real-data integration test for the iceberg trajectory wrapper.

Data sources:
    1. BYU/NIC consolidated D27 iceberg track
    2. ERA5 D27 wind forcing
    3. GLORYS D27 ocean / sea-ice forcing

IMPORTANT
---------
This is an INTEGRATION TEST, not a scientifically final D27 simulation.

The original BYU D27 geometry is preserved:

    7 nautical miles  -> 12,964 m
    4 nautical miles  ->  7,408 m

OpenBerg's current IcebergObj definition limits:
    length <= 10,000 m
    width  <= 10,000 m

Therefore this test uses:

    OpenBerg test length = 10,000 m
    OpenBerg test width  =  7,408 m

The original observed geometry is never overwritten in the source data.

Sail and draft are also temporary integration-test values:

    sail  = 10 m
    draft = 90 m

These are NOT measured D27 values.

The current GLORYS D27 file contains only one vertical level
(~0.494 m), so this test disables OpenBerg's vertical-profile mode.
That allows us to test the complete software/data connection without
pretending that the current one-depth GLORYS file is scientifically
complete for a 90 m iceberg draft.

Once multi-depth GLORYS data are available, this test should be updated
for scientifically meaningful OpenBerg vertical-profile simulations.
"""

from __future__ import annotations

import math
from datetime import datetime
from pathlib import Path
from typing import Optional, Tuple

import numpy as np
import pandas as pd

from iceberg_wrapper.era5_reader import create_era5_reader
from iceberg_wrapper.glorys_reader import create_glorys_reader
from iceberg_wrapper.iceberg_model import IcebergDriftModel


# ============================================================================
# Configuration
# ============================================================================

PROJECT_ROOT = Path(__file__).resolve().parent

BYU_FILE = (
    PROJECT_ROOT
    / "data"
    / "iceberg"
    / "byu_nic_v8"
    / "raw"
    / "d27.csv"
)

ERA5_FILE = (
    PROJECT_ROOT
    / "data"
    / "environmental"
    / "era5"
    / "D27.nc"
)

GLORYS_FILE = (
    PROJECT_ROOT
    / "data"
    / "environmental"
    / "glorys"
    / "D27.nc"
)

# BYU observation to use for the integration test.
TARGET_BYU_DATE = 2022147

# BYU's size fields are in nautical miles.
NAUTICAL_MILE_TO_METRE = 1852.0

# Temporary OpenBerg-compatible geometry.
#
# IMPORTANT:
# These are NOT used to overwrite the observed BYU dimensions.
OPENBERG_MAX_LENGTH_M = 10_000.0

# Temporary geometry because actual D27 sail/draft is not being supplied
# by this BYU track.
TEST_SAIL_M = 10.0
TEST_DRAFT_M = 90.0

# Integration-test duration.
RUN_HOURS = 6.0
TIME_STEP_SECONDS = 1800

# BYU gives a day rather than an observation time.
#
# 12:00 is only a deterministic alignment convention for this test.
# It is NOT claimed to be the actual observation timestamp.
TEST_OBSERVATION_HOUR = 12


# ============================================================================
# Utility functions
# ============================================================================

def is_valid_coordinate(latitude: float, longitude: float) -> bool:
    """Return True if latitude/longitude are finite and within valid bounds."""

    return (
        math.isfinite(latitude)
        and math.isfinite(longitude)
        and -90.0 <= latitude <= 90.0
        and -180.0 <= longitude <= 180.0
        and not (latitude == 0.0 and longitude == 0.0)
    )


def is_valid_sensor_position(
    latitude: object,
    longitude: object,
) -> bool:
    """Check whether a sensor position is usable."""

    try:
        lat = float(latitude)
        lon = float(longitude)
    except (TypeError, ValueError):
        return False

    return is_valid_coordinate(lat, lon)


def parse_byu_date(value: object) -> datetime:
    """
    Convert a BYU/NIC YYYYDDD date into a Python datetime.

    Example:
        2022147 -> 2022-05-27

    The time is intentionally set to 12:00 because the BYU track gives
    a daily observation date rather than an exact observation timestamp.
    """

    try:
        numeric_value = int(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"Invalid BYU date value: {value!r}") from exc

    date_text = str(numeric_value)

    if len(date_text) != 7:
        raise ValueError(
            f"Expected BYU date in YYYYDDD format, got {value!r}"
        )

    date = datetime.strptime(date_text, "%Y%j")

    return date.replace(hour=TEST_OBSERVATION_HOUR)


def choose_sensor_position(
    row: pd.Series,
) -> Tuple[str, float, float]:
    """
    Select a usable D27 position from the available sensor columns.

    For this individual integration test we prefer:

        ASCAT -> NIC

    if a valid position exists.

    This is a deterministic test-selection rule, NOT a universal scientific
    sensor hierarchy for the full BYU database.
    """

    sensor_candidates = [
        ("ASCAT", "ascat_1", "ascat_2"),
        ("NIC", "nic_1", "nic_2"),
    ]

    for sensor_name, lat_column, lon_column in sensor_candidates:

        if lat_column not in row.index or lon_column not in row.index:
            continue

        latitude = row[lat_column]
        longitude = row[lon_column]

        if is_valid_sensor_position(latitude, longitude):
            return (
                sensor_name,
                float(latitude),
                float(longitude),
            )

    raise ValueError(
        "The selected BYU D27 record has no valid ASCAT or NIC position."
    )


def load_d27_observation() -> dict:
    """
    Load the selected D27 observation from the BYU/NIC CSV.

    Returns a project-level iceberg dictionary suitable for
    IcebergDriftModel.add_icebergs().
    """

    print()
    print("Loading BYU/NIC D27 observation...")

    if not BYU_FILE.exists():
        raise FileNotFoundError(
            f"BYU D27 file not found:\n{BYU_FILE}"
        )

    df = pd.read_csv(BYU_FILE)

    required_columns = {
        "date",
        "size_1",
        "size_2",
    }

    missing = required_columns - set(df.columns)

    if missing:
        raise ValueError(
            "BYU D27 file is missing required columns: "
            + ", ".join(sorted(missing))
        )

    matches = df[df["date"].astype(str) == str(TARGET_BYU_DATE)]

    if matches.empty:
        raise ValueError(
            f"Could not find BYU date {TARGET_BYU_DATE} in {BYU_FILE}"
        )

    row = matches.iloc[0]

    sensor_name, latitude, longitude = choose_sensor_position(row)

    try:
        size_1_nm = float(row["size_1"])
        size_2_nm = float(row["size_2"])
    except (TypeError, ValueError) as exc:
        raise ValueError(
            "D27 size_1/size_2 values are not numeric."
        ) from exc

    if not math.isfinite(size_1_nm) or size_1_nm <= 0:
        raise ValueError(
            f"Invalid D27 size_1 value: {size_1_nm}"
        )

    if not math.isfinite(size_2_nm) or size_2_nm <= 0:
        raise ValueError(
            f"Invalid D27 size_2 value: {size_2_nm}"
        )

    observed_length_m = size_1_nm * NAUTICAL_MILE_TO_METRE
    observed_width_m = size_2_nm * NAUTICAL_MILE_TO_METRE

    observation_time = parse_byu_date(TARGET_BYU_DATE)

    print(f"  Iceberg ID:       D27_2022_TEST")
    print(f"  Observation date: {TARGET_BYU_DATE}")
    print(f"  Sensor:           {sensor_name}")
    print(f"  Latitude:         {latitude:.6f}")
    print(f"  Longitude:        {longitude:.6f}")
    print(f"  Size 1:           {size_1_nm:.1f} nautical miles")
    print(f"  Size 2:           {size_2_nm:.1f} nautical miles")
    print(f"  Length:           {observed_length_m:.1f} m")
    print(f"  Width:            {observed_width_m:.1f} m")
    print(f"  Test time:        {observation_time}")

    if latitude >= 0:
        raise ValueError(
            f"D27 latitude {latitude} is not Antarctic."
        )

    return {
        "id": "D27_2022_TEST",

        # Project/current position.
        "latitude": latitude,
        "longitude": longitude,

        # Original BYU geometry.
        #
        # These are replaced below ONLY for the OpenBerg integration
        # geometry sent through the project mapper.
        "observed_length_m": observed_length_m,
        "observed_width_m": observed_width_m,

        # Temporary OpenBerg-compatible geometry.
        "length_m": observed_length_m,
        "width_m": observed_width_m,

        # Temporary geometry only.
        "freeboard_m": TEST_SAIL_M,
        "estimated_draft_m": TEST_DRAFT_M,

        # Project metadata.
        "timestamp": observation_time,
        "shape_class": None,
        "draft_uncertainty_m": None,
        "drift_speed_knots": None,
        "drift_direction_degrees": None,
        "predicted_latitude": None,
        "predicted_longitude": None,
        "forecast_time": None,
        "bias_corrected_latitude": None,
        "bias_corrected_longitude": None,
        "bias_correction_applied": False,
        "status": "integration_test",
        "confidence": None,

        # Preserve source information externally.
        "source_sensor": sensor_name,
        "source_date": TARGET_BYU_DATE,
        "size_1_nm": size_1_nm,
        "size_2_nm": size_2_nm,
    }


def print_file_status() -> None:
    """Check that all required input files exist."""

    print()
    print("Checking input files...")

    files = [
        ("BYU/NIC D27", BYU_FILE),
        ("ERA5 D27", ERA5_FILE),
        ("GLORYS D27", GLORYS_FILE),
    ]

    for label, path in files:

        if not path.exists():
            raise FileNotFoundError(
                f"{label} file not found:\n{path}"
            )

        print(f"  OK: {label}")
        print(f"      {path}")


def print_environment_info(reader, label: str) -> None:
    """Print basic OpenDrift Reader information."""

    print(f"  {label} Reader created successfully.")

    if hasattr(reader, "xmin"):
        print(
            f"      Coverage: "
            f"xmin={reader.xmin:.6f}, "
            f"xmax={reader.xmax:.6f}, "
            f"ymin={reader.ymin:.6f}, "
            f"ymax={reader.ymax:.6f}"
        )

    if hasattr(reader, "start_time"):
        print(f"      Start time: {reader.start_time}")

    if hasattr(reader, "end_time"):
        print(f"      End time:   {reader.end_time}")

    if hasattr(reader, "variables"):
        print(
            "      Variables: "
            + ", ".join(str(v) for v in reader.variables)
        )


def validate_reader_coverage(
    reader,
    latitude: float,
    longitude: float,
    reader_name: str,
) -> None:
    """Verify that the iceberg position is inside a Reader's spatial domain."""

    if not (
        reader.xmin <= longitude <= reader.xmax
        and reader.ymin <= latitude <= reader.ymax
    ):
        raise ValueError(
            f"{reader_name} Reader does not cover the D27 position.\n"
            f"  D27: lon={longitude}, lat={latitude}\n"
            f"  Reader: "
            f"lon={reader.xmin}..{reader.xmax}, "
            f"lat={reader.ymin}..{reader.ymax}"
        )


# ============================================================================
# Main test
# ============================================================================

def main() -> None:

    print("=" * 70)
    print("D27 REAL-DATA OPENBERG INTEGRATION TEST")
    print("=" * 70)

    # ----------------------------------------------------------------------
    # 1. Check input files
    # ----------------------------------------------------------------------

    print_file_status()

    # ----------------------------------------------------------------------
    # 2. Load BYU observation
    # ----------------------------------------------------------------------

    iceberg = load_d27_observation()

    observed_length_m = iceberg["observed_length_m"]
    observed_width_m = iceberg["observed_width_m"]

    # ----------------------------------------------------------------------
    # 3. Create temporary OpenBerg-compatible geometry
    # ----------------------------------------------------------------------

    print()
    print("Temporary OpenBerg integration-test geometry:")

    print(
        f"  Original BYU length:  "
        f"{observed_length_m:.1f} m"
    )

    print(
        f"  Original BYU width:   "
        f"{observed_width_m:.1f} m"
    )

    if observed_length_m > OPENBERG_MAX_LENGTH_M:

        print(
            f"  OpenBerg length limit: "
            f"{OPENBERG_MAX_LENGTH_M:.1f} m"
        )

        print(
            f"  OpenBerg test length: "
            f"{OPENBERG_MAX_LENGTH_M:.1f} m"
        )

        iceberg["length_m"] = OPENBERG_MAX_LENGTH_M

    else:
        iceberg["length_m"] = observed_length_m

    if observed_width_m > OPENBERG_MAX_LENGTH_M:

        raise ValueError(
            "The observed D27 width exceeds OpenBerg's 10,000 m "
            "width limit. Do not silently clip it."
        )

    iceberg["width_m"] = observed_width_m

    print(
        f"  OpenBerg test width:  "
        f"{iceberg['width_m']:.1f} m"
    )

    print(
        f"  Temporary sail:       "
        f"{TEST_SAIL_M:.1f} m"
    )

    print(
        f"  Temporary draft:      "
        f"{TEST_DRAFT_M:.1f} m"
    )

    print()
    print("  WARNING:")
    print("  The OpenBerg test geometry is temporary.")
    print("  It is NOT the measured D27 geometry.")
    print("  The original BYU dimensions remain preserved above.")

    # ----------------------------------------------------------------------
    # 4. Create ERA5 Reader
    # ----------------------------------------------------------------------

    print()
    print("Creating ERA5 Reader...")

    era5_reader = create_era5_reader(ERA5_FILE)

    print_environment_info(
        era5_reader,
        "ERA5",
    )

    validate_reader_coverage(
        era5_reader,
        latitude=iceberg["latitude"],
        longitude=iceberg["longitude"],
        reader_name="ERA5",
    )

    # ----------------------------------------------------------------------
    # 5. Create GLORYS Reader
    # ----------------------------------------------------------------------

    print()
    print("Creating GLORYS Reader...")

    glorys_reader = create_glorys_reader(GLORYS_FILE)

    print_environment_info(
        glorys_reader,
        "GLORYS",
    )

    validate_reader_coverage(
        glorys_reader,
        latitude=iceberg["latitude"],
        longitude=iceberg["longitude"],
        reader_name="GLORYS",
    )

    # ----------------------------------------------------------------------
    # 6. Initialize OpenBerg
    # ----------------------------------------------------------------------

    print()
    print("Initializing OpenBerg...")

    model = IcebergDriftModel()

    print("  OpenBerg initialized.")

    # ----------------------------------------------------------------------
    # 7. Configure integration-test vertical handling
    # ----------------------------------------------------------------------
    #
    # The current D27 GLORYS file contains only one vertical level,
    # approximately 0.494 m.
    #
    # OpenBerg supports a vertical-profile configuration and its official
    # example explicitly demonstrates:
    #
    #     o.set_config('drift:vertical_profile', False)
    #
    # We use that configuration ONLY for this integration test.
    #
    # This does NOT make the current GLORYS file scientifically equivalent
    # to a multi-depth ocean profile.
    #
    # It simply lets us test the complete Reader -> OpenBerg connection.
    # ----------------------------------------------------------------------

    print()
    print("Configuring OpenBerg for the current integration-test dataset...")

    model.model.set_config(
        "drift:vertical_profile",
        False,
    )

    print(
        "  drift:vertical_profile = False"
    )

    print(
        "  NOTE: This is temporary because the current GLORYS D27"
    )
    print(
        "        file contains only one vertical level."
    )

    # ----------------------------------------------------------------------
    # 8. Add real environmental Readers
    # ----------------------------------------------------------------------

    print()
    print("Adding real environmental Readers...")

    model.add_reader(era5_reader)

    print("  Added ERA5 wind Reader.")

    model.add_reader(glorys_reader)

    print("  Added GLORYS ocean/sea-ice Reader.")

    # ----------------------------------------------------------------------
    # 9. Check that the D27 start time is covered
    # ----------------------------------------------------------------------

    start_time = iceberg["timestamp"]

    print()
    print("Checking Reader time coverage...")
    print(f"  Test start time: {start_time}")

    for reader, name in [
        (era5_reader, "ERA5"),
        (glorys_reader, "GLORYS"),
    ]:

        if reader.start_time is not None:
            if start_time < reader.start_time:
                raise ValueError(
                    f"{name} Reader starts after the test time.\n"
                    f"  Reader start: {reader.start_time}\n"
                    f"  Test time:   {start_time}"
                )

        if reader.end_time is not None:
            if start_time > reader.end_time:
                raise ValueError(
                    f"{name} Reader ends before the test time.\n"
                    f"  Reader end: {reader.end_time}\n"
                    f"  Test time:  {start_time}"
                )

        print(f"  {name}: start time is covered.")

    # ----------------------------------------------------------------------
    # 10. Seed D27
    # ----------------------------------------------------------------------

    print()
    print("Seeding D27...")

    model.add_icebergs(
        [iceberg],
        start_time=start_time,
    )

    print("  D27 seeded successfully.")

    # ----------------------------------------------------------------------
    # 11. Run OpenBerg
    # ----------------------------------------------------------------------

    print()
    print(
        f"Running OpenBerg for {RUN_HOURS:.1f} hours..."
    )

    print(
        f"  Time step: {TIME_STEP_SECONDS} seconds"
    )

    model.run(
        hours=RUN_HOURS,
        time_step_seconds=TIME_STEP_SECONDS,
    )

    print("  Simulation complete.")

    # ----------------------------------------------------------------------
    # 12. Retrieve trajectory
    # ----------------------------------------------------------------------

    print()
    print("Retrieving trajectory...")

    trajectory = model.get_trajectory()

    if trajectory.empty:
        raise RuntimeError(
            "OpenBerg completed but produced zero trajectory records."
        )

    print(
        f"  Number of trajectory records: "
        f"{len(trajectory)}"
    )

    # ----------------------------------------------------------------------
    # 13. Basic output checks
    # ----------------------------------------------------------------------

    required_columns = {
        "iceberg_id",
        "time",
        "latitude",
        "longitude",
    }

    missing_columns = required_columns - set(trajectory.columns)

    if missing_columns:
        raise RuntimeError(
            "Trajectory output is missing required columns: "
            + ", ".join(sorted(missing_columns))
        )

    ids = set(trajectory["iceberg_id"].astype(str))

    if "D27_2022_TEST" not in ids:
        raise RuntimeError(
            "D27_2022_TEST could not be mapped back to the trajectory output."
        )

    d27 = trajectory[
        trajectory["iceberg_id"].astype(str) == "D27_2022_TEST"
    ].copy()

    if d27.empty:
        raise RuntimeError(
            "No trajectory records were found for D27_2022_TEST."
        )

    # ----------------------------------------------------------------------
    # 14. Print trajectory
    # ----------------------------------------------------------------------

    print()
    print("=" * 70)
    print("D27 TRAJECTORY OUTPUT")
    print("=" * 70)

    display_columns = [
        column
        for column in [
            "iceberg_id",
            "time",
            "latitude",
            "longitude",
            "iceb_x_velocity",
            "iceb_y_velocity",
            "derived_speed_ms",
            "derived_direction_deg_compass",
            "sail",
            "draft",
            "length",
            "width",
        ]
        if column in d27.columns
    ]

    print(
        d27[display_columns].to_string(
            index=False
        )
    )

    # ----------------------------------------------------------------------
    # 15. Verify that the trajectory moved
    # ----------------------------------------------------------------------

    initial_latitude = float(d27.iloc[0]["latitude"])
    initial_longitude = float(d27.iloc[0]["longitude"])

    final_latitude = float(d27.iloc[-1]["latitude"])
    final_longitude = float(d27.iloc[-1]["longitude"])

    latitude_change = abs(
        final_latitude - initial_latitude
    )

    longitude_change = abs(
        final_longitude - initial_longitude
    )

    position_changed = (
        latitude_change > 1e-8
        or longitude_change > 1e-8
    )

    if not position_changed:
        raise RuntimeError(
            "OpenBerg produced trajectory records, but the iceberg "
            "did not change latitude or longitude."
        )

    # ----------------------------------------------------------------------
    # 16. Final summary
    # ----------------------------------------------------------------------

    print()
    print("=" * 70)
    print("INTEGRATION TEST SUMMARY")
    print("=" * 70)

    print("  BYU observation:")
    print(
        f"    Date:      {TARGET_BYU_DATE}"
    )
    print(
        f"    Latitude:  {iceberg['latitude']:.6f}"
    )
    print(
        f"    Longitude: {iceberg['longitude']:.6f}"
    )

    print()
    print("  Original BYU geometry:")
    print(
        f"    Length: {observed_length_m:.1f} m"
    )
    print(
        f"    Width:  {observed_width_m:.1f} m"
    )

    print()
    print("  OpenBerg integration geometry:")
    print(
        f"    Length: {iceberg['length_m']:.1f} m"
    )
    print(
        f"    Width:  {iceberg['width_m']:.1f} m"
    )
    print(
        f"    Sail:   {iceberg['freeboard_m']:.1f} m"
    )
    print(
        f"    Draft:  {iceberg['estimated_draft_m']:.1f} m"
    )

    print()
    print("  Trajectory:")
    print(
        f"    Records:       {len(d27)}"
    )
    print(
        f"    Initial:       "
        f"({initial_latitude:.6f}, {initial_longitude:.6f})"
    )
    print(
        f"    Final:         "
        f"({final_latitude:.6f}, {final_longitude:.6f})"
    )
    print(
        f"    Latitude Δ:    {latitude_change:.8f}°"
    )
    print(
        f"    Longitude Δ:   {longitude_change:.8f}°"
    )

    print()
    print("  Result:")
    print("    ✓ BYU/NIC D27 data loaded")
    print("    ✓ ERA5 Reader created")
    print("    ✓ GLORYS Reader created")
    print("    ✓ Readers cover D27 position")
    print("    ✓ Readers cover test start time")
    print("    ✓ OpenBerg initialized")
    print("    ✓ D27 seeded successfully")
    print("    ✓ OpenBerg simulation completed")
    print("    ✓ Trajectory records produced")
    print("    ✓ D27 project ID recovered")
    print("    ✓ D27 position changed")

    print()
    print(
        "IMPORTANT: This successful integration test does NOT yet "
        "constitute scientific validation."
    )

    print(
        "The current GLORYS file has only one vertical level, and the "
        "sail/draft are temporary."
    )

    print("=" * 70)


if __name__ == "__main__":
    main()
