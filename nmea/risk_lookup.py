import os
import sys
import numpy as np
import pandas as pd
import xarray as xr
from shapely.geometry import Point

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from config.master_config import MASTER_CONFIG
from master.route_manager import get_active_corridor

class RiskLookup:
    def __init__(self, run_id=None):
        if run_id is None:
            run_id = MASTER_CONFIG.get("run_id", "default_run")
            
        self.run_dir = os.path.join(os.path.dirname(__file__), "..", "runs", run_id)
        self.grid_path = os.path.join(self.run_dir, "polaris_grid.csv")
        
        _, self.corridor_polygon = get_active_corridor()
        
        self.ds = None
        self.df = None
        
        self._load_grid()
        
    def _load_grid(self):
        if not os.path.exists(self.grid_path):
            raise FileNotFoundError(f"Active risk grid not found at {self.grid_path}. Has the pipeline been run?")
            
        self.df = pd.read_csv(self.grid_path)
        
        
    def get_risk(self, lat, lon):
        point = Point(lon, lat)
        
        if not point.within(self.corridor_polygon):
            return {
                "status": "outside_polaris_grid",
                "latitude": lat,
                "longitude": lon
            }
            
        # Find nearest point (without interpolating categorical data)
        # Using haversine or simple euclidean since points are dense enough
        distances = np.sqrt((self.df['latitude'] - lat)**2 + (self.df['longitude'] - lon)**2)
        nearest_idx = distances.idxmin()
        nearest_row = self.df.loc[nearest_idx]
        
        result = nearest_row.to_dict()
        
        # Replace nan with None for JSON serialization compatibility
        for k, v in result.items():
            if isinstance(v, float) and np.isnan(v):
                result[k] = None
                
        return result
        
    def evaluate_position(self, lat, lon):
        return self.get_risk(lat, lon)

if __name__ == "__main__":
    try:
        lookup = RiskLookup()
        # Test inside corridor
        lat, lon = -62.0, -60.0
        res = lookup.get_risk(lat, lon)
        print(f"Lookup at ({lat}, {lon}):")
        for k, v in res.items():
            print(f"  {k}: {v}")
            
        # Test outside corridor
        lat, lon = 0.0, 0.0
        res = lookup.get_risk(lat, lon)
        print(f"\nLookup at ({lat}, {lon}):")
        for k, v in res.items():
            print(f"  {k}: {v}")
    except Exception as e:
        print(e)
