from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Optional


# These limits come from OpenBerg's IcebergObj definition.
OPENBERG_MIN_LENGTH_M = 1.0
OPENBERG_MAX_LENGTH_M = 10_000.0

OPENBERG_MIN_WIDTH_M = 1.0
OPENBERG_MAX_WIDTH_M = 10_000.0

OPENBERG_MIN_SAIL_M = 1.0
OPENBERG_MAX_SAIL_M = 100.0

OPENBERG_MIN_DRAFT_M = 1.0
OPENBERG_MAX_DRAFT_M = 1_000.0


@dataclass(frozen=True)
class CompatibilityResult:
    """
    Result of checking whether an iceberg geometry is compatible
    with OpenBerg's declared element-property limits.
    """

    compatible: bool
    reason: str


def check_geometry_compatibility(
    length_m: float,
    width_m: float,
) -> CompatibilityResult:
    """
    Check whether horizontal iceberg dimensions are valid for OpenBerg.

    IMPORTANT:
    This function does NOT resize, clip, or modify the input values.

    Parameters
    ----------
    length_m:
        Iceberg major dimension in metres.

    width_m:
        Iceberg minor dimension in metres.

    Returns
    -------
    CompatibilityResult
    """

    try:
        length = float(length_m)
        width = float(width_m)
    except (TypeError, ValueError):
        return CompatibilityResult(
            False,
            "non_numeric_geometry",
        )

    if not math.isfinite(length) or not math.isfinite(width):
        return CompatibilityResult(
            False,
            "non_finite_geometry",
        )

    if length < OPENBERG_MIN_LENGTH_M:
        return CompatibilityResult(
            False,
            "length_below_openberg_minimum",
        )

    if width < OPENBERG_MIN_WIDTH_M:
        return CompatibilityResult(
            False,
            "width_below_openberg_minimum",
        )

    if length > OPENBERG_MAX_LENGTH_M:
        return CompatibilityResult(
            False,
            "length_exceeds_openberg_maximum",
        )

    if width > OPENBERG_MAX_WIDTH_M:
        return CompatibilityResult(
            False,
            "width_exceeds_openberg_maximum",
        )

    return CompatibilityResult(
        True,
        "compatible",
    )


def check_vertical_geometry(
    sail_m: Optional[float],
    draft_m: Optional[float],
) -> CompatibilityResult:
    """
    Check whether freeboard/sail and draft values are suitable
    for OpenBerg.

    No values are estimated or modified here.

    This is deliberately separate from horizontal geometry because
    BYU/NIC track observations do not provide reliable vertical
    iceberg geometry by themselves.
    """

    if sail_m is None or draft_m is None:
        return CompatibilityResult(
            False,
            "vertical_geometry_missing",
        )

    try:
        sail = float(sail_m)
        draft = float(draft_m)
    except (TypeError, ValueError):
        return CompatibilityResult(
            False,
            "non_numeric_vertical_geometry",
        )

    if not math.isfinite(sail) or not math.isfinite(draft):
        return CompatibilityResult(
            False,
            "non_finite_vertical_geometry",
        )

    if sail < OPENBERG_MIN_SAIL_M:
        return CompatibilityResult(
            False,
            "sail_below_openberg_minimum",
        )

    if sail > OPENBERG_MAX_SAIL_M:
        return CompatibilityResult(
            False,
            "sail_exceeds_openberg_maximum",
        )

    if draft < OPENBERG_MIN_DRAFT_M:
        return CompatibilityResult(
            False,
            "draft_below_openberg_minimum",
        )

    if draft > OPENBERG_MAX_DRAFT_M:
        return CompatibilityResult(
            False,
            "draft_exceeds_openberg_maximum",
        )

    if draft <= sail:
        return CompatibilityResult(
            False,
            "draft_must_exceed_sail",
        )

    return CompatibilityResult(
        True,
        "compatible",
    )


def is_openberg_ready(
    length_m: float,
    width_m: float,
    sail_m: Optional[float],
    draft_m: Optional[float],
) -> CompatibilityResult:
    """
    Perform the complete OpenBerg input compatibility check.

    An iceberg is OpenBerg-ready only if both:

        1. horizontal geometry is compatible
        2. vertical geometry is available and compatible
    """

    geometry = check_geometry_compatibility(
        length_m,
        width_m,
    )

    if not geometry.compatible:
        return geometry

    vertical = check_vertical_geometry(
        sail_m,
        draft_m,
    )

    if not vertical.compatible:
        return vertical

    return CompatibilityResult(
        True,
        "openberg_ready",
    )