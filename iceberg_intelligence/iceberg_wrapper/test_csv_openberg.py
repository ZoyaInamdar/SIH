"""
test_csv_openberg.py

End-to-end test script for synthetic environmental forcing with OpenBerg.

Pipeline flow:
  Synthetic CSVs (ERA5 & GLORYS)
             |
             v
  CF-compliant NetCDF (csv_to_netcdf.py)
             |
             v
  OpenDrift NetCDF Readers (reader_netCDF_CF_generic)
             |
             v
  OpenBerg (IcebergDriftModel)
             |
             v
  OpenBerg simulation (24 hours)
             |
             v
  Trajectory CSV & Raw NetCDF output (outputs/synthetic_openberg/)
"""

from __future__ import annotations

import sys
from datetime import datetime
from pathlib import Path

# Add project root to sys.path if needed
project_root = Path(__file__).resolve().parents[1]
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

import pandas as pd
from opendrift.readers import reader_netCDF_CF_generic

from iceberg_wrapper.csv_to_netcdf import convert_all_demo_csvs
from iceberg_wrapper.iceberg_model import IcebergDriftModel


def run_synthetic_end_to_end_test() -> None:
    print("=" * 60)
    print("OPENBERG SYNTHETIC END-TO-END TEST")
    print("==================================")
    print()

    # 1. Convert CSV -> NetCDF
    print("Converting CSV -> NetCDF...")
    converted_files = convert_all_demo_csvs()
    era5_nc_files = converted_files["era5"]
    glorys_nc_files = converted_files["glorys"]
    print("[success]")
    print()

    # 2. Validate ERA5 Readers
    print("Validating ERA5 Reader...")
    era5_readers = []
    for era5_path in era5_nc_files:
        r = reader_netCDF_CF_generic.Reader(str(era5_path))
        era5_readers.append(r)
        # Confirm wind variables are recognized
        assert hasattr(r, "variables"), f"Reader for {era5_path} missing variables attribute"
        vars_set = set(r.variables)
        assert "eastward_wind" in vars_set or "x_wind" in vars_set, f"x_wind not recognized in {era5_path}"
        assert "northward_wind" in vars_set or "y_wind" in vars_set, f"y_wind not recognized in {era5_path}"
    print("[success]")
    print()

    # 3. Validate GLORYS Readers
    print("Validating GLORYS Reader...")
    glorys_readers = []
    for glorys_path in glorys_nc_files:
        r = reader_netCDF_CF_generic.Reader(str(glorys_path))
        glorys_readers.append(r)
        assert hasattr(r, "variables"), f"Reader for {glorys_path} missing variables attribute"
        vars_set = set(r.variables)
        assert "eastward_sea_water_velocity" in vars_set or "x_sea_water_velocity" in vars_set, f"x_sea_water_velocity not recognized in {glorys_path}"
        assert "northward_sea_water_velocity" in vars_set or "y_sea_water_velocity" in vars_set, f"y_sea_water_velocity not recognized in {glorys_path}"
    print("[success]")
    print()

    # 4. Initialize OpenBerg
    print("Initializing OpenBerg...")
    model = IcebergDriftModel()
    all_readers = era5_readers + glorys_readers
    model.add_reader(all_readers)
    print("[success]")
    print()

    # 5. Seed 3 icebergs
    print("Seeding 3 icebergs...")
    demo_icebergs = [
        {
            "id": "IB_DEMO_001",
            "latitude": -65.0,
            "longitude": 4.0,
            "length_m": 500.0,
            "width_m": 300.0,
            "freeboard_m": 30.0,
            "estimated_draft_m": 67.5,
        },
        {
            "id": "IB_DEMO_002",
            "latitude": -65.0,
            "longitude": 10.0,
            "length_m": 450.0,
            "width_m": 280.0,
            "freeboard_m": 28.0,
            "estimated_draft_m": 66.0,
        },
        {
            "id": "IB_DEMO_003",
            "latitude": -65.0,
            "longitude": 16.0,
            "length_m": 400.0,
            "width_m": 250.0,
            "freeboard_m": 26.0,
            "estimated_draft_m": 64.5,
        },
    ]

    start_time = datetime(2026, 1, 1, 0, 0, 0)
    model.add_icebergs(demo_icebergs, start_time=start_time)
    print("[success]")
    print()

    # 6. Run OpenBerg for 24 hours
    print("Running OpenBerg for 24 hours...")
    out_dir = Path("outputs/synthetic_openberg")
    out_dir.mkdir(parents=True, exist_ok=True)
    raw_nc_output = out_dir / "openberg_demo_raw.nc"

    model.run(hours=24.0, time_step_seconds=1800, outfile=raw_nc_output)
    print("[success]")
    print()

    # Retrieve trajectory DataFrame
    df_traj = model.get_trajectory()

    # Trajectory record validation
    counts = {}
    expected_init = {
        "IB_DEMO_001": (-65.0, 4.0),
        "IB_DEMO_002": (-65.0, 10.0),
        "IB_DEMO_003": (-65.0, 16.0),
    }

    for demo_id, (exp_lat, exp_lon) in expected_init.items():
        df_ib = df_traj[df_traj["iceberg_id"] == demo_id].sort_values("time")
        n_records = len(df_ib)
        counts[demo_id] = n_records
        assert n_records > 0, f"No trajectory records returned for {demo_id}"

        # Initial position check
        init_row = df_ib.iloc[0]
        init_lat = float(init_row["latitude"])
        init_lon = float(init_row["longitude"])
        assert abs(init_lat - exp_lat) < 0.01, f"{demo_id} initial lat {init_lat} != {exp_lat}"
        assert abs(init_lon - exp_lon) < 0.01, f"{demo_id} initial lon {init_lon} != {exp_lon}"

        # Movement check (position changes over simulation)
        final_row = df_ib.iloc[-1]
        fin_lat = float(final_row["latitude"])
        fin_lon = float(final_row["longitude"])
        dist_moved = ((fin_lat - init_lat)**2 + (fin_lon - init_lon)**2)**0.5
        assert dist_moved > 0.0001, f"{demo_id} trajectory did not change position"

    print("Trajectory records:")
    for demo_id, cnt in counts.items():
        print(f"  {demo_id}: {cnt}")
    print()

    # 7. Write trajectory CSVs
    print("Writing trajectory CSVs...")
    all_traj_csv = out_dir / "all_demo_trajectories.csv"
    df_traj.to_csv(all_traj_csv, index=False)

    for demo_id in ["IB_DEMO_001", "IB_DEMO_002", "IB_DEMO_003"]:
        ib_csv = out_dir / f"{demo_id}_trajectory.csv"
        df_ib = df_traj[df_traj["iceberg_id"] == demo_id]
        df_ib.to_csv(ib_csv, index=False)

    print("[success]")
    print()
    print("=" * 60)
    print("TEST PASSED")
    print("===========")


if __name__ == "__main__":
    run_synthetic_end_to_end_test()
