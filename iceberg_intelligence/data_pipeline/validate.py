from __future__ import annotations

import math

import pandas as pd


def haversine_km(
    lat1: float,
    lon1: float,
    lat2: float,
    lon2: float,
) -> float:
    radius_km = 6371.0

    lat1 = math.radians(lat1)
    lat2 = math.radians(lat2)

    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)

    a = (
        math.sin(dlat / 2) ** 2
        + math.cos(lat1)
        * math.cos(lat2)
        * math.sin(dlon / 2) ** 2
    )

    return 2 * radius_km * math.asin(math.sqrt(a))


def compare_position(
    predicted_latitude: float,
    predicted_longitude: float,
    observed_latitude: float,
    observed_longitude: float,
) -> dict:
    """Calculate positional error."""

    error_km = haversine_km(
        predicted_latitude,
        predicted_longitude,
        observed_latitude,
        observed_longitude,
    )

    return {
        "predicted_latitude": predicted_latitude,
        "predicted_longitude": predicted_longitude,
        "observed_latitude": observed_latitude,
        "observed_longitude": observed_longitude,
        "position_error_km": error_km,
    }


def calculate_summary(errors: pd.DataFrame) -> dict:
    """Calculate basic trajectory error statistics."""

    if errors.empty:
        raise ValueError(
            "Cannot calculate validation summary from empty data."
        )

    values = errors["position_error_km"]

    return {
        "records": int(len(values)),
        "mean_error_km": float(values.mean()),
        "median_error_km": float(values.median()),
        "rmse_km": float(
            (values.pow(2).mean()) ** 0.5
        ),
        "maximum_error_km": float(values.max()),
    }