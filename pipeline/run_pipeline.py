import os
import sys

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from config.master_config import MASTER_CONFIG
from master.route_manager import validate_route
import extract_sic
import extract_sit
import extract_ice_type
import calculate_polaris

def run_pipeline():
    run_id = MASTER_CONFIG.get("run_id", "default_run")
    run_dir = os.path.join("runs", run_id)
    os.makedirs(run_dir, exist_ok=True)
    
    print(f"================================================================")
    print(f"Starting Risk Pipeline for Run ID: {run_id}")
    print(f"Run Directory: {run_dir}")
    print(f"================================================================\n")
    
    print("1. Validating Route...")
    try:
        validate_route()
    except Exception as e:
        print(f"Route validation failed: {e}")
        sys.exit(1)
        
    print("\n2. Extracting Sea Ice Concentration (SIC)...")
    extract_sic.run(run_dir=run_dir)
    
    print("\n3. Extracting Sea Ice Thickness (SIT)...")
    extract_sit.run(run_dir=run_dir)
    
    print("\n4. Extracting Ice Type...")
    extract_ice_type.run(run_dir=run_dir)
    
    print("\n4.5. Extracting Iceberg Hazards...")
    import extract_icebergs
    extract_icebergs.run(run_dir=run_dir)
    
    vessel_class = MASTER_CONFIG.get("vessel_class", "PC4")
    print(f"\n5. Running POLARIS & DLIRI Assessment for {vessel_class}...")
    calculate_polaris.run(vessel_class=vessel_class, run_dir=run_dir)
    
    print("\nPipeline Execution Complete!")
    print(f"All active outputs are available in: {run_dir}")

if __name__ == "__main__":
    run_pipeline()
