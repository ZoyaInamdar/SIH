"""
csv_to_netcdf.py

Conversion utility to convert synthetic environmental CSV files (ERA5-style and
GLORYS-style) into CF-compliant NetCDF files for OpenDrift readers.

ERA5:
  Dimensions: time, latitude, longitude
  Variables: eastward_wind (u10), northward_wind (v10)

GLORYS:
  Dimensions: time, depth, latitude, longitude
  Variables: eastward_sea_water_velocity (uo), northward_sea_water_velocity (vo),
             sea_water_temperature (thetao), sea_water_salinity (so),
             sea_surface_height_above_geoid (zos), sea_ice_area_fraction (siconc),
             sea_ice_thickness (sithick), eastward_sea_ice_velocity (usi),
             northward_sea_ice_velocity (vsi)
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Union

import pandas as pd
import xarray as xr

logger = logging.getLogger(__name__)


def convert_era5_csv_to_netcdf(csv_path: Union[str, Path], nc_path: Union[str, Path]) -> Path:
    """Convert an ERA5 synthetic wind CSV file into a CF-compliant NetCDF file."""
    csv_file = Path(csv_path)
    nc_file = Path(nc_path)

    if not csv_file.exists():
        raise FileNotFoundError(f"ERA5 CSV file not found: {csv_file}")

    df = pd.read_csv(csv_file)
    df["valid_time"] = pd.to_datetime(df["valid_time"])

    # Set index and convert to xarray Dataset
    ds = df.set_index(["valid_time", "latitude", "longitude"]).to_xarray()

    # Rename variables and dimensions to standard CF names
    ds = ds.rename({
        "valid_time": "time",
        "u10": "eastward_wind",
        "v10": "northward_wind",
    })

    # Set CF attributes
    ds["time"].attrs = {"standard_name": "time", "long_name": "time"}
    ds["latitude"].attrs = {"standard_name": "latitude", "long_name": "latitude", "units": "degrees_north"}
    ds["longitude"].attrs = {"standard_name": "longitude", "long_name": "longitude", "units": "degrees_east"}

    ds["eastward_wind"].attrs = {
        "standard_name": "eastward_wind",
        "long_name": "10 metre U wind component",
        "units": "m s-1",
    }
    ds["northward_wind"].attrs = {
        "standard_name": "northward_wind",
        "long_name": "10 metre V wind component",
        "units": "m s-1",
    }

    ds.attrs["Conventions"] = "CF-1.8"
    ds.attrs["source"] = "Synthetic ERA5 demonstration wind forcing"

    nc_file.parent.mkdir(parents=True, exist_ok=True)
    ds.to_netcdf(nc_file)
    logger.info("Converted ERA5 CSV %s -> NetCDF %s", csv_file.name, nc_file.name)
    return nc_file


def convert_glorys_csv_to_netcdf(csv_path: Union[str, Path], nc_path: Union[str, Path]) -> Path:
    """Convert a GLORYS synthetic ocean/sea-ice CSV file into a CF-compliant NetCDF file."""
    csv_file = Path(csv_path)
    nc_file = Path(nc_path)

    if not csv_file.exists():
        raise FileNotFoundError(f"GLORYS CSV file not found: {csv_file}")

    df = pd.read_csv(csv_file)
    df["time"] = pd.to_datetime(df["time"])

    # Set index and convert to xarray Dataset
    ds = df.set_index(["time", "depth", "latitude", "longitude"]).to_xarray()

    rename_map = {
        "uo": "eastward_sea_water_velocity",
        "vo": "northward_sea_water_velocity",
        "thetao": "sea_water_temperature",
        "so": "sea_water_salinity",
        "zos": "sea_surface_height_above_geoid",
        "siconc": "sea_ice_area_fraction",
        "sithick": "sea_ice_thickness",
        "usi": "eastward_sea_ice_velocity",
        "vsi": "northward_sea_ice_velocity",
    }

    ds = ds.rename(rename_map)

    # Set CF attributes
    ds["time"].attrs = {"standard_name": "time", "long_name": "time"}
    ds["depth"].attrs = {
        "standard_name": "depth",
        "long_name": "depth",
        "units": "m",
        "positive": "down",
        "axis": "Z",
    }
    ds["latitude"].attrs = {"standard_name": "latitude", "long_name": "latitude", "units": "degrees_north"}
    ds["longitude"].attrs = {"standard_name": "longitude", "long_name": "longitude", "units": "degrees_east"}

    ds["eastward_sea_water_velocity"].attrs = {
        "standard_name": "eastward_sea_water_velocity",
        "long_name": "Eastward sea water velocity",
        "units": "m s-1",
    }
    ds["northward_sea_water_velocity"].attrs = {
        "standard_name": "northward_sea_water_velocity",
        "long_name": "Northward sea water velocity",
        "units": "m s-1",
    }
    ds["sea_water_temperature"].attrs = {
        "standard_name": "sea_water_temperature",
        "long_name": "Sea water temperature",
        "units": "degC",
    }
    ds["sea_water_salinity"].attrs = {
        "standard_name": "sea_water_salinity",
        "long_name": "Sea water salinity",
        "units": "1",
    }
    ds["sea_surface_height_above_geoid"].attrs = {
        "standard_name": "sea_surface_height_above_geoid",
        "long_name": "Sea surface height above geoid",
        "units": "m",
    }
    ds["sea_ice_area_fraction"].attrs = {
        "standard_name": "sea_ice_area_fraction",
        "long_name": "Sea ice area fraction",
        "units": "1",
    }
    ds["sea_ice_thickness"].attrs = {
        "standard_name": "sea_ice_thickness",
        "long_name": "Sea ice thickness",
        "units": "m",
    }
    ds["eastward_sea_ice_velocity"].attrs = {
        "standard_name": "eastward_sea_ice_velocity",
        "long_name": "Eastward sea ice velocity",
        "units": "m s-1",
    }
    ds["northward_sea_ice_velocity"].attrs = {
        "standard_name": "northward_sea_ice_velocity",
        "long_name": "Northward sea ice velocity",
        "units": "m s-1",
    }

    ds.attrs["Conventions"] = "CF-1.8"
    ds.attrs["source"] = "Synthetic GLORYS demonstration ocean and sea-ice forcing"

    nc_file.parent.mkdir(parents=True, exist_ok=True)
    ds.to_netcdf(nc_file)
    logger.info("Converted GLORYS CSV %s -> NetCDF %s", csv_file.name, nc_file.name)
    return nc_file


def convert_all_demo_csvs(base_dir: Union[str, Path] = "data/environmental") -> dict[str, list[Path]]:
    """Convert all synthetic demonstration CSV files into NetCDF format."""
    base_path = Path(base_dir)
    era5_dir = base_path / "era5"
    glorys_dir = base_path / "glorys"

    era5_nc_dir = era5_dir / "netcdf"
    glorys_nc_dir = glorys_dir / "netcdf"

    converted_era5 = []
    converted_glorys = []

    for demo_id in ["IB_DEMO_001", "IB_DEMO_002", "IB_DEMO_003"]:
        era5_csv = era5_dir / f"{demo_id}_era5.csv"
        era5_nc = era5_nc_dir / f"{demo_id}_era5.nc"
        converted_era5.append(convert_era5_csv_to_netcdf(era5_csv, era5_nc))

        glorys_csv = glorys_dir / f"{demo_id}_glorys.csv"
        glorys_nc = glorys_nc_dir / f"{demo_id}_glorys.nc"
        converted_glorys.append(convert_glorys_csv_to_netcdf(glorys_csv, glorys_nc))

    return {
        "era5": converted_era5,
        "glorys": converted_glorys,
    }


if __name__ == "__main__":
    res = convert_all_demo_csvs()
    print("Successfully converted all demonstration CSVs to NetCDF:")
    for key, paths in res.items():
        print(f"  {key.upper()}:")
        for p in paths:
            print(f"    - {p}")
