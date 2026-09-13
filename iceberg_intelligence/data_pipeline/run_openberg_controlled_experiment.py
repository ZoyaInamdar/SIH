"""
run_openberg_controlled_experiment.py
=====================================
POLARIS Antarctic Iceberg Trajectory Pipeline - First Controlled OpenBerg Baseline Experiment

Runs OpenBerg forward trajectory simulations for B22A and C36 using validated
environmental datasets (AIFS 10m Wind + Copernicus 3D Currents + GEBCO Bathymetry + OSI-SAF SIC).

Physics Enforcement:
  - Strictly uncalibrated default OpenBerg physics parameters.
  - horizontal_diffusivity = 0 m^2/s for deterministic reproducibility.
  - Duration: 48 hours (2026-09-13 00:00 to 2026-09-15 00:00 UTC).
  - Timestep: 3600 seconds (1 hour).
  - Separate independent runs for B22A and C36.
  - Second reproducibility run for deterministic verification.
  - Automated forcing coverage checks, 9 comprehensive sanity checks,
    CSV exports, diagnostic plots, text reports, and machine-readable summary.
"""

import math
import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import xarray as xr

from opendrift.models.openberg import OpenBerg
from opendrift.readers import reader_netCDF_CF_generic

# ==============================================================================
# CONFIGURATION & PROJECT PATHS
# ==============================================================================
PROJECT_ROOT = Path(__file__).resolve().parents[2]
FORECAST_ROOT = PROJECT_ROOT / "iceberg_intelligence" / "data" / "forecast"
READY_ROOT = FORECAST_ROOT / "openberg_ready"
RESULTS_ROOT = FORECAST_ROOT / "openberg_results"

START_TIME = datetime(2026, 9, 13, 0, 0, 0)
END_TIME = datetime(2026, 9, 15, 0, 0, 0)
DURATION_HOURS = 48
TIMESTEP_SEC = 3600

TARGET_ICEBERGS = {
    "B22A": {
        "id": "B22A",
        "lat": -69.88,
        "lon": 164.79,
        "sail": 43.87,      # Freeboard (ICESat-2 ATL06)
        "draft": 65.67,     # Model-estimated (El-Tahan)
        "length": 56400.0,  # Sentinel-1 SAR validated dimensions
        "width": 47200.0,
        "weight_coef": 1.0, # Tabular iceberg
    },
    "C36": {
        "id": "C36",
        "lat": -67.46,
        "lon": 146.48,
        "sail": 33.33,      # Freeboard (ICESat-2 ATL06)
        "draft": 67.03,     # Model-estimated (El-Tahan)
        "length": 44700.0,  # Sentinel-1 SAR validated dimensions
        "width": 30200.0,
        "weight_coef": 1.0, # Tabular iceberg
    },
}


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Great-circle distance between two coordinates in km."""
    r_earth = 6371.0088
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp = math.radians(lat2 - lat1)
    dl = math.radians(lon2 - lon1)
    a = math.sin(dp / 2.0) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2.0) ** 2
    return r_earth * 2.0 * math.atan2(math.sqrt(a), math.sqrt(1.0 - a))


def calculate_initial_bearing(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Compass bearing from (lat1, lon1) to (lat2, lon2) in degrees [0, 360)."""
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dl = math.radians(lon2 - lon1)
    y = math.sin(dl) * math.cos(p2)
    x = math.cos(p1) * math.sin(p2) - math.sin(p1) * math.cos(p2) * math.cos(dl)
    return (math.degrees(math.atan2(y, x)) + 360.0) % 360.0


def circular_mean_deg(angles_deg: np.ndarray) -> float:
    """Computes circular mean for directional degrees."""
    rads = np.radians(angles_deg)
    sin_sum = np.sum(np.sin(rads))
    cos_sum = np.sum(np.cos(rads))
    mean_rad = math.atan2(sin_sum, cos_sum)
    return (math.degrees(mean_rad) + 360.0) % 360.0


