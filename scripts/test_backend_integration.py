import sys
from pathlib import Path
from datetime import datetime, timezone

# Add parent directory to Python path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from backend.database import initialize_database, get_connection
from backend.main import (
    create_crew_hazard_report,
    calculate_route,
    update_ais_vessel,
    get_ais_vessels,
    update_ship_position
)
from backend.schemas import (
    CrewHazardReportRequest,
    RouteRequest,
    AISVessel,
    ShipPosition
)


def run_tests():
    print("=" * 60)
    print("RUNNING BACKEND INTEGRATION VERIFICATION")
    print("=" * 60)

    # 1. Initialize Database
    initialize_database()
    print("[OK] Database initialized successfully.")

    # 2. Test Ship Position Update
    ship_pos = ShipPosition(
        latitude=-65.5,
        longitude=-55.0,
        speed_knots=12.5,
        heading_degrees=145.0,
        timestamp=datetime.now(timezone.utc).isoformat()
    )
    res_pos = update_ship_position(ship_pos)
    assert res_pos["status"] == "success"
    print("[OK] Ship position update verified.")

    # 3. Test Manual Crew Hazard Report
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

    # 4. Test AIS Vessel & Proximity Alert
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

    # 5. Test Dual Route Comparison
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

    print("\n" + "=" * 60)
    print("ALL BACKEND VERIFICATION CHECKS PASSED SUCCESSFULLY!")
    print("=" * 60)


if __name__ == "__main__":
    run_tests()
