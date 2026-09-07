from __future__ import annotations

from typing import Any, Mapping, Optional

from .compatibility import check_vertical_geometry


PROJECT_FIELDS = [
    "iceberg_id",
    "current_latitude",
    "current_longitude",
    "timestamp",
    "length_m",
    "width_m",
    "freeboard_m",
    "shape_class",
    "estimated_draft_m",
    "draft_uncertainty_m",
    "drift_speed_knots",
    "drift_direction_degrees",
    "predicted_latitude",
    "predicted_longitude",
    "forecast_time",
    "bias_corrected_latitude",
    "bias_corrected_longitude",
    "bias_correction_applied",
    "status",
    "confidence",
]


def build_project_iceberg(
    iceberg_id: str,
    observation: Mapping[str, Any],
    *,
    freeboard_m: Optional[float] = None,
    estimated_draft_m: Optional[float] = None,
    draft_uncertainty_m: Optional[float] = None,
) -> dict[str, Any]:
    """
    Build the application's complete iceberg record.

    The function preserves the project-level schema.

    IMPORTANT:
    This function does NOT invent freeboard or draft values.

    If they are not supplied by a real vertical-geometry source,
    the resulting project record contains None for those fields.
    """

    length_m = float(observation["length_m"])
    width_m = float(observation["width_m"])

    if length_m <= 0:
        raise ValueError(
            f"{iceberg_id}: length_m must be positive."
        )

    if width_m <= 0:
        raise ValueError(
            f"{iceberg_id}: width_m must be positive."
        )

    return {
        "iceberg_id": iceberg_id,

        "current_latitude": float(
            observation["latitude"]
        ),

        "current_longitude": float(
            observation["longitude"]
        ),

        "timestamp": observation["timestamp"],

        "length_m": length_m,
        "width_m": width_m,

        "freeboard_m": (
            None
            if freeboard_m is None
            else float(freeboard_m)
        ),

        "shape_class": None,

        "estimated_draft_m": (
            None
            if estimated_draft_m is None
            else float(estimated_draft_m)
        ),

        "draft_uncertainty_m": (
            None
            if draft_uncertainty_m is None
            else float(draft_uncertainty_m)
        ),

        # These are observational values.
        # They are NOT passed into OpenBerg as initial velocity.
        "drift_speed_knots": None,
        "drift_direction_degrees": None,

        # Model output fields.
        "predicted_latitude": None,
        "predicted_longitude": None,
        "forecast_time": None,

        # Later ML/bias-correction fields.
        "bias_corrected_latitude": None,
        "bias_corrected_longitude": None,
        "bias_correction_applied": False,

        "status": "prepared",

        "confidence": None,
    }


def build_openberg_iceberg(
    iceberg_id: str,
    observation: Mapping[str, Any],
    *,
    freeboard_m: Optional[float] = None,
    estimated_draft_m: Optional[float] = None,
) -> dict[str, Any]:
    """
    Convert a project iceberg record into the exact OpenBerg
    seed properties required by the wrapper.

    No application metadata is passed to OpenBerg.

    Required OpenBerg properties:

        lon
        lat
        length
        width
        sail
        draft

    A real freeboard and draft must be supplied.
    """

    if freeboard_m is None or estimated_draft_m is None:
        raise ValueError(
            f"{iceberg_id}: real freeboard_m and estimated_draft_m "
            "are required before running OpenBerg. "
            "The pipeline will not use synthetic placeholder "
            "vertical geometry for real iceberg observations."
        )

    vertical_result = check_vertical_geometry(
        freeboard_m,
        estimated_draft_m,
    )

    if not vertical_result.compatible:
        raise ValueError(
            f"{iceberg_id}: invalid vertical geometry: "
            f"{vertical_result.reason}"
        )

    return {
        "id": iceberg_id,

        "lon": float(
            observation["longitude"]
        ),

        "lat": float(
            observation["latitude"]
        ),

        "length": float(
            observation["length_m"]
        ),

        "width": float(
            observation["width_m"]
        ),

        # Isolated mapping:
        # project freeboard -> OpenBerg sail.
        #
        # This is a mapping of an actual supplied vertical
        # measurement, NOT an invented value.
        "sail": float(freeboard_m),

        "draft": float(estimated_draft_m),
    }


def validate_project_record(record: Mapping[str, Any]) -> None:
    """
    Basic validation for the project iceberg schema.
    """

    missing = [
        field
        for field in PROJECT_FIELDS
        if field not in record
    ]

    if missing:
        raise ValueError(
            "Project iceberg record is missing fields: "
            + ", ".join(missing)
        )