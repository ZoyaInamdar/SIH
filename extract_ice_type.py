import os
import sys
import numpy as np
import pandas as pd
import xarray as xr
import geopandas as gpd
from shapely.geometry import Point
import matplotlib.pyplot as plt
from matplotlib.colors import ListedColormap, BoundaryNorm
import copernicusmarine as cm

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '.')))
from master.route_manager import get_active_corridor

def run(run_dir="."):
    gdf_route, corridor_polygon = get_active_corridor()
    min_lon, min_lat, max_lon, max_lat = corridor_polygon.bounds
    
    dataset_id = "osisaf_obs-si_glo_phy-sitype_nrt_sh-P1D"
    variable = "ice_type"
    
    try:
        ds_full = cm.open_dataset(dataset_id=dataset_id)
        latest_time = ds_full["time"].max().values
        
        flag_values = ds_full[variable].attrs.get('flag_values', [])
        flag_meanings = ds_full[variable].attrs.get('flag_meanings', '')
        if isinstance(flag_meanings, str):
            flag_meanings = flag_meanings.split()
        categories = {int(k): str(v) for k, v in zip(flag_values, flag_meanings)}
        
        ds_subset = ds_full.sel(
            time=latest_time,
            latitude=slice(min_lat, max_lat),
            longitude=slice(min_lon, max_lon)
        )
        
        df = ds_subset[variable].to_dataframe().reset_index()
        df = df.dropna(subset=[variable])
        
        if df.empty:
            print("No valid ice type data found in this bounding box for the latest time.")
            sys.exit(0)
            
        categories_map = {**categories, **{float(k): v for k, v in categories.items()}}
        df["ice_type_label"] = df[variable].map(categories_map)
        df["time"] = pd.to_datetime(latest_time)
            
        geometry = [Point(xy) for xy in zip(df.longitude, df.latitude)]
        gdf_points = gpd.GeoDataFrame(df, crs="EPSG:4326", geometry=geometry)
        
        mask = gdf_points.within(corridor_polygon)
        gdf_filtered = gdf_points.loc[mask].copy()
        
        csv_filename = os.path.join(run_dir, "ice_type_latest.csv")
        gdf_filtered[['latitude', 'longitude', variable, 'ice_type_label', 'time']].to_csv(csv_filename, index=False)
        
        fig, ax = plt.subplots(figsize=(10, 8))
        gdf_route.plot(ax=ax, color='red', linewidth=2, label='Route')
        gpd.GeoSeries([corridor_polygon]).plot(ax=ax, facecolor='none', edgecolor='blue', linestyle='--', label='50km Corridor')
        
        if not gdf_filtered.empty:
            cat_values = sorted(categories.keys())
            cat_labels = [categories[k] for k in cat_values]
            
            palette = ['#1f77b4', '#aec7e8', '#ff7f0e', '#d62728', '#2ca02c', '#9467bd', '#8c564b']
            cmap = ListedColormap(palette[:len(cat_values)])
            bounds = [v - 0.5 for v in cat_values] + [cat_values[-1] + 0.5]
            norm = BoundaryNorm(bounds, cmap.N)
            
            scatter = ax.scatter(gdf_filtered['longitude'], gdf_filtered['latitude'],
                                 c=gdf_filtered[variable], cmap=cmap, norm=norm, s=15, marker='s')
            
            cbar = plt.colorbar(scatter, ax=ax, ticks=cat_values, spacing='proportional')
            cbar.ax.set_yticklabels(cat_labels)
            cbar.set_label('Ice Type')

        ax.set_title(f"Antarctic Ice Type\nLatest: {str(latest_time)[:10]}")
        ax.set_xlabel("Longitude")
        ax.set_ylabel("Latitude")
        ax.legend()
        plt.tight_layout()
        
        plot_filename = os.path.join(run_dir, "ice_type_grid.png")
        plt.savefig(plot_filename)
        
        print("--- Extraction Summary ---")
        print(f"Dataset/Product ID : {dataset_id}")
        print(f"Variable Name      : {variable}")
        print(f"Ice-Type Categories: {categories}")
        print(f"Number of Cells Extracted: {len(gdf_filtered)}")
        
        if not gdf_filtered.empty:
            ext_min_lon = gdf_filtered['longitude'].min()
            ext_max_lon = gdf_filtered['longitude'].max()
            ext_min_lat = gdf_filtered['latitude'].min()
            ext_max_lat = gdf_filtered['latitude'].max()
            print(f"Spatial Bounds     : Lon [{ext_min_lon:.4f}, {ext_max_lon:.4f}], Lat [{ext_min_lat:.4f}, {ext_max_lat:.4f}]")
        else:
            print("Spatial Bounds     : None (No cells extracted)")
            
        print(f"Latest Timestamp   : {latest_time}")
        
    except Exception as e:
        print(f"An error occurred: {e}")
        sys.exit(1)

if __name__ == "__main__":
    run(".")
