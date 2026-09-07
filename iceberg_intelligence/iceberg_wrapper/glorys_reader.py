from __future__ import annotations

from pathlib import Path
from .environment_reader import create_environment_reader


def create_glorys_reader(filename: str | Path):
    """
    Create an OpenDrift reader for a GLORYS environmental dataset (.nc, .grib, .grib2).

    Parameters
    ----------
    filename:
        Path to the GLORYS file.

    Returns
    -------
    OpenDrift reader instance.
    """
    return create_environment_reader(filename)