"""
iceberg_model.py

IcebergDriftModel -- the main wrapper. This is the only class the rest of the
project should ever import from this package. It hides all OpenDrift/OpenBerg
API details (ElementType, seed_elements kwargs, reader wiring, xarray result
format) behind a small, stable interface.

    model = IcebergDriftModel()
    model.add_synthetic_environment()
    model.add_icebergs(icebergs, start_time=datetime(2026, 1, 1, 12, 0, 0))
    model.run(hours=6)
    trajectory_df = model.get_trajectory()

Verified against the installed OpenDrift 1.14.12 (pip metadata; source
reports 1.14.11 -- see note in README about this discrepancy). If a future
OpenDrift upgrade changes `seed_elements`, `run`, or the `.result` xarray
schema, this is the one file that needs to change.
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Union

import numpy as np
import pandas as pd
from opendrift.models.openberg import OpenBerg

from . import iceberg_mapper
from .synthetic_environment import create_synthetic_environment

logger = logging.getLogger(__name__)


class IcebergDriftModelError(RuntimeError):
    """Raised for any failure in setting up or running the drift model."""


class IcebergDriftModel:
    """Adapter/orchestration layer around OpenDrift's OpenBerg model.

    Responsibilities: prepare data, add Readers, seed icebergs, run OpenBerg,
    retrieve output, map output back to project iceberg IDs. It does NOT
    implement any iceberg physics of its own -- OpenBerg does that.
    """

    def __init__(self, loglevel: int = logging.WARNING) -> None:
        try:
            self.model = OpenBerg(loglevel=loglevel)
        except Exception as exc:
            raise IcebergDriftModelError(f"failed to initialize OpenBerg: {exc}") from exc

        # trajectory index (seeding order, 0-based) -> project iceberg_id
        self._id_by_trajectory: List[Any] = []
        self._has_run = False

    # ------------------------------------------------------------------
    # Environment
    # ------------------------------------------------------------------

    def add_reader(self, reader: Union[Any, List[Any]]) -> None:
        """Add one or more OpenDrift Readers (synthetic now, real NetCDF
        Readers later) without the caller needing to know which kind it is.
        """
        readers = reader if isinstance(reader, list) else [reader]
        try:
            self.model.add_reader(readers)
        except Exception as exc:
            raise IcebergDriftModelError(f"failed to add reader(s): {exc}") from exc

    def add_synthetic_environment(self, **kwargs: Any) -> None:
        """Attach the synthetic Antarctic-like test environment.
        kwargs are forwarded to create_synthetic_environment() (e.g. to
        override lon_range/lat_range/ocean_u/wind_u for a different test).
        """
        reader = create_synthetic_environment(**kwargs)
        self.add_reader(reader)

    # ------------------------------------------------------------------
    # Seeding
    # ------------------------------------------------------------------

    def add_icebergs(
        self,
        icebergs: List[Dict[str, Any]],
        start_time: datetime,
    ) -> None:
        """Seed project iceberg records into OpenBerg.

        `icebergs` uses the project schema (see iceberg_mapper.map_iceberg
        for the exact expected keys) -- NOT OpenBerg's internal field names.

        Can be called more than once (e.g. to seed icebergs detected at
        different times); each call appends to the trajectory index in
        order, and the internal ID mapping is extended to match.
        """
        if not isinstance(start_time, datetime):
            raise IcebergDriftModelError("start_time must be a datetime instance")

        try:
            mapped = iceberg_mapper.map_icebergs(icebergs)
        except iceberg_mapper.IcebergMappingError as exc:
            raise IcebergDriftModelError(f"iceberg mapping failed: {exc}") from exc

        lons = [m["lon"] for m in mapped]
        lats = [m["lat"] for m in mapped]
        lengths = [m["length"] for m in mapped]
        widths = [m["width"] for m in mapped]
        sails = [m["sail"] for m in mapped]
        drafts = [m["draft"] for m in mapped]
        ids = [m["id"] for m in mapped]

        logger.info("Seeding %d iceberg(s)...", len(mapped))
        try:
            self.model.seed_elements(
                lon=lons,
                lat=lats,
                time=start_time,
                number=len(mapped),
                length=lengths,
                width=widths,
                sail=sails,
                draft=drafts,
            )
        except Exception as exc:
            raise IcebergDriftModelError(f"OpenBerg seed_elements() failed: {exc}") from exc

        self._id_by_trajectory.extend(ids)

    # ------------------------------------------------------------------
    # Running
    # ------------------------------------------------------------------

    def run(self, hours: float, time_step_seconds: int = 1800) -> None:
        """Run the simulation for the given duration."""
        if not self._id_by_trajectory:
            raise IcebergDriftModelError("no icebergs have been seeded -- call add_icebergs() first")
        if hours <= 0:
            raise IcebergDriftModelError(f"hours must be positive, got {hours}")

        logger.info("Running simulation for %.2f hours...", hours)
        try:
            self.model.run(duration=timedelta(hours=hours), time_step=time_step_seconds)
        except Exception as exc:
            raise IcebergDriftModelError(f"OpenBerg run() failed: {exc}") from exc

        if getattr(self.model, "result", None) is None:
            raise IcebergDriftModelError("simulation completed but produced no result dataset")

        self._has_run = True
        logger.info("Simulation complete.")

    # ------------------------------------------------------------------
    # Output
    # ------------------------------------------------------------------

    def get_trajectory(self) -> pd.DataFrame:
        """Return trajectory output as a pandas DataFrame with columns:

            iceberg_id, time, latitude, longitude,
            iceb_x_velocity, iceb_y_velocity,   (m/s, direct from OpenBerg)
            derived_speed_ms, derived_direction_deg_compass,  (see note below)
            sail, draft, length, width

        `derived_speed_ms` / `derived_direction_deg_compass` are NOT provided
        directly by OpenDrift -- they are calculated here from the model's
        own `iceb_x_velocity` / `iceb_y_velocity` (m/s, eastward/northward):

            speed = sqrt(vx^2 + vy^2)                     [m/s]
            direction = (90 - degrees(atan2(vy, vx))) % 360   [compass bearing,
                degrees clockwise from North, direction of travel]
        """
        if not self._has_run:
            raise IcebergDriftModelError("run() has not completed successfully yet")

        ds = self.model.result
        wanted_vars = [
            v
            for v in ["lon", "lat", "iceb_x_velocity", "iceb_y_velocity", "sail", "draft", "length", "width"]
            if v in ds.data_vars
        ]
        df = ds[wanted_vars].to_dataframe().reset_index()

        id_lookup = dict(enumerate(self._id_by_trajectory))
        df["iceberg_id"] = df["trajectory"].map(id_lookup)
        if df["iceberg_id"].isna().any():
            raise IcebergDriftModelError(
                "could not map every trajectory index back to a project iceberg_id -- "
                "this indicates seeding order and result order have diverged"
            )

        df = df.rename(columns={"lon": "longitude", "lat": "latitude"})

        if "iceb_x_velocity" in df.columns and "iceb_y_velocity" in df.columns:
            vx = df["iceb_x_velocity"].to_numpy()
            vy = df["iceb_y_velocity"].to_numpy()
            df["derived_speed_ms"] = np.sqrt(vx**2 + vy**2)
            df["derived_direction_deg_compass"] = (90 - np.degrees(np.arctan2(vy, vx))) % 360

        ordered_cols = [
            c
            for c in [
                "iceberg_id", "time", "latitude", "longitude",
                "iceb_x_velocity", "iceb_y_velocity",
                "derived_speed_ms", "derived_direction_deg_compass",
                "sail", "draft", "length", "width",
            ]
            if c in df.columns
        ]
        return df[ordered_cols]