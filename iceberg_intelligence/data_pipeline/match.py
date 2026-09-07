from __future__ import annotations

import pandas as pd

from .compatibility import check_geometry_compatibility


def _inside(value: float, minimum: float, maximum: float) -> bool:
    """
    Check whether a numeric value lies within an inclusive range.
    """
    return minimum <= float(value) <= maximum


def _time_inside(
    timestamp: pd.Timestamp,
    start_time,
    end_time,
) -> bool:
    """
    Check whether timestamp lies within an environmental dataset's
    temporal coverage.
    """

    timestamp = pd.Timestamp(timestamp)

    if start_time is None or end_time is None:
        return False

    start = pd.Timestamp(start_time)
    end = pd.Timestamp(end_time)

    return start <= timestamp <= end


def find_common_observations(
    iceberg_df: pd.DataFrame,
    era5_metadata: dict,
    glorys_metadata: dict,
) -> pd.DataFrame:
    """
    Match iceberg observations against ERA5 and GLORYS coverage.

    This function does not modify iceberg observations.

    It records independently:

        - ERA5 spatial/temporal coverage
        - GLORYS spatial/temporal coverage
        - combined environmental coverage
        - OpenBerg horizontal geometry compatibility

    An observation can therefore remain in the dataset even if
    OpenBerg cannot currently use it.
    """

    matches = []

    for index, row in iceberg_df.iterrows():

        if not bool(row["position_available"]):
            continue

        latitude = float(row["latitude"])
        longitude = float(row["longitude"])
        timestamp = pd.Timestamp(row["timestamp"])

        # ---------------------------------------------------------
        # ERA5 coverage
        # ---------------------------------------------------------

        era5_covered = (
            _inside(
                latitude,
                era5_metadata["latitude_min"],
                era5_metadata["latitude_max"],
            )
            and
            _inside(
                longitude,
                era5_metadata["longitude_min"],
                era5_metadata["longitude_max"],
            )
            and
            _time_inside(
                timestamp,
                era5_metadata["time_start"],
                era5_metadata["time_end"],
            )
        )

        # ---------------------------------------------------------
        # GLORYS coverage
        # ---------------------------------------------------------

        glorys_covered = (
            _inside(
                latitude,
                glorys_metadata["latitude_min"],
                glorys_metadata["latitude_max"],
            )
            and
            _inside(
                longitude,
                glorys_metadata["longitude_min"],
                glorys_metadata["longitude_max"],
            )
            and
            _time_inside(
                timestamp,
                glorys_metadata["time_start"],
                glorys_metadata["time_end"],
            )
        )

        environment_matched = (
            era5_covered
            and glorys_covered
        )

        # ---------------------------------------------------------
        # OpenBerg horizontal geometry
        # ---------------------------------------------------------

        length_m = row.get("length_m")
        width_m = row.get("width_m")

        geometry_result = check_geometry_compatibility(
            length_m,
            width_m,
        )

        matches.append(
            {
                "source_index": index,
                "timestamp": timestamp,
                "latitude": latitude,
                "longitude": longitude,
                "sensor_source": row.get("sensor_source"),

                "length_m": length_m,
                "width_m": width_m,

                "era5_covered": era5_covered,
                "glorys_covered": glorys_covered,
                "environment_matched": environment_matched,

                "openberg_geometry_compatible": (
                    geometry_result.compatible
                ),

                "geometry_compatibility_reason": (
                    geometry_result.reason
                ),
            }
        )

    return pd.DataFrame(matches)


def select_anchor_observation(
    matched_df: pd.DataFrame,
) -> pd.Series:
    """
    Select the first observation that is:

        1. covered by ERA5
        2. covered by GLORYS
        3. horizontally compatible with OpenBerg

    Vertical geometry is intentionally NOT checked here because
    that information comes from a separate source.
    """

    if matched_df.empty:
        raise RuntimeError(
            "No usable iceberg observations were found."
        )

    usable = matched_df[
        matched_df["environment_matched"]
        &
        matched_df["openberg_geometry_compatible"]
    ]

    if usable.empty:
        raise RuntimeError(
            "No observation is simultaneously covered by "
            "ERA5 + GLORYS and compatible with OpenBerg geometry."
        )

    # Sort chronologically before selecting the anchor.
    usable = usable.sort_values("timestamp")

    return usable.iloc[0]