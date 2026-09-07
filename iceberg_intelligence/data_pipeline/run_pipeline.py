from __future__ import annotations

import argparse
import logging
from pathlib import Path

import pandas as pd

from opendrift.readers import reader_netCDF_CF_generic

from .config import (
    CASES,
    ensure_output_directory,
    era5_path,
    get_case,
    glorys_path,
    iceberg_path,
)
from .environment import inspect_environment
from .load_icebergs import load_byu_track
from .match import find_common_observations
from .prepare_case import build_openberg_iceberg
from .qc import apply_qc
from .run_openberg import run_openberg_case


logger = logging.getLogger("data_pipeline")


def configure_logging() -> None:
    """
    Configure concise pipeline logging.
    """

    logging.basicConfig(
        level=logging.INFO,
        format="%(levelname)s | %(message)s",
    )


def print_case_header(case_name: str) -> None:
    print()
    print("=" * 70)
    print(f"ICEBERG PIPELINE: {case_name}")
    print("=" * 70)
    print()


def save_dataframe(
    dataframe: pd.DataFrame,
    filename: Path,
) -> None:
    """
    Save a pipeline table.
    """

    filename.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    dataframe.to_csv(
        filename,
        index=False,
    )

    logger.info(
        "Saved: %s",
        filename,
    )


def load_environment_readers(
    era5_filename: Path,
    glorys_filename: Path,
):
    """
    Create the actual OpenDrift Readers.

    These Readers are not modified by the pipeline.
    """

    logger.info(
        "Creating ERA5 Reader: %s",
        era5_filename,
    )

    era5_reader = reader_netCDF_CF_generic.Reader(
        str(era5_filename)
    )

    logger.info(
        "Creating GLORYS Reader: %s",
        glorys_filename,
    )

    glorys_reader = reader_netCDF_CF_generic.Reader(
        str(glorys_filename)
    )

    return era5_reader, glorys_reader


def run_pipeline(
    case_name: str,
    *,
    hours: float = 6.0,
) -> None:
    """
    Execute the complete real-data compatibility pipeline.

    Important:
    This function deliberately stops before OpenBerg if real
    vertical iceberg geometry is unavailable.

    It never invents sail/draft values.
    """

    print_case_header(case_name)

    case = get_case(case_name)

    output_dir = ensure_output_directory()

    # =============================================================
    # STEP 1 — Load iceberg observations
    # =============================================================

    iceberg_filename = iceberg_path(case_name)

    logger.info(
        "Loading iceberg observations..."
    )
    logger.info(
        "File: %s",
        iceberg_filename,
    )

    iceberg_df = load_byu_track(
        iceberg_filename,
        sensor_policy="ascat_then_nic",
    )

    if iceberg_df.empty:
        raise RuntimeError(
            f"No observations found in {iceberg_filename}"
        )

    logger.info(
        "Loaded %d iceberg observations.",
        len(iceberg_df),
    )

    # =============================================================
    # STEP 2 — Quality control
    # =============================================================

    logger.info(
        "Applying trajectory quality control..."
    )

    iceberg_df = apply_qc(
        iceberg_df
    )

    clean_df = iceberg_df[
        ~iceberg_df["qc_any_flag"]
    ].copy()

    logger.info(
        "Observations after QC: %d",
        len(clean_df),
    )

    if clean_df.empty:
        raise RuntimeError(
            "No observations remain after QC."
        )

    # =============================================================
    # STEP 3 — Inspect environmental datasets
    # =============================================================

    era5_filename = era5_path(case_name)
    glorys_filename = glorys_path(case_name)

    logger.info(
        "Inspecting ERA5 environment..."
    )

    era5_metadata = inspect_environment(
        era5_filename
    )

    logger.info(
        "ERA5 coverage: lat %.3f to %.3f, "
        "lon %.3f to %.3f",
        era5_metadata["latitude_min"],
        era5_metadata["latitude_max"],
        era5_metadata["longitude_min"],
        era5_metadata["longitude_max"],
    )

    logger.info(
        "Inspecting GLORYS environment..."
    )

    glorys_metadata = inspect_environment(
        glorys_filename
    )

    logger.info(
        "GLORYS coverage: lat %.3f to %.3f, "
        "lon %.3f to %.3f",
        glorys_metadata["latitude_min"],
        glorys_metadata["latitude_max"],
        glorys_metadata["longitude_min"],
        glorys_metadata["longitude_max"],
    )

    if glorys_metadata.get("depth_count", 0) < 2:
        logger.warning(
            "GLORYS file has only one depth level. "
            "This is sufficient for the current Reader "
            "integration test but is not a full depth-resolved "
            "OpenBerg forcing dataset."
        )

    # =============================================================
    # STEP 4 — Match observations to environmental coverage
    # =============================================================

    logger.info(
        "Matching iceberg observations against "
        "ERA5 + GLORYS coverage..."
    )

    matched = find_common_observations(
        clean_df,
        era5_metadata,
        glorys_metadata,
    )

    if matched.empty:
        raise RuntimeError(
            "No position observations could be matched."
        )

    compatibility_file = (
        output_dir
        / f"{case_name.lower()}_compatibility.csv"
    )

    save_dataframe(
        matched,
        compatibility_file,
    )

    environment_matched = matched[
        matched["environment_matched"]
    ].copy()

    geometry_compatible = environment_matched[
        environment_matched[
            "openberg_geometry_compatible"
        ]
    ].copy()

    logger.info(
        "Position observations: %d",
        len(matched),
    )

    logger.info(
        "Environment-matched observations: %d",
        len(environment_matched),
    )

    logger.info(
        "OpenBerg geometry-compatible observations: %d",
        len(geometry_compatible),
    )

    # =============================================================
    # STEP 5 — Incompatible branch
    # =============================================================

    if geometry_compatible.empty:

        logger.warning(
            "NO OPENBERG-COMPATIBLE REAL GEOMETRY "
            "WAS FOUND FOR CASE %s.",
            case_name,
        )

        reasons = (
            environment_matched[
                "geometry_compatibility_reason"
            ]
            .value_counts()
        )

        print()
        print("RESULT")
        print("-" * 70)
        print(
            f"Case: {case_name}"
        )
        print(
            f"Environment-matched observations: "
            f"{len(environment_matched)}"
        )
        print(
            f"OpenBerg-compatible observations: "
            f"{len(geometry_compatible)}"
        )
        print()
        print(
            "Status: OPENBERG_OUTSIDE_DOMAIN"
        )
        print()
        print("Compatibility reasons:")

        for reason, count in reasons.items():
            print(
                f"  {reason}: {count}"
            )

        print()
        print(
            "The real iceberg observations are NOT discarded."
        )
        print(
            f"Full compatibility report: "
            f"{compatibility_file}"
        )
        print()

        return

    # =============================================================
    # STEP 6 — Select first compatible observation
    # =============================================================

    anchor = geometry_compatible.sort_values(
        "timestamp"
    ).iloc[0]

    logger.info(
        "Selected anchor observation:"
    )

    logger.info(
        "  timestamp: %s",
        anchor["timestamp"],
    )

    logger.info(
        "  latitude: %.6f",
        anchor["latitude"],
    )

    logger.info(
        "  longitude: %.6f",
        anchor["longitude"],
    )

    logger.info(
        "  length: %.2f m",
        anchor["length_m"],
    )

    logger.info(
        "  width: %.2f m",
        anchor["width_m"],
    )

    # =============================================================
    # STEP 7 — Vertical geometry gate
    # =============================================================

    print()
    print("=" * 70)
    print("VERTICAL GEOMETRY CHECK")
    print("=" * 70)

    print()
    print(
        "Horizontal OpenBerg geometry is compatible."
    )

    print(
        "However, BYU/NIC does not provide the "
        "freeboard + draft pair required by this pipeline."
    )

    print()
    print(
        "Status: OPENBERG_WAITING_FOR_VERTICAL_GEOMETRY"
    )

    print()
    print(
        "The pipeline will NOT invent sail/freeboard or draft."
    )

    print(
        "A future vertical-geometry source must provide:"
    )

    print(
        "  freeboard_m"
    )

    print(
        "  estimated_draft_m"
    )

    print()
    print(
        "Only then will build_openberg_iceberg() be called."
    )

    print()

    # =============================================================
    # STEP 8 — Explicitly stop before OpenBerg
    # =============================================================

    # DO NOT do this:
    #
    # sail = 20
    # draft = 100
    #
    # Those would be artificial values for a real iceberg.
    #
    # The pipeline intentionally stops here until a real vertical
    # geometry source is connected.

    return


def main() -> None:
    configure_logging()

    parser = argparse.ArgumentParser(
        description=(
            "Antarctic iceberg data compatibility pipeline"
        )
    )

    parser.add_argument(
        "--case",
        required=True,
        choices=sorted(CASES.keys()),
        help="Iceberg/environment case to process.",
    )

    parser.add_argument(
        "--hours",
        type=float,
        default=6.0,
        help=(
            "Future OpenBerg simulation duration in hours. "
            "Currently retained for the OpenBerg stage."
        ),
    )

    args = parser.parse_args()

    run_pipeline(
        args.case,
        hours=args.hours,
    )


if __name__ == "__main__":
    main()