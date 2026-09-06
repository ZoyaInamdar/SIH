from dataclasses import dataclass
from typing import List, Optional, Tuple

import numpy as np


# ============================================================
# OBSERVATION
# ============================================================

@dataclass
class IceRasterObservation:
    """
    One historical sea-ice concentration raster.

    concentration:
        2D NumPy array.

        Values:
            0.0 = 0% ice
            1.0 = 100% ice

    timestamp_hours:
        Time of observation relative to the beginning of
        the rolling window, expressed in hours.
    """

    timestamp_hours: float
    concentration: np.ndarray


# ============================================================
# MODEL RESULT
# ============================================================

@dataclass
class PersistenceForecast:
    """
    Result of the per-cell linear-trend persistence model.
    """

    predicted_concentration: np.ndarray

    slope_per_hour: np.ndarray

    intercept: np.ndarray

    confidence: np.ndarray

    valid_observations: np.ndarray

    forecast_time_hours: float


# ============================================================
# VALIDATION
# ============================================================

def validate_observations(
    observations: List[IceRasterObservation],
) -> Tuple[int, int]:

    if len(observations) < 2:
        raise ValueError(
            "At least two observations are required "
            "for linear trend estimation."
        )

    shapes = [
        observation.concentration.shape
        for observation in observations
    ]

    if len(set(shapes)) != 1:
        raise ValueError(
            "All ice rasters must have the same shape."
        )

    rows, cols = shapes[0]

    if rows == 0 or cols == 0:
        raise ValueError(
            "Ice rasters cannot be empty."
        )

    timestamps = [
        observation.timestamp_hours
        for observation in observations
    ]

    if len(set(timestamps)) != len(timestamps):
        raise ValueError(
            "Observation timestamps must be unique."
        )

    if timestamps != sorted(timestamps):
        raise ValueError(
            "Observations must be ordered from oldest "
            "to newest."
        )

    return rows, cols


# ============================================================
# CONCENTRATION CLEANING
# ============================================================

def clean_raster(
    raster: np.ndarray,
) -> np.ndarray:
    """
    Convert raster to floating-point concentration values
    and clamp them to [0, 1].
    """

    raster = np.asarray(
        raster,
        dtype=float,
    )

    raster = np.nan_to_num(
        raster,
        nan=np.nan,
        posinf=np.nan,
        neginf=np.nan,
    )

    return np.clip(
        raster,
        0.0,
        1.0,
    )


# ============================================================
# LINEAR REGRESSION
# ============================================================

def linear_regression_per_cell(
    observations: List[IceRasterObservation],
) -> Tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    """
    Calculate linear regression independently for every
    grid cell.

    Model:

        ice_concentration = slope * time + intercept

    Returns:

        slope
        intercept
        r_squared
        valid_observations
    """

    rows, cols = validate_observations(
        observations
    )

    times = np.array(
        [
            observation.timestamp_hours
            for observation in observations
        ],
        dtype=float,
    )

    # Shape:
    #
    # observations × rows × cols
    #
    values = np.stack(
        [
            clean_raster(
                observation.concentration
            )
            for observation in observations
        ],
        axis=0,
    )

    slope = np.full(
        (rows, cols),
        np.nan,
        dtype=float,
    )

    intercept = np.full(
        (rows, cols),
        np.nan,
        dtype=float,
    )

    r_squared = np.full(
        (rows, cols),
        np.nan,
        dtype=float,
    )

    valid_count = np.zeros(
        (rows, cols),
        dtype=int,
    )

    # --------------------------------------------------------
    # Calculate each cell independently.
    # --------------------------------------------------------

    for row in range(rows):

        for col in range(cols):

            cell_values = values[
                :,
                row,
                col,
            ]

            valid_mask = np.isfinite(
                cell_values
            )

            valid_times = times[
                valid_mask
            ]

            valid_values = cell_values[
                valid_mask
            ]

            valid_count[
                row,
                col
            ] = len(valid_values)

            # Need at least two valid observations.
            if len(valid_values) < 2:
                continue

            # Center time for numerical stability.
            time_mean = np.mean(
                valid_times
            )

            value_mean = np.mean(
                valid_values
            )

            centered_time = (
                valid_times
                - time_mean
            )

            centered_values = (
                valid_values
                - value_mean
            )

            denominator = np.sum(
                centered_time ** 2
            )

            if denominator == 0:
                continue

            cell_slope = (
                np.sum(
                    centered_time
                    * centered_values
                )
                / denominator
            )

            cell_intercept = (
                value_mean
                - cell_slope * time_mean
            )

            predicted = (
                cell_slope
                * valid_times
                + cell_intercept
            )

            residuals = (
                valid_values
                - predicted
            )

            ss_res = np.sum(
                residuals ** 2
            )

            ss_tot = np.sum(
                centered_values ** 2
            )

            if ss_tot > 0:
                cell_r_squared = (
                    1.0
                    - ss_res / ss_tot
                )

            else:
                # Constant concentration:
                # trend is zero and fit is perfect.
                cell_r_squared = 1.0

            slope[
                row,
                col
            ] = cell_slope

            intercept[
                row,
                col
            ] = cell_intercept

            r_squared[
                row,
                col
            ] = max(
                0.0,
                min(
                    1.0,
                    cell_r_squared,
                ),
            )

    return (
        slope,
        intercept,
        r_squared,
        valid_count,
    )


