import os
import sys
import numpy as np

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from config.master_config import MASTER_CONFIG
import pipeline.run_pipeline as run_pipeline
from nmea.risk_lookup import RiskLookup
from master.route_manager import get_active_corridor

def test_route_validation():
    print("\n--- Testing Route Validation ---")
    MASTER_CONFIG["route"] = []
    try:
        get_active_corridor(MASTER_CONFIG)
        print("FAILED: Empty route was not rejected.")
    except ValueError:
        print("PASSED: Empty route rejected.")
        
    MASTER_CONFIG["route"] = [(-67.0, -55.0)]
    try:
        get_active_corridor(MASTER_CONFIG)
        print("FAILED: Route with 1 point was not rejected.")
    except ValueError:
        print("PASSED: Route with 1 point rejected.")

def test_route_change_and_pipeline():
    print("\n--- Testing Route Change & Pipeline ---")
    
    # Route A
    MASTER_CONFIG["route"] = [
        (-67.0, -55.0),
        (-62.0, -60.0),
        (-60.0, -65.0),
        (-58.0, -70.0)
    ]
    MASTER_CONFIG["run_id"] = "route_A"
    
    run_pipeline.run_pipeline()
    
    lookup_A = RiskLookup(run_id="route_A")
    _, corridor_A = get_active_corridor(MASTER_CONFIG)
    bounds_A = corridor_A.bounds
    print(f"\nRoute A Bounds: {bounds_A}")
    
    # Route B (different area, maybe Weddell sea only)
    MASTER_CONFIG["route"] = [
        (-40.0, -70.0),
        (-45.0, -75.0)
    ]
    MASTER_CONFIG["run_id"] = "route_B"
    
    run_pipeline.run_pipeline()
    
    lookup_B = RiskLookup(run_id="route_B")
    _, corridor_B = get_active_corridor(MASTER_CONFIG)
    bounds_B = corridor_B.bounds
    print(f"\nRoute B Bounds: {bounds_B}")
    
    if bounds_A != bounds_B:
        print("PASSED: Corridor extents differ for different routes.")
    else:
        print("FAILED: Corridor extents are the same.")
        
    # Check NMEA lookup
    print("\n--- Testing NMEA Lookup ---")
    
    # Inside Route B
    res1 = lookup_B.get_risk(-70.0, -40.0)
    if res1.get("status") != "outside_polaris_grid":
        print("PASSED: Lookup inside corridor returns data.")
    else:
        print("FAILED: Lookup inside corridor failed.")
        
    # Outside Route B
    res2 = lookup_B.get_risk(-55.0, -67.0)
    if res2.get("status") == "outside_polaris_grid":
        print("PASSED: Lookup outside corridor returns outside_polaris_grid.")
    else:
        print(f"FAILED: Lookup outside corridor returned data: {res2}")
        
    # No RIO interpolation
    if res1.get("status") != "outside_polaris_grid":
        if res1.get("rio_method") in ["NOT_AVAILABLE", "POLARIS_FULL"]:
            print("PASSED: RIO method is valid (no arbitrary interpolation).")
        else:
            print("FAILED: RIO method is invalid.")

if __name__ == "__main__":
    test_route_validation()
    test_route_change_and_pipeline()
    print("\nAll Tests Executed.")
