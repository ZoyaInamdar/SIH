-- ============================================================================
-- POLARIS Iceberg Intelligence Pipeline — Seed Stage 2 OpenBerg Controlled Baseline
-- File: 026_seed_stage2_openberg_baseline.sql
-- ============================================================================

PRAGMA foreign_keys = ON;

-- 1. Seed Iceberg Master Identities (B22A, C36, D15A)
INSERT OR REPLACE INTO icebergs (iceberg_id, name, origin, created_at) VALUES
('B22A', 'B22A', 'Ross Sea / Thwaites Calving', '2026-09-10T00:00:00Z'),
('C36', 'C36', 'George V Coast / Mertz Region', '2026-09-10T00:00:00Z'),
('D15A', 'D15A', 'East Antarctica / Davis Sea', '2026-09-10T00:00:00Z');

-- 2. Seed Iceberg Satellite Observations (Sentinel-1 SAR + ICESat-2 ATL06)
INSERT OR REPLACE INTO iceberg_observations (iceberg_id, timestamp, latitude, longitude, length_km, width_km, area_km2, source) VALUES
('B22A', '2026-09-10T00:00:00Z', -69.88, 164.79, 56.4, 47.2, 2663.23, 'Sentinel-1 SAR Polygon 2b14c602 + ICESat-2 ATL06 RGT0261'),
('C36', '2026-09-10T00:00:00Z', -67.46, 146.48, 44.7, 30.2, 1351.82, 'Sentinel-1 SAR Polygon a03a93dd + ICESat-2 ATL06 RGT0078'),
('D15A', '2026-09-10T00:00:00Z', -66.63, 81.92, 99.2, 41.6, 4121.59, 'Sentinel-1 SAR Polygon 862a5864 + ICESat-2 ATL06 RGT0820');

-- 3. Seed Estimated Draft Values (El-Tahan 1982 Tabular Relationship - NOT Measured)
INSERT INTO iceberg_draft_estimates (iceberg_id, freeboard_m, estimated_draft_m, shape_class, method, method_version, total_height_m, created_at) VALUES
('B22A', 43.87, 65.67, 'TABULAR', 'El-Tahan (1982) Empirical Tabular Hydrostatic Relationship', 'POLARIS Vertical Geometry v1.0', 109.54, '2026-09-12T00:00:00Z'),
('C36', 33.33, 67.03, 'TABULAR', 'El-Tahan (1982) Empirical Tabular Hydrostatic Relationship', 'POLARIS Vertical Geometry v1.0', 100.36, '2026-09-12T00:00:00Z'),
('D15A', 38.27, 66.38, 'TABULAR', 'El-Tahan (1982) Empirical Tabular Hydrostatic Relationship', 'POLARIS Vertical Geometry v1.0', 104.65, '2026-09-12T00:00:00Z');

-- 4. Seed Environmental Forcing Metadata
INSERT INTO environmental_sources (source_name, variable_group, file_reference, spatial_extent, temporal_extent, notes, created_at) VALUES
('ECMWF AIFS Operational Wind Forecast', 'Atmospheric Wind (10u, 10v -> x_wind, y_wind)', 'data/forecast/openberg_ready/{iceberg_id}/{iceberg_id}_aifs_wind_openberg.nc', 'Spatial resolution: 0.25 deg', '2026-09-13T00:00:00Z to 2026-09-15T00:00:00Z (6-hourly)', 'VALIDATED_FOR_OPENBERG', '2026-09-13T00:00:00Z'),
('Copernicus Marine 3D Ocean Analysis and Forecast', '3D Ocean Currents (uo, vo -> x_sea_water_velocity, y_sea_water_velocity)', 'data/forecast/openberg_ready/{iceberg_id}/{iceberg_id}_copernicus_currents_openberg.nc', 'Spatial resolution: 0.083 deg (~4.0 km zonal)', '2026-09-13T00:00:00Z to 2026-09-15T00:00:00Z (6-hourly, depths 0.494-92.326m)', 'VALIDATED_FOR_OPENBERG', '2026-09-13T00:00:00Z'),
('GEBCO Regional Bathymetry Grid', 'Seafloor Bathymetry (sea_floor_depth_below_sea_level)', 'data/forecast/openberg_ready/{iceberg_id}/{iceberg_id}_gebco_openberg.nc', 'Spatial resolution: 15 arc-second (~460 m)', 'Static 2D Field', 'VALIDATED_FOR_OPENBERG', '2026-09-13T00:00:00Z'),
('OSI-SAF Sea Ice Concentration', 'Sea Ice Concentration (sea_ice_area_fraction)', 'data/forecast/openberg_ready/{iceberg_id}/{iceberg_id}_sea_ice_openberg.nc', 'Spatial resolution: 10.0 km polar stereographic', 'Initialization State (2026-09-11 to 2026-09-12 NRT observations, NOT 48h forecast)', 'VALIDATED_FOR_OPENBERG (Static Initial Concentration Field)', '2026-09-13T00:00:00Z');

