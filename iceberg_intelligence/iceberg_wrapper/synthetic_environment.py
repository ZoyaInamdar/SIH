"""
synthetic_environment.py

Creates a SYNTHETIC, Antarctic-shaped test environment for OpenBerg, using
OpenDrift's documented static-grid reader:

    opendrift.readers.reader_constant_2d.Reader

These are NOT real measurements. They are deterministic placeholder values so
the wrapper/architecture can be exercised end-to-end before real NetCDF
Readers (ERA5 wind, ocean currents, sea ice, waves) are available.

This module knows nothing about individual iceberg records -- it only builds
an environmental field. Keep it that way; iceberg-specific logic belongs in
iceberg_mapper.py / iceberg_model.py.

Grid convention (verified against the installed OpenDrift 1.14.12):
`reader_constant_2d.Reader(x, y, array_dict)` expects `x` = 1D longitude
coordinates, `y` = 1D latitude coordinates, and each array in `array_dict`
shaped (len(y), len(x)) -- i.e. row = latitude, column = longitude.
"""

from __future__ import annotations

import numpy as np
from opendrift.readers import reader_constant_2d
from opendrift.readers.reader_constant_2d import Reader as ConstantReader

# Synthetic Antarctic-like test domain -- NOT a real forcing region.
DEFAULT_LON_RANGE = (0.0, 20.0)     # degrees E
DEFAULT_LAT_RANGE = (-70.0, -60.0)  # degrees
DEFAULT_GRID_POINTS = 5             # points per axis; grid is coarse on purpose

# Simple deterministic synthetic values (SYNTHETIC TEST DATA, not measurements)
DEFAULT_OCEAN_U = 0.10   # m/s, x_sea_water_velocity
DEFAULT_OCEAN_V = 0.03   # m/s, y_sea_water_velocity
DEFAULT_WIND_U = 5.0     # m/s, x_wind
DEFAULT_WIND_V = 2.0     # m/s, y_wind


def create_synthetic_environment(
    lon_range: tuple[float, float] = DEFAULT_LON_RANGE,
    lat_range: tuple[float, float] = DEFAULT_LAT_RANGE,
    grid_points: int = DEFAULT_GRID_POINTS,
    ocean_u: float = DEFAULT_OCEAN_U,
    ocean_v: float = DEFAULT_OCEAN_V,
    wind_u: float = DEFAULT_WIND_U,
    wind_v: float = DEFAULT_WIND_V,
) -> ConstantReader:
    """Build a single synthetic OpenDrift Reader covering ocean current and
    wind over a coarse regular grid.

    Values are currently uniform (deterministic scalars broadcast across the
    grid) but the grid itself is a real 2D array, so this can later be edited
    to hold spatially varying synthetic fields without changing the
    IcebergDriftModel code that calls this function.

    All other OpenBerg-required variables (waves, sea ice, temperature,
    salinity, sea floor depth, land mask, ...) are intentionally NOT set
    here -- OpenBerg already has documented fallback values for those, and
    `land_binary_mask` is filled automatically by OpenDrift's built-in
    global landmask reader once this reader is added to the model.
    """
    lon = np.linspace(lon_range[0], lon_range[1], grid_points)
    lat = np.linspace(lat_range[0], lat_range[1], grid_points)
    shape = (grid_points, grid_points)  # (len(lat), len(lon))

    array_dict = {
        "x_sea_water_velocity": np.full(shape, ocean_u, dtype=float),
        "y_sea_water_velocity": np.full(shape, ocean_v, dtype=float),
        "x_wind": np.full(shape, wind_u, dtype=float),
        "y_wind": np.full(shape, wind_v, dtype=float),
    }

    reader = reader_constant_2d.Reader(lon, lat, array_dict)
    reader.name = "synthetic_antarctic_test_environment"
    return reader