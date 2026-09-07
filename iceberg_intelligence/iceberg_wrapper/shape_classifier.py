from __future__ import annotations

from dataclasses import dataclass
from math import pi
from typing import Optional


# ---------------------------------------------------------------------------
# Prototype classification constants
# ---------------------------------------------------------------------------

# Literature-supported prototype discriminator for tabular-like icebergs.
#
# L/F = iceberg length / freeboard.
#
# We deliberately use this as a classification indicator rather than as a
# rejection criterion.
TABULAR_LF_THRESHOLD = 5.0


@dataclass(frozen=True)
class ShapeClassification:
    """
    Result returned by the rule-based iceberg shape classifier.

    Attributes
    ----------
    shape_class:
        One of:
            "TABULAR"
            "DOMED"
            "IRREGULAR"
            "UNKNOWN"

    confidence:
        Qualitative rule-based confidence.

        This is NOT a calibrated statistical probability.
        Possible values:
            "HIGH"
            "MEDIUM"
            "LOW"

    ratio_lf:
        Length/freeboard ratio, when freeboard is available.

    ratio_lw:
        Length/width ratio, when both dimensions are available.

    evidence:
        Human-readable explanation of why the class was selected.

    method:
        Name of the classification method.

    method_version:
        Version of this prototype method.
    """

    shape_class: str
    confidence: str
    ratio_lf: Optional[float]
    ratio_lw: Optional[float]
    evidence: str
    method: str = "rule_based_geometry"
    method_version: str = "prototype_1"


def _validate_positive(
    value: Optional[float],
    name: str,
) -> None:
    """Validate an optional positive numeric value."""
    if value is None:
        return

    if not isinstance(value, (int, float)):
        raise TypeError(f"{name} must be numeric or None.")

    if value <= 0:
        raise ValueError(f"{name} must be greater than zero.")


def _validate_geometry(
    length_m: float,
    width_m: float,
    freeboard_m: Optional[float],
) -> None:
    """Validate the basic iceberg geometry."""
    _validate_positive(length_m, "length_m")
    _validate_positive(width_m, "width_m")
    _validate_positive(freeboard_m, "freeboard_m")


def _calculate_ratio(
    numerator: Optional[float],
    denominator: Optional[float],
) -> Optional[float]:
    """Safely calculate a ratio."""
    if numerator is None or denominator is None:
        return None

    if denominator <= 0:
        return None

    return numerator / denominator


def _calculate_compactness(
    area_m2: Optional[float],
    perimeter_m: Optional[float],
) -> Optional[float]:
    """
    Calculate planform compactness:

        C = 4*pi*A / P^2

    C approaches 1 for a circle and becomes smaller for elongated/
    irregular planforms.

    This is currently used only as optional morphology evidence.
    It is NOT used with an arbitrary hard threshold in this prototype.
    """
    if area_m2 is None or perimeter_m is None:
        return None

    if area_m2 <= 0 or perimeter_m <= 0:
        return None

    return (4.0 * pi * area_m2) / (perimeter_m ** 2)