-- 5. Seed OpenBerg Physics Configuration (Uncalibrated Baseline, Diffusivity=0)
INSERT OR REPLACE INTO model_configurations (configuration_id, model_name, model_version, ca, cda, cw, cdw, draft_m, length_m, width_m, freeboard_m, timestep_seconds, current_mode, cda_mode, description, created_at) VALUES
('B22A_CONTROLLED_BASELINE', 'OpenBerg', 'v1.14.11', 0.80, 0.00220, 0.25, 0.00550, 65.67, 56400.0, 47200.0, 43.87, 3600, '3d_depth_integrated_copernicus', 'uncalibrated_default', 'B22A 48h Controlled Physics Baseline (Uncalibrated Standard Physics, horizontal_diffusivity=0 m2/s)', '2026-09-13T00:00:00Z'),
('C36_CONTROLLED_BASELINE', 'OpenBerg', 'v1.14.11', 0.80, 0.00220, 0.25, 0.00550, 67.03, 44700.0, 30200.0, 33.33, 3600, '3d_depth_integrated_copernicus', 'uncalibrated_default', 'C36 48h Controlled Physics Baseline (Uncalibrated Standard Physics, horizontal_diffusivity=0 m2/s)', '2026-09-13T00:00:00Z');

-- 6. Seed OpenBerg Prediction Run Records
INSERT OR REPLACE INTO iceberg_predictions (prediction_id, iceberg_id, model_name, model_version, run_label, start_time, end_time, draft_source, draft_m, sail_m, length_m, width_m, timestep_seconds, created_at) VALUES
('PRED_B22A_BASELINE_48H', 'B22A', 'OpenBerg', 'v1.14.11', 'B22A_CONTROLLED_BASELINE', '2026-09-13T00:00:00Z', '2026-09-15T00:00:00Z', 'El-Tahan Empirical Model', 65.67, 43.87, 56400.0, 47200.0, 3600, '2026-09-13T00:00:00Z'),
('PRED_C36_BASELINE_48H', 'C36', 'OpenBerg', 'v1.14.11', 'C36_CONTROLLED_BASELINE', '2026-09-13T00:00:00Z', '2026-09-15T00:00:00Z', 'El-Tahan Empirical Model', 67.03, 33.33, 44700.0, 30200.0, 3600, '2026-09-13T00:00:00Z');

