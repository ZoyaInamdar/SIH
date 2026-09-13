-- ============================================================================
-- POLARIS — Canonical Backend SQLite Database Schema
-- File: database/schema.sql
-- Application Target: backend/antarctic.db
-- ============================================================================

PRAGMA foreign_keys = ON;

-- ----------------------------------------------------------------------------
-- 1. Table: ship_positions
-- Own-ship real-time and historical navigation telemetry.
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS ship_positions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    latitude REAL NOT NULL CHECK (latitude BETWEEN -90 AND 90),
    longitude REAL NOT NULL CHECK (longitude BETWEEN -180 AND 180),
    speed_knots REAL NOT NULL,
    heading_degrees REAL NOT NULL,
    timestamp TEXT NOT NULL
);

-- ----------------------------------------------------------------------------
-- 2. Table: icebergs
-- Master operational iceberg state, satellite geometries, and 48h forecasts.
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS icebergs (
    iceberg_id TEXT PRIMARY KEY,
    current_latitude REAL NOT NULL CHECK (current_latitude BETWEEN -90 AND 90),
    current_longitude REAL NOT NULL CHECK (current_longitude BETWEEN -180 AND 180),
    timestamp TEXT NOT NULL,
    length_m REAL,
    width_m REAL,
    freeboard_m REAL,
    shape_class TEXT,
    estimated_draft_m REAL,
    draft_uncertainty_m REAL,
    drift_speed_knots REAL,
    drift_direction_degrees REAL,
    predicted_latitude REAL,
    predicted_longitude REAL,
    forecast_time TEXT,
    bias_corrected_latitude REAL,
    bias_corrected_longitude REAL,
    bias_correction_applied INTEGER NOT NULL DEFAULT 0,
    status TEXT NOT NULL,
    confidence REAL NOT NULL,
    source TEXT DEFAULT 'unknown',
    last_updated TEXT
);

-- ----------------------------------------------------------------------------
-- 3. Table: sea_ice
-- Gridded sea-ice concentration and operational risk levels (OSI-SAF / AMSR2).
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS sea_ice (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    latitude REAL NOT NULL,
    longitude REAL NOT NULL,
    concentration REAL NOT NULL,
    risk_level TEXT NOT NULL,
    confidence REAL NOT NULL,
    timestamp TEXT NOT NULL
);

-- ----------------------------------------------------------------------------
-- 4. Table: hazards
-- Dynamic navigation hazard zones and proximity warning buffers.
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS hazards (
    id TEXT PRIMARY KEY,
    hazard_type TEXT NOT NULL,
    latitude REAL NOT NULL,
    longitude REAL NOT NULL,
    radius_m REAL NOT NULL,
    risk_level TEXT NOT NULL,
    confidence REAL NOT NULL,
    source TEXT NOT NULL,
    timestamp TEXT NOT NULL
);

-- ----------------------------------------------------------------------------
-- 5. Table: routes
-- Optimized navigation routes with POLARIS risk metrics and fuel estimates.
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS routes (
    route_id TEXT PRIMARY KEY,
    points TEXT NOT NULL DEFAULT '[]',
    distance_km REAL NOT NULL,
    estimated_fuel_cost REAL,
    risk_level TEXT NOT NULL,
    timestamp TEXT NOT NULL
);

-- ----------------------------------------------------------------------------
-- 6. Table: ais_vessels
-- AIS marine traffic and NCPOR research fleet tracking.
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS ais_vessels (
    vessel_id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    latitude REAL NOT NULL,
    longitude REAL NOT NULL,
    speed_knots REAL NOT NULL DEFAULT 0.0,
    heading_degrees REAL NOT NULL DEFAULT 0.0,
    is_ncpor_fleet INTEGER NOT NULL DEFAULT 0,
    timestamp TEXT NOT NULL
);

-- ----------------------------------------------------------------------------
-- 7. Table: fused_risk_grid
-- Multi-criteria POLARIS navigation risk grid (POLARIS RIO, DLIRI, sea ice, icebergs).
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS fused_risk_grid (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id TEXT NOT NULL,
    latitude REAL NOT NULL,
    longitude REAL NOT NULL,
    sic REAL NOT NULL,
    sit REAL,
    rio REAL,
    dliri REAL,
    iceberg_presence INTEGER NOT NULL DEFAULT 0,
    iceberg_distance_km REAL,
    iceberg_forecast_time TEXT,
    sea_ice_risk TEXT NOT NULL,
    iceberg_risk TEXT NOT NULL,
    risk_score REAL NOT NULL,
    risk_score_type TEXT NOT NULL,
    operational_risk TEXT NOT NULL,
    risk_source TEXT NOT NULL,
    vessel_class TEXT NOT NULL,
    timestamp TEXT NOT NULL
);

-- ----------------------------------------------------------------------------
-- 8. Table: trajectory_points
-- Time-series predicted trajectory steps for operational visualization.
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS trajectory_points (
    point_id INTEGER PRIMARY KEY AUTOINCREMENT,
    iceberg_id TEXT NOT NULL REFERENCES icebergs(iceberg_id) ON DELETE CASCADE,
    step_index INTEGER NOT NULL,
    timestamp TEXT NOT NULL,
    latitude REAL NOT NULL,
    longitude REAL NOT NULL,
    velocity_x REAL,
    velocity_y REAL,
    speed_mps REAL,
    heading_deg REAL
);

-- ----------------------------------------------------------------------------
-- 9. Table: openberg_diagnostics
-- Summary kinematics and physical verification diagnostics for forecast runs.
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS openberg_diagnostics (
    diagnostic_id TEXT PRIMARY KEY,
    iceberg_id TEXT NOT NULL REFERENCES icebergs(iceberg_id) ON DELETE CASCADE,
    duration_hours REAL NOT NULL,
    record_count INTEGER NOT NULL,
    path_net_ratio REAL NOT NULL,
    mean_speed_knots REAL NOT NULL,
    minimum_clearance_m REAL,
    grounding_detected INTEGER NOT NULL DEFAULT 0,
    stranding_detected INTEGER NOT NULL DEFAULT 0,
    classification TEXT NOT NULL,
    created_at TEXT DEFAULT (datetime('now'))
);

-- Indexes for performance
CREATE INDEX IF NOT EXISTS idx_icebergs_status ON icebergs(status);
CREATE INDEX IF NOT EXISTS idx_traj_iceberg_step ON trajectory_points(iceberg_id, step_index);
CREATE INDEX IF NOT EXISTS idx_hazards_type ON hazards(hazard_type);
CREATE INDEX IF NOT EXISTS idx_fused_risk_run ON fused_risk_grid(run_id);
