from __future__ import annotations

import math

import pandas as pd


MAX_REASONABLE_SPEED_MPS = 5.0
MAX_TIME_GAP_DAYS = 3.0


def haversine_km(
    lat1: float,
    lon1: float,
    lat2: float,
    lon2: float,
) -> float:
    """Calculate great-circle distance in kilometres."""

    radius_km = 6371.0

    lat1_rad = math.radians(lat1)
    lat2_rad = math.radians(lat2)

    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)

    a = (
        math.sin(dlat / 2) ** 2
        + math.cos(lat1_rad)
        * math.cos(lat2_rad)
        * math.sin(dlon / 2) ** 2
    )

    return 2 * radius_km * math.asin(math.sqrt(a))


def apply_qc(df: pd.DataFrame) -> pd.DataFrame:
    """
    Add QC flags without silently deleting observations.
    """

    result = df.copy()

    result["qc_invalid_coordinate"] = (
        ~result["position_available"]
    )

    result["qc_non_antarctic"] = (
        result["position_available"]
        & (result["latitude"] >= 0)
    )

    result["time_gap_days"] = (
        result["timestamp"]
        .diff()
        .dt.total_seconds()
        / 86400.0
    )

    result["qc_large_time_gap"] = (
        result["time_gap_days"] > MAX_TIME_GAP_DAYS
    )

    previous_lat = result["latitude"].shift()
    previous_lon = result["longitude"].shift()

    distances_km = []

    for lat1, lon1, lat2, lon2 in zip(
        previous_lat,
        previous_lon,
        result["latitude"],
        result["longitude"],
    ):
        if any(pd.isna(v) for v in (lat1, lon1, lat2, lon2)):
            distances_km.append(float("nan"))
            continue

        distances_km.append(
            haversine_km(
                float(lat1),
                float(lon1),
                float(lat2),
                float(lon2),
            )
        )

    result["step_distance_km"] = distances_km

    result["implied_speed_mps"] = (
        result["step_distance_km"] * 1000.0
        / (result["time_gap_days"] * 86400.0)
    )

    result["qc_unreasonable_speed"] = (
        result["implied_speed_mps"] > MAX_REASONABLE_SPEED_MPS
    )

    result["qc_duplicate_timestamp"] = (
        result["timestamp"].duplicated(keep=False)
    )

    result["qc_any_flag"] = (
        result["qc_invalid_coordinate"]
        | result["qc_non_antarctic"]
        | result["qc_large_time_gap"]
        | result["qc_unreasonable_speed"]
        | result["qc_duplicate_timestamp"]
    )

    return result


def usable_observations(df: pd.DataFrame) -> pd.DataFrame:
    """
    Return observations suitable for trajectory processing.

    Raw rows remain available in the original dataframe.
    """

    mask = (
        df["position_available"]
        & ~df["qc_non_antarctic"]
        & ~df["qc_unreasonable_speed"]
        & ~df["qc_duplicate_timestamp"]
    )

    return df.loc[mask].copy()