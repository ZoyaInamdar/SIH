"""
test_wrapper.py

End-to-end test of the iceberg_wrapper package using synthetic data only.
Run with:  python -m iceberg_wrapper.test_wrapper
(or:       python iceberg_wrapper/test_wrapper.py   from the project root)

This does NOT hide exceptions -- any failure in setup, seeding, or running
propagates and fails loudly, per project requirements.
"""

import logging
import sys
from datetime import datetime

from iceberg_wrapper import IcebergDriftModel, IcebergDriftModelError

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger("test_wrapper")

SYNTHETIC_ICEBERGS = [
    {
        "id": "IB001",
        "latitude": -65.0,
        "longitude": 10.0,
        "length_m": 500,
        "width_m": 300,
        "freeboard_m": 30,
        "estimated_draft_m": 270,
    },
    {
        "id": "IB002",
        "latitude": -65.5,
        "longitude": 11.0,
        "length_m": 300,
        "width_m": 200,
        "freeboard_m": 20,
        "estimated_draft_m": 180,
    },
]

START_TIME = datetime(2026, 1, 1, 12, 0, 0)
RUN_HOURS = 6


def main() -> int:
    logger.info("Initializing OpenBerg...")
    model = IcebergDriftModel(loglevel=logging.WARNING)

    logger.info("Adding synthetic environment...")
    model.add_synthetic_environment()

    logger.info("Seeding %d icebergs...", len(SYNTHETIC_ICEBERGS))
    model.add_icebergs(SYNTHETIC_ICEBERGS, start_time=START_TIME)

    logger.info("Running simulation...")
    model.run(hours=RUN_HOURS)
    logger.info("Simulation complete.")

    trajectory = model.get_trajectory()
    logger.info("Number of trajectory records: %d", len(trajectory))

    # --- Verifications -----------------------------------------------
    if trajectory.empty:
        raise AssertionError("simulation produced no trajectory points")

    seen_ids = set(trajectory["iceberg_id"].unique())
    expected_ids = {rec["id"] for rec in SYNTHETIC_ICEBERGS}
    if seen_ids != expected_ids:
        raise AssertionError(f"expected iceberg IDs {expected_ids}, got {seen_ids}")

    for rec in SYNTHETIC_ICEBERGS:
        iceberg_id = rec["id"]
        rows = trajectory[trajectory["iceberg_id"] == iceberg_id].sort_values("time")
        first_row = rows.iloc[0]
        last_row = rows.iloc[-1]
        moved = (
            abs(first_row["latitude"] - last_row["latitude"]) > 1e-6
            or abs(first_row["longitude"] - last_row["longitude"]) > 1e-6
        )
        if not moved:
            raise AssertionError(f"iceberg {iceberg_id} did not move from its initial position")
        logger.info(
            "%s: start=(%.5f, %.5f) end=(%.5f, %.5f) speed=%.4f m/s",
            iceberg_id,
            first_row["latitude"], first_row["longitude"],
            last_row["latitude"], last_row["longitude"],
            last_row.get("derived_speed_ms", float("nan")),
        )

    print("\n--- Trajectory summary (first 5 rows) ---")
    print(trajectory.head().to_string(index=False))
    print("\nAll checks passed.")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except IcebergDriftModelError as exc:
        logger.error("Wrapper error: %s", exc)
        sys.exit(1)