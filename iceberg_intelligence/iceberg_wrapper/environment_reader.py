"""
environment_reader.py

Unified environment reader abstraction for OpenDrift.

Supports:
  - NetCDF (.nc, .nc4, .netcdf) -> reader_netCDF_CF_generic
  - GRIB   (.grib, .grb)        -> reader_grib2 / xarray cfgrib reader
  - GRIB2  (.grib2, .grb2)      -> reader_grib2 / xarray cfgrib reader

The abstraction isolates file format detection so that IcebergDriftModel
and the rest of the application work with standard OpenDrift Reader objects
regardless of the underlying file format.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from opendrift.readers import reader_netCDF_CF_generic

logger = logging.getLogger(__name__)


def create_environment_reader(filename: str | Path) -> Any:
    """
    Create an OpenDrift Reader for a NetCDF or GRIB/GRIB2 environmental file.

    Parameters
    ----------
    filename:
        Path to environmental dataset (.nc, .grib, .grib2, etc.).

    Returns
    -------
    OpenDrift Reader instance.
    """
    filepath = Path(filename)

    if not filepath.exists():
        raise FileNotFoundError(f"Environmental file not found: {filepath}")

    suffix = filepath.suffix.lower()

    print("Initializing environment reader...")

    if suffix in {".nc", ".nc4", ".netcdf"}:
        print("Detected format: NetCDF")
        print("Using OpenDrift NetCDF CF Reader...")
        reader = reader_netCDF_CF_generic.Reader(str(filepath))

    elif suffix in {".grib", ".grb", ".grib2", ".grb2"}:
        fmt = "GRIB2" if "2" in suffix else "GRIB"
        print(f"Detected format: {fmt}")
        print(f"Using OpenDrift {fmt} Reader...")
        try:
            from opendrift.readers import reader_grib2
            reader = reader_grib2.Reader(str(filepath))
        except Exception as err:
            logger.debug("Standard reader_grib2 failed (%s), attempting xarray cfgrib backend...", err)
            try:
                import xarray as xr
                try:
                    ds = xr.open_dataset(filepath, engine="cfgrib")
                except ValueError as e:
                    if "filter_by_keys" in str(e):
                        ds = xr.open_dataset(
                            filepath,
                            engine="cfgrib",
                            backend_kwargs={"filter_by_keys": {"dataType": "an"}},
                        )
                    else:
                        raise
                if "valid_time" in ds and "time" not in ds:
                    ds = ds.rename({"valid_time": "time"})
                reader = reader_netCDF_CF_generic.Reader(ds)
                reader.name = str(filepath)
            except Exception as exc:
                raise RuntimeError(
                    f"Could not initialize GRIB reader for {filepath}: {exc}"
                ) from exc

    else:
        raise ValueError(
            f"Unsupported environmental dataset format: {suffix}. "
            "Expected .nc, .grib, or .grib2."
        )

    print("Reader initialized successfully.")

    if hasattr(reader, "xmin") and hasattr(reader, "xmax"):
        print(
            f"Coverage: xmin={reader.xmin:.4f}, xmax={reader.xmax:.4f}, "
            f"ymin={reader.ymin:.4f}, ymax={reader.ymax:.4f}"
        )

    if hasattr(reader, "start_time") and hasattr(reader, "end_time"):
        if reader.start_time is not None:
            print(f"Time coverage: {reader.start_time} -> {reader.end_time}")

    if hasattr(reader, "variables"):
        vars_list = [str(v) for v in reader.variables]
        print(f"Variables: {', '.join(vars_list)}")

    return reader
