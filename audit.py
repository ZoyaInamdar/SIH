import os
import sys
import numpy as np
import pandas as pd
import xarray as xr
import geopandas as gpd
from shapely.geometry import LineString, Point
import matplotlib.pyplot as plt
import copernicusmarine as cm

print("="*60)
print("PHASE 1 — AUDIT THE RAW ICE-TYPE SOURCE")
print("="*60)
dataset_id = "osisaf_obs-si_glo_phy-sitype_nrt_sh-P1D"
variable = "ice_type"

try:
    ds_full = cm.open_dataset(dataset_id=dataset_id)
    print(f"Dataset ID: {dataset_id}")
    print(f"Variable: {variable}")
    print(f"Dimensions: {ds_full.dims}")
    print(f"Coordinates: {list(ds_full.coords.keys())}")
    
    lat = ds_full['lat'] if 'lat' in ds_full else ds_full['latitude']
    lon = ds_full['lon'] if 'lon' in ds_full else ds_full['longitude']
    
    print(f"Latitude Min/Max: {lat.min().values:.4f} / {lat.max().values:.4f}")
    print(f"Longitude Min/Max: {lon.min().values:.4f} / {lon.max().values:.4f}")
    print(f"Latitude Resolution (approx): {np.abs(lat.values[1] - lat.values[0]):.4f}")
    print(f"Longitude Resolution (approx): {np.abs(lon.values[1] - lon.values[0]):.4f}")
    
    # CRS / Proj
    proj_keys = [k for k in ds_full.variables if 'proj' in k.lower() or 'grid' in k.lower() or 'crs' in k.lower()]
    print(f"Grid Mapping Variables: {proj_keys}")
    if proj_keys:
        for k in proj_keys:
            print(f" - {k}: {ds_full[k].attrs}")
            
    print(f"Lat Units: {lat.attrs.get('units', 'None')}")
    print(f"Lon Units: {lon.attrs.get('units', 'None')}")
    
    var_attrs = ds_full[variable].attrs
    print(f"\n{variable} Attributes:")
    for k, v in var_attrs.items():
        print(f"  {k}: {v}")
        
    latest_time = ds_full["time"].max().values
    
    # Read one time slice to inspect raw values
    ds_slice = ds_full[variable].sel(time=latest_time).values.flatten()
    ds_slice_valid = ds_slice[~np.isnan(ds_slice)]
    unique_vals = np.unique(ds_slice_valid)
    print(f"\nUnique raw Ice-Type values: {unique_vals}")
except Exception as e:
    print(f"Error loading CMEMS dataset: {e}")

print("\n" + "="*60)
print("PHASE 2 — RAW DISTRIBUTION")
print("="*60)
# We already have ice_type_latest.csv for the corridor. Let's see its distribution.
try:
    df_ice = pd.read_csv("ice_type_latest.csv")
    print("\nROUTE + 50 KM CORRIDOR (from ice_type_latest.csv)")
    print(df_ice['ice_type_label'].value_counts(dropna=False))
except Exception as e:
    print(f"Error loading ice_type_latest.csv: {e}")

print("\n" + "="*60)
print("PHASE 3 — INVESTIGATE ZERO EXACT MATCHES")
print("="*60)
try:
    df_sic = pd.read_csv("sic_today.csv")
    print(f"SIC target cells: {len(df_sic)}")
    print("Sample SIC Coordinates:")
    for i in range(5):
        print(f"  ({df_sic['latitude'].iloc[i]:.6f}, {df_sic['longitude'].iloc[i]:.6f})")
        
    print(f"\nIce Type cells (corridor): {len(df_ice)}")
    print("Sample Ice Type Coordinates:")
    for i in range(5):
        print(f"  ({df_ice['latitude'].iloc[i]:.6f}, {df_ice['longitude'].iloc[i]:.6f})")
except Exception as e:
    print(f"Error checking coordinates: {e}")
    
print("\n" + "="*60)
print("PHASE 4 — CHECK WHETHER NEAREST-NEIGHBOUR MATCHING IS VALID")
print("="*60)
try:
    # Use exact same join from calculate_polaris
    gdf_sic = gpd.GeoDataFrame(df_sic, geometry=[Point(xy) for xy in zip(df_sic.longitude, df_sic.latitude)], crs="EPSG:4326")
    gdf_ice = gpd.GeoDataFrame(df_ice, geometry=[Point(xy) for xy in zip(df_ice.longitude, df_ice.latitude)], crs="EPSG:4326")
    
    matched_nn = gpd.sjoin_nearest(
        gdf_sic.to_crs("EPSG:3031"),
        gdf_ice.to_crs("EPSG:3031"),
        how='left',
        max_distance=15000,
        distance_col='match_dist_m'
    )
    matched_nn = matched_nn[~matched_nn.index.duplicated(keep='first')]
    
    print(f"Total matched via NN: {matched_nn['match_dist_m'].notna().sum()}")
    
    if matched_nn['match_dist_m'].notna().sum() > 0:
        dists = matched_nn['match_dist_m'].dropna() / 1000.0  # to km
        print(f"Min distance: {dists.min():.3f} km")
        print(f"Mean distance: {dists.mean():.3f} km")
        print(f"Median distance: {dists.median():.3f} km")
        print(f"P90 distance: {np.percentile(dists, 90):.3f} km")
        print(f"P95 distance: {np.percentile(dists, 95):.3f} km")
        print(f"P99 distance: {np.percentile(dists, 99):.3f} km")
        print(f"Max distance: {dists.max():.3f} km")
        
        print(f"<= 1 km: {(dists <= 1).sum()}")
        print(f"<= 3 km: {(dists <= 3).sum()}")
        print(f"<= 5 km: {(dists <= 5).sum()}")
        print(f"<= 10 km: {(dists <= 10).sum()}")
        print(f"<= 15 km: {(dists <= 15).sum()}")
except Exception as e:
    print(f"Error in Phase 4: {e}")

