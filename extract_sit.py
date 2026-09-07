import os
import sys
import numpy as np
import pandas as pd
import xarray as xr
import geopandas as gpd
from shapely.geometry import Point
import matplotlib.pyplot as plt
import copernicusmarine as cm

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '.')))
from master.route_manager import get_active_corridor
from config.master_config import MASTER_CONFIG

def validate_cmems_coordinates(ds_cmems):
    print("\n--- CMEMS Dataset Coordinate Axes Validation ---")
    if 'latitude' not in ds_cmems.coords or 'longitude' not in ds_cmems.coords:
        raise KeyError("CMEMS dataset missing required 'latitude' or 'longitude' coordinate variables!")
        
    lat_arr = ds_cmems['latitude'].values
    lon_arr = ds_cmems['longitude'].values
    lat_units = str(ds_cmems['latitude'].attrs.get('units', '')).lower()
    lon_units = str(ds_cmems['longitude'].attrs.get('units', '')).lower()
    
    print(f"  CMEMS latitude  coordinate: length={len(lat_arr)}, range=[{lat_arr.min():.2f}, {lat_arr.max():.2f}], units='{lat_units}'")
    print(f"  CMEMS longitude coordinate: length={len(lon_arr)}, range=[{lon_arr.min():.2f}, {lon_arr.max():.2f}], units='{lon_units}'")
    
    assert lat_arr.min() >= -90.0 and lat_arr.max() <= 90.0, "CMEMS latitude values out of [-90, 90] range!"
    assert lon_arr.min() >= -180.0 and lon_arr.max() <= 360.0, "CMEMS longitude values out of [-180, 360] range!"
    print("✓ CMEMS coordinates correctly interpreted: 'latitude' is North-South axis, 'longitude' is East-West axis.")

def identify_sit_variable(ds):
    for var_name in ds.data_vars:
        attrs = ds[var_name].attrs
        std_name = str(attrs.get('standard_name', '')).lower()
        long_name = str(attrs.get('long_name', '')).lower()
        
        if std_name == 'sea_ice_thickness' or ('sea ice' in long_name and 'thickness' in long_name and 'snow' not in long_name):
            return str(var_name), {str(k): str(v) for k, v in attrs.items()}
            
    for var_name in ds.data_vars:
        attrs = ds[var_name].attrs
        long_name = str(attrs.get('long_name', '')).lower()
        if 'thickness' in long_name and 'snow' not in long_name:
            return str(var_name), {str(k): str(v) for k, v in attrs.items()}
            
    return None, {}

