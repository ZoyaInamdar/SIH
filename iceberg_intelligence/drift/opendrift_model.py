"""
drift/opendrift_model.py

A thin runner around OpenDrift's OpenBerg model. This file has exactly one
job: take already-mapped, OpenBerg-ready iceberg parameters and optional
environmental Readers, run OpenBerg, and hand back its raw output.

It is NOT a second iceberg model. It does not:
    - implement ocean-current force, wind drag, Coriolis, wave radiation,
      sea-ice force, or melting/erosion physics (OpenBerg does all of this)
    - implement a standalone Leeway/"current + factor*wind" approximation
    - know what a project IcebergObservation or iceberg_id is
      (see iceberg_wrapper/iceberg_mapper.py for that)
    - convert output into a trajectory table, validate it against
      observations, or bias-correct it (see drift/trajectory.py,
      drift/validation.py, drift/bias_correction.py)
    - hold any real or synthetic environmental data (see the module
      docstring note on synthetic forcing, at the bottom of this file)

Verified against the installed OpenDrift 1.14.12:
    - OpenBerg(loglevel=...) constructor
    - OpenBerg.add_reader(readers: list)
    - OpenBerg.seed_elements(lon, lat, time, number=None, **kwargs) --
      length/width/sail/draft are passed as kwargs, exactly as OpenBerg's
      own IcebergObj element type expects
    - OpenBerg.run(duration=timedelta, time_step=seconds) -- populates
      `.result`, an xarray.Dataset with dims (trajectory, time)
If a future OpenDrift version changes any of these signatures, this is the
one file that needs to change.
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta
from typing import Any, List, Optional, Sequence, Union

from opendrift.models.openberg import OpenBerg

logger = logging.getLogger(__name__)

Number = Union[int, float]
NumberOrList = Union[Number, Sequence[Number]]


class OpenBergRunError(RuntimeError):
    """Raised when OpenBerg setup, seeding, or running fails."""


class OpenBergRunner:
    """Thin adapter around OpenDrift's OpenBerg model.

    Usage:
        runner = OpenBergRunner()
        runner.add_reader(ocean_current_reader)
        runner.add_reader(wind_reader)
        runner.seed(lat=-65.0, lon=10.0, time=start_time,
                    length=500.0, width=300.0, sail=30.0, draft=270.0)
        runner.run(duration_hours=6)
        raw_result = runner.get_raw_result()   # xarray.Dataset

    All inputs here are expected to already be in OpenBerg's own units and
    field names (metres, m/s, WGS84 degrees) -- that conversion is
    iceberg_wrapper/iceberg_mapper.py's responsibility, not this file's.
    """

    def __init__(self, loglevel: int = logging.WARNING) -> None:
        try:
            self.model = OpenBerg(loglevel=loglevel)
        except Exception as exc:
            raise OpenBergRunError(f"failed to initialize OpenBerg: {exc}") from exc

        self._readers_added = 0
        self._seeded_count = 0
        self._has_run = False

    # ------------------------------------------------------------------
    # Readers
    # ------------------------------------------------------------------

    def add_reader(self, reader: Union[Any, List[Any]]) -> None:
        """Attach one or more OpenDrift Readers (ocean current, wind,
        bathymetry, or any other OpenBerg-required forcing).

        This method does not care whether `reader` is synthetic or a real
        NetCDF-backed reader -- that distinction is made by whoever
        constructs the reader, not by this runner.
        """
        readers = reader if isinstance(reader, list) else [reader]
        if not readers:
            raise OpenBergRunError("add_reader() called with an empty reader list")
        try:
            self.model.add_reader(readers)
        except Exception as exc:
            raise OpenBergRunError(f"failed to add reader(s): {exc}") from exc
        self._readers_added += len(readers)

    # ------------------------------------------------------------------
    # Seeding
    # ------------------------------------------------------------------

    def seed(
        self,
        lat: NumberOrList,
        lon: NumberOrList,
        time: datetime,
        length: NumberOrList,
        width: NumberOrList,
        sail: NumberOrList,
        draft: NumberOrList,
        number: Optional[int] = None,
    ) -> None:
        """Seed one or more icebergs into OpenBerg.

        Each of lat/lon/length/width/sail/draft may be a single number (one
        iceberg) or a sequence of equal length (multiple icebergs seeded
        together, matching OpenDrift's own seed_elements() convention).

        `sail` corresponds to OpenBerg's freeboard-related element property;
        how a project's `freeboard_m` maps to `sail` is decided in
        iceberg_mapper.py, not here.
        """
        self._validate_seed_inputs(lat, lon, time, length, width, sail, draft)

        try:
            self.model.seed_elements(
                lon=lon,
                lat=lat,
                time=time,
                number=number,
                length=length,
                width=width,
                sail=sail,
                draft=draft,
            )
        except Exception as exc:
            raise OpenBergRunError(f"OpenBerg seed_elements() failed: {exc}") from exc

        self._seeded_count += number if number is not None else len(
            lat if isinstance(lat, (list, tuple)) else [lat]
        )

    @staticmethod
    def _as_list(value: NumberOrList) -> List[Number]:
        return list(value) if isinstance(value, (list, tuple)) else [value]

    def _validate_seed_inputs(
        self,
        lat: NumberOrList,
        lon: NumberOrList,
        time: datetime,
        length: NumberOrList,
        width: NumberOrList,
        sail: NumberOrList,
        draft: NumberOrList,
    ) -> None:
        """Sanity checks on physically well-formed input. This is NOT
        business-rule validation (that belongs in iceberg_mapper.py) --
        it only guards against values that would make no physical sense
        or would cause OpenBerg to fail or misbehave silently.
        """
        if not isinstance(time, datetime):
            raise OpenBergRunError("time must be a datetime instance")

        for value in self._as_list(lat):
            if not (-90.0 <= float(value) <= 90.0):
                raise OpenBergRunError(f"latitude {value} out of range [-90, 90]")
        for value in self._as_list(lon):
            if not (-180.0 <= float(value) <= 180.0):
                raise OpenBergRunError(f"longitude {value} out of range [-180, 180]")
        for name, values in (("length", length), ("width", width), ("sail", sail), ("draft", draft)):
            for value in self._as_list(values):
                if float(value) <= 0:
                    raise OpenBergRunError(f"{name} must be positive, got {value}")

        lat_list, lon_list = self._as_list(lat), self._as_list(lon)
        if len(lat_list) != len(lon_list):
            raise OpenBergRunError(
                f"lat and lon must have the same length (got {len(lat_list)} and {len(lon_list)})"
            )

    # ------------------------------------------------------------------
    # Running
    # ------------------------------------------------------------------

    def run(self, duration_hours: float, time_step_seconds: int = 1800) -> None:
        """Run the OpenBerg simulation for the given duration."""
        if self._seeded_count == 0:
            raise OpenBergRunError("no icebergs have been seeded -- call seed() first")
        if duration_hours <= 0:
            raise OpenBergRunError(f"duration_hours must be positive, got {duration_hours}")
        if time_step_seconds <= 0:
            raise OpenBergRunError(f"time_step_seconds must be positive, got {time_step_seconds}")

        logger.info(
            "Running OpenBerg for %.2f hours (%d iceberg element(s), %d reader(s))...",
            duration_hours, self._seeded_count, self._readers_added,
        )
        try:
            self.model.run(duration=timedelta(hours=duration_hours), time_step=time_step_seconds)
        except Exception as exc:
            raise OpenBergRunError(f"OpenBerg run() failed: {exc}") from exc

        if getattr(self.model, "result", None) is None:
            raise OpenBergRunError("OpenBerg run() completed but produced no result dataset")

        self._has_run = True
        logger.info("OpenBerg run complete.")

    # ------------------------------------------------------------------
    # Output
    # ------------------------------------------------------------------

    def get_raw_result(self):
        """Return OpenBerg's raw output: an xarray.Dataset with dimensions
        (trajectory, time). No post-processing, no iceberg_id mapping, no
        derived fields -- that is drift/trajectory.py's job.
        """
        if not self._has_run:
            raise OpenBergRunError("run() has not completed successfully yet")
        return self.model.result


def run_openberg_simulation(
    lat: NumberOrList,
    lon: NumberOrList,
    time: datetime,
    length: NumberOrList,
    width: NumberOrList,
    sail: NumberOrList,
    draft: NumberOrList,
    duration_hours: float,
    readers: Optional[List[Any]] = None,
    time_step_seconds: int = 1800,
    loglevel: int = logging.WARNING,
):
    """Convenience function wrapping OpenBergRunner for the common
    single-call case: seed once, run once, return the raw result.

    For multi-step workflows (e.g. seeding icebergs detected at different
    times) use OpenBergRunner directly instead of this function.
    """
    runner = OpenBergRunner(loglevel=loglevel)
    if readers:
        runner.add_reader(readers)
    runner.seed(lat=lat, lon=lon, time=time, length=length, width=width, sail=sail, draft=draft)
    runner.run(duration_hours=duration_hours, time_step_seconds=time_step_seconds)
    return runner.get_raw_result()


# ---------------------------------------------------------------------------
# DEMO / TEST-ONLY CODE BELOW
#
# Nothing above this line depends on synthetic data. The function below
# exists only so this file can be smoke-tested standalone, before real
# environmental Readers exist. It is intentionally NOT part of the public
# interface (leading underscore) and is only used in the __main__ block.
# ---------------------------------------------------------------------------

def _build_demo_synthetic_reader():
    """TEST-ONLY: a minimal constant-field reader so this module can be
    run standalone. Do not import this from production code -- real
    Readers (NetCDF-backed ocean current / wind / bathymetry) are built
    elsewhere once the real environmental dataset is finalized.
    """
    import numpy as np
    from opendrift.readers import reader_constant_2d

    lon = np.linspace(0.0, 20.0, 5)
    lat = np.linspace(-70.0, -60.0, 5)
    shape = (5, 5)  # (len(lat), len(lon))
    array_dict = {
        "x_sea_water_velocity": np.full(shape, 0.10),
        "y_sea_water_velocity": np.full(shape, 0.03),
        "x_wind": np.full(shape, 5.0),
        "y_wind": np.full(shape, 2.0),
    }
    reader = reader_constant_2d.Reader(lon, lat, array_dict)
    reader.name = "demo_synthetic_reader_TEST_ONLY"
    return reader


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

    demo_reader = _build_demo_synthetic_reader()
    result = run_openberg_simulation(
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

    # TEST-ONLY: eyeball the actual trajectory for this one demo iceberg.
    # Production code should NOT do this here -- turning raw OpenBerg
    # output into a clean per-iceberg trajectory table is drift/trajectory.py's
    # job, not this file's. This is just so `python drift/opendrift_model.py`
    # shows something readable instead of a bare xarray repr.
    lon = result.lon.values[0]
    lat = result.lat.values[0]
    time_values = result.time.values

    print("\n--- Demo trajectory (iceberg 0) ---")
    for t, la, lo in zip(time_values, lat, lon):
        print(f"{t}   {la:.3f}   {lo:.3f}")