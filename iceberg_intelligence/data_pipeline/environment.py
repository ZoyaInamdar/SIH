from __future__ import annotations

from pathlib import Path

import pandas as pd
import xarray as xr


def _find_coordinate(
    ds: xr.Dataset,
    candidates: tuple[str, ...],
) -> str | None:

    for name in candidates:
        if name in ds.coords:
            return name

    for name in candidates:
        if name in ds.variables:
            return name

    return None


def inspect_environment(filename: str | Path) -> dict:
    """
    Inspect a NetCDF environmental dataset.

    Returns metadata needed by the pipeline.
    """

    filename = Path(filename)

    if not filename.exists():
        raise FileNotFoundError(
            f"Environmental file not found: {filename}"
        )

    with xr.open_dataset(filename) as ds:

        lat_name = _find_coordinate(
            ds,
            ("latitude", "lat"),
        )

        lon_name = _find_coordinate(
            ds,
            ("longitude", "lon"),
        )

        time_name = _find_coordinate(
            ds,
            ("time", "valid_time"),
        )

        if lat_name is None:
            raise ValueError(
                f"No latitude coordinate found in {filename}"
            )

        if lon_name is None:
            raise ValueError(
                f"No longitude coordinate found in {filename}"
            )

        latitudes = ds[lat_name].values
        longitudes = ds[lon_name].values

        result = {
            "file": str(filename),
            "latitude_min": float(latitudes.min()),
            "latitude_max": float(latitudes.max()),
            "longitude_min": float(longitudes.min()),
            "longitude_max": float(longitudes.max()),
            "latitude_name": lat_name,
            "longitude_name": lon_name,
            "time_name": time_name,
            "variables": sorted(ds.data_vars),
        }

        if time_name is not None:
            times = pd.to_datetime(ds[time_name].values)

            result["time_start"] = times.min()
            result["time_end"] = times.max()
            result["time_count"] = len(times)

        if "depth" in ds.coords or "depth" in ds.variables:
            depth_values = ds["depth"].values

            result["depth_count"] = int(depth_values.size)
            result["depth_min"] = float(depth_values.min())
            result["depth_max"] = float(depth_values.max())

        else:
            result["depth_count"] = 0
            result["depth_min"] = None
            result["depth_max"] = None

    return result


def observation_is_covered(
    latitude: float,
    longitude: float,
    timestamp: pd.Timestamp,
    metadata: dict,
) -> bool:
    """Check whether one observation falls inside a dataset."""

    if not (
        metadata["latitude_min"]
        <= latitude
        <= metadata["latitude_max"]
    ):
        return False

    if not (
        metadata["longitude_min"]
        <= longitude
        <= metadata["longitude_max"]
    ):
        return False

    if "time_start" in metadata:
        if timestamp < metadata["time_start"]:
            return False

        if timestamp > metadata["time_end"]:
            return False

    return True