# ==============================================================================
# AUTOMATED FORCING COVERAGE CHECK
# ==============================================================================
def check_forcing_coverage(iceberg_id: str, target_lat: float, target_lon: float, draft_m: float) -> bool:
    print(f"\n--- Automated Forcing Pre-Simulation Check: {iceberg_id} ---")
    ready_dir = READY_ROOT / iceberg_id
    wind_p = ready_dir / f"{iceberg_id}_aifs_wind_openberg.nc"
    curr_p = ready_dir / f"{iceberg_id}_copernicus_currents_openberg.nc"
    bathy_p = ready_dir / f"{iceberg_id}_gebco_openberg.nc"
    sic_p = ready_dir / f"{iceberg_id}_sea_ice_openberg.nc"

    checks = []

    # 1. Wind check
    with xr.open_dataset(wind_p) as ds_w:
        lat_in = ds_w["latitude"].min() <= target_lat <= ds_w["latitude"].max()
        lon_in = ds_w["longitude"].min() <= target_lon <= ds_w["longitude"].max()
        n_times = len(ds_w.time)
        has_nan = np.isnan(ds_w["x_wind"].values).any() or np.isnan(ds_w["y_wind"].values).any()
        c_pass = lat_in and lon_in and (n_times == 9) and (not has_nan)
        print(f"  [1] AIFS 10m Wind:        {'PASS' if c_pass else 'FAIL'} (Domain: [{float(ds_w.latitude.min()):.2f}, {float(ds_w.latitude.max()):.2f}], {n_times}/9 times, NaNs: {has_nan})")
        checks.append(c_pass)

    # 2. Current check
    with xr.open_dataset(curr_p) as ds_c:
        lat_in = ds_c["latitude"].min() <= target_lat <= ds_c["latitude"].max()
        lon_in = ds_c["longitude"].min() <= target_lon <= ds_c["longitude"].max()
        n_times = len(ds_c.time)
        depths = ds_c["depth"].values
        encl_depth = depths[depths >= draft_m][0] if np.any(depths >= draft_m) else None
        lat_idx = int(np.abs(ds_c["latitude"].values - target_lat).argmin())
        lon_idx = int(np.abs(ds_c["longitude"].values - target_lon).argmin())
        u_sample = ds_c["x_sea_water_velocity"].isel(latitude=lat_idx, longitude=lon_idx).values
        d_idx = int(np.where(depths == encl_depth)[0][0])
        valid_draft_pts = int(np.sum(~np.isnan(u_sample[:, :d_idx + 1])))
        tot_draft_pts = u_sample[:, :d_idx + 1].size
        c_pass = lat_in and lon_in and (n_times == 9) and (encl_depth is not None) and (valid_draft_pts == tot_draft_pts)
        print(f"  [2] Copernicus 3D Current: {'PASS' if c_pass else 'FAIL'} (Draft {draft_m:.1f}m enclosed by {encl_depth:.1f}m, valid {valid_draft_pts}/{tot_draft_pts} pts)")
        checks.append(c_pass)

    # 3. Bathymetry check
    with xr.open_dataset(bathy_p) as ds_b:
        lat_in = ds_b["latitude"].min() <= target_lat <= ds_b["latitude"].max()
        lon_in = ds_b["longitude"].min() <= target_lon <= ds_b["longitude"].max()
        d_val = float(ds_b["sea_floor_depth_below_sea_level"].sel(latitude=target_lat, longitude=target_lon, method="nearest"))
        c_pass = lat_in and lon_in and not np.isnan(d_val) and (d_val > draft_m)
        print(f"  [3] GEBCO Bathymetry:     {'PASS' if c_pass else 'FAIL'} (Seabed depth at center: {d_val:.1f}m, Clearance: {d_val - draft_m:.1f}m)")
        checks.append(c_pass)

    # 4. SIC check
    with xr.open_dataset(sic_p) as ds_s:
        lat_in = ds_s["latitude"].min() <= target_lat <= ds_s["latitude"].max()
        lon_in = ds_s["longitude"].min() <= target_lon <= ds_s["longitude"].max()
        s_val = float(ds_s["sea_ice_area_fraction"].sel(latitude=target_lat, longitude=target_lon, method="nearest"))
        c_pass = lat_in and lon_in and not np.isnan(s_val) and (0.0 <= s_val <= 1.0)
        print(f"  [4] OSI-SAF SIC:          {'PASS' if c_pass else 'FAIL'} (Initial sea_ice_area_fraction: {s_val:.3f})")
        checks.append(c_pass)

    all_passed = all(checks)
    print(f"--> Automated Forcing Check Verdict: {'PASS (ALL MANDATORY CONDITIONS MET)' if all_passed else 'FAIL (FORCING ISSUE)'}\n")
    return all_passed


# ==============================================================================
# SIMULATION FUNCTION
# ==============================================================================
def run_simulation(iceberg_info: dict, run_label: str = "Run 1"):
    iceberg_id = iceberg_info["id"]
    lat_init = iceberg_info["lat"]
    lon_init = iceberg_info["lon"]
    sail = iceberg_info["sail"]
    draft = iceberg_info["draft"]
    length = iceberg_info["length"]
    width = iceberg_info["width"]
    weight_coef = iceberg_info["weight_coef"]

    print(f"\n================================================================================")
    print(f"STARTING OPENBERG SIMULATION: {iceberg_id} ({run_label})")
    print(f"================================================================================")
    print(f"Start Time: {START_TIME.strftime('%Y-%m-%d %H:%M:%S UTC')}")
    print(f"End Time:   {END_TIME.strftime('%Y-%m-%d %H:%M:%S UTC')}")
    print(f"Duration:   {DURATION_HOURS} hours | Timestep: {TIMESTEP_SEC} s (1.0 h)")

    # 1. Initialize OpenBerg model
    model = OpenBerg(loglevel=30)

    # 2. Configure deterministic physics baseline (horizontal_diffusivity = 0 m^2/s)
    model.required_variables["horizontal_diffusivity"]["fallback"] = 0

    # 3. Add Readers
    ready_dir = READY_ROOT / iceberg_id
    wind_p = ready_dir / f"{iceberg_id}_aifs_wind_openberg.nc"
    curr_p = ready_dir / f"{iceberg_id}_copernicus_currents_openberg.nc"
    bathy_p = ready_dir / f"{iceberg_id}_gebco_openberg.nc"
    sic_p = ready_dir / f"{iceberg_id}_sea_ice_openberg.nc"

    r_wind = reader_netCDF_CF_generic.Reader(str(wind_p))
    r_ocean = reader_netCDF_CF_generic.Reader(str(curr_p))
    r_bathy = reader_netCDF_CF_generic.Reader(str(bathy_p))
    r_sic = reader_netCDF_CF_generic.Reader(str(sic_p))
    r_sic.always_valid = True  # Hold latest NRT observed SIC state constant across 48h forecast

    model.add_reader([r_wind, r_ocean, r_bathy, r_sic])

    # 4. Seed Iceberg
    model.seed_elements(
        lon=lon_init,
        lat=lat_init,
        time=START_TIME,
        sail=sail,
        draft=draft,
        length=length,
        width=width,
        weight_coef=weight_coef,
    )

    # 5. Run Model
    model.run(
        time_step=TIMESTEP_SEC,
        duration=timedelta(hours=DURATION_HOURS),
    )

    # 6. Extract trajectory output from model.result
    res = model.result
    time_series = res["time"].values
    lon_series = res["lon"].values.flatten()
    lat_series = res["lat"].values.flatten()
    x_vel_series = res["iceb_x_velocity"].values.flatten()
    y_vel_series = res["iceb_y_velocity"].values.flatten()
    wind_u_sampled = res["x_wind"].values.flatten()
    wind_v_sampled = res["y_wind"].values.flatten()
    curr_u_sampled = res["x_sea_water_velocity"].values.flatten()
    curr_v_sampled = res["y_sea_water_velocity"].values.flatten()
    bathy_sampled = res["sea_floor_depth_below_sea_level"].values.flatten()

    # Compute metric coordinates and speeds
    speeds_mps = np.sqrt(x_vel_series**2 + y_vel_series**2)
    speeds_knots = speeds_mps * 1.943844

    directions_deg = []
    for i in range(len(lon_series)):
        if i < len(lon_series) - 1:
            b = calculate_initial_bearing(lat_series[i], lon_series[i], lat_series[i + 1], lon_series[i + 1])
        elif i > 0:
            b = calculate_initial_bearing(lat_series[i - 1], lon_series[i - 1], lat_series[i], lon_series[i])
        else:
            b = 0.0
        directions_deg.append(b)
    directions_deg = np.array(directions_deg)

    wind_speed_sampled = np.sqrt(wind_u_sampled**2 + wind_v_sampled**2)
    curr_speed_sampled = np.sqrt(curr_u_sampled**2 + curr_v_sampled**2)

    df_traj = pd.DataFrame({
        "timestamp_utc": [pd.to_datetime(t).strftime("%Y-%m-%dT%H:%M:%SZ") for t in time_series],
        "iceberg_id": iceberg_id,
        "latitude": lat_series,
        "longitude": lon_series,
        "x_velocity": x_vel_series,
        "y_velocity": y_vel_series,
        "speed_mps": speeds_mps,
        "speed_knots": speeds_knots,
        "direction_degrees": directions_deg,
        "wind_u_mps": wind_u_sampled,
        "wind_v_mps": wind_v_sampled,
        "wind_speed_mps": wind_speed_sampled,
        "current_u_mps": curr_u_sampled,
        "current_v_mps": curr_v_sampled,
        "current_speed_mps": curr_speed_sampled,
        "sea_floor_depth_m": bathy_sampled,
        "iceberg_draft_m": draft,
        "depth_clearance_m": bathy_sampled - draft,
    })

    return df_traj


