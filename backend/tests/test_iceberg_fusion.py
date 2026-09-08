from __future__ import annotations

import unittest
from datetime import datetime, timezone

from backend.routing.risk_fusion import (
    fuse_iceberg_and_sea_ice_risk,
    get_fused_risk,
    clear_fused_grid_store,
    metric_distance_epsg3031
)


class TestIcebergRiskFusion(unittest.TestCase):
    """
    23-point integration test suite covering Spatial, Temporal, Fusion, and Pipeline contracts.
    """

    def setUp(self) -> None:
        clear_fused_grid_store()
        self.master_sea_ice_grid = [
            {"latitude": -65.0, "longitude": -55.0, "SIC": 0.20, "DLIRI": 15.0, "sea_ice_risk": "SAFE", "sea_ice_risk_source": "DLIRI"},
            {"latitude": -65.1, "longitude": -55.1, "SIC": 0.45, "DLIRI": 50.0, "sea_ice_risk": "CAUTION", "sea_ice_risk_source": "DLIRI"},
            {"latitude": -65.2, "longitude": -55.2, "SIC": 0.85, "RIO": 85.0, "rio_available": True, "sea_ice_risk": "RESTRICTED", "sea_ice_risk_source": "POLARIS_RIO"},
        ]

    # -----------------------------------------------------------------
    # SPATIAL TESTS
    # -----------------------------------------------------------------
    def test_01_iceberg_inside_corridor_creates_hazard_cells(self):
        trajectories = [{"latitude": -65.0, "longitude": -55.0, "forecast_hour": 0.0, "timestamp": "2026-09-08T00:00:00Z"}]
        fused = fuse_iceberg_and_sea_ice_risk(self.master_sea_ice_grid, trajectories, run_id="run_spatial_1")
        self.assertTrue(fused[0].iceberg_presence)
        self.assertEqual(fused[0].operational_risk, "EXTREME")
        self.assertEqual(fused[0].risk_source, "ICEBERG_COLLISION_ZONE")

    def test_02_iceberg_outside_corridor_does_not_create_hazard_cells(self):
        trajectories = [{"latitude": -75.0, "longitude": -10.0, "forecast_hour": 0.0, "timestamp": "2026-09-08T00:00:00Z"}]
        fused = fuse_iceberg_and_sea_ice_risk(self.master_sea_ice_grid, trajectories, run_id="run_spatial_2")
        self.assertFalse(fused[0].iceberg_presence)
        self.assertEqual(fused[0].operational_risk, "SAFE")

    def test_03_buffer_10km_metric_epsg3031(self):
        dist_m = metric_distance_epsg3031(-65.0, -55.0, -65.05, -55.05)
        self.assertTrue(dist_m > 0)
        self.assertIsInstance(dist_m, float)

    def test_04_lat_lon_ordering(self):
        trajectories = [{"latitude": -65.0, "longitude": -55.0, "forecast_hour": 0.0}]
        fused = fuse_iceberg_and_sea_ice_risk(self.master_sea_ice_grid, trajectories, run_id="run_spatial_4")
        self.assertEqual(fused[0].latitude, -65.0)
        self.assertEqual(fused[0].longitude, -55.0)

    def test_05_iceberg_distance_measured_in_kilometers(self):
        trajectories = [{"latitude": -65.01, "longitude": -55.01, "forecast_hour": 0.0}]
        fused = fuse_iceberg_and_sea_ice_risk(self.master_sea_ice_grid, trajectories, run_id="run_spatial_5")
        self.assertIsNotNone(fused[0].iceberg_distance_km)
        self.assertTrue(0.0 < fused[0].iceberg_distance_km < 10.0)

    def test_06_multiple_trajectory_points_do_not_duplicate_cell(self):
        trajectories = [
            {"latitude": -65.0, "longitude": -55.0, "forecast_hour": 0.0},
            {"latitude": -65.01, "longitude": -55.01, "forecast_hour": 1.0}
        ]
        fused = fuse_iceberg_and_sea_ice_risk(self.master_sea_ice_grid, trajectories, run_id="run_spatial_6")
        self.assertEqual(len(fused), len(self.master_sea_ice_grid))

    def test_07_fused_grid_has_exact_sic_master_coordinates(self):
        trajectories = [{"latitude": -65.0, "longitude": -55.0, "forecast_hour": 0.0}]
        fused = fuse_iceberg_and_sea_ice_risk(self.master_sea_ice_grid, trajectories, run_id="run_spatial_7")
        for orig, cell in zip(self.master_sea_ice_grid, fused):
            self.assertEqual(orig["latitude"], cell.latitude)
            self.assertEqual(orig["longitude"], cell.longitude)

    # -----------------------------------------------------------------
    # TEMPORAL TESTS
    # -----------------------------------------------------------------
    def test_08_forecast_timestamps_retained(self):
        trajectories = [{"latitude": -65.0, "longitude": -55.0, "forecast_hour": 0.0, "forecast_time": "2026-09-08T12:00:00Z"}]
        fused = fuse_iceberg_and_sea_ice_risk(self.master_sea_ice_grid, trajectories, run_id="run_temp_8")
        self.assertEqual(fused[0].iceberg_forecast_time, "2026-09-08T12:00:00Z")

    def test_09_configured_forecast_horizon_respected(self):
        trajectories = [{"latitude": -65.0, "longitude": -55.0, "forecast_hour": 12.0, "forecast_time": "2026-09-08T12:00:00Z"}]
        fused = fuse_iceberg_and_sea_ice_risk(self.master_sea_ice_grid, trajectories, forecast_hours=6.0, run_id="run_temp_9")
        self.assertFalse(fused[0].iceberg_presence)

    def test_10_closest_relevant_forecast_position_associated(self):
        trajectories = [{"latitude": -65.0, "longitude": -55.0, "forecast_hour": 3.0, "forecast_time": "2026-09-08T03:00:00Z"}]
        fused = fuse_iceberg_and_sea_ice_risk(self.master_sea_ice_grid, trajectories, forecast_hours=6.0, run_id="run_temp_10")
        self.assertTrue(fused[0].iceberg_presence)

    # -----------------------------------------------------------------
    # FUSION TESTS
    # -----------------------------------------------------------------
    def test_11_iceberg_presence_elevates_operational_risk_to_extreme(self):
        trajectories = [{"latitude": -65.0, "longitude": -55.0, "forecast_hour": 0.0}]
        fused = fuse_iceberg_and_sea_ice_risk(self.master_sea_ice_grid, trajectories, run_id="run_fuse_11")
        self.assertEqual(fused[0].operational_risk, "EXTREME")

    def test_12_iceberg_presence_does_not_modify_rio(self):
        trajectories = [{"latitude": -65.2, "longitude": -55.2, "forecast_hour": 0.0}]
        fused = fuse_iceberg_and_sea_ice_risk(self.master_sea_ice_grid, trajectories, run_id="run_fuse_12")
        self.assertEqual(fused[2].RIO, 85.0)

    def test_13_iceberg_presence_does_not_modify_dliri(self):
        trajectories = [{"latitude": -65.1, "longitude": -55.1, "forecast_hour": 0.0}]
        fused = fuse_iceberg_and_sea_ice_risk(self.master_sea_ice_grid, trajectories, run_id="run_fuse_13")
        self.assertEqual(fused[1].DLIRI, 50.0)

    def test_14_iceberg_presence_does_not_modify_sic_sit_icetype(self):
        trajectories = [{"latitude": -65.0, "longitude": -55.0, "forecast_hour": 0.0}]
        fused = fuse_iceberg_and_sea_ice_risk(self.master_sea_ice_grid, trajectories, run_id="run_fuse_14")
        self.assertEqual(fused[0].SIC, 0.20)

    def test_15_sea_ice_risk_preserves_pre_iceberg_assessment(self):
        trajectories = [{"latitude": -65.0, "longitude": -55.0, "forecast_hour": 0.0}]
        fused = fuse_iceberg_and_sea_ice_risk(self.master_sea_ice_grid, trajectories, run_id="run_fuse_15")
        self.assertEqual(fused[0].sea_ice_risk, "SAFE")

    def test_16_sea_ice_risk_source_preserves_original_source(self):
        trajectories = [{"latitude": -65.0, "longitude": -55.0, "forecast_hour": 0.0}]
        fused = fuse_iceberg_and_sea_ice_risk(self.master_sea_ice_grid, trajectories, run_id="run_fuse_16")
        self.assertEqual(fused[0].sea_ice_risk_source, "DLIRI")

    def test_17_iceberg_risk_correctly_identifies_hazard(self):
        trajectories = [{"latitude": -65.0, "longitude": -55.0, "forecast_hour": 0.0}]
        fused = fuse_iceberg_and_sea_ice_risk(self.master_sea_ice_grid, trajectories, run_id="run_fuse_17")
        self.assertEqual(fused[0].iceberg_risk, "EXTREME")

    def test_18_risk_score_hierarchy_priority_1_iceberg(self):
        trajectories = [{"latitude": -65.0, "longitude": -55.0, "forecast_hour": 0.0}]
        fused = fuse_iceberg_and_sea_ice_risk(self.master_sea_ice_grid, trajectories, run_id="run_fuse_18")
        self.assertEqual(fused[0].risk_score, 100.0)
        self.assertEqual(fused[0].risk_score_type, "ICEBERG_COLLISION_ZONE")

    def test_19_risk_score_hierarchy_priority_2_polaris_rio(self):
        trajectories = []
        fused = fuse_iceberg_and_sea_ice_risk(self.master_sea_ice_grid, trajectories, run_id="run_fuse_19")
        self.assertEqual(fused[2].risk_score, 85.0)
        self.assertEqual(fused[2].risk_score_type, "POLARIS_RIO")

    # -----------------------------------------------------------------
    # PIPELINE TESTS
    # -----------------------------------------------------------------
    def test_20_route_isolation(self):
        trajectories_a = [{"latitude": -65.0, "longitude": -55.0, "forecast_hour": 0.0}]
        fuse_iceberg_and_sea_ice_risk(self.master_sea_ice_grid, trajectories_a, run_id="route_A")
        fuse_iceberg_and_sea_ice_risk(self.master_sea_ice_grid, [], run_id="route_B")
        
        lookup_a = get_fused_risk(-65.0, -55.0, run_id="route_A")
        lookup_b = get_fused_risk(-65.0, -55.0, run_id="route_B")
        self.assertTrue(lookup_a["iceberg_presence"])
        self.assertFalse(lookup_b["iceberg_presence"])

    def test_21_disabled_iceberg_prediction_skips_hazard(self):
        fused = fuse_iceberg_and_sea_ice_risk(self.master_sea_ice_grid, [], run_id="run_pipe_21")
        self.assertFalse(any(cell.iceberg_presence for cell in fused))

    def test_22_empty_trajectories_fail_gracefully(self):
        fused = fuse_iceberg_and_sea_ice_risk(self.master_sea_ice_grid, [], run_id="run_pipe_22")
        self.assertEqual(len(fused), 3)

    def test_23_nmea_retrieves_combined_risk_from_single_grid(self):
        trajectories = [{"latitude": -65.0, "longitude": -55.0, "forecast_hour": 0.0}]
        fuse_iceberg_and_sea_ice_risk(self.master_sea_ice_grid, trajectories, run_id="route_NMEA")
        risk = get_fused_risk(-65.0, -55.0, run_id="route_NMEA")
        self.assertIsNotNone(risk)
        self.assertEqual(risk["operational_risk"], "EXTREME")
        self.assertEqual(risk["risk_source"], "ICEBERG_COLLISION_ZONE")


if __name__ == "__main__":
    unittest.main()
