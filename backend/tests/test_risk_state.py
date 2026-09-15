from __future__ import annotations

import unittest
from datetime import datetime, timezone

from backend.schemas import RiskState
from backend.services.risk_state_service import (
    evaluate_node_risk_state,
    aggregate_risk_state_grid,
    get_risk_state_at,
    get_risk_state_grid,
    get_risk_state_geojson,
    clear_risk_state_store,
)
from backend.database import update_iceberg_sonar_feedback
from backend.routing.astar import AStarRouter
from backend.routing.grid import create_ocean_grid


class TestUnifiedRiskStateLayer(unittest.TestCase):
    """
    Test suite verifying the Unified RiskState Interception Layer:
    - Deliverable 1: Pydantic Schema integrity
    - Deliverable 2: Convergence of the 3 processing models into RiskState
    - Deliverable 3: Consumer data access (NMEA, A*, Map/Globe) & Sonar feedback loop
    """

    def setUp(self) -> None:
        clear_risk_state_store()

    # =========================================================================
    # 1. SCHEMA VALIDATION TESTS
    # =========================================================================

    def test_01_risk_state_schema_instantiation(self):
        rs = RiskState(
            node_id="node_1",
            latitude=-62.5,
            longitude=-60.0,
            timestamp=datetime.now(timezone.utc).isoformat(),
            sic=0.25,
            wmo_zone="CAUTION",
            sea_ice_risk="CAUTION",
            operational_risk="CAUTION",
            risk_score=25.0,
            speed_penalty_factor=0.5,
        )
        self.assertEqual(rs.node_id, "node_1")
        self.assertEqual(rs.sic, 0.25)
        self.assertEqual(rs.wmo_zone, "CAUTION")
        self.assertTrue(rs.navigable)

    def test_02_risk_state_serialization(self):
        rs = evaluate_node_risk_state(
            latitude=-62.8,
            longitude=-58.5,
            sic=0.10,
        )
        data = rs.to_dict()
        self.assertIsInstance(data, dict)
        self.assertEqual(data["latitude"], -62.8)
        self.assertEqual(data["wmo_zone"], "SAFE")

        geojson = rs.to_geojson_feature()
        self.assertEqual(geojson["type"], "Feature")
        self.assertEqual(geojson["geometry"]["coordinates"], [-58.5, -62.8])
        self.assertIn("operational_risk", geojson["properties"])

    # =========================================================================
    # 2. THREE-MODEL CONVERGENCE TESTS
    # =========================================================================

    def test_03_model1_sea_ice_wmo_and_persistence(self):
        # Open water / Safe (sic < 0.15)
        rs_safe = evaluate_node_risk_state(latitude=-62.8, longitude=-58.5, sic=0.08)
        self.assertEqual(rs_safe.wmo_zone, "SAFE")
        self.assertEqual(rs_safe.operational_risk, "SAFE")

        # WMO Caution (0.15 - 0.30)
        rs_caution = evaluate_node_risk_state(latitude=-62.8, longitude=-58.5, sic=0.22)
        self.assertEqual(rs_caution.wmo_zone, "CAUTION")
        self.assertEqual(rs_caution.sea_ice_risk, "SAFE")

        # Restricted WMO zone (0.30 - 0.80) -> CAUTION in risk fusion
        rs_restricted = evaluate_node_risk_state(latitude=-62.8, longitude=-58.5, sic=0.50)
        self.assertEqual(rs_restricted.wmo_zone, "RESTRICTED")
        self.assertEqual(rs_restricted.operational_risk, "CAUTION")

        # Avoid WMO zone (>= 0.80) -> RESTRICTED in risk fusion
        rs_avoid = evaluate_node_risk_state(latitude=-62.8, longitude=-58.5, sic=0.88)
        self.assertEqual(rs_avoid.wmo_zone, "AVOID")
        self.assertEqual(rs_avoid.operational_risk, "RESTRICTED")

    def test_04_model2_iceberg_presence_overrides_operational_risk(self):
        # Iceberg at exact coordinates should trigger EXTREME collision risk
        trajectories = [{
            "iceberg_id": "ICB-TEST-01",
            "latitude": -62.8,
            "longitude": -58.5,
            "estimated_draft_m": 220.0,
            "confidence": 0.95,
        }]
        rs = evaluate_node_risk_state(
            latitude=-62.8,
            longitude=-58.5,
            sic=0.05,  # Clear water
            iceberg_trajectories=trajectories,
            iceberg_buffer_km=10.0,
        )
        self.assertTrue(rs.iceberg_presence)
        self.assertEqual(rs.nearest_iceberg_id, "ICB-TEST-01")
        self.assertEqual(rs.operational_risk, "EXTREME")
        self.assertEqual(rs.risk_score, 100.0)
        self.assertEqual(rs.primary_risk_source, "ICEBERG_COLLISION_ZONE")
        self.assertFalse(rs.navigable)

    def test_05_model3_vessel_polaris_and_speed_penalty(self):
        # No iceberg, POLARIS RIO provided
        rs = evaluate_node_risk_state(
            latitude=-62.8,
            longitude=-58.5,
            sic=0.35,
            rio=65.0,
            sea_ice_risk="RESTRICTED",
        )
        self.assertEqual(rs.risk_score, 65.0)
        self.assertEqual(rs.primary_risk_source, "POLARIS_RIO")
        self.assertTrue(rs.speed_penalty_factor > 0)

    def test_06_land_blockage(self):
        # Coordinates on Antarctic mainland / island
        rs_land = evaluate_node_risk_state(
            latitude=-65.0,
            longitude=-64.0,  # Palmer Archipelago land
        )
        self.assertFalse(rs_land.navigable)
        self.assertEqual(rs_land.operational_risk, "BLOCKED")
        self.assertEqual(rs_land.primary_risk_source, "LAND")

    # =========================================================================
    # 3. SONAR FEEDBACK LOOP PROPAGATION
    # =========================================================================

    def test_07_sonar_feedback_propagates_to_risk_state(self):
        # Simulate sonar update to an iceberg record
        iceberg_record = {
            "iceberg_id": "ICB-SONAR-99",
            "current_latitude": -62.80,
            "current_longitude": -58.50,
            "estimated_draft_m": 310.5,  # Corrected by sonar
            "confidence": 0.96,           # Increased by sonar
            "source": "sonar-corrected",
        }
        grid = [{"latitude": -62.80, "longitude": -58.50, "SIC": 0.10}]

        risk_states = aggregate_risk_state_grid(
            sea_ice_grid=grid,
            iceberg_records=[iceberg_record],
            iceberg_buffer_km=10.0,
            run_id="run_sonar_test"
        )
        self.assertEqual(len(risk_states), 1)
        rs = risk_states[0]
        self.assertTrue(rs.iceberg_presence)
        self.assertEqual(rs.nearest_iceberg_id, "ICB-SONAR-99")
        # Verify sonar draft and confidence propagated directly
        self.assertEqual(rs.estimated_draft_m, 310.5)
        self.assertEqual(rs.iceberg_confidence, 0.96)
        self.assertEqual(rs.operational_risk, "EXTREME")

    # =========================================================================
    # 4. CONSUMER DATA-ACCESS TESTS (NMEA, ROUTE PLANNER, MAP/GLOBE)
    # =========================================================================

    def test_08_nmea_telemetry_reads_precomputed_risk_state(self):
        grid = [
            {"latitude": -62.80, "longitude": -58.50, "SIC": 0.20},
            {"latitude": -62.85, "longitude": -58.55, "SIC": 0.60},
        ]
        aggregate_risk_state_grid(
            sea_ice_grid=grid,
            iceberg_records=[],
            run_id="nmea_run_test"
        )

        # NMEA query near the first node
        rs = get_risk_state_at(-62.801, -58.501, run_id="nmea_run_test", max_lookup_distance_km=10.0)
        self.assertIsNotNone(rs)
        self.assertEqual(rs.sic, 0.20)
        self.assertEqual(rs.wmo_zone, "CAUTION")

        # NMEA query too far from any cell returns None
        rs_far = get_risk_state_at(-50.0, 0.0, run_id="nmea_run_test", max_lookup_distance_km=10.0)
        self.assertIsNone(rs_far)

    def test_09_route_planner_astar_uses_risk_state_cost_and_blocks(self):
        # Create a small navigable water grid in Bransfield Strait
        grid_data = create_ocean_grid(
            min_lat=-62.85, max_lat=-62.80,
            min_lon=-58.60, max_lon=-58.50,
            resolution=0.05
        )

        # Attach a hazardous RiskState to middle cell
        mid_row = len(grid_data) // 2
        mid_col = len(grid_data[0]) // 2
        hazardous_rs = RiskState(
            node_id="hazard_node",
            latitude=grid_data[mid_row][mid_col]["latitude"],
            longitude=grid_data[mid_row][mid_col]["longitude"],
            timestamp=datetime.now(timezone.utc).isoformat(),
            operational_risk="EXTREME",
            navigable=False,
            speed_penalty_factor=99.0
        )
        grid_data[mid_row][mid_col]["risk_state"] = hazardous_rs

        router = AStarRouter(grid_data)
        # Middle cell should be blocked based on RiskState
        self.assertTrue(router.is_blocked((mid_row, mid_col)))

        # Adjacent cell cost calculation uses RiskState penalty
        safe_rs = RiskState(
            node_id="safe_node",
            latitude=grid_data[0][0]["latitude"],
            longitude=grid_data[0][0]["longitude"],
            timestamp=datetime.now(timezone.utc).isoformat(),
            operational_risk="SAFE",
            navigable=True,
            speed_penalty_factor=1.5
        )
        grid_data[0][1]["risk_state"] = safe_rs
        cost = router.calculate_cell_cost((0, 0), (0, 1))
        # Cost should include the 1.5 speed_penalty_factor
        self.assertTrue(cost > 1.5)

    def test_10_map_and_globe_data_access(self):
        grid = [{"latitude": -62.80, "longitude": -58.50, "SIC": 0.15}]
        aggregate_risk_state_grid(
            sea_ice_grid=grid,
            iceberg_records=[],
            run_id="globe_run_test"
        )

        # 1. Grid access
        states = get_risk_state_grid("globe_run_test")
        self.assertEqual(len(states), 1)

        # 2. GeoJSON access for 2D Map & 3D Globe
        geojson = get_risk_state_geojson("globe_run_test")
        self.assertEqual(geojson["type"], "FeatureCollection")
        self.assertEqual(len(geojson["features"]), 1)
        self.assertEqual(geojson["features"][0]["geometry"]["coordinates"], [-58.50, -62.80])


if __name__ == "__main__":
    unittest.main()