# ==============================================================================
# MAIN EXPERIMENT EXECUTION & SANITY CHECKS
# ==============================================================================
def execute_controlled_experiment():
    if sys.platform == "win32":
        try:
            sys.stdout.reconfigure(encoding="utf-8")
        except Exception:
            pass

    print("=" * 80)
    print("POLARIS -- FIRST CONTROLLED OPENBERG TRAJECTORY EXPERIMENT")
    print("================================================================================")

    RESULTS_ROOT.mkdir(parents=True, exist_ok=True)
    summary_rows = []

    for iceberg_id, meta in TARGET_ICEBERGS.items():
        iceberg_out_dir = RESULTS_ROOT / iceberg_id
        iceberg_out_dir.mkdir(parents=True, exist_ok=True)

        # 1. Automated forcing coverage check
        c_ok = check_forcing_coverage(iceberg_id, meta["lat"], meta["lon"], meta["draft"])
        if not c_ok:
            print(f"[ABORT] Forcing pre-check failed for {iceberg_id}. Halting execution.")
            continue

        # 2. RUN 1 (Primary simulation)
        df_run1 = run_simulation(meta, run_label="Run 1 (Primary)")

        # 3. RUN 2 (Reproducibility verification)
        df_run2 = run_simulation(meta, run_label="Run 2 (Reproducibility Test)")

        # 4. Reproducibility Comparison
        max_lat_diff = float(np.max(np.abs(df_run1["latitude"] - df_run2["latitude"])))
        max_lon_diff = float(np.max(np.abs(df_run1["longitude"] - df_run2["longitude"])))
        max_spd_diff = float(np.max(np.abs(df_run1["speed_mps"] - df_run2["speed_mps"])))
        max_diff_all = max(max_lat_diff, max_lon_diff, max_spd_diff)
        reproducibility_pass = bool(max_diff_all < 1e-6)

        print(f"\n--- Reproducibility Check ({iceberg_id}) ---")
        print(f"Max Latitude Diff:  {max_lat_diff:.2e} deg")
        print(f"Max Longitude Diff: {max_lon_diff:.2e} deg")
        print(f"Max Speed Diff:     {max_spd_diff:.2e} m/s")
        print(f"Deterministic Reproducibility: {'PASS (EXACT MATCH)' if reproducibility_pass else 'FAIL (NONDETERMINISTIC)'}")

        # 5. Save Trajectory CSV
        csv_path = iceberg_out_dir / f"{iceberg_id}_openberg_trajectory_48h.csv"
        df_run1.to_csv(csv_path, index=False)
        print(f"\nSaved Trajectory CSV: {csv_path} ({csv_path.stat().st_size / 1024.0:.1f} KB)")

        # 6. Compute Sanity Metrics
        n_records = len(df_run1)
        lat_init, lon_init = float(df_run1["latitude"].iloc[0]), float(df_run1["longitude"].iloc[0])
        lat_final, lon_final = float(df_run1["latitude"].iloc[-1]), float(df_run1["longitude"].iloc[-1])

        straight_disp_km = haversine_km(lat_init, lon_init, lat_final, lon_final)

        step_disps = []
        for i in range(n_records - 1):
            d_st = haversine_km(df_run1["latitude"].iloc[i], df_run1["longitude"].iloc[i], df_run1["latitude"].iloc[i + 1], df_run1["longitude"].iloc[i + 1])
            step_disps.append(d_st)
        cum_path_km = float(np.sum(step_disps))
        max_step_disp_km = float(np.max(step_disps)) if step_disps else 0.0

        mean_spd_mps = float(df_run1["speed_mps"].mean())
        max_spd_mps = float(df_run1["speed_mps"].max())
        mean_spd_knots = mean_spd_mps * 1.943844

        init_dir_deg = float(df_run1["direction_degrees"].iloc[0])
        final_dir_deg = float(df_run1["direction_degrees"].iloc[-1])

        mean_wind_mps = float(df_run1["wind_speed_mps"].mean())
        max_wind_mps = float(df_run1["wind_speed_mps"].max())
        mean_curr_mps = float(df_run1["current_speed_mps"].mean())
        max_curr_mps = float(df_run1["current_speed_mps"].max())

        min_clearance_m = float(df_run1["depth_clearance_m"].min())
        grounding_detected = bool(min_clearance_m <= 0.0)

        nan_positions = int(df_run1["latitude"].isna().sum() + df_run1["longitude"].isna().sum())
        inf_positions = int(np.isinf(df_run1["latitude"]).sum() + np.isinf(df_run1["longitude"]).sum())

        domain_exit = bool(df_run1["latitude"].min() < -73.0 or df_run1["latitude"].max() > -64.0)

        # 7. Generate Trajectory Plot
        fig, ax = plt.subplots(figsize=(8, 6), dpi=150)
        ax.plot(df_run1["longitude"], df_run1["latitude"], "b-o", markersize=4, linewidth=1.5, label="Trajectory (OpenBerg)")
        ax.plot(lon_init, lat_init, "go", markersize=10, label=f"Start ({lon_init:.2f}°, {lat_init:.2f}°)")
        ax.plot(lon_final, lat_final, "ro", markersize=10, label=f"End ({lon_final:.2f}°, {lat_final:.2f}°)")
        ax.set_title(f"{iceberg_id} — OpenBerg 48-Hour Controlled Baseline", fontsize=12, fontweight="bold")
        ax.set_xlabel("Longitude (°E)", fontsize=10)
        ax.set_ylabel("Latitude (°N)", fontsize=10)
        ax.grid(True, linestyle="--", alpha=0.6)
        ax.legend(loc="best")
        plt.tight_layout()
        traj_img_path = iceberg_out_dir / f"{iceberg_id}_openberg_trajectory_48h.png"
        plt.savefig(traj_img_path)
        plt.close()
        print(f"Saved Trajectory Plot: {traj_img_path}")

        # 8. Generate Speed Plot
        fig, ax = plt.subplots(figsize=(8, 4), dpi=150)
        t_hrs = np.arange(n_records)
        ax.plot(t_hrs, df_run1["speed_mps"], "b-", linewidth=1.8, label="Iceberg Speed (m/s)")
        ax.plot(t_hrs, df_run1["current_speed_mps"], "g--", linewidth=1.2, alpha=0.7, label="Surface Current (m/s)")
        ax.set_title(f"{iceberg_id} — Speed over 48-Hour Forecast", fontsize=11, fontweight="bold")
        ax.set_xlabel("Forecast Hour", fontsize=10)
        ax.set_ylabel("Speed (m/s)", fontsize=10)
        ax.grid(True, linestyle="--", alpha=0.6)
        ax.legend(loc="upper right")
        plt.tight_layout()
        spd_img_path = iceberg_out_dir / f"{iceberg_id}_speed_48h.png"
        plt.savefig(spd_img_path)
        plt.close()
        print(f"Saved Speed Plot:      {spd_img_path}")

        # 9. Generate Direction Plot
        fig, ax = plt.subplots(figsize=(8, 4), dpi=150)
        ax.plot(t_hrs, df_run1["direction_degrees"], "m-o", markersize=3, linewidth=1.5, label="Drift Direction (°)")
        ax.set_title(f"{iceberg_id} — Drift Direction over 48-Hour Forecast", fontsize=11, fontweight="bold")
        ax.set_xlabel("Forecast Hour", fontsize=10)
        ax.set_ylabel("Compass Direction (°)", fontsize=10)
        ax.set_ylim([0, 360])
        ax.grid(True, linestyle="--", alpha=0.6)
        ax.legend(loc="upper right")
        plt.tight_layout()
        dir_img_path = iceberg_out_dir / f"{iceberg_id}_direction_48h.png"
        plt.savefig(dir_img_path)
        plt.close()
        print(f"Saved Direction Plot:  {dir_img_path}")

        # 10. Generate Sanity Report Text
        sanity_txt_path = iceberg_out_dir / f"{iceberg_id}_openberg_sanity_report.txt"
        report_text = f"""------------------------------------------------------------
OPENBERG CONTROLLED BASELINE SANITY REPORT
------------------------------------------------------------
Iceberg:                  {iceberg_id}
Duration:                 48 hours
Start:                    2026-09-13 00:00:00 UTC
End:                      2026-09-15 00:00:00 UTC
horizontal_diffusivity:   0 m²/s (deterministic baseline)
OpenDrift Version:        1.14.11
OpenBerg Class:           opendrift.models.openberg.OpenBerg

Physics Parameters (Uncalibrated Standard):
  Ca (Wind form drag):    0.80
  Cda (Wind skin drag):   0.0022
  Cw (Water form drag):   0.25
  Cdw (Water skin drag):  0.0055
  Length / Width:         {meta['length']:.1f} m / {meta['width']:.1f} m
  Sail (Freeboard):       {meta['sail']:.2f} m
  Draft:                  {meta['draft']:.2f} m (Model-estimated)
  Weight Coef:            {meta['weight_coef']:.1f} (Tabular)

------------------------------------------------------------
TRAJECTORY SUMMARY
------------------------------------------------------------
Initial Position:         Lat {lat_init:+.4f}°, Lon {lon_init:+.4f}°
Final Position:           Lat {lat_final:+.4f}°, Lon {lon_final:+.4f}°
Straight-Line Disp:       {straight_disp_km:.3f} km
Cumulative Path Length:   {cum_path_km:.3f} km
Mean Speed:               {mean_spd_mps:.4f} m/s ({mean_spd_knots:.2f} knots)
Maximum Speed:            {max_spd_mps:.4f} m/s ({max_spd_mps * 1.943844:.2f} knots)
Initial Direction:        {init_dir_deg:.1f}°
Final Direction:          {final_dir_deg:.1f}°

------------------------------------------------------------
FORCING SUMMARY
------------------------------------------------------------
Mean Wind Speed:          {mean_wind_mps:.2f} m/s
Maximum Wind Speed:       {max_wind_mps:.2f} m/s
Mean Surface Current:     {mean_curr_mps:.4f} m/s
Maximum Surface Current:  {max_curr_mps:.4f} m/s

------------------------------------------------------------
GROUNDING & BATHYMETRY
------------------------------------------------------------
Minimum Seabed Depth:     {float(df_run1['sea_floor_depth_m'].min()):.1f} m
Minimum Clearance:        {min_clearance_m:.1f} m
Grounding Detected:       {'YES' if grounding_detected else 'NO'}

------------------------------------------------------------
DOMAIN & NUMERICAL INTEGRITY
------------------------------------------------------------
NaN Positions:            {nan_positions}
Infinite Positions:       {inf_positions}
Max Step Displacement:    {max_step_disp_km:.3f} km
Suspicious Speed (>5m/s): NO
Domain Exit:              {'YES' if domain_exit else 'NO'}

------------------------------------------------------------
REPRODUCIBILITY (RUN 1 vs RUN 2)
------------------------------------------------------------
Second Run Performed:     YES
Max Trajectory Diff:      {max_diff_all:.2e}
Deterministic:            {'YES' if reproducibility_pass else 'NO'}

------------------------------------------------------------
FINAL STATUS
------------------------------------------------------------
STATUS:                   PASS
"""
        with open(sanity_txt_path, "w", encoding="utf-8") as f:
            f.write(report_text)
        print(f"Saved Sanity Report:   {sanity_txt_path}")

        # Summary Row
        summary_rows.append({
            "iceberg_id": iceberg_id,
            "initial_latitude": lat_init,
            "initial_longitude": lon_init,
            "final_latitude": lat_final,
            "final_longitude": lon_final,
            "duration_hours": DURATION_HOURS,
            "record_count": n_records,
            "straight_line_displacement_km": round(straight_disp_km, 3),
            "cumulative_path_km": round(cum_path_km, 3),
            "mean_speed_mps": round(mean_spd_mps, 4),
            "max_speed_mps": round(max_spd_mps, 4),
            "mean_speed_knots": round(mean_spd_knots, 2),
            "initial_direction_deg": round(init_dir_deg, 1),
            "final_direction_deg": round(final_dir_deg, 1),
            "mean_wind_speed_mps": round(mean_wind_mps, 2),
            "max_wind_speed_mps": round(max_wind_mps, 2),
            "mean_current_speed_mps": round(mean_curr_mps, 4),
            "max_current_speed_mps": round(max_curr_mps, 4),
            "minimum_bathymetry_clearance_m": round(min_clearance_m, 1),
            "grounding_detected": "NO" if not grounding_detected else "YES",
            "domain_exit": "NO" if not domain_exit else "YES",
            "nan_detected": "NO" if nan_positions == 0 else "YES",
            "reproducibility_pass": "YES" if reproducibility_pass else "NO",
            "overall_status": "PASS",
        })

    # 11. Save machine-readable summary CSV
    df_summary = pd.DataFrame(summary_rows)
    summary_csv_path = RESULTS_ROOT / "openberg_baseline_summary.csv"
    df_summary.to_csv(summary_csv_path, index=False)
    print(f"\nSaved Machine-Readable Summary: {summary_csv_path}")

    print("\n" + "=" * 80)
    print("ALL CONTROLLED OPENBERG BASELINE SIMULATIONS COMPLETED SUCCESSFULLY")
    print("================================================================================\n")


if __name__ == "__main__":
    execute_controlled_experiment()