# ============================================================
# FORECAST
# ============================================================

def forecast_ice_raster(
    observations: List[IceRasterObservation],
    forecast_horizon_hours: float,
) -> PersistenceForecast:
    """
    Produce a future sea-ice raster using per-cell
    linear trend extrapolation.
    """

    if forecast_horizon_hours < 0:
        raise ValueError(
            "Forecast horizon cannot be negative."
        )

    (
        slope,
        intercept,
        r_squared,
        valid_count,
    ) = linear_regression_per_cell(
        observations
    )

    latest_time = (
        observations[-1].timestamp_hours
    )

    forecast_time = (
        latest_time
        + forecast_horizon_hours
    )

    predicted = (
        slope
        * forecast_time
        + intercept
    )

    # --------------------------------------------------------
    # Persistence fallback
    #
    # If a cell does not have enough valid history,
    # retain the latest observed value.
    # --------------------------------------------------------

    latest_raster = clean_raster(
        observations[-1].concentration
    )

    invalid_mask = (
        ~np.isfinite(predicted)
        | (valid_count < 2)
    )

    predicted[
        invalid_mask
    ] = latest_raster[
        invalid_mask
    ]

    # --------------------------------------------------------
    # Physical bounds
    # --------------------------------------------------------

    predicted = np.clip(
        predicted,
        0.0,
        1.0,
    )

    # --------------------------------------------------------
    # Confidence
    #
    # Confidence combines:
    #
    #   1. number of historical observations
    #   2. regression fit quality
    #   3. forecast horizon
    #
    # This is a confidence score, NOT a probability.
    # --------------------------------------------------------

    confidence = calculate_forecast_confidence(
        valid_observations=valid_count,
        r_squared=r_squared,
        forecast_horizon_hours=forecast_horizon_hours,
    )

    return PersistenceForecast(
        predicted_concentration=predicted,

        slope_per_hour=slope,

        intercept=intercept,

        confidence=confidence,

        valid_observations=valid_count,

        forecast_time_hours=forecast_time,
    )


# ============================================================
# CONFIDENCE
# ============================================================

def calculate_forecast_confidence(
    valid_observations: np.ndarray,
    r_squared: np.ndarray,
    forecast_horizon_hours: float,
) -> np.ndarray:
    """
    Calculate per-cell model confidence.

    Confidence is deliberately conservative.

    More observations + better linear fit
    = higher confidence.

    Longer forecast horizon
    = lower confidence.
    """

    observation_factor = np.clip(
        valid_observations / 5.0,
        0.0,
        1.0,
    )

    fit_factor = np.nan_to_num(
        r_squared,
        nan=0.0,
    )

    # Horizon penalty.
    horizon_factor = np.exp(
        -forecast_horizon_hours / 72.0
    )

    confidence = (
        observation_factor
        * fit_factor
        * horizon_factor
    )

    return np.clip(
        confidence,
        0.0,
        1.0,
    )


# ============================================================
# ROLLING WINDOW
# ============================================================

def select_rolling_window(
    observations: List[IceRasterObservation],
    window_size: int = 6,
) -> List[IceRasterObservation]:
    """
    Select the most recent observations for the
    persistence model.

    Example:

        window_size = 6

        history:
            t1 t2 t3 t4 t5 t6 t7 t8

        selected:
                    t3 t4 t5 t6 t7 t8
    """

    if window_size < 2:
        raise ValueError(
            "window_size must be at least 2."
        )

    if not observations:
        raise ValueError(
            "No observations provided."
        )

    return observations[
        -window_size:
    ]


# ============================================================
# HIGH-LEVEL MODEL FUNCTION
# ============================================================

def run_persistence_baseline(
    observations: List[IceRasterObservation],
    forecast_horizon_hours: float,
    window_size: int = 6,
) -> PersistenceForecast:
    """
    Run the complete persistence baseline.

    Steps:

        1. Select rolling history.
        2. Fit per-cell linear trends.
        3. Extrapolate forward.
        4. Clamp concentration to [0, 1].
        5. Calculate confidence.
    """

    window = select_rolling_window(
        observations=observations,
        window_size=window_size,
    )

    return forecast_ice_raster(
        observations=window,
        forecast_horizon_hours=forecast_horizon_hours,
    )