"""
run_iceberg_pipeline.py

End-to-end orchestration module for the Antarctic iceberg trajectory project.

Pipeline flow:
  Raw iceberg data
         |
         v
  Existing data loading (data_pipeline.load_icebergs)
         |
         v
  Existing data cleaning / QC / normalization (data_pipeline.qc)
         |
         v
  Existing environment matching (data_pipeline.match)
         |
         v
  Existing iceberg geometry compatibility checks (data_pipeline.compatibility)
         |
         v
  Existing shape / draft preparation where available (iceberg_wrapper)
         |
         v
  Existing OpenBerg wrapper (iceberg_wrapper.iceberg_model)
         |
         v
  OpenBerg simulation
         |
         v
  Trajectory retrieval
         |
         v
  CSV & Summary output

Usage:
  python run_iceberg_pipeline.py --case B50 --hours 6
"""

from __future__ import annotations

import argparse
import logging
import sys
from datetime import timedelta
from pathlib import Path
from typing import Any, Dict, Optional

import pandas as pd

from data_pipeline.config import (
    CASES,
    PROJECT_ROOT,
    era5_path,
    get_case,
    glorys_path,
    iceberg_path,
)
from data_pipeline.compatibility import (
    check_geometry_compatibility,
    check_vertical_geometry,
)
from data_pipeline.environment import inspect_environment
from data_pipeline.load_icebergs import load_byu_track
from data_pipeline.match import find_common_observations
from data_pipeline.prepare_case import (
    build_openberg_iceberg,
    build_project_iceberg,
)
from data_pipeline.qc import apply_qc, usable_observations
from iceberg_wrapper.draft_estimator import estimate_draft
from iceberg_wrapper.era5_reader import create_era5_reader
from iceberg_wrapper.glorys_reader import create_glorys_reader
from iceberg_wrapper.iceberg_model import IcebergDriftModel
from iceberg_wrapper.shape_classifier import classify_iceberg


# ============================================================================
# Logging Configuration
# ============================================================================

def setup_logging() -> None:
    """Configure clean ASCII logging."""
    logging.basicConfig(
        level=logging.INFO,
        format="[%(levelname)s] %(message)s",
        handlers=[logging.StreamHandler(sys.stdout)],
    )


logger = logging.getLogger("iceberg_pipeline")


# ============================================================================
# Directory Setup & Output Helpers
# ============================================================================

def get_output_dirs() -> tuple[Path, Path, Path, Path]:
    """Ensure output directories exist and return their paths."""
    base_out = PROJECT_ROOT / "outputs"
    traj_dir = base_out / "trajectories"
    openberg_dir = base_out / "openberg"
    val_dir = base_out / "validation"
    meta_dir = base_out / "metadata"

    for d in (traj_dir, openberg_dir, val_dir, meta_dir):
        if d.is_file():
            d.unlink()
        d.mkdir(parents=True, exist_ok=True)

    return traj_dir, openberg_dir, val_dir, meta_dir


def write_run_summary(
    case_name: str,
    iceberg_id: Optional[str],
    run_status: str,
    start_time: Optional[pd.Timestamp],
    forecast_hours: float,
    trajectory_records: int,
    observations_available: int,
    observations_used: int,
    environment_status: str,
    geometry_status: str,
    vertical_geometry_status: str,
    era5_file: str,
    glorys_file: str,
    openberg_executed: bool,
    trajectory_output: str,
    raw_output: str,
    validation_output: str,
    error_message: str,
    initial_lat: Optional[float] = None,
    initial_lon: Optional[float] = None,
    final_lat: Optional[float] = None,
    final_lon: Optional[float] = None,
) -> Path:
    """Write the run summary CSV files in metadata/ and validation/."""
    traj_dir, openberg_dir, val_dir, meta_dir = get_output_dirs()

    summary_data = {
        "case": case_name,
        "iceberg_id": iceberg_id if iceberg_id is not None else case_name,
        "run_status": run_status,
        "status": run_status,
        "start_time": str(start_time) if start_time is not None else "",
        "forecast_hours": forecast_hours,
        "trajectory_records": trajectory_records,
        "number_of_trajectory_records": trajectory_records,
        "observations_available": observations_available,
        "observations_used": observations_used,
        "environment_status": environment_status,
        "geometry_status": geometry_status,
        "vertical_geometry_status": vertical_geometry_status,
        "era5_file": era5_file,
        "glorys_file": glorys_file,
        "openberg_executed": openberg_executed,
        "trajectory_output": trajectory_output,
        "raw_output": raw_output,
        "validation_output": validation_output,
        "error_message": error_message,
        "initial_latitude": initial_lat if initial_lat is not None else "",
        "initial_longitude": initial_lon if initial_lon is not None else "",
        "final_latitude": final_lat if final_lat is not None else "",
        "final_longitude": final_lon if final_lon is not None else "",
    }

    summary_df = pd.DataFrame([summary_data])

    meta_summary = meta_dir / f"{case_name}_run_summary.csv"
    val_summary = val_dir / f"{case_name}_run_summary.csv"

    summary_df.to_csv(meta_summary, index=False)
    summary_df.to_csv(val_summary, index=False)

    return meta_summary


# ============================================================================
# Core Pipeline Execution
# ============================================================================

def run_pipeline(case_name: str, hours: float = 6.0) -> None:
    """Run the complete end-to-end iceberg pipeline."""
    case_name = case_name.upper()
    print("=" * 60)
    print("B50 ICEBERG PIPELINE" if case_name == "B50" else f"{case_name} ICEBERG PIPELINE")
    print("=" * 60)
    print(f"Case: {case_name}")
    print(f"Forecast duration: {hours:.1f} hours")
    print()

    traj_dir, openberg_dir, val_dir, meta_dir = get_output_dirs()

    # ------------------------------------------------------------------------
    # STAGE 1: Load iceberg observations
    # ------------------------------------------------------------------------
    print("Loading iceberg data...")
    iceberg_file = iceberg_path(case_name)
    if not iceberg_file.exists():
        status = "READER_ERROR"
        print(f"Status: {status}")
        print(f"Error: Iceberg data file not found: {iceberg_file}")
        write_run_summary(
            case_name=case_name,
            iceberg_id=case_name,
            run_status=status,
            start_time=None,
            forecast_hours=hours,
            trajectory_records=0,
            observations_available=0,
            observations_used=0,
            environment_status="UNCHECKED",
            geometry_status="UNCHECKED",
            vertical_geometry_status="UNCHECKED",
            era5_file=era5_path(case_name).name if era5_path(case_name).exists() else "MISSING",
            glorys_file=glorys_path(case_name).name if glorys_path(case_name).exists() else "MISSING",
            openberg_executed=False,
            trajectory_output="NONE",
            raw_output="NONE",
            validation_output="NONE",
            error_message=f"Iceberg data file not found: {iceberg_file}",
        )
        return

    df_raw = load_byu_track(iceberg_file, sensor_policy="ascat_then_nic")
    total_raw_obs = len(df_raw)
    print(f"Loaded: {total_raw_obs} observations from {iceberg_file.name}")
    print()

    # ------------------------------------------------------------------------
    # STAGE 2: Quality control & Normalization
    # ------------------------------------------------------------------------
    print("Running QC...")
    df_qc = apply_qc(df_raw)
    clean_df = usable_observations(df_qc)
    usable_count = len(clean_df)
    print(f"Usable observations: {usable_count}/{total_raw_obs}")

    era5_file = era5_path(case_name)
    glorys_file = glorys_path(case_name)

    if clean_df.empty:
        status = "NO_USABLE_OBSERVATIONS"
        print(f"Status: {status}")
        write_run_summary(
            case_name=case_name,
            iceberg_id=case_name,
            run_status=status,
            start_time=None,
            forecast_hours=hours,
            trajectory_records=0,
            observations_available=total_raw_obs,
            observations_used=0,
            environment_status="UNCHECKED",
            geometry_status="UNCHECKED",
            vertical_geometry_status="UNCHECKED",
            era5_file=era5_file.name,
            glorys_file=glorys_file.name,
            openberg_executed=False,
            trajectory_output="NONE",
            raw_output="NONE",
            validation_output="NONE",
            error_message="No usable observations remained after quality control.",
        )
        return
    print()

    # ------------------------------------------------------------------------
    # STAGE 3: Load environmental Readers
    # ------------------------------------------------------------------------
    print("Loading ERA5...")
    if not era5_file.exists():
        raise FileNotFoundError(f"ERA5 environment file not found: {era5_file}")
    era5_reader = create_era5_reader(era5_file)
    era5_meta = inspect_environment(era5_file)
    print(f"ERA5 coverage: lat {era5_meta['latitude_min']:.2f} to {era5_meta['latitude_max']:.2f}, lon {era5_meta['longitude_min']:.2f} to {era5_meta['longitude_max']:.2f}")

    print("Loading GLORYS...")
    if not glorys_file.exists():
        raise FileNotFoundError(f"GLORYS environment file not found: {glorys_file}")
    glorys_reader = create_glorys_reader(glorys_file)
    glorys_meta = inspect_environment(glorys_file)
    print(f"GLORYS coverage: lat {glorys_meta['latitude_min']:.2f} to {glorys_meta['latitude_max']:.2f}, lon {glorys_meta['longitude_min']:.2f} to {glorys_meta['longitude_max']:.2f}")

    if glorys_meta.get("depth_count", 0) < 2:
        print("WARNING: GLORYS file contains only 1 vertical level. Vertical profile mode will be disabled on OpenBerg.")
    print()

    # ------------------------------------------------------------------------
    # STAGE 4: Match iceberg observations to environment
    # ------------------------------------------------------------------------
    print("Matching observations to environment...")
    matched_df = find_common_observations(clean_df, era5_meta, glorys_meta)
    env_matched = matched_df[matched_df["environment_matched"]].copy()
    print(f"Matched observations: {len(env_matched)}/{usable_count}")

    if env_matched.empty:
        status = "OPENBERG_OUTSIDE_DOMAIN"
        print(f"Status: {status}")
        write_run_summary(
            case_name=case_name,
            iceberg_id=case_name,
            run_status=status,
            start_time=None,
            forecast_hours=hours,
            trajectory_records=0,
            observations_available=total_raw_obs,
            observations_used=usable_count,
            environment_status="OUTSIDE_DOMAIN",
            geometry_status="UNCHECKED",
            vertical_geometry_status="UNCHECKED",
            era5_file=era5_file.name,
            glorys_file=glorys_file.name,
            openberg_executed=False,
            trajectory_output="NONE",
            raw_output="NONE",
            validation_output="NONE",
            error_message="No observations fell inside environmental spatial/temporal domain.",
        )
        return
    print()

    # ------------------------------------------------------------------------
    # STAGE 5: OpenBerg geometry compatibility
    # ------------------------------------------------------------------------
    print("Checking OpenBerg geometry...")
    geom_compat = env_matched[env_matched["openberg_geometry_compatible"]].copy()
    print(f"Compatible observations: {len(geom_compat)}/{len(env_matched)}")

    if geom_compat.empty:
        status = "OPENBERG_GEOMETRY_INCOMPATIBLE"
        reasons = env_matched["geometry_compatibility_reason"].value_counts().to_dict()
        print(f"Status: {status}")
        print("Reasons:")
        for reason, count in reasons.items():
            print(f"  - {reason}: {count}")

        write_run_summary(
            case_name=case_name,
            iceberg_id=case_name,
            run_status=status,
            start_time=None,
            forecast_hours=hours,
            trajectory_records=0,
            observations_available=total_raw_obs,
            observations_used=len(env_matched),
            environment_status="MATCHED",
            geometry_status="INCOMPATIBLE",
            vertical_geometry_status="UNCHECKED",
            era5_file=era5_file.name,
            glorys_file=glorys_file.name,
            openberg_executed=False,
            trajectory_output="NONE",
            raw_output="NONE",
            validation_output="NONE",
            error_message=f"Horizontal dimensions incompatible with OpenBerg limits: {reasons}",
        )
        return

    # Select the earliest horizontally compatible observation
    candidate = geom_compat.sort_values("timestamp").iloc[0]
    obs_timestamp = pd.Timestamp(candidate["timestamp"])
    lat = float(candidate["latitude"])
    lon = float(candidate["longitude"])
    length_m = float(candidate["length_m"])
    width_m = float(candidate["width_m"])

    print(f"Selected anchor observation:")
    print(f"  Timestamp: {obs_timestamp}")
    print(f"  Position:  lat={lat:.4f}, lon={lon:.4f}")
    print(f"  Geometry:  length={length_m:.1f} m, width={width_m:.1f} m")

    # Environmental time coverage check for full requested forecast period
    forecast_end = obs_timestamp + pd.Timedelta(hours=hours)
    era5_start = pd.Timestamp(era5_meta["time_start"])
    era5_end = pd.Timestamp(era5_meta["time_end"])
    glorys_start = pd.Timestamp(glorys_meta["time_start"])
    glorys_end = pd.Timestamp(glorys_meta["time_end"])

    era5_ok = (obs_timestamp >= era5_start) and (forecast_end <= era5_end)
    glorys_ok = (obs_timestamp >= glorys_start) and (forecast_end <= glorys_end)

    if not (era5_ok and glorys_ok):
        status = "INSUFFICIENT_ENVIRONMENTAL_TIME_COVERAGE"
        print(f"Status: {status}")
        print(f"  Requested forecast window: {obs_timestamp} -> {forecast_end}")
        print(f"  ERA5 time coverage:       {era5_start} -> {era5_end}")
        print(f"  GLORYS time coverage:     {glorys_start} -> {glorys_end}")
        print("OpenBerg not executed.")
        print("Reason: required environmental time coverage for requested forecast duration is unavailable.")
        print("No trajectory was fabricated.")

        write_run_summary(
            case_name=case_name,
            iceberg_id=case_name,
            run_status=status,
            start_time=obs_timestamp,
            forecast_hours=hours,
            trajectory_records=0,
            observations_available=total_raw_obs,
            observations_used=len(geom_compat),
            environment_status="TIME_COVERAGE_INSUFFICIENT",
            geometry_status="COMPATIBLE",
            vertical_geometry_status="UNCHECKED",
            era5_file=era5_file.name,
            glorys_file=glorys_file.name,
            openberg_executed=False,
            trajectory_output="NONE",
            raw_output="NONE",
            validation_output="NONE",
            error_message=f"Environmental dataset time coverage ends before forecast period completes ({forecast_end} > {glorys_end}).",
            initial_lat=lat,
            initial_lon=lon,
        )
        return

    # Vertical geometry check
    raw_obs_idx = candidate["source_index"]
    raw_obs = df_raw.loc[raw_obs_idx]

    freeboard_m: Optional[float] = raw_obs.get("freeboard_m")
    if pd.isna(freeboard_m):
        freeboard_m = None

    estimated_draft_m: Optional[float] = raw_obs.get("estimated_draft_m")
    if pd.isna(estimated_draft_m):
        estimated_draft_m = None

    # If freeboard is available, attempt shape classification & draft estimation
    if freeboard_m is not None and estimated_draft_m is None:
        try:
            obs_dict = {
                "length_m": length_m,
                "width_m": width_m,
                "freeboard_m": float(freeboard_m),
            }
            classification = classify_iceberg(obs_dict)
            draft_res = estimate_draft(float(freeboard_m), classification.shape_class)
            if draft_res.status == "SUCCESS":
                estimated_draft_m = draft_res.estimated_draft_m
        except Exception as exc:
            logger.debug("Draft estimation attempt failed: %s", exc)

    print("Checking vertical geometry...")
    vert_res = check_vertical_geometry(freeboard_m, estimated_draft_m)

    if not vert_res.compatible:
        status = "OPENBERG_WAITING_FOR_VERTICAL_GEOMETRY"
        print(f"Status: {status}")
        print(f"  Reason: {vert_res.reason}")
        print("OpenBerg not executed.")
        print("Reason: required real iceberg vertical geometry is unavailable.")
        print("No trajectory was fabricated.")

        write_run_summary(
            case_name=case_name,
            iceberg_id=case_name,
            run_status=status,
            start_time=obs_timestamp,
            forecast_hours=hours,
            trajectory_records=0,
            observations_available=total_raw_obs,
            observations_used=len(geom_compat),
            environment_status="COVERED",
            geometry_status="COMPATIBLE",
            vertical_geometry_status="MISSING",
            era5_file=era5_file.name,
            glorys_file=glorys_file.name,
            openberg_executed=False,
            trajectory_output="NONE",
            raw_output="NONE",
            validation_output="NONE",
            error_message="BYU track data does not supply required freeboard/draft vertical geometry.",
            initial_lat=lat,
            initial_lon=lon,
        )
        return
    print()

    # ------------------------------------------------------------------------
    # STAGE 6: Prepare iceberg for OpenBerg
    # ------------------------------------------------------------------------
    print("Preparing OpenBerg input...")
    obs_record = {
        "latitude": lat,
        "longitude": lon,
        "timestamp": obs_timestamp,
        "length_m": length_m,
        "width_m": width_m,
    }
    project_iceberg = build_project_iceberg(
        iceberg_id=case_name,
        observation=obs_record,
        freeboard_m=freeboard_m,
        estimated_draft_m=estimated_draft_m,
    )
    openberg_iceberg = build_openberg_iceberg(
        iceberg_id=case_name,
        observation=obs_record,
        freeboard_m=freeboard_m,
        estimated_draft_m=estimated_draft_m,
    )
    print("Iceberg successfully prepared for OpenBerg.")
    print()

    # ------------------------------------------------------------------------
    # STAGE 7: Run OpenBerg
    # ------------------------------------------------------------------------
    print("Running OpenBerg...")
    model = IcebergDriftModel()

    if glorys_meta.get("depth_count", 0) < 2:
        model.model.set_config("drift:vertical_profile", False)

    model.add_reader(era5_reader)
    model.add_reader(glorys_reader)

    model.add_icebergs([openberg_iceberg], start_time=obs_timestamp.to_pydatetime())

    raw_nc_path = openberg_dir / f"{case_name}_openberg_raw.nc"
    model.run(hours=hours, outfile=raw_nc_path)
    print("Simulation complete.")
    print()

    # ------------------------------------------------------------------------
    # STAGE 8 & 9: Retrieve trajectory & Save Trajectory CSV
    # ------------------------------------------------------------------------
    print("Saving trajectory...")
    trajectory = model.get_trajectory()

    traj_csv_path = traj_dir / f"{case_name}_trajectory.csv"
    trajectory.to_csv(traj_csv_path, index=False)

    num_records = len(trajectory)
    init_lat = float(trajectory.iloc[0]["latitude"])
    init_lon = float(trajectory.iloc[0]["longitude"])
    fin_lat = float(trajectory.iloc[-1]["latitude"])
    fin_lon = float(trajectory.iloc[-1]["longitude"])

    print(f"Trajectory records: {num_records}")
    print(f"Saved: {traj_csv_path}")
    print(f"Saved: {raw_nc_path}")

    status = "SUCCESS"
    write_run_summary(
        case_name=case_name,
        iceberg_id=case_name,
        run_status=status,
        start_time=obs_timestamp,
        forecast_hours=hours,
        trajectory_records=num_records,
        observations_available=total_raw_obs,
        observations_used=len(geom_compat),
        environment_status="COVERED",
        geometry_status="COMPATIBLE",
        vertical_geometry_status="AVAILABLE",
        era5_file=era5_file.name,
        glorys_file=glorys_file.name,
        openberg_executed=True,
        trajectory_output=str(traj_csv_path),
        raw_output=str(raw_nc_path),
        validation_output="NONE",
        error_message="",
        initial_lat=init_lat,
        initial_lon=init_lon,
        final_lat=fin_lat,
        final_lon=fin_lon,
    )

    print()
    print("=" * 60)
    print(f"{case_name} pipeline complete.")
    print("=" * 60)


def main() -> None:
    setup_logging()

    parser = argparse.ArgumentParser(
        description="Antarctic Iceberg Trajectory Pipeline Orchestrator"
    )
    parser.add_argument(
        "--case",
        required=True,
        choices=sorted(CASES.keys()),
        help="Iceberg case identifier (e.g. B50, D27, D28, B39, D21B)",
    )
    parser.add_argument(
        "--hours",
        type=float,
        default=6.0,
        help="Forecast duration in hours (default: 6.0)",
    )

    args = parser.parse_args()

    run_pipeline(case_name=args.case, hours=args.hours)


if __name__ == "__main__":
    main()
