from __future__ import annotations

import logging
from typing import Any, Mapping

from iceberg_wrapper.iceberg_model import IcebergDriftModel


logger = logging.getLogger(__name__)


def run_openberg_case(
    iceberg: Mapping[str, Any],
    era5_reader,
    glorys_reader,
    *,
    hours: float = 6.0,
):
    """
    Run OpenBerg for one real iceberg observation.

    The wrapper remains responsible for OpenBerg details.

    The data pipeline only supplies:

        - project iceberg record
        - ERA5 Reader
        - GLORYS Reader
    """

    logger.info("Initializing OpenBerg...")

    model = IcebergDriftModel()

    logger.info("Adding ERA5 Reader...")
    model.add_reader(era5_reader)

    logger.info("Adding GLORYS Reader...")
    model.add_reader(glorys_reader)

    logger.info(
        "Seeding iceberg %s...",
        iceberg["iceberg_id"],
    )

    model.add_icebergs(
        [iceberg],
        start_time=iceberg["timestamp"],
    )

    logger.info(
        "Running OpenBerg for %.2f hours...",
        hours,
    )

    model.run(hours=hours)

    trajectory = model.get_trajectory()

    if trajectory is None or trajectory.empty:
        raise RuntimeError(
            "OpenBerg completed without producing trajectory output."
        )

    logger.info(
        "OpenBerg completed: %d trajectory records.",
        len(trajectory),
    )

    return trajectory