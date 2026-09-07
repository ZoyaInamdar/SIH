"""
drift/trajectory.py

Extracts, validates, cleans, and represents the trajectory produced by
OpenBerg (see drift/opendrift_model.py). This file does NOT implement any
physics -- OpenBerg already predicted the movement; this file only turns its
raw xarray.Dataset output into a clean, typed, chronological trajectory.

Pipeline position:

    opendrift_model.py  -->  trajectory.py  -->  validation.py  -->  bias_correction.py

This module has no dependency on OpenDrift/OpenBerg itself -- it only needs
an xarray.Dataset shaped the way OpenBerg produces it (see
`extract_trajectory`'s docstring for the exact expected shape). That keeps
validation.py and bias_correction.py free to depend on this module without
needing OpenDrift installed.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import numpy as np
import pandas as pd
import xarray as xr


class TrajectoryExtractionError(ValueError):
    """Raised when a trajectory cannot be safely extracted from a dataset."""


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class TrajectoryPoint:
    """A single validated position on an iceberg's trajectory."""

    timestamp: datetime
    latitude: float
    longitude: float

    def __post_init__(self) -> None:
        if not (-90.0 <= self.latitude <= 90.0):
            raise ValueError(f"latitude {self.latitude} out of range [-90, 90]")
        if not (-180.0 <= self.longitude <= 180.0):
            raise ValueError(f"longitude {self.longitude} out of range [-180, 180]")
        if self.timestamp.tzinfo is None:
            raise ValueError("timestamp must be timezone-aware (UTC)")


@dataclass
class IcebergTrajectory:
    """A chronological sequence of trajectory points for one iceberg.

    `iceberg_id` is preserved end-to-end when the caller provides one (e.g.
    from iceberg_wrapper's seeding order); it is NOT invented here.
    """

    iceberg_id: Optional[str]
    points: List[TrajectoryPoint] = field(default_factory=list)

    def __post_init__(self) -> None:
        if len(self.points) < 2:
            raise TrajectoryExtractionError(
                f"trajectory must contain at least two valid points, got {len(self.points)}"
            )
        timestamps = [p.timestamp for p in self.points]
        if timestamps != sorted(timestamps):
            raise TrajectoryExtractionError("trajectory points are not in chronological order")

    # Thin convenience wrappers -- logic lives in the module-level functions
    # below so validation.py/bias_correction.py can use either style.
    def to_dataframe(self) -> pd.DataFrame:
        return trajectory_to_dataframe(self)

    def to_dict(self) -> Dict[str, Any]:
        return trajectory_to_dict(self)


# ---------------------------------------------------------------------------
# Extraction
# ---------------------------------------------------------------------------

def _require_variables(dataset: xr.Dataset) -> None:
    missing = [v for v in ("lat", "lon", "time") if v not in dataset.variables]
    if missing:
        raise TrajectoryExtractionError(f"dataset is missing required variable(s): {missing}")


def _to_utc_datetime(value: np.datetime64) -> datetime:
    """Convert a numpy/xarray time value to a timezone-aware UTC datetime."""
    ts = pd.Timestamp(value)
    if ts.tzinfo is None:
        ts = ts.tz_localize("UTC")
    else:
        ts = ts.tz_convert("UTC")
    return ts.to_pydatetime()


def _trajectory_count(dataset: xr.Dataset) -> int:
    """Number of iceberg trajectories in the dataset (1 if there is no
    'trajectory' dimension at all -- a bare (time,) shaped dataset)."""
    if "trajectory" in dataset.dims:
        return dataset.sizes["trajectory"]
    return 1


def _extract_one(
    dataset: xr.Dataset,
    trajectory_index: int,
    iceberg_id: Optional[str],
) -> IcebergTrajectory:
    """Extract a single IcebergTrajectory at the given trajectory index."""
    if "trajectory" in dataset.dims:
        lat_values = dataset["lat"].values[trajectory_index]
        lon_values = dataset["lon"].values[trajectory_index]
    else:
        # Dataset has no trajectory dimension -- treat as a single trajectory.
        lat_values = np.asarray(dataset["lat"].values)
        lon_values = np.asarray(dataset["lon"].values)

    time_values = dataset["time"].values

    if len(lat_values) != len(time_values) or len(lon_values) != len(time_values):
        raise TrajectoryExtractionError(
            "lat/lon length does not match time length "
            f"(lat={len(lat_values)}, lon={len(lon_values)}, time={len(time_values)})"
        )

    points: List[TrajectoryPoint] = []
    for t, la, lo in zip(time_values, lat_values, lon_values):
        la_f, lo_f = float(la), float(lo)
        if np.isnan(la_f) or np.isnan(lo_f):
            continue  # ignore invalid/NaN coordinates
        points.append(TrajectoryPoint(timestamp=_to_utc_datetime(t), latitude=la_f, longitude=lo_f))

    points.sort(key=lambda p: p.timestamp)  # guarantee chronological order

    return IcebergTrajectory(iceberg_id=iceberg_id, points=points)


def extract_trajectory(
    dataset: xr.Dataset,
    iceberg_id: Optional[str] = None,
    trajectory_index: Optional[int] = None,
) -> IcebergTrajectory:
    """Extract one standardized IcebergTrajectory from an OpenBerg output dataset.

    Expected dataset shape (as produced by drift/opendrift_model.py):
        dataset["lat"], dataset["lon"]  -- dims (trajectory, time), or just
                                            (time,) if there is no trajectory dim
        dataset["time"]                 -- dim (time,)

    Args:
        dataset: raw OpenDrift/OpenBerg output.
        iceberg_id: project iceberg_id to attach to the result, if known.
            Not inferred from the dataset -- OpenBerg has no notion of it.
        trajectory_index: which trajectory to extract when the dataset holds
            more than one. Required if the dataset has more than one
            trajectory; ignored (or optional) when it holds exactly one.

    Returns:
        IcebergTrajectory with points in chronological order, NaN
        coordinates removed.

    Raises:
        TrajectoryExtractionError if required variables are missing, the
        requested trajectory doesn't exist, or fewer than two valid points
        remain after cleaning.
    """
    _require_variables(dataset)

    n_trajectories = _trajectory_count(dataset)

    if trajectory_index is None:
        if n_trajectories == 1:
            trajectory_index = 0
        else:
            raise TrajectoryExtractionError(
                f"dataset contains {n_trajectories} trajectories -- "
                f"trajectory_index must be specified (use extract_all_trajectories() "
                f"to get all of them at once)"
            )
    elif not (0 <= trajectory_index < n_trajectories):
        raise TrajectoryExtractionError(
            f"trajectory_index {trajectory_index} out of range (dataset has {n_trajectories})"
        )

    return _extract_one(dataset, trajectory_index, iceberg_id)


def extract_all_trajectories(
    dataset: xr.Dataset,
    iceberg_ids: Optional[List[str]] = None,
) -> List[IcebergTrajectory]:
    """Extract every trajectory in the dataset.

    Args:
        dataset: raw OpenDrift/OpenBerg output.
        iceberg_ids: project iceberg_ids in the same order icebergs were
            seeded (i.e. trajectory index 0 -> iceberg_ids[0], etc.). If
            omitted, each trajectory's iceberg_id is left as None.

    Raises:
        TrajectoryExtractionError if `iceberg_ids` is provided but its
        length does not match the number of trajectories.
    """
    _require_variables(dataset)
    n_trajectories = _trajectory_count(dataset)

    if iceberg_ids is not None and len(iceberg_ids) != n_trajectories:
        raise TrajectoryExtractionError(
            f"got {len(iceberg_ids)} iceberg_ids for {n_trajectories} trajectories"
        )

    return [
        _extract_one(dataset, i, iceberg_ids[i] if iceberg_ids else None)
        for i in range(n_trajectories)
    ]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def trajectory_to_dataframe(trajectory: IcebergTrajectory) -> pd.DataFrame:
    """Convert an IcebergTrajectory into a pandas DataFrame with columns
    iceberg_id, timestamp, latitude, longitude."""
    return pd.DataFrame(
        {
            "iceberg_id": [trajectory.iceberg_id] * len(trajectory.points),
            "timestamp": [p.timestamp for p in trajectory.points],
            "latitude": [p.latitude for p in trajectory.points],
            "longitude": [p.longitude for p in trajectory.points],
        }
    )


def trajectory_to_dict(trajectory: IcebergTrajectory) -> Dict[str, Any]:
    """Convert an IcebergTrajectory into a plain dict, e.g. for JSON export."""
    return {
        "iceberg_id": trajectory.iceberg_id,
        "points": [
            {
                "timestamp": p.timestamp.isoformat(),
                "latitude": p.latitude,
                "longitude": p.longitude,
            }
            for p in trajectory.points
        ],
    }


def get_start_point(trajectory: IcebergTrajectory) -> TrajectoryPoint:
    """Return the earliest point in the trajectory."""
    return trajectory.points[0]


def get_end_point(trajectory: IcebergTrajectory) -> TrajectoryPoint:
    """Return the latest point in the trajectory."""
    return trajectory.points[-1]


# ---------------------------------------------------------------------------
# DEMO / TEST-ONLY CODE BELOW
# ---------------------------------------------------------------------------

def _build_fallback_synthetic_dataset() -> xr.Dataset:
    """TEST-ONLY: a minimal hand-built dataset shaped like OpenBerg output,
    used only if drift/opendrift_model.py (and OpenDrift itself) is not
    available in this environment. Not used anywhere outside __main__.
    """
    times = pd.date_range("2026-01-01T12:00:00", periods=5, freq="30min")
    lat = np.array([[-65.000, -64.996, -64.982, -64.985, -64.984]])
    lon = np.array([[10.000, 10.030, 10.050, 10.081, 10.100]])
    return xr.Dataset(
        data_vars={
            "lat": (("trajectory", "time"), lat),
            "lon": (("trajectory", "time"), lon),
        },
        coords={"trajectory": [0], "time": times.values},
    )


if __name__ == "__main__":
    try:
        from opendrift_model import run_openberg_simulation, _build_demo_synthetic_reader

        demo_reader = _build_demo_synthetic_reader()
        raw_result = run_openberg_simulation(
            lat=-65.0,
            lon=10.0,
            time=datetime(2026, 1, 1, 12, 0, 0),
            length=500.0,
            width=300.0,
            sail=30.0,
            draft=270.0,
            duration_hours=6,
            readers=[demo_reader],
        )
        print("(using live OpenBerg output from opendrift_model.py)")
    except ImportError:
        raw_result = _build_fallback_synthetic_dataset()
        print("(OpenDrift not available -- using a hand-built fallback dataset)")

    trajectory = extract_trajectory(raw_result, iceberg_id="IB001")

    print(f"\n--- Trajectory for iceberg {trajectory.iceberg_id} ---")
    for point in trajectory.points:
        print(f"{point.timestamp.isoformat()}   {point.latitude:.3f}   {point.longitude:.3f}")

    print(f"\nNumber of trajectory points: {len(trajectory.points)}")
    start, end = get_start_point(trajectory), get_end_point(trajectory)
    print(f"Start: {start.timestamp.isoformat()} ({start.latitude:.3f}, {start.longitude:.3f})")
    print(f"End:   {end.timestamp.isoformat()} ({end.latitude:.3f}, {end.longitude:.3f})")