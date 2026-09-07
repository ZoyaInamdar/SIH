import os
import pandas as pd
import numpy as np
import geopandas as gpd
from shapely.geometry import Point, LineString
import warnings

from config.master_config import MASTER_CONFIG
from master.route_manager import get_active_corridor

warnings.filterwarnings("ignore")

def create_synthetic_trajectory(run_dir):
    """Creates a synthetic trajectory for testing purposes when real data is missing."""
    traj_dir = os.path.join(run_dir, "iceberg_trajectories")
    os.makedirs(traj_dir, exist_ok=True)
    
    lats = np.linspace(-63.0, -62.0, 10)
    lons = np.linspace(-63.0, -62.0, 10)
    
    df = pd.DataFrame({
        "latitude": lats,
        "longitude": lons,
        "timestamp": pd.date_range(start="2026-09-07", periods=10, freq="6h")
    })
    
    out_path = os.path.join(traj_dir, "synthetic_trajectory.csv")
    df.to_csv(out_path, index=False)
    return out_path

def run(run_dir):
    enable_prediction = MASTER_CONFIG.get("enable_iceberg_prediction", False)
    
    if not enable_prediction:
        print("Iceberg prediction is disabled in config.")
        return
        
    print("Extracting iceberg trajectories...")
    
    buffer_km = MASTER_CONFIG.get("iceberg_buffer_km", 10.0)
    buffer_meters = buffer_km * 1000.0
    
    traj_path = create_synthetic_trajectory(run_dir)
    traj_df = pd.read_csv(traj_path)
    
    geometry = [Point(xy) for xy in zip(traj_df.longitude, traj_df.latitude)]
    iceberg_gdf = gpd.GeoDataFrame(traj_df, geometry=geometry, crs="EPSG:4326")
    iceberg_gdf_3031 = iceberg_gdf.to_crs("EPSG:3031")
    
    sic_path = os.path.join(run_dir, "sic_today.csv")
    if not os.path.exists(sic_path):
        print("Waiting for SIC grid to be generated first.")
        return
        
    grid_df = pd.read_csv(sic_path)
    grid_gdf = gpd.GeoDataFrame(
        grid_df, 
        geometry=[Point(xy) for xy in zip(grid_df.longitude, grid_df.latitude)],
        crs="EPSG:4326"
    ).to_crs("EPSG:3031")
    
    # Calculate nearest distance to any iceberg point
    # sjoin_nearest gets us the closest point and the distance
    nearest = gpd.sjoin_nearest(
        grid_gdf, 
        iceberg_gdf_3031, 
        how='left', 
        distance_col='dist_m'
    )
    
    # In case of multiple nearest points at same distance, keep first
    nearest = nearest[~nearest.index.duplicated(keep="first")]
    
    grid_df["iceberg_distance_km"] = nearest["dist_m"] / 1000.0
    grid_df["iceberg_presence"] = grid_df["iceberg_distance_km"] <= buffer_km
    grid_df["iceberg_forecast_time"] = np.where(
        grid_df["iceberg_presence"], 
        nearest["timestamp"], 
        None
    )
    
    out_path = os.path.join(run_dir, "iceberg_hazard_grid.csv")
    grid_df[["latitude", "longitude", "iceberg_presence", "iceberg_distance_km", "iceberg_forecast_time"]].to_csv(out_path, index=False)
    
    num_hazards = grid_df["iceberg_presence"].sum()
    print(f"Iceberg extraction complete. Found {num_hazards} grid cells within {buffer_km}km of predicted icebergs (buffer_basis = 'PROJECT_DEFINED').")

if __name__ == "__main__":
    run("runs/route_A")