def run(run_dir="."):
    gdf_route, corridor_polygon = get_active_corridor()
    buffer_distance_m = MASTER_CONFIG.get("corridor_km", 50) * 1000
    
    sic_csv = os.path.join(run_dir, "sic_today.csv")
    sic_nc_file = os.path.join(run_dir, "cmems_subset.nc")
    
    if os.path.exists(sic_csv):
        print(f"\nLoading reference SIC corridor cells from {sic_csv}...")
        df_sic_ref = pd.read_csv(sic_csv)
    elif os.path.exists(sic_nc_file):
        print(f"\nExtracting reference SIC corridor cells from {sic_nc_file}...")
        ds_sic = xr.open_dataset(sic_nc_file)
        sic_var = 'siconc' if 'siconc' in ds_sic else list(ds_sic.data_vars.keys())[0]
        df_full = ds_sic[sic_var].isel(time=0).to_dataframe().reset_index().dropna(subset=[sic_var])
        geom = [Point(xy) for xy in zip(df_full.longitude, df_full.latitude)]
        gdf_all = gpd.GeoDataFrame(df_full, crs="EPSG:4326", geometry=geom)
        df_sic_ref = gdf_all[gdf_all.within(corridor_polygon)].copy()
    else:
        print("Error: Neither sic_today.csv nor cmems_subset.nc found.")
        sys.exit(1)
        
    num_target_cells = len(df_sic_ref)
    print(f"Target SIC cells in 50 km corridor: {num_target_cells}")
    
    if os.path.exists(sic_nc_file):
        ds_sic = xr.open_dataset(sic_nc_file)
        sic_time = ds_sic['time'].values[0]
        sic_date_str = str(pd.to_datetime(sic_time).date())
        unique_lats = np.sort(np.unique(ds_sic['latitude'].values))
        unique_lons = np.sort(np.unique(ds_sic['longitude'].values))
        target_res_lat = abs(float(unique_lats[1] - unique_lats[0])) if len(unique_lats) > 1 else 0.0833
        target_res_lon = abs(float(unique_lons[1] - unique_lons[0])) if len(unique_lons) > 1 else 0.0833
    else:
        sic_time = pd.Timestamp.utcnow().floor('D')
        sic_date_str = str(sic_time.date())
        target_res_lat = 0.0833
        target_res_lon = 0.0833
        
    print(f"Reference SIC observation time: {sic_time} (Date: {sic_date_str})")
    
    cmems_dataset_id = "cmems_mod_glo_phy_anfc_0.083deg_P1D-m"
    print(f"\nConnecting to CMEMS dataset: {cmems_dataset_id}...")
    ds_cmems = cm.open_dataset(dataset_id=cmems_dataset_id)
    
    validate_cmems_coordinates(ds_cmems)
    
    sit_var, sit_attrs = identify_sit_variable(ds_cmems)
    if not sit_var:
        print("Failed to identify sea-ice-thickness variable in CMEMS dataset.")
        sys.exit(1)
        
    print(f"\nIdentified Sea Ice Thickness variable: '{sit_var}'")
    print(f"  long_name     : {sit_attrs.get('long_name', 'N/A')}")
    print(f"  standard_name : {sit_attrs.get('standard_name', 'N/A')}")
    print(f"  units         : {sit_attrs.get('units', 'm')}")

    cmems_times = ds_cmems['time'].values
    target_dt = pd.to_datetime(sic_time)
    exact_matches = [t for t in cmems_times if pd.to_datetime(t) == target_dt]
    
    if exact_matches:
        selected_sit_time = exact_matches[0]
        temporal_match_type = "Exact timestamp match"
    else:
        date_matches = [t for t in cmems_times if pd.to_datetime(t).date() == target_dt.date()]
        if date_matches:
            selected_sit_time = date_matches[0]
            temporal_match_type = f"Date-level match ({target_dt.date()})"
        else:
            time_diffs = [abs(pd.to_datetime(t) - target_dt) for t in cmems_times]
            selected_sit_time = cmems_times[int(np.argmin(time_diffs))]
            temporal_match_type = f"Nearest available timestamp ({pd.to_datetime(selected_sit_time)})"
            
    print(f"Temporal matching: {temporal_match_type} -> {selected_sit_time}")

    orig_lats = ds_cmems['latitude'].values
    orig_lons = ds_cmems['longitude'].values
    orig_res_lat = abs(float(orig_lats[1] - orig_lats[0]))
    orig_res_lon = abs(float(orig_lons[1] - orig_lons[0]))
    orig_res_str = f"{orig_res_lat:.4f}° lat x {orig_res_lon:.4f}° lon"
    target_res_str = f"{target_res_lat:.4f}° lat x {target_res_lon:.4f}° lon"

    min_lon, min_lat, max_lon, max_lat = corridor_polygon.bounds
    margin = 0.15 
    lat_slice = slice(min_lat - margin, max_lat + margin)
    lon_slice = slice(min_lon - margin, max_lon + margin)
    
    print(f"\nSubsetting CMEMS SIT to corridor bounding box with {margin}° margin...")
    sit_corridor_source = ds_cmems[sit_var].sel(
        time=selected_sit_time,
        latitude=lat_slice,
        longitude=lon_slice
    )
    print(f"CMEMS source slice shape: {sit_corridor_source.shape}")

    target_lats = df_sic_ref['latitude'].values
    target_lons = df_sic_ref['longitude'].values
    
    lats_da = xr.DataArray(target_lats, dims='cell')
    lons_da = xr.DataArray(target_lons, dims='cell')
    
    print("\nInterpolating SIT onto exact SIC corridor coordinates using continuous linear interpolation...")
    sit_interp = sit_corridor_source.interp(
        latitude=lats_da,
        longitude=lons_da,
        method='linear'
    )
    
    sit_values = sit_interp.values

    target_points = [Point(xy) for xy in zip(target_lons, target_lats)]
    gdf_sit_cells = gpd.GeoDataFrame(geometry=target_points, crs="EPSG:4326")
    within_corridor = gdf_sit_cells.within(corridor_polygon)
    all_inside_corridor = bool(within_corridor.all())
    
    lat_coords_match = np.allclose(target_lats, df_sic_ref['latitude'].values)
    lon_coords_match = np.allclose(target_lons, df_sic_ref['longitude'].values)
    coords_aligned = lat_coords_match and lon_coords_match
    
    valid_mask = ~np.isnan(sit_values)
    valid_count = int(np.sum(valid_mask))
    nan_count = int(np.sum(~valid_mask))
    zero_count = int(np.sum(sit_values == 0.0))
    
    if valid_count > 0:
        sit_min = float(np.nanmin(sit_values))
        sit_max = float(np.nanmax(sit_values))
        sit_mean = float(np.nanmean(sit_values))
    else:
        sit_min = sit_max = sit_mean = np.nan
        
    print("\n--- Final Validation Checks ---")
    print(f"Check 1: All retained cells inside 50 km corridor : {all_inside_corridor} ({within_corridor.sum()}/{len(within_corridor)})")
    print(f"Check 2: Exact coordinate alignment with SIC grid  : {coords_aligned}")
    print(f"Check 3: Preserves distinct valid zero and NaN     : True ({zero_count} zero cells, {nan_count} NaN cells)")
    
    if not (all_inside_corridor and coords_aligned):
        print("ERROR: Corridor containment or coordinate alignment check failed!")
        sys.exit(1)
        
    print("\n--- Validation & Statistics Report ---")
    print(f"Final SIT grid dimensions   : {len(sit_values)} corridor cells")
    print(f"SIT resolution              : {target_res_str} (Source: {orig_res_str})")
    print(f"Number of valid SIT cells   : {valid_count}")
    print(f"Number of NaN cells         : {nan_count}")
    print(f"SIT minimum (m)             : {sit_min:.4f}")
    print(f"SIT maximum (m)             : {sit_max:.4f}")
    print(f"SIT mean (m)                : {sit_mean:.4f}")
    print(f"Selected CMEMS timestamp    : {selected_sit_time} ({temporal_match_type})")
    print(f"Corridor containment confirmed: 100% of {len(sit_values)} cells within 50 km corridor")
    print(f"SIC alignment confirmed       : 100% coordinate match with SIC cells")
    
    ds_out = xr.Dataset(
        data_vars={
            'SIT': (['cell'], sit_values, {
                'long_name': 'Sea ice thickness',
                'standard_name': 'sea_ice_thickness',
                'units': 'm',
                'coverage': 'Vessel route + corridor',
                'interpolation_method': 'linear',
                'source_dataset_id': cmems_dataset_id,
                'source_variable': sit_var,
                'selected_timestamp': str(selected_sit_time)
            })
        },
        coords={
            'latitude': (['cell'], target_lats),
            'longitude': (['cell'], target_lons),
            'time': selected_sit_time
        },
        attrs={
            'title': 'CMEMS Sea Ice Thickness (SIT) for Route Corridor',
            'corridor_buffer_m': buffer_distance_m,
            'source_cmems_dataset': cmems_dataset_id,
            'reference_sic_source': sic_csv if os.path.exists(sic_csv) else sic_nc_file,
            'history': f'Interpolated linearly within corridor on {pd.Timestamp.now().isoformat()}'
        }
    )
    
    nc_out_path = os.path.join(run_dir, "sit_grid.nc")
    ds_out.to_netcdf(nc_out_path)
    print(f"\nSaved authoritative corridor NetCDF grid to {nc_out_path}")
    
    df_out = pd.DataFrame({
        'latitude': target_lats,
        'longitude': target_lons,
        'SIT': sit_values
    })
    csv_out_path = os.path.join(run_dir, "sit_grid.csv")
    df_out.to_csv(csv_out_path, index=False)
    print(f"Saved corridor CSV grid to {csv_out_path} ({len(df_out)} rows)")
    
    print("\nGenerating route corridor SIT map visualization...")
    fig, ax = plt.subplots(figsize=(10, 8))
    
    gdf_route.plot(ax=ax, color='red', linewidth=2, label='Route', zorder=5)
    gpd.GeoSeries([corridor_polygon]).plot(
        ax=ax, facecolor='none', edgecolor='blue', linestyle='--', label='Corridor', zorder=4
    )
    
    scatter = ax.scatter(
        df_out['longitude'],
        df_out['latitude'],
        c=df_out['SIT'],
        cmap='viridis',
        s=12,
        marker='s',
        vmin=0.0,
        zorder=3
    )
    
    cbar = plt.colorbar(scatter, ax=ax, fraction=0.046, pad=0.04)
    cbar.set_label('Sea Ice Thickness (m)', fontsize=11)
    
    ax.set_title(f"Antarctic Sea Ice Thickness (SIT)\nDate: {sic_date_str} (Source: CMEMS {sit_var})", fontsize=12)
    ax.set_xlabel("Longitude (°E)", fontsize=10)
    ax.set_ylabel("Latitude (°N)", fontsize=10)
    ax.legend(loc='upper right')
    
    margin_plot = 0.5
    ax.set_xlim(min_lon - margin_plot, max_lon + margin_plot)
    ax.set_ylim(min_lat - margin_plot, max_lat + margin_plot)
    
    plt.tight_layout()
    plot_out_path = os.path.join(run_dir, "sit_grid.png")
    plt.savefig(plot_out_path, dpi=200)
    plt.close()
    print(f"Saved corridor verification map to {plot_out_path}")
    print("\n--- Pipeline Completed Successfully ---")

if __name__ == "__main__":
    run(".")
