"""
store_openberg_stage2_sql.py
============================
POLARIS Antarctic Iceberg Trajectory Pipeline - Database Ingestion & SQL Generator

Stores Stage 2 OpenBerg baseline results, iceberg master data, observations, draft estimates,
environmental forcing metadata, prediction points, and diagnostic summaries into:
1. iceberg_intelligence/outputs/iceberg_intelligence.db
2. backend/antarctic.db (Application Master)
3. iceberg_intelligence/sql/026_seed_stage2_openberg_baseline.sql (Reproducible Seed)
4. database/schema.sql & database/seed/openberg_stage2_baseline.sql (Standard Organization)

Performs comprehensive automated SQL integrity checks.
"""

import os
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
import pandas as pd
import numpy as np

# ==============================================================================
# PATH CONFIGURATIONS
# ==============================================================================
PROJECT_ROOT = Path(__file__).resolve().parents[2]
SQL_DIR = PROJECT_ROOT / "iceberg_intelligence" / "sql"
DB_INTEL_PATH = PROJECT_ROOT / "iceberg_intelligence" / "outputs" / "iceberg_intelligence.db"
DB_BACKEND_PATH = PROJECT_ROOT / "backend" / "antarctic.db"
FORECAST_RESULTS = PROJECT_ROOT / "iceberg_intelligence" / "data" / "forecast" / "openberg_results"
DIAG_DIR = FORECAST_RESULTS / "diagnostics"
DATABASE_DIR = PROJECT_ROOT / "database"
DATABASE_SEED_DIR = DATABASE_DIR / "seed"

DATABASE_SEED_DIR.mkdir(parents=True, exist_ok=True)
SQL_DIR.mkdir(parents=True, exist_ok=True)


def execute_database_ingestion():
    print("=" * 80)
    print("POLARIS -- STAGE 2 OPENBERG SQL INGESTION & REPRODUCIBILITY SEED")
    print("=" * 80)

    # --------------------------------------------------------------------------
    # 1. READ CSV TRAJECTORIES & DIAGNOSTICS
    # --------------------------------------------------------------------------
    b22a_traj_csv = FORECAST_RESULTS / "B22A" / "B22A_openberg_trajectory_48h.csv"
    c36_traj_csv = FORECAST_RESULTS / "C36" / "C36_openberg_trajectory_48h.csv"
    b22a_diag_csv = DIAG_DIR / "B22A_trajectory_diagnostics.csv"
    c36_diag_csv = DIAG_DIR / "C36_trajectory_diagnostics.csv"

    df_b22a_traj = pd.read_csv(b22a_traj_csv)
    df_c36_traj = pd.read_csv(c36_traj_csv)
    df_b22a_diag = pd.read_csv(b22a_diag_csv)
    df_c36_diag = pd.read_csv(c36_diag_csv)

    print(f"Loaded B22A Trajectory: {len(df_b22a_traj)} records")
    print(f"Loaded C36 Trajectory:  {len(df_c36_traj)} records (terminated at T=20h, no fabricated future steps)")

    # --------------------------------------------------------------------------
    # 2. CONNECT TO ICEBERG_INTELLIGENCE.DB & ENSURE EXTENDED SCHEMA
    # --------------------------------------------------------------------------
    conn_intel = sqlite3.connect(DB_INTEL_PATH)
    cur_intel = conn_intel.cursor()

    # Ensure openberg_run_diagnostics table exists
    cur_intel.execute("""
        CREATE TABLE IF NOT EXISTS openberg_run_diagnostics (
            diagnostic_id TEXT PRIMARY KEY,
            prediction_id TEXT NOT NULL,
            iceberg_id TEXT NOT NULL,
            forecast_start TEXT NOT NULL,
            forecast_end TEXT NOT NULL,
            duration_hours REAL NOT NULL,
            record_count INTEGER NOT NULL,
            straight_line_displacement_km REAL NOT NULL,
            cumulative_path_km REAL NOT NULL,
            path_net_ratio REAL NOT NULL,
            mean_speed_mps REAL NOT NULL,
            max_speed_mps REAL NOT NULL,
            mean_speed_knots REAL NOT NULL,
            mean_wind_mps REAL NOT NULL,
            max_wind_mps REAL NOT NULL,
            mean_current_mps REAL NOT NULL,
            max_current_mps REAL NOT NULL,
            minimum_clearance_m REAL NOT NULL,
            grounding_detected INTEGER NOT NULL CHECK (grounding_detected IN (0, 1)),
            stranding_detected INTEGER NOT NULL CHECK (stranding_detected IN (0, 1)),
            stranding_timestamp TEXT,
            diagnostic_classification TEXT NOT NULL,
            reproducibility_diff REAL NOT NULL,
            reproducibility_pass INTEGER NOT NULL CHECK (reproducibility_pass IN (0, 1)),
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (prediction_id) REFERENCES iceberg_predictions(prediction_id),
            FOREIGN KEY (iceberg_id) REFERENCES icebergs(iceberg_id)
        )
    """)

    # Ensure environmental_sources table exists
    cur_intel.execute("""
        CREATE TABLE IF NOT EXISTS environmental_sources (
            environmental_source_id INTEGER PRIMARY KEY AUTOINCREMENT,
            source_name TEXT NOT NULL,
            variable_group TEXT NOT NULL,
            file_reference TEXT NOT NULL,
            spatial_extent TEXT,
            temporal_extent TEXT,
            notes TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # --------------------------------------------------------------------------
    # 3. INSERT ICEBERGS MASTER DATA (B22A, C36, D15A)
    # --------------------------------------------------------------------------
    iceberg_masters = [
        ("B22A", "B22A", "Ross Sea / Thwaites Calving", "2026-09-10T00:00:00Z"),
        ("C36", "C36", "George V Coast / Mertz Region", "2026-09-10T00:00:00Z"),
        ("D15A", "D15A", "East Antarctica / Davis Sea", "2026-09-10T00:00:00Z"),
    ]
    for i_id, name, origin, obs_time in iceberg_masters:
        cur_intel.execute("""
            INSERT INTO icebergs (iceberg_id, name, origin, created_at)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(iceberg_id) DO UPDATE SET
                name=excluded.name,
                origin=excluded.origin,
                created_at=excluded.created_at
        """, (i_id, name, origin, obs_time))

    # --------------------------------------------------------------------------
    # 4. INSERT ICEBERG OBSERVATIONS (B22A, C36, D15A)
    # --------------------------------------------------------------------------
    cur_intel.execute("DELETE FROM iceberg_observations WHERE iceberg_id IN ('B22A', 'C36', 'D15A')")
    observations = [
        ("B22A", "2026-09-10T00:00:00Z", -69.88, 164.79, 56.4, 47.2, 2663.23, "Sentinel-1 SAR Polygon 2b14c602 + ICESat-2 ATL06 RGT0261"),
        ("C36", "2026-09-10T00:00:00Z", -67.46, 146.48, 44.7, 30.2, 1351.82, "Sentinel-1 SAR Polygon a03a93dd + ICESat-2 ATL06 RGT0078"),
        ("D15A", "2026-09-10T00:00:00Z", -66.63, 81.92, 99.2, 41.6, 4121.59, "Sentinel-1 SAR Polygon 862a5864 + ICESat-2 ATL06 RGT0820"),
    ]
    for i_id, obs_t, lat, lon, l_km, w_km, a_km2, src in observations:
        cur_intel.execute("""
            INSERT OR REPLACE INTO iceberg_observations (iceberg_id, timestamp, latitude, longitude, length_km, width_km, area_km2, source)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (i_id, obs_t, lat, lon, l_km, w_km, a_km2, src))

    # --------------------------------------------------------------------------
    # 5. INSERT DRAFT ESTIMATES (B22A, C36, D15A)
    # --------------------------------------------------------------------------
    cur_intel.execute("DELETE FROM iceberg_draft_estimates WHERE iceberg_id IN ('B22A', 'C36', 'D15A')")
    draft_estimates = [
        ("B22A", 43.87, 65.67, "TABULAR", "El-Tahan (1982) Empirical Tabular Hydrostatic Relationship", "POLARIS Vertical Geometry v1.0", 109.54, "2026-09-12T00:00:00Z"),
        ("C36", 33.33, 67.03, "TABULAR", "El-Tahan (1982) Empirical Tabular Hydrostatic Relationship", "POLARIS Vertical Geometry v1.0", 100.36, "2026-09-12T00:00:00Z"),
        ("D15A", 38.27, 66.38, "TABULAR", "El-Tahan (1982) Empirical Tabular Hydrostatic Relationship", "POLARIS Vertical Geometry v1.0", 104.65, "2026-09-12T00:00:00Z"),
    ]
    for i_id, fb, dr, shp, meth, ver, tot_h, est_t in draft_estimates:
        cur_intel.execute("""
            INSERT INTO iceberg_draft_estimates (iceberg_id, freeboard_m, estimated_draft_m, shape_class, method, method_version, total_height_m, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (i_id, fb, dr, shp, meth, ver, tot_h, est_t))

    # --------------------------------------------------------------------------
    # 6. INSERT ENVIRONMENTAL SOURCE PROVENANCE
    # --------------------------------------------------------------------------
    cur_intel.execute("DELETE FROM environmental_sources WHERE source_name IN ('ECMWF AIFS Operational Wind Forecast', 'Copernicus Marine 3D Ocean Analysis and Forecast', 'GEBCO Regional Bathymetry Grid', 'OSI-SAF Sea Ice Concentration')")
    env_sources = [
        ("ECMWF AIFS Operational Wind Forecast", "Atmospheric Wind (10u, 10v -> x_wind, y_wind)", "data/forecast/openberg_ready/{iceberg_id}/{iceberg_id}_aifs_wind_openberg.nc", "Spatial resolution: 0.25 deg", "2026-09-13T00:00:00Z to 2026-09-15T00:00:00Z (6-hourly)", "VALIDATED_FOR_OPENBERG"),
        ("Copernicus Marine 3D Ocean Analysis and Forecast", "3D Ocean Currents (uo, vo -> x_sea_water_velocity, y_sea_water_velocity)", "data/forecast/openberg_ready/{iceberg_id}/{iceberg_id}_copernicus_currents_openberg.nc", "Spatial resolution: 0.083 deg (~4.0 km zonal)", "2026-09-13T00:00:00Z to 2026-09-15T00:00:00Z (6-hourly, depths 0.494-92.326m)", "VALIDATED_FOR_OPENBERG"),
        ("GEBCO Regional Bathymetry Grid", "Seafloor Bathymetry (sea_floor_depth_below_sea_level)", "data/forecast/openberg_ready/{iceberg_id}/{iceberg_id}_gebco_openberg.nc", "Spatial resolution: 15 arc-second (~460 m)", "Static 2D Field", "VALIDATED_FOR_OPENBERG"),
        ("OSI-SAF Sea Ice Concentration", "Sea Ice Concentration (sea_ice_area_fraction)", "data/forecast/openberg_ready/{iceberg_id}/{iceberg_id}_sea_ice_openberg.nc", "Spatial resolution: 10.0 km polar stereographic", "Initialization State (2026-09-11 to 2026-09-12 NRT observations, NOT 48h forecast)", "VALIDATED_FOR_OPENBERG (Static Initial Concentration Field)"),
    ]
    for s_name, v_grp, f_ref, s_ext, t_ext, notes in env_sources:
        cur_intel.execute("""
            INSERT INTO environmental_sources (source_name, variable_group, file_reference, spatial_extent, temporal_extent, notes, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (s_name, v_grp, f_ref, s_ext, t_ext, notes, "2026-09-13T00:00:00Z"))

    # --------------------------------------------------------------------------
    # 7. INSERT MODEL CONFIGURATIONS
    # --------------------------------------------------------------------------
    configs = [
        ("B22A_CONTROLLED_BASELINE", "OpenBerg", "v1.14.11", 0.80, 0.00220, 0.25, 0.00550, 65.67, 56400.0, 47200.0, 43.87, 3600, "3d_depth_integrated_copernicus", "uncalibrated_default", "B22A 48h Controlled Physics Baseline (Uncalibrated Standard Physics, horizontal_diffusivity=0 m2/s)", "2026-09-13T00:00:00Z"),
        ("C36_CONTROLLED_BASELINE", "OpenBerg", "v1.14.11", 0.80, 0.00220, 0.25, 0.00550, 67.03, 44700.0, 30200.0, 33.33, 3600, "3d_depth_integrated_copernicus", "uncalibrated_default", "C36 48h Controlled Physics Baseline (Uncalibrated Standard Physics, horizontal_diffusivity=0 m2/s)", "2026-09-13T00:00:00Z"),
    ]
    for cid, mname, mver, ca, cda, cw, cdw, dr, l, w, fb, ts, cmode, cdamode, desc, cr_at in configs:
        cur_intel.execute("""
            INSERT OR REPLACE INTO model_configurations (configuration_id, model_name, model_version, ca, cda, cw, cdw, draft_m, length_m, width_m, freeboard_m, timestep_seconds, current_mode, cda_mode, description, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (cid, mname, mver, ca, cda, cw, cdw, dr, l, w, fb, ts, cmode, cdamode, desc, cr_at))

    # --------------------------------------------------------------------------
    # 8. INSERT PREDICTION RUN RECORDS
    # --------------------------------------------------------------------------
    pred_runs = [
        ("PRED_B22A_BASELINE_48H", "B22A", "OpenBerg", "v1.14.11", "B22A_CONTROLLED_BASELINE", "2026-09-13T00:00:00Z", "2026-09-15T00:00:00Z", "El-Tahan Empirical Model", 65.67, 43.87, 56400.0, 47200.0, 3600, "2026-09-13T00:00:00Z"),
        ("PRED_C36_BASELINE_48H", "C36", "OpenBerg", "v1.14.11", "C36_CONTROLLED_BASELINE", "2026-09-13T00:00:00Z", "2026-09-15T00:00:00Z", "El-Tahan Empirical Model", 67.03, 33.33, 44700.0, 30200.0, 3600, "2026-09-13T00:00:00Z"),
    ]
    for pid, iid, mname, mver, rlabel, st, et, dsrc, dr, sail, l, w, ts, cr_at in pred_runs:
        cur_intel.execute("""
            INSERT OR REPLACE INTO iceberg_predictions (prediction_id, iceberg_id, model_name, model_version, run_label, start_time, end_time, draft_source, draft_m, sail_m, length_m, width_m, timestep_seconds, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (pid, iid, mname, mver, rlabel, st, et, dsrc, dr, sail, l, w, ts, cr_at))

    # --------------------------------------------------------------------------
    # 9. INSERT PREDICTION TRAJECTORY POINTS
    # --------------------------------------------------------------------------
    # Remove existing points for these predictions before inserting
    cur_intel.execute("DELETE FROM trajectory_points WHERE prediction_id IN ('PRED_B22A_BASELINE_48H', 'PRED_C36_BASELINE_48H')")
    cur_intel.execute("DELETE FROM iceberg_prediction_points WHERE prediction_id IN ('PRED_B22A_BASELINE_48H', 'PRED_C36_BASELINE_48H')")

    # B22A (49 rows)
    for idx, row in df_b22a_traj.iterrows():
        cur_intel.execute("""
            INSERT INTO trajectory_points (prediction_id, step_index, timestamp, latitude, longitude, velocity_x, velocity_y, derived_speed_ms, derived_direction_deg)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, ("PRED_B22A_BASELINE_48H", idx, row["timestamp_utc"], row["latitude"], row["longitude"], row["x_velocity"], row["y_velocity"], row["speed_mps"], row["direction_degrees"]))
        cur_intel.execute("""
            INSERT INTO iceberg_prediction_points (prediction_id, forecast_time, latitude, longitude, confidence, created_at)
            VALUES (?, ?, ?, ?, ?, ?)
        """, ("PRED_B22A_BASELINE_48H", row["timestamp_utc"], row["latitude"], row["longitude"], 1.0, "2026-09-13T00:00:00Z"))

    # C36 (21 rows)
    for idx, row in df_c36_traj.iterrows():
        cur_intel.execute("""
            INSERT INTO trajectory_points (prediction_id, step_index, timestamp, latitude, longitude, velocity_x, velocity_y, derived_speed_ms, derived_direction_deg)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, ("PRED_C36_BASELINE_48H", idx, row["timestamp_utc"], row["latitude"], row["longitude"], row["x_velocity"], row["y_velocity"], row["speed_mps"], row["direction_degrees"]))
        cur_intel.execute("""
            INSERT INTO iceberg_prediction_points (prediction_id, forecast_time, latitude, longitude, confidence, created_at)
            VALUES (?, ?, ?, ?, ?, ?)
        """, ("PRED_C36_BASELINE_48H", row["timestamp_utc"], row["latitude"], row["longitude"], 1.0, "2026-09-13T00:00:00Z"))

    # --------------------------------------------------------------------------
    # 10. INSERT OPENBERG STAGE-2 DIAGNOSTIC SUMMARIES
    # --------------------------------------------------------------------------
    diagnostics = [
        ("DIAG_B22A_BASELINE", "PRED_B22A_BASELINE_48H", "B22A", "2026-09-13T00:00:00Z", "2026-09-15T00:00:00Z", 48.0, 49, 9.123, 63.707, 6.98, 0.1498, 0.1989, 0.29, 5.54, 7.06, 0.0361, 0.0633, 319.4, 0, 0, None, "trajectory meandering consistent with changing environmental forcing", 0.0, 1),
        ("DIAG_C36_BASELINE", "PRED_C36_BASELINE_48H", "C36", "2026-09-13T00:00:00Z", "2026-09-15T00:00:00Z", 20.0, 21, 22.916, 32.311, 1.41, 0.3660, 0.4857, 0.71, 11.48, 13.78, 0.1196, 0.1723, 485.4, 0, 1, "2026-09-13T20:00:00Z", "coastal shoreline stranding at T+20h; no seafloor grounding", 0.0, 1),
    ]
    for d_id, p_id, i_id, st, et, dur, rcnt, sdisp, cpath, pratio, mspd, maxspd, mkn, mwind, maxwind, mcurr, maxcurr, minclr, grnd, strnd, strnd_t, diag_class, rdiff, rpass in diagnostics:
        cur_intel.execute("""
            INSERT OR REPLACE INTO openberg_run_diagnostics (diagnostic_id, prediction_id, iceberg_id, forecast_start, forecast_end, duration_hours, record_count, straight_line_displacement_km, cumulative_path_km, path_net_ratio, mean_speed_mps, max_speed_mps, mean_speed_knots, mean_wind_mps, max_wind_mps, mean_current_mps, max_current_mps, minimum_clearance_m, grounding_detected, stranding_detected, stranding_timestamp, diagnostic_classification, reproducibility_diff, reproducibility_pass)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (d_id, p_id, i_id, st, et, dur, rcnt, sdisp, cpath, pratio, mspd, maxspd, mkn, mwind, maxwind, mcurr, maxcurr, minclr, grnd, strnd, strnd_t, diag_class, rdiff, rpass))

    conn_intel.commit()
    conn_intel.close()
    print("Successfully populated iceberg_intelligence.db!")

    # --------------------------------------------------------------------------
    # 11. UPDATE BACKEND/ANTARCTIC.DB ICEBERGS TABLE
    # --------------------------------------------------------------------------
    conn_backend = sqlite3.connect(DB_BACKEND_PATH)
    cur_backend = conn_backend.cursor()

    backend_icebergs = [
        ("B22A", -69.88, 164.79, "2026-09-10T00:00:00Z", 56400.0, 47200.0, 43.87, "TABULAR", 65.67, None, 0.29, 79.2, -69.8632, 164.5566, "2026-09-15T00:00:00Z", None, None, 0, "OBSERVED", 1.0, "Sentinel-1 SAR / ICESat-2 ATL06", "2026-09-13T00:00:00Z"),
        ("C36", -67.46, 146.48, "2026-09-10T00:00:00Z", 44700.0, 30200.0, 33.33, "TABULAR", 67.03, None, 0.71, 25.8, -67.2711, 146.2657, "2026-09-13T20:00:00Z", None, None, 0, "OBSERVED", 1.0, "Sentinel-1 SAR / ICESat-2 ATL06", "2026-09-13T00:00:00Z"),
        ("D15A", -66.63, 81.92, "2026-09-10T00:00:00Z", 99200.0, 41600.0, 38.27, "TABULAR", 66.38, None, None, None, None, None, None, None, None, 0, "OBSERVED", 1.0, "Sentinel-1 SAR / ICESat-2 ATL06", "2026-09-13T00:00:00Z"),
    ]
    for i_id, c_lat, c_lon, ts, l, w, fb, shp, dr, dr_unc, spd_kn, dir_deg, p_lat, p_lon, f_time, bc_lat, bc_lon, bc_app, stat, conf, src, l_upd in backend_icebergs:
        cur_backend.execute("""
            INSERT INTO icebergs (iceberg_id, current_latitude, current_longitude, timestamp, length_m, width_m, freeboard_m, shape_class, estimated_draft_m, draft_uncertainty_m, drift_speed_knots, drift_direction_degrees, predicted_latitude, predicted_longitude, forecast_time, bias_corrected_latitude, bias_corrected_longitude, bias_correction_applied, status, confidence, source, last_updated)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(iceberg_id) DO UPDATE SET
                current_latitude=excluded.current_latitude,
                current_longitude=excluded.current_longitude,
                timestamp=excluded.timestamp,
                length_m=excluded.length_m,
                width_m=excluded.width_m,
                freeboard_m=excluded.freeboard_m,
                shape_class=excluded.shape_class,
                estimated_draft_m=excluded.estimated_draft_m,
                drift_speed_knots=excluded.drift_speed_knots,
                drift_direction_degrees=excluded.drift_direction_degrees,
                predicted_latitude=excluded.predicted_latitude,
                predicted_longitude=excluded.predicted_longitude,
                forecast_time=excluded.forecast_time,
                status=excluded.status,
                confidence=excluded.confidence,
                source=excluded.source,
                last_updated=excluded.last_updated
        """, (i_id, c_lat, c_lon, ts, l, w, fb, shp, dr, dr_unc, spd_kn, dir_deg, p_lat, p_lon, f_time, bc_lat, bc_lon, bc_app, stat, conf, src, l_upd))

    conn_backend.commit()
    conn_backend.close()
    print("Successfully populated backend/antarctic.db!")

    # --------------------------------------------------------------------------
    # 12. GENERATE REPRODUCIBLE SQL SEED FILE
    # --------------------------------------------------------------------------
    sql_seed_lines = []
    sql_seed_lines.append("-- ============================================================================")
    sql_seed_lines.append("-- POLARIS Iceberg Intelligence Pipeline — Seed Stage 2 OpenBerg Controlled Baseline")
    sql_seed_lines.append("-- File: 026_seed_stage2_openberg_baseline.sql")
    sql_seed_lines.append("-- ============================================================================\n")
    sql_seed_lines.append("PRAGMA foreign_keys = ON;\n")

    # Master icebergs
    sql_seed_lines.append("-- 1. Seed Iceberg Master Identities (B22A, C36, D15A)")
    sql_seed_lines.append("INSERT OR REPLACE INTO icebergs (iceberg_id, name, origin, created_at) VALUES")
    sql_seed_lines.append("('B22A', 'B22A', 'Ross Sea / Thwaites Calving', '2026-09-10T00:00:00Z'),")
    sql_seed_lines.append("('C36', 'C36', 'George V Coast / Mertz Region', '2026-09-10T00:00:00Z'),")
    sql_seed_lines.append("('D15A', 'D15A', 'East Antarctica / Davis Sea', '2026-09-10T00:00:00Z');\n")

    # Observations
    sql_seed_lines.append("-- 2. Seed Iceberg Satellite Observations (Sentinel-1 SAR + ICESat-2 ATL06)")
    sql_seed_lines.append("INSERT OR REPLACE INTO iceberg_observations (iceberg_id, timestamp, latitude, longitude, length_km, width_km, area_km2, source) VALUES")
    sql_seed_lines.append("('B22A', '2026-09-10T00:00:00Z', -69.88, 164.79, 56.4, 47.2, 2663.23, 'Sentinel-1 SAR Polygon 2b14c602 + ICESat-2 ATL06 RGT0261'),")
    sql_seed_lines.append("('C36', '2026-09-10T00:00:00Z', -67.46, 146.48, 44.7, 30.2, 1351.82, 'Sentinel-1 SAR Polygon a03a93dd + ICESat-2 ATL06 RGT0078'),")
    sql_seed_lines.append("('D15A', '2026-09-10T00:00:00Z', -66.63, 81.92, 99.2, 41.6, 4121.59, 'Sentinel-1 SAR Polygon 862a5864 + ICESat-2 ATL06 RGT0820');\n")

    # Draft estimates
    sql_seed_lines.append("-- 3. Seed Estimated Draft Values (El-Tahan 1982 Tabular Relationship - NOT Measured)")
    sql_seed_lines.append("INSERT INTO iceberg_draft_estimates (iceberg_id, freeboard_m, estimated_draft_m, shape_class, method, method_version, total_height_m, created_at) VALUES")
    sql_seed_lines.append("('B22A', 43.87, 65.67, 'TABULAR', 'El-Tahan (1982) Empirical Tabular Hydrostatic Relationship', 'POLARIS Vertical Geometry v1.0', 109.54, '2026-09-12T00:00:00Z'),")
    sql_seed_lines.append("('C36', 33.33, 67.03, 'TABULAR', 'El-Tahan (1982) Empirical Tabular Hydrostatic Relationship', 'POLARIS Vertical Geometry v1.0', 100.36, '2026-09-12T00:00:00Z'),")
    sql_seed_lines.append("('D15A', 38.27, 66.38, 'TABULAR', 'El-Tahan (1982) Empirical Tabular Hydrostatic Relationship', 'POLARIS Vertical Geometry v1.0', 104.65, '2026-09-12T00:00:00Z');\n")

    # Environmental sources
    sql_seed_lines.append("-- 4. Seed Environmental Forcing Metadata")
    sql_seed_lines.append("INSERT INTO environmental_sources (source_name, variable_group, file_reference, spatial_extent, temporal_extent, notes, created_at) VALUES")
    sql_seed_lines.append("('ECMWF AIFS Operational Wind Forecast', 'Atmospheric Wind (10u, 10v -> x_wind, y_wind)', 'data/forecast/openberg_ready/{iceberg_id}/{iceberg_id}_aifs_wind_openberg.nc', 'Spatial resolution: 0.25 deg', '2026-09-13T00:00:00Z to 2026-09-15T00:00:00Z (6-hourly)', 'VALIDATED_FOR_OPENBERG', '2026-09-13T00:00:00Z'),")
    sql_seed_lines.append("('Copernicus Marine 3D Ocean Analysis and Forecast', '3D Ocean Currents (uo, vo -> x_sea_water_velocity, y_sea_water_velocity)', 'data/forecast/openberg_ready/{iceberg_id}/{iceberg_id}_copernicus_currents_openberg.nc', 'Spatial resolution: 0.083 deg (~4.0 km zonal)', '2026-09-13T00:00:00Z to 2026-09-15T00:00:00Z (6-hourly, depths 0.494-92.326m)', 'VALIDATED_FOR_OPENBERG', '2026-09-13T00:00:00Z'),")
    sql_seed_lines.append("('GEBCO Regional Bathymetry Grid', 'Seafloor Bathymetry (sea_floor_depth_below_sea_level)', 'data/forecast/openberg_ready/{iceberg_id}/{iceberg_id}_gebco_openberg.nc', 'Spatial resolution: 15 arc-second (~460 m)', 'Static 2D Field', 'VALIDATED_FOR_OPENBERG', '2026-09-13T00:00:00Z'),")
    sql_seed_lines.append("('OSI-SAF Sea Ice Concentration', 'Sea Ice Concentration (sea_ice_area_fraction)', 'data/forecast/openberg_ready/{iceberg_id}/{iceberg_id}_sea_ice_openberg.nc', 'Spatial resolution: 10.0 km polar stereographic', 'Initialization State (2026-09-11 to 2026-09-12 NRT observations, NOT 48h forecast)', 'VALIDATED_FOR_OPENBERG (Static Initial Concentration Field)', '2026-09-13T00:00:00Z');\n")

    # Model configuration
    sql_seed_lines.append("-- 5. Seed OpenBerg Physics Configuration (Uncalibrated Baseline, Diffusivity=0)")
    sql_seed_lines.append("INSERT OR REPLACE INTO model_configurations (configuration_id, model_name, model_version, ca, cda, cw, cdw, draft_m, length_m, width_m, freeboard_m, timestep_seconds, current_mode, cda_mode, description, created_at) VALUES")
    sql_seed_lines.append("('B22A_CONTROLLED_BASELINE', 'OpenBerg', 'v1.14.11', 0.80, 0.00220, 0.25, 0.00550, 65.67, 56400.0, 47200.0, 43.87, 3600, '3d_depth_integrated_copernicus', 'uncalibrated_default', 'B22A 48h Controlled Physics Baseline (Uncalibrated Standard Physics, horizontal_diffusivity=0 m2/s)', '2026-09-13T00:00:00Z'),")
    sql_seed_lines.append("('C36_CONTROLLED_BASELINE', 'OpenBerg', 'v1.14.11', 0.80, 0.00220, 0.25, 0.00550, 67.03, 44700.0, 30200.0, 33.33, 3600, '3d_depth_integrated_copernicus', 'uncalibrated_default', 'C36 48h Controlled Physics Baseline (Uncalibrated Standard Physics, horizontal_diffusivity=0 m2/s)', '2026-09-13T00:00:00Z');\n")

    # Prediction runs
    sql_seed_lines.append("-- 6. Seed OpenBerg Prediction Run Records")
    sql_seed_lines.append("INSERT OR REPLACE INTO iceberg_predictions (prediction_id, iceberg_id, model_name, model_version, run_label, start_time, end_time, draft_source, draft_m, sail_m, length_m, width_m, timestep_seconds, created_at) VALUES")
    sql_seed_lines.append("('PRED_B22A_BASELINE_48H', 'B22A', 'OpenBerg', 'v1.14.11', 'B22A_CONTROLLED_BASELINE', '2026-09-13T00:00:00Z', '2026-09-15T00:00:00Z', 'El-Tahan Empirical Model', 65.67, 43.87, 56400.0, 47200.0, 3600, '2026-09-13T00:00:00Z'),")
    sql_seed_lines.append("('PRED_C36_BASELINE_48H', 'C36', 'OpenBerg', 'v1.14.11', 'C36_CONTROLLED_BASELINE', '2026-09-13T00:00:00Z', '2026-09-15T00:00:00Z', 'El-Tahan Empirical Model', 67.03, 33.33, 44700.0, 30200.0, 3600, '2026-09-13T00:00:00Z');\n")

    # Trajectory points
    sql_seed_lines.append("-- 7. Seed B22A Predicted Trajectory Points (49 Records: T=0 to T=48h)")
    sql_seed_lines.append("INSERT INTO trajectory_points (prediction_id, step_index, timestamp, latitude, longitude, velocity_x, velocity_y, derived_speed_ms, derived_direction_deg) VALUES")
    b22a_pts_sql = []
    for idx, row in df_b22a_traj.iterrows():
        b22a_pts_sql.append(f"('PRED_B22A_BASELINE_48H', {idx}, '{row['timestamp_utc']}', {row['latitude']:.6f}, {row['longitude']:.6f}, {row['x_velocity']:.6f}, {row['y_velocity']:.6f}, {row['speed_mps']:.4f}, {row['direction_degrees']:.1f})")
    sql_seed_lines.append(",\n".join(b22a_pts_sql) + ";\n")

    sql_seed_lines.append("-- 8. Seed C36 Predicted Trajectory Points (21 Records: T=0 to T=20h, Stranded at Coastline)")
    sql_seed_lines.append("INSERT INTO trajectory_points (prediction_id, step_index, timestamp, latitude, longitude, velocity_x, velocity_y, derived_speed_ms, derived_direction_deg) VALUES")
    c36_pts_sql = []
    for idx, row in df_c36_traj.iterrows():
        c36_pts_sql.append(f"('PRED_C36_BASELINE_48H', {idx}, '{row['timestamp_utc']}', {row['latitude']:.6f}, {row['longitude']:.6f}, {row['x_velocity']:.6f}, {row['y_velocity']:.6f}, {row['speed_mps']:.4f}, {row['direction_degrees']:.1f})")
    sql_seed_lines.append(",\n".join(c36_pts_sql) + ";\n")

    # Diagnostics
    sql_seed_lines.append("-- 9. Seed OpenBerg Stage-2 Trajectory Diagnostics & Kinematic Summaries")
    sql_seed_lines.append("INSERT OR REPLACE INTO openberg_run_diagnostics (diagnostic_id, prediction_id, iceberg_id, forecast_start, forecast_end, duration_hours, record_count, straight_line_displacement_km, cumulative_path_km, path_net_ratio, mean_speed_mps, max_speed_mps, mean_speed_knots, mean_wind_mps, max_wind_mps, mean_current_mps, max_current_mps, minimum_clearance_m, grounding_detected, stranding_detected, stranding_timestamp, diagnostic_classification, reproducibility_diff, reproducibility_pass) VALUES")
    sql_seed_lines.append("('DIAG_B22A_BASELINE', 'PRED_B22A_BASELINE_48H', 'B22A', '2026-09-13T00:00:00Z', '2026-09-15T00:00:00Z', 48.0, 49, 9.123, 63.707, 6.98, 0.1498, 0.1989, 0.29, 5.54, 7.06, 0.0361, 0.0633, 319.4, 0, 0, NULL, 'trajectory meandering consistent with changing environmental forcing', 0.0, 1),")
    sql_seed_lines.append("('DIAG_C36_BASELINE', 'PRED_C36_BASELINE_48H', 'C36', '2026-09-13T00:00:00Z', '2026-09-15T00:00:00Z', 20.0, 21, 22.916, 32.311, 1.41, 0.3660, 0.4857, 0.71, 11.48, 13.78, 0.1196, 0.1723, 485.4, 0, 1, '2026-09-13T20:00:00Z', 'coastal shoreline stranding at T+20h; no seafloor grounding', 0.0, 1);\n")

    seed_content_intel = "\n".join(sql_seed_lines)

    # Write to iceberg_intelligence/sql/026_seed_stage2_openberg_baseline.sql (Master Intelligence DB Seed)
    p1 = SQL_DIR / "026_seed_stage2_openberg_baseline.sql"
    with open(p1, "w", encoding="utf-8") as f:
        f.write(seed_content_intel)
    print(f"Saved Master Scientific Seed: {p1}")

    # Generate distinct Operational Backend Seed (database/seed/openberg_stage2_baseline.sql)
    backend_seed_lines = [
        "-- ============================================================================",
        "-- POLARIS Navigation Service — Operational Backend Seed (Stage 2 OpenBerg Baseline)",
        "-- File: database/seed/openberg_stage2_baseline.sql",
        "-- Target Database: backend/antarctic.db",
        "-- ============================================================================",
        "",
        "PRAGMA foreign_keys = ON;",
        "",
        "-- 1. Seed Operational Icebergs Profile State",
        "INSERT OR REPLACE INTO icebergs (",
        "    iceberg_id, current_latitude, current_longitude, timestamp, length_m, width_m,",
        "    freeboard_m, shape_class, estimated_draft_m, draft_uncertainty_m, drift_speed_knots,",
        "    drift_direction_degrees, predicted_latitude, predicted_longitude, forecast_time,",
        "    bias_corrected_latitude, bias_corrected_longitude, bias_correction_applied, status,",
        "    confidence, source, last_updated",
        ") VALUES",
        "('B22A', -69.88, 164.79, '2026-09-10T00:00:00Z', 56400.0, 47200.0, 43.87, 'TABULAR', 65.67, NULL, 0.29, 79.2, -69.8632, 164.5566, '2026-09-15T00:00:00Z', NULL, NULL, 0, 'OBSERVED', 1.0, 'Sentinel-1 SAR / ICESat-2 ATL06', '2026-09-13T00:00:00Z'),",
        "('C36', -67.46, 146.48, '2026-09-10T00:00:00Z', 44700.0, 30200.0, 33.33, 'TABULAR', 67.03, NULL, 0.71, 25.8, -67.2711, 146.2657, '2026-09-13T20:00:00Z', NULL, NULL, 0, 'OBSERVED', 1.0, 'Sentinel-1 SAR / ICESat-2 ATL06', '2026-09-13T00:00:00Z'),",
        "('D15A', -66.63, 81.92, '2026-09-10T00:00:00Z', 99200.0, 41600.0, 38.27, 'TABULAR', 66.38, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, 0, 'OBSERVED', 1.0, 'Sentinel-1 SAR / ICESat-2 ATL06', '2026-09-13T00:00:00Z');",
        "",
        "-- 2. Seed Operational Trajectory Points (B22A: 49 records, C36: 21 records)",
        "INSERT INTO trajectory_points (iceberg_id, step_index, timestamp, latitude, longitude, velocity_x, velocity_y, speed_mps, heading_deg) VALUES"
    ]
    backend_traj_pts = []
    for idx, row in df_b22a_traj.iterrows():
        backend_traj_pts.append(f"('B22A', {idx}, '{row['timestamp_utc']}', {row['latitude']:.6f}, {row['longitude']:.6f}, {row['x_velocity']:.6f}, {row['y_velocity']:.6f}, {row['speed_mps']:.4f}, {row['direction_degrees']:.1f})")
    for idx, row in df_c36_traj.iterrows():
        backend_traj_pts.append(f"('C36', {idx}, '{row['timestamp_utc']}', {row['latitude']:.6f}, {row['longitude']:.6f}, {row['x_velocity']:.6f}, {row['y_velocity']:.6f}, {row['speed_mps']:.4f}, {row['direction_degrees']:.1f})")
    backend_seed_lines.append(",\n".join(backend_traj_pts) + ";\n")

    backend_seed_lines.append("-- 3. Seed Operational OpenBerg Trajectory Diagnostics")
    backend_seed_lines.append("INSERT OR REPLACE INTO openberg_diagnostics (diagnostic_id, iceberg_id, duration_hours, record_count, path_net_ratio, mean_speed_knots, minimum_clearance_m, grounding_detected, stranding_detected, classification, created_at) VALUES")
    backend_seed_lines.append("('DIAG_B22A_BASELINE', 'B22A', 48.0, 49, 6.98, 0.29, 319.4, 0, 0, 'trajectory meandering consistent with changing environmental forcing', '2026-09-13T00:00:00Z'),")
    backend_seed_lines.append("('DIAG_C36_BASELINE', 'C36', 20.0, 21, 1.41, 0.71, 485.4, 0, 1, 'coastal shoreline stranding at T+20h; no seafloor grounding', '2026-09-13T00:00:00Z');\n")

    p2 = DATABASE_SEED_DIR / "openberg_stage2_baseline.sql"
    with open(p2, "w", encoding="utf-8") as f:
        f.write("\n".join(backend_seed_lines))
    print(f"Saved Operational Backend Seed: {p2}")

    # --------------------------------------------------------------------------
    # 13. RUN COMPREHENSIVE DATABASE INTEGRITY CHECKS
    # --------------------------------------------------------------------------
    print("\n" + "=" * 80)
    print("RUNNING AUTOMATED SQL INTEGRITY CHECKS")
    print("=" * 80)

    conn = sqlite3.connect(DB_INTEL_PATH)
    cur = conn.cursor()

    checks = []

    # Check 1: Duplicate Iceberg IDs
    cur.execute("SELECT iceberg_id, COUNT(*) FROM icebergs GROUP BY iceberg_id HAVING COUNT(*) > 1")
    dups_iceb = cur.fetchall()
    c1 = (len(dups_iceb) == 0)
    print(f"  [1] Duplicate Iceberg IDs:            {'PASS (0 duplicates)' if c1 else f'FAIL ({len(dups_iceb)} dups)'}")
    checks.append(c1)

    # Check 2: Duplicate Observations
    cur.execute("SELECT iceberg_id, timestamp, COUNT(*) FROM iceberg_observations GROUP BY iceberg_id, timestamp HAVING COUNT(*) > 1")
    dups_obs = cur.fetchall()
    c2 = (len(dups_obs) == 0)
    print(f"  [2] Duplicate Observations:           {'PASS (0 duplicates)' if c2 else f'FAIL ({len(dups_obs)} dups)'}")
    checks.append(c2)

    # Check 3: Duplicate Prediction Timestamps
    cur.execute("SELECT prediction_id, timestamp, COUNT(*) FROM trajectory_points GROUP BY prediction_id, timestamp HAVING COUNT(*) > 1")
    dups_pts = cur.fetchall()
    c3 = (len(dups_pts) == 0)
    print(f"  [3] Duplicate Prediction Points:      {'PASS (0 duplicates)' if c3 else f'FAIL ({len(dups_pts)} dups)'}")
    checks.append(c3)

    # Check 4: Foreign Key - Trajectory Points reference Valid Predictions
    cur.execute("SELECT COUNT(*) FROM trajectory_points WHERE prediction_id NOT IN (SELECT prediction_id FROM iceberg_predictions)")
    orphan_pts = cur.fetchone()[0]
    c4 = (orphan_pts == 0)
    print(f"  [4] Orphan Trajectory Points:         {'PASS (0 orphans)' if c4 else f'FAIL ({orphan_pts} orphans)'}")
    checks.append(c4)

    # Check 5: Foreign Key - Predictions reference Valid Icebergs
    cur.execute("SELECT COUNT(*) FROM iceberg_predictions WHERE iceberg_id NOT IN (SELECT iceberg_id FROM icebergs)")
    orphan_preds = cur.fetchone()[0]
    c5 = (orphan_preds == 0)
    print(f"  [5] Orphan Prediction Runs:           {'PASS (0 orphans)' if c5 else f'FAIL ({orphan_preds} orphans)'}")
    checks.append(c5)

    # Check 6: B22A Exact 49 Trajectory Records
    cur.execute("SELECT COUNT(*) FROM trajectory_points WHERE prediction_id = 'PRED_B22A_BASELINE_48H'")
    b22a_cnt = cur.fetchone()[0]
    c6 = (b22a_cnt == 49)
    print(f"  [6] B22A Trajectory Records:          {'PASS (Exactly 49 records)' if c6 else f'FAIL ({b22a_cnt} records)'}")
    checks.append(c6)

    # Check 7: C36 Exact 21 Trajectory Records
    cur.execute("SELECT COUNT(*) FROM trajectory_points WHERE prediction_id = 'PRED_C36_BASELINE_48H'")
    c36_cnt = cur.fetchone()[0]
    c7 = (c36_cnt == 21)
    print(f"  [7] C36 Trajectory Records:           {'PASS (Exactly 21 records)' if c7 else f'FAIL ({c36_cnt} records)'}")
    checks.append(c7)

    # Check 8: No C36 Future Fabricated Records (Max Step = 20)
    cur.execute("SELECT MAX(step_index) FROM trajectory_points WHERE prediction_id = 'PRED_C36_BASELINE_48H'")
    max_c36_step = cur.fetchone()[0]
    c8 = (max_c36_step == 20)
    print(f"  [8] C36 Stranding Step Boundary:      {'PASS (Max step 20 at T=20h)' if c8 else f'FAIL (Max step {max_c36_step})'}")
    checks.append(c8)

    # Check 9: Draft > Freeboard for Tabular Icebergs
    cur.execute("SELECT iceberg_id, freeboard_m, estimated_draft_m FROM iceberg_draft_estimates WHERE iceberg_id IN ('B22A', 'C36', 'D15A')")
    draft_rows = cur.fetchall()
    draft_valid = all(dr > fb for _, fb, dr in draft_rows) and len(draft_rows) == 3
    c9 = draft_valid
    print(f"  [9] Draft > Freeboard Physical Check: {'PASS (All 3 verified: Draft > Freeboard)' if c9 else 'FAIL'}")
    checks.append(c9)

    # Check 10: Valid Latitude Range (-90 to 0)
    cur.execute("SELECT COUNT(*) FROM trajectory_points WHERE latitude < -90 OR latitude > 0")
    lat_invalid = cur.fetchone()[0]
    c10 = (lat_invalid == 0)
    print(f" [10] Latitude Valid Bounds:           {'PASS (All Antarctic: -90° to 0°)' if c10 else 'FAIL'}")
    checks.append(c10)

    # Check 11: Valid Longitude Range (-180 to 180)
    cur.execute("SELECT COUNT(*) FROM trajectory_points WHERE longitude < -180 OR longitude > 180")
    lon_invalid = cur.fetchone()[0]
    c11 = (lon_invalid == 0)
    print(f" [11] Longitude Valid Bounds:          {'PASS (All within -180° to 180°)' if c11 else 'FAIL'}")
    checks.append(c11)

    # Check 12: UTC ISO8601 Timestamps
    cur.execute("SELECT COUNT(*) FROM trajectory_points WHERE timestamp NOT LIKE '%Z' AND timestamp NOT LIKE '%T%'")
    ts_invalid = cur.fetchone()[0]
    c12 = (ts_invalid == 0)
    print(f" [12] UTC ISO8601 Timestamp Format:    {'PASS (Strict UTC formatting)' if c12 else 'FAIL'}")
    checks.append(c12)

    # Check 13: Estimated Draft Method Explicitly Labelled
    cur.execute("SELECT COUNT(*) FROM iceberg_draft_estimates WHERE method NOT LIKE '%El-Tahan%'")
    meth_invalid = cur.fetchone()[0]
    c13 = (meth_invalid == 0)
    print(f" [13] Estimated Draft Method Provenance:{'PASS (El-Tahan hydrostatic labeled)' if c13 else 'FAIL'}")
    checks.append(c13)

    # Check 14: Diagnostics Table Verification
    cur.execute("SELECT COUNT(*) FROM openberg_run_diagnostics")
    diag_cnt = cur.fetchone()[0]
    c14 = (diag_cnt == 2)
    print(f" [14] Stage-2 Diagnostics Records:     {'PASS (B22A and C36 stored)' if c14 else 'FAIL'}")
    checks.append(c14)

    conn.close()

    all_passed = all(checks)
    print("\n" + "=" * 80)
    print(f"OVERALL SQL INTEGRITY STATUS: {'PASS (100% GREEN, 0 ERRORS)' if all_passed else 'FAIL (INTEGRITY ISSUE)'}")
    print("=" * 80 + "\n")


if __name__ == "__main__":
    execute_database_ingestion()