-- 7. Seed B22A Predicted Trajectory Points (49 Records: T=0 to T=48h)
INSERT INTO trajectory_points (prediction_id, step_index, timestamp, latitude, longitude, velocity_x, velocity_y, derived_speed_ms, derived_direction_deg) VALUES
('PRED_B22A_BASELINE_48H', 0, '2026-09-13T00:00:00Z', -69.880000, 164.790000, 0.000000, 0.000000, 0.0000, 79.2),
('PRED_B22A_BASELINE_48H', 1, '2026-09-13T01:00:00Z', -69.876760, 164.839130, 0.108445, 0.005824, 0.1086, 33.5),
('PRED_B22A_BASELINE_48H', 2, '2026-09-13T02:00:00Z', -69.859790, 164.871770, 0.117757, -0.002117, 0.1178, 112.8),
('PRED_B22A_BASELINE_48H', 3, '2026-09-13T03:00:00Z', -69.867485, 164.924910, 0.127193, -0.008439, 0.1275, 97.7),
('PRED_B22A_BASELINE_48H', 4, '2026-09-13T04:00:00Z', -69.869050, 164.958620, 0.135788, -0.012767, 0.1364, 55.9),
('PRED_B22A_BASELINE_48H', 5, '2026-09-13T05:00:00Z', -69.866450, 164.969790, 0.143613, -0.016295, 0.1445, 29.8),
('PRED_B22A_BASELINE_48H', 6, '2026-09-13T06:00:00Z', -69.856030, 164.987120, 0.151131, -0.019951, 0.1524, 89.1),
('PRED_B22A_BASELINE_48H', 7, '2026-09-13T07:00:00Z', -69.855865, 165.018860, 0.159547, -0.023740, 0.1613, 79.2),
('PRED_B22A_BASELINE_48H', 8, '2026-09-13T08:00:00Z', -69.854270, 165.043210, 0.155563, -0.029055, 0.1583, 99.4),
('PRED_B22A_BASELINE_48H', 9, '2026-09-13T09:00:00Z', -69.856940, 165.090360, 0.151334, -0.034588, 0.1552, 137.7),
('PRED_B22A_BASELINE_48H', 10, '2026-09-13T10:00:00Z', -69.864746, 165.111000, 0.146549, -0.040662, 0.1521, 283.0),
('PRED_B22A_BASELINE_48H', 11, '2026-09-13T11:00:00Z', -69.861300, 165.067810, 0.140606, -0.047492, 0.1484, 123.8),
('PRED_B22A_BASELINE_48H', 12, '2026-09-13T12:00:00Z', -69.868640, 165.099690, 0.136518, -0.052413, 0.1462, 121.2),
('PRED_B22A_BASELINE_48H', 13, '2026-09-13T13:00:00Z', -69.881615, 165.162060, 0.130443, -0.059561, 0.1434, 131.6),
('PRED_B22A_BASELINE_48H', 14, '2026-09-13T14:00:00Z', -69.885020, 165.173220, 0.108157, -0.061391, 0.1244, 57.6),
('PRED_B22A_BASELINE_48H', 15, '2026-09-13T15:00:00Z', -69.875810, 165.215320, 0.087905, -0.061032, 0.1070, 75.0),
('PRED_B22A_BASELINE_48H', 16, '2026-09-13T16:00:00Z', -69.874886, 165.225330, 0.070369, -0.060580, 0.0929, 196.7),
('PRED_B22A_BASELINE_48H', 17, '2026-09-13T17:00:00Z', -69.891880, 165.210500, 0.051116, -0.059807, 0.0787, 246.9),
('PRED_B22A_BASELINE_48H', 18, '2026-09-13T18:00:00Z', -69.892624, 165.205380, 0.027496, -0.059964, 0.0660, 53.0),
('PRED_B22A_BASELINE_48H', 19, '2026-09-13T19:00:00Z', -69.885380, 165.233300, 0.007862, -0.059123, 0.0596, 222.7),
('PRED_B22A_BASELINE_48H', 20, '2026-09-13T20:00:00Z', -69.889380, 165.222580, -0.023096, -0.052627, 0.0575, 218.5),
('PRED_B22A_BASELINE_48H', 21, '2026-09-13T21:00:00Z', -69.901680, 165.194090, -0.056480, -0.046409, 0.0731, 310.3),
('PRED_B22A_BASELINE_48H', 22, '2026-09-13T22:00:00Z', -69.888160, 165.147810, -0.091286, -0.040979, 0.1001, 240.8),
('PRED_B22A_BASELINE_48H', 23, '2026-09-13T23:00:00Z', -69.892510, 165.125210, -0.120927, -0.031530, 0.1250, 289.4),
('PRED_B22A_BASELINE_48H', 24, '2026-09-14T00:00:00Z', -69.887400, 165.083070, -0.154095, -0.024938, 0.1561, 263.3),
('PRED_B22A_BASELINE_48H', 25, '2026-09-14T01:00:00Z', -69.889530, 165.029950, -0.185933, -0.015965, 0.1866, 281.8),
('PRED_B22A_BASELINE_48H', 26, '2026-09-14T02:00:00Z', -69.886830, 164.992520, -0.188224, -0.007747, 0.1884, 228.2),
('PRED_B22A_BASELINE_48H', 27, '2026-09-14T03:00:00Z', -69.895780, 164.963440, -0.189700, 0.000788, 0.1897, 298.7),
('PRED_B22A_BASELINE_48H', 28, '2026-09-14T04:00:00Z', -69.892280, 164.944850, -0.191434, 0.007477, 0.1916, 296.1),
('PRED_B22A_BASELINE_48H', 29, '2026-09-14T05:00:00Z', -69.889480, 164.928250, -0.192634, 0.015489, 0.1933, 259.7),
('PRED_B22A_BASELINE_48H', 30, '2026-09-14T06:00:00Z', -69.891495, 164.896060, -0.193846, 0.023216, 0.1952, 261.4),
('PRED_B22A_BASELINE_48H', 31, '2026-09-14T07:00:00Z', -69.893220, 164.862950, -0.194605, 0.031217, 0.1971, 226.1),
('PRED_B22A_BASELINE_48H', 32, '2026-09-14T08:00:00Z', -69.905205, 164.826680, -0.194890, 0.035373, 0.1981, 250.0),
('PRED_B22A_BASELINE_48H', 33, '2026-09-14T09:00:00Z', -69.906980, 164.812420, -0.193693, 0.039550, 0.1977, 284.7),
('PRED_B22A_BASELINE_48H', 34, '2026-09-14T10:00:00Z', -69.902070, 164.758200, -0.193627, 0.043136, 0.1984, 278.6),
('PRED_B22A_BASELINE_48H', 35, '2026-09-14T11:00:00Z', -69.900085, 164.720060, -0.192679, 0.049166, 0.1989, 347.1),
('PRED_B22A_BASELINE_48H', 36, '2026-09-14T12:00:00Z', -69.897380, 164.718260, -0.190968, 0.053259, 0.1983, 161.9),
('PRED_B22A_BASELINE_48H', 37, '2026-09-14T13:00:00Z', -69.905000, 164.725520, -0.191173, 0.054923, 0.1989, 221.1),
('PRED_B22A_BASELINE_48H', 38, '2026-09-14T14:00:00Z', -69.908510, 164.716600, -0.190113, 0.052591, 0.1973, 257.8),
('PRED_B22A_BASELINE_48H', 39, '2026-09-14T15:00:00Z', -69.911260, 164.679600, -0.188821, 0.051054, 0.1956, 284.1),
('PRED_B22A_BASELINE_48H', 40, '2026-09-14T16:00:00Z', -69.909170, 164.655320, -0.185314, 0.051430, 0.1923, 299.8),
('PRED_B22A_BASELINE_48H', 41, '2026-09-14T17:00:00Z', -69.900680, 164.612200, -0.184778, 0.050890, 0.1917, 193.9),
('PRED_B22A_BASELINE_48H', 42, '2026-09-14T18:00:00Z', -69.910710, 164.604970, -0.187013, 0.051077, 0.1939, 18.7),
('PRED_B22A_BASELINE_48H', 43, '2026-09-14T19:00:00Z', -69.894650, 164.620800, -0.181810, 0.050596, 0.1887, 93.0),
('PRED_B22A_BASELINE_48H', 44, '2026-09-14T20:00:00Z', -69.894830, 164.630400, -0.175486, 0.036964, 0.1793, 303.7),
('PRED_B22A_BASELINE_48H', 45, '2026-09-14T21:00:00Z', -69.885960, 164.591700, -0.160277, 0.026153, 0.1624, 321.5),
('PRED_B22A_BASELINE_48H', 46, '2026-09-14T22:00:00Z', -69.876100, 164.568940, -0.147862, 0.017480, 0.1489, 339.5),
('PRED_B22A_BASELINE_48H', 47, '2026-09-14T23:00:00Z', -69.868440, 164.560640, -0.137566, 0.007137, 0.1378, 345.3),
('PRED_B22A_BASELINE_48H', 48, '2026-09-15T00:00:00Z', -69.863190, 164.556640, -0.126673, -0.003796, 0.1267, 345.3);

-- 8. Seed C36 Predicted Trajectory Points (21 Records: T=0 to T=20h, Stranded at Coastline)
INSERT INTO trajectory_points (prediction_id, step_index, timestamp, latitude, longitude, velocity_x, velocity_y, derived_speed_ms, derived_direction_deg) VALUES
('PRED_C36_BASELINE_48H', 0, '2026-09-13T00:00:00Z', -67.460000, 146.480000, 0.000000, 0.000000, 0.0000, 25.8),
('PRED_C36_BASELINE_48H', 1, '2026-09-13T01:00:00Z', -67.442986, 146.501420, -0.160874, 0.432655, 0.4616, 2.6),
('PRED_C36_BASELINE_48H', 2, '2026-09-13T02:00:00Z', -67.412120, 146.505100, -0.186763, 0.428153, 0.4671, 52.5),
('PRED_C36_BASELINE_48H', 3, '2026-09-13T03:00:00Z', -67.406320, 146.524780, -0.205791, 0.409678, 0.4585, 358.1),
('PRED_C36_BASELINE_48H', 4, '2026-09-13T04:00:00Z', -67.394340, 146.523770, -0.235961, 0.406686, 0.4702, 329.8),
('PRED_C36_BASELINE_48H', 5, '2026-09-13T05:00:00Z', -67.378410, 146.499710, -0.262590, 0.396751, 0.4758, 340.7),
('PRED_C36_BASELINE_48H', 6, '2026-09-13T06:00:00Z', -67.354970, 146.478400, -0.288420, 0.383198, 0.4796, 340.9),
('PRED_C36_BASELINE_48H', 7, '2026-09-13T07:00:00Z', -67.342155, 146.466900, -0.316621, 0.368303, 0.4857, 333.3),
('PRED_C36_BASELINE_48H', 8, '2026-09-13T08:00:00Z', -67.328910, 146.449620, -0.311190, 0.331614, 0.4548, 10.3),
('PRED_C36_BASELINE_48H', 9, '2026-09-13T09:00:00Z', -67.320920, 146.453380, -0.307136, 0.295690, 0.4263, 285.1),
('PRED_C36_BASELINE_48H', 10, '2026-09-13T10:00:00Z', -67.318920, 146.434070, -0.304812, 0.263479, 0.4029, 293.3),
('PRED_C36_BASELINE_48H', 11, '2026-09-13T11:00:00Z', -67.306370, 146.358500, -0.302260, 0.234172, 0.3824, 284.1),
('PRED_C36_BASELINE_48H', 12, '2026-09-13T12:00:00Z', -67.305580, 146.350330, -0.301690, 0.199275, 0.3616, 125.9),
('PRED_C36_BASELINE_48H', 13, '2026-09-13T13:00:00Z', -67.311066, 146.369980, -0.300086, 0.172619, 0.3462, 295.5),
('PRED_C36_BASELINE_48H', 14, '2026-09-13T14:00:00Z', -67.306860, 146.347180, -0.283491, 0.174400, 0.3328, 10.1),
('PRED_C36_BASELINE_48H', 15, '2026-09-13T15:00:00Z', -67.290130, 146.354930, -0.268346, 0.171858, 0.3187, 319.3),
('PRED_C36_BASELINE_48H', 16, '2026-09-13T16:00:00Z', -67.281944, 146.336720, -0.254618, 0.164357, 0.3031, 235.7),
('PRED_C36_BASELINE_48H', 17, '2026-09-13T17:00:00Z', -67.291820, 146.299240, -0.239533, 0.161074, 0.2887, 303.7),
('PRED_C36_BASELINE_48H', 18, '2026-09-13T18:00:00Z', -67.285390, 146.274260, -0.217101, 0.162100, 0.2709, 11.7),
('PRED_C36_BASELINE_48H', 19, '2026-09-13T19:00:00Z', -67.271140, 146.281880, -0.198740, 0.157898, 0.2538, 270.0),
('PRED_C36_BASELINE_48H', 20, '2026-09-13T20:00:00Z', -67.271140, 146.265670, -0.193572, 0.149653, 0.2447, 270.0);

-- 9. Seed OpenBerg Stage-2 Trajectory Diagnostics & Kinematic Summaries
INSERT OR REPLACE INTO openberg_run_diagnostics (diagnostic_id, prediction_id, iceberg_id, forecast_start, forecast_end, duration_hours, record_count, straight_line_displacement_km, cumulative_path_km, path_net_ratio, mean_speed_mps, max_speed_mps, mean_speed_knots, mean_wind_mps, max_wind_mps, mean_current_mps, max_current_mps, minimum_clearance_m, grounding_detected, stranding_detected, stranding_timestamp, diagnostic_classification, reproducibility_diff, reproducibility_pass) VALUES
('DIAG_B22A_BASELINE', 'PRED_B22A_BASELINE_48H', 'B22A', '2026-09-13T00:00:00Z', '2026-09-15T00:00:00Z', 48.0, 49, 9.123, 63.707, 6.98, 0.1498, 0.1989, 0.29, 5.54, 7.06, 0.0361, 0.0633, 319.4, 0, 0, NULL, 'trajectory meandering consistent with changing environmental forcing', 0.0, 1),
('DIAG_C36_BASELINE', 'PRED_C36_BASELINE_48H', 'C36', '2026-09-13T00:00:00Z', '2026-09-15T00:00:00Z', 20.0, 21, 22.916, 32.311, 1.41, 0.3660, 0.4857, 0.71, 11.48, 13.78, 0.1196, 0.1723, 485.4, 0, 1, '2026-09-13T20:00:00Z', 'coastal shoreline stranding at T+20h; no seafloor grounding', 0.0, 1);
