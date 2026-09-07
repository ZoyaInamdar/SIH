from __future__ import annotations

from pathlib import Path
from .environment_reader import create_environment_reader


def create_era5_reader(filename: str | Path):
    """
    Create an OpenDrift reader for an ERA5 environmental dataset (.nc, .grib, .grib2).

    Parameters
    ----------
    filename:
        Path to the ERA5 file.

    Returns
    -------
    OpenDrift reader instance.
    """
    return create_environment_reader(filename)