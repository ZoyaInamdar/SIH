import os
import sys
import numpy as np
import pandas as pd
import xarray as xr
import geopandas as gpd
from shapely.geometry import Point
import matplotlib.pyplot as plt
from datetime import datetime, timedelta
import copernicusmarine as cm

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '.')))
from master.route_manager import get_active_corridor

def run(run_dir="."):
    os.makedirs(run_dir, exist_ok=True)
    
    gdf_route, corridor_polygon = get_active_corridor()
    min_lon, min_lat, max_lon, max_lat = corridor_polygon.bounds
    print(f"Corridor Bounding Box: Lon [{min_lon:.2f}, {max_lon:.2f}], Lat [{min_lat:.2f}, {max_lat:.2f}]")
    
    today = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
    tomorrow = today + timedelta(days=1)
    
    start_date_str = today.strftime('%Y-%m-%d %H:%M:%S')
    end_date_str = tomorrow.strftime('%Y-%m-%d %H:%M:%S')
    
    print(f"Fetching data for: {start_date_str} to {end_date_str}")
    
    dataset_id = "cmems_mod_glo_phy_anfc_0.083deg_P1D-m"
    variable = "siconc"
    output_filename = os.path.join(run_dir, "cmems_subset.nc")
    
    try:
        print("Downloading CMEMS subset...")
        cm.subset(
            dataset_id=dataset_id,
            variables=[variable],
            minimum_longitude=min_lon,
            maximum_longitude=max_lon,
            minimum_latitude=min_lat,
            maximum_latitude=max_lat,
            start_datetime=start_date_str,
            end_datetime=end_date_str,
            output_filename=output_filename,
            force_download=True
        )
    except Exception as e:
        print(f"Error fetching data from CMEMS: {e}")
        sys.exit(1)
        
    print("Processing subset data...")
    ds = xr.open_dataset(output_filename)
    df = ds.to_dataframe().reset_index()
    df = df.dropna(subset=[variable])
    
    if df.empty:
        print("No valid Sea Ice Concentration data found in this bounding box.")
        sys.exit(0)
    
    geometry = [Point(xy) for xy in zip(df.longitude, df.latitude)]
    gdf_points = gpd.GeoDataFrame(df, crs="EPSG:4326", geometry=geometry)
    mask = gdf_points.within(corridor_polygon)
    gdf_filtered = gdf_points.loc[mask].copy()
    
    print(f"Total points within bounding box: {len(df)}")
    print(f"Total points within 50km corridor: {len(gdf_filtered)}")
    
    gdf_filtered['date'] = gdf_filtered['time'].dt.date
    today_date = today.date()
    tomorrow_date = tomorrow.date()
    
    df_today = gdf_filtered[gdf_filtered['date'] == today_date]
    df_tomorrow = gdf_filtered[gdf_filtered['date'] == tomorrow_date]
    
    cols_to_save = ['latitude', 'longitude', variable]
    today_csv = os.path.join(run_dir, "sic_today.csv")
    tomorrow_csv = os.path.join(run_dir, "sic_tomorrow.csv")
    
    df_today[cols_to_save].to_csv(today_csv, index=False)
    df_tomorrow[cols_to_save].to_csv(tomorrow_csv, index=False)
    
    print(f"Saved today's data to {today_csv} ({len(df_today)} points)")
    print(f"Saved tomorrow's data to {tomorrow_csv} ({len(df_tomorrow)} points)")
    
    try:
        fig, axes = plt.subplots(1, 2, figsize=(15, 6))
        
        ax1 = axes[0]
        gdf_route.plot(ax=ax1, color='red', linewidth=2, label='Route')
        gpd.GeoSeries([corridor_polygon]).plot(ax=ax1, facecolor='none', edgecolor='blue', linestyle='--', label='50km Corridor')
        
        if not df_today.empty:
            scatter1 = ax1.scatter(df_today['longitude'], df_today['latitude'], 
                                   c=df_today[variable], cmap='Blues_r', s=10, vmin=0, vmax=1)
            plt.colorbar(scatter1, ax=ax1, label='Sea Ice Concentration (0-1)')
            
        ax1.set_title(f"SIC - Today ({today_date})")
        ax1.set_xlabel("Longitude")
        ax1.set_ylabel("Latitude")
        ax1.legend()
        
        ax2 = axes[1]
        gdf_route.plot(ax=ax2, color='red', linewidth=2, label='Route')
        gpd.GeoSeries([corridor_polygon]).plot(ax=ax2, facecolor='none', edgecolor='blue', linestyle='--', label='50km Corridor')
        
        if not df_tomorrow.empty:
            scatter2 = ax2.scatter(df_tomorrow['longitude'], df_tomorrow['latitude'], 
                                   c=df_tomorrow[variable], cmap='Blues_r', s=10, vmin=0, vmax=1)
            plt.colorbar(scatter2, ax=ax2, label='Sea Ice Concentration (0-1)')
            
        ax2.set_title(f"SIC - Tomorrow ({tomorrow_date})")
        ax2.set_xlabel("Longitude")
        ax2.set_ylabel("Latitude")
        ax2.legend()
        
        plt.tight_layout()
        plot_filename = os.path.join(run_dir, "sic_prototype_results.png")
        plt.savefig(plot_filename)
        print(f"Saved visualization to {plot_filename}")
        
    except Exception as e:
        print(f"Failed to generate plot: {e}")

if __name__ == "__main__":
    run(".")
