import sys
from pathlib import Path
from datetime import datetime, timezone

# Add parent directory to Python path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from backend.database import initialize_database
from backend.main import (
    create_crew_hazard_report,
    calculate_route,
    update_ais_vessel,
    get_ais_vessels,
    update_ship_position,
    seed_simulation_data,
    get_dashboard_summary,
    list_vessel_profiles,
    run_risk_fusion,
    nmea_risk_lookup,
    daylight,
    system_status,
    add_iceberg
)
from backend.schemas import (
    CrewHazardReportRequest,
    RouteRequest,
    AISVessel,
    ShipPosition,
    RiskFusionRequest,
    Iceberg
)


def run_tests():
    print("=" * 60)
    print("RUNNING COMPLETE BACKEND INTEGRATION & FRONTEND READINESS VERIFICATION")
    print("=" * 60)

    # 1. Initialize Database
    initialize_database()
    print("[OK] Database initialized successfully.")

    # 2. System Status & Health
    status_resp = system_status()
    assert status_resp["backend"] == "running"
    assert status_resp["database"] == "connected"
    print("[OK] System health & status check verified.")

    # 3. Seed Simulation Datasets
    seed_resp = seed_simulation_data()
    assert seed_resp["status"] == "success"
    print("[OK] Simulation dataset seeder verified.")

    # 4. Dashboard Summary Overview
    dash_resp = get_dashboard_summary()
    assert dash_resp["status"] == "success"
    assert dash_resp["iceberg_count"] >= 4
    assert dash_resp["hazard_count"] >= 3
    assert dash_resp["ais_vessel_count"] >= 2
    print(f"[OK] Dashboard summary overview verified ({dash_resp['iceberg_count']} icebergs, {dash_resp['hazard_count']} hazards, {dash_resp['ais_vessel_count']} AIS vessels).")

    # 5. Vessel Profiles List
    vessel_resp = list_vessel_profiles()
    assert vessel_resp["status"] == "success"
    assert vessel_resp["count"] >= 2
    print(f"[OK] Vessel profiles list verified ({vessel_resp['count']} profiles available).")

    # 6. Ship Position Update
    ship_pos = ShipPosition(
        latitude=-65.5,
        longitude=-55.0,
        speed_knots=12.5,
        heading_degrees=145.0,
        timestamp=datetime.now(timezone.utc).isoformat()
    )
    res_pos = update_ship_position(ship_pos)
    assert res_pos["status"] == "success"
    print("[OK] Live ship position update verified.")

    # 7. Manual Crew Hazard Report
    crew_req = CrewHazardReportRequest(
        description="Uncharted ice floe reported by lookout",
        latitude=-66.0,
        longitude=-54.0,
        vessel_id="MV-VG-001"
    )
    res_crew = create_crew_hazard_report(crew_req)
    assert res_crew["status"] == "success"
    assert res_crew["hazard"]["radius_m"] == 500.0
    assert res_crew["hazard"]["source"] == "CREW_REPORT"
    assert res_crew["hazard"]["status"] == "UNVALIDATED_OBSERVATION"
    print(f"[OK] Crew hazard report verified: {res_crew['hazard']['id']}")

    # 8. AIS Vessel & Proximity Alert
    ais_vessel = AISVessel(
        vessel_id="NCPOR-AKADEMIK-01",
        name="Akademik Tryoshnikov",
        latitude=-65.6,
        longitude=-55.1,
        speed_knots=10.0,
        heading_degrees=180.0,
        is_ncpor_fleet=True,
        timestamp=datetime.now(timezone.utc).isoformat()
    )
    res_ais = update_ais_vessel(ais_vessel)
    assert res_ais["status"] == "success"

    vessels_resp = get_ais_vessels()
    assert vessels_resp["status"] == "success"
    assert vessels_resp["count"] >= 1
    print(f"[OK] AIS vessel registration & proximity check verified ({vessels_resp['count']} vessel(s) stored).")

    # 9. Risk Fusion & NMEA Lookup
    fuse_req = RiskFusionRequest(run_id="run_demo_01", corridor_km=50.0, iceberg_buffer_km=10.0)
    fuse_resp = run_risk_fusion(fuse_req)
    assert fuse_resp["status"] == "success"
    
    nmea_resp = nmea_risk_lookup(-65.5, -55.0, run_id="run_demo_01")
    assert nmea_resp["status"] == "success"
    print("[OK] Risk fusion engine & NMEA lookup verified.")

    # 10. Astronomical Daylight Calculation
    daylight_resp = daylight(-65.5, -55.0)
    assert daylight_resp["status"] == "success"
    print(f"[OK] Astronomical daylight status verified: {daylight_resp['daylight_status']}")

    # 11. Dual Route Comparison
    route_req = RouteRequest(
        start_latitude=-65.0,
        start_longitude=-55.0,
        destination_latitude=-67.0,
        destination_longitude=-50.0,
        grid_resolution=0.2,
        vessel_id="MV-VG-001"
    )
    res_route = calculate_route(route_req)
    assert res_route["status"] == "success"
    assert "standard_route" in res_route
    assert "fuel_efficient_route" in res_route
    assert "distance_increase_percent" in res_route
    assert "fuel_saved_percent" in res_route
    assert "summary" in res_route

    print(f"[OK] Dual route calculation & comparison verified:")
    print(f"    - Standard Route distance: {res_route['standard_route']['distance_km']} km")
    print(f"    - Fuel-Efficient Route distance: {res_route['fuel_efficient_route']['distance_km']} km")
    print(f"    - Distance delta: +{res_route['distance_increase_percent']}%")
    print(f"    - Fuel savings: {res_route['fuel_saved_percent']}%")
    print(f"    - Summary: \"{res_route['summary']}\"")

    # 12. Iceberg Draft Auto-Calculation (El-Tahan Formula)
    test_icb = Iceberg(
        iceberg_id="ICB-TEST-ELTAHAN",
        current_latitude=-65.1,
        current_longitude=-52.1,
        freeboard_m=30.0,
        shape_class="tabular",
        estimated_draft_m=None,
        timestamp=datetime.now(timezone.utc).isoformat()
    )
    res_icb = add_iceberg(test_icb)
    assert res_icb["status"] == "success"
    assert res_icb["data"]["estimated_draft_m"] is not None
    assert res_icb["data"]["estimated_draft_m"] > 50.0
    print(f"[OK] El-Tahan iceberg auto-draft calculation verified (freeboard 30m -> estimated draft {res_icb['data']['estimated_draft_m']}m).")

    print("\n" + "=" * 60)
    print("ALL BACKEND VERIFICATION CHECKS PASSED SUCCESSFULLY!")
    print("FRONTEND INTEGRATION READY.")
    print("=" * 60)


if __name__ == "__main__":
    run_tests()