def classify_shape(
    length_m: float,
    width_m: float,
    freeboard_m: Optional[float] = None,
    area_m2: Optional[float] = None,
    perimeter_m: Optional[float] = None,
    surface_elevation_range_m: Optional[float] = None,
    surface_elevation_std_m: Optional[float] = None,
) -> ShapeClassification:
    """
    Classify an iceberg using transparent geometric rules.

    Primary discriminator
    ---------------------
    L/F = length / freeboard

    A value of L/F >= 5 is treated as strong evidence for a TABULAR
    classification.

    Important
    ---------
    L/F alone cannot reliably distinguish DOMED from IRREGULAR morphology.
    Therefore, if L/F < 5 and no sufficiently informative surface morphology
    is supplied, the classifier returns UNKNOWN rather than inventing a
    classification.

    Parameters
    ----------
    length_m:
        Iceberg major/long dimension in metres.

    width_m:
        Iceberg minor/short dimension in metres.

    freeboard_m:
        Iceberg freeboard in metres. Required for the primary L/F test.

    area_m2:
        Optional planform area in square metres.

    perimeter_m:
        Optional planform perimeter in metres.

    surface_elevation_range_m:
        Optional range of surface elevation measurements in metres.

    surface_elevation_std_m:
        Optional standard deviation of surface elevation measurements
        in metres.

    Returns
    -------
    ShapeClassification
        Classification result with ratios and explanation.

    Raises
    ------
    ValueError
        If a supplied geometric value is non-positive.
    TypeError
        If a supplied value is not numeric.
    """
    _validate_geometry(
        length_m=length_m,
        width_m=width_m,
        freeboard_m=freeboard_m,
    )

    _validate_positive(area_m2, "area_m2")
    _validate_positive(perimeter_m, "perimeter_m")
    _validate_positive(
        surface_elevation_range_m,
        "surface_elevation_range_m",
    )
    _validate_positive(
        surface_elevation_std_m,
        "surface_elevation_std_m",
    )

    ratio_lf = _calculate_ratio(length_m, freeboard_m)
    ratio_lw = _calculate_ratio(length_m, width_m)

    compactness = _calculate_compactness(
        area_m2,
        perimeter_m,
    )

    # ------------------------------------------------------------------
    # Rule 1: No freeboard -> L/F cannot be calculated.
    # ------------------------------------------------------------------
    if ratio_lf is None:
        return ShapeClassification(
            shape_class="UNKNOWN",
            confidence="LOW",
            ratio_lf=None,
            ratio_lw=ratio_lw,
            evidence=(
                "Freeboard is unavailable, so the primary length/freeboard "
                "ratio cannot be calculated. The iceberg is therefore not "
                "forced into a shape class."
            ),
        )

    # ------------------------------------------------------------------
    # Rule 2: Strong tabular evidence.
    # ------------------------------------------------------------------
    if ratio_lf >= TABULAR_LF_THRESHOLD:
        evidence = (
            f"L/F = {ratio_lf:.3f}, which is >= "
            f"{TABULAR_LF_THRESHOLD:.1f}. This provides strong "
            "prototype evidence for a tabular iceberg."
        )

        if ratio_lw is not None:
            evidence += f" L/W = {ratio_lw:.3f}."

        return ShapeClassification(
            shape_class="TABULAR",
            confidence="HIGH",
            ratio_lf=ratio_lf,
            ratio_lw=ratio_lw,
            evidence=evidence,
        )

    # ------------------------------------------------------------------
    # Rule 3: Non-tabular but insufficient morphology.
    #
    # We intentionally DO NOT say:
    #
    #     L/F < 5 -> DOMED
    #
    # because that would be an unsupported assumption.
    # ------------------------------------------------------------------
    morphology_available = (
        surface_elevation_range_m is not None
        or surface_elevation_std_m is not None
        or compactness is not None
    )

    if not morphology_available:
        return ShapeClassification(
            shape_class="UNKNOWN",
            confidence="LOW",
            ratio_lf=ratio_lf,
            ratio_lw=ratio_lw,
            evidence=(
                f"L/F = {ratio_lf:.3f}, below the tabular discriminator "
                f"of {TABULAR_LF_THRESHOLD:.1f}. However, L/F alone does "
                "not reliably distinguish domed from irregular morphology. "
                "No additional surface morphology was supplied, so the "
                "classifier returns UNKNOWN rather than forcing a class."
            ),
        )

    # ------------------------------------------------------------------
    # Optional morphology rules.
    #
    # These are deliberately conservative. We only classify when the
    # caller provides explicit surface-profile information.
    #
    # We do not invent universal numerical thresholds for DOMED or
    # IRREGULAR here. Those should be calibrated against real DEM/
    # morphology data later.
    # ------------------------------------------------------------------

    if (
        surface_elevation_range_m is not None
        and surface_elevation_std_m is not None
    ):
        # The values are available, but without a validated threshold
        # separating rounded from irregular surfaces, we should not
        # manufacture a scientific classification.
        return ShapeClassification(
            shape_class="UNKNOWN",
            confidence="LOW",
            ratio_lf=ratio_lf,
            ratio_lw=ratio_lw,
            evidence=(
                f"L/F = {ratio_lf:.3f}, below the tabular threshold. "
                "Surface-elevation information is available, but the "
                "prototype does not yet contain validated morphology "
                "thresholds for distinguishing DOMED from IRREGULAR."
            ),
        )

    # If only planform compactness is available, retain the feature for
    # future calibration but do not use an arbitrary threshold.
    if compactness is not None:
        return ShapeClassification(
            shape_class="UNKNOWN",
            confidence="LOW",
            ratio_lf=ratio_lf,
            ratio_lw=ratio_lw,
            evidence=(
                f"L/F = {ratio_lf:.3f}, below the tabular threshold. "
                f"Planform compactness = {compactness:.3f} is available, "
                "but no validated compactness threshold is currently "
                "used to distinguish DOMED from IRREGULAR."
            ),
        )

    return ShapeClassification(
        shape_class="UNKNOWN",
        confidence="LOW",
        ratio_lf=ratio_lf,
        ratio_lw=ratio_lw,
        evidence="Insufficient morphology information.",
    )


def classify_iceberg(iceberg: dict) -> ShapeClassification:
    """
    Convenience wrapper for a project-level iceberg dictionary.

    Expected keys
    -------------
    length_m
    width_m
    freeboard_m

    Optional keys
    -------------
    area_m2
    perimeter_m
    surface_elevation_range_m
    surface_elevation_std_m
    """
    required = (
        "length_m",
        "width_m",
    )

    missing = [key for key in required if key not in iceberg]

    if missing:
        raise ValueError(
            f"Missing required iceberg fields: {', '.join(missing)}"
        )

    return classify_shape(
        length_m=iceberg["length_m"],
        width_m=iceberg["width_m"],
        freeboard_m=iceberg.get("freeboard_m"),
        area_m2=iceberg.get("area_m2"),
        perimeter_m=iceberg.get("perimeter_m"),
        surface_elevation_range_m=iceberg.get(
            "surface_elevation_range_m"
        ),
        surface_elevation_std_m=iceberg.get(
            "surface_elevation_std_m"
        ),
    )