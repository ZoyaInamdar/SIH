from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Optional


@dataclass(frozen=True)
class DraftEstimate:
    """
    Result of an iceberg draft estimation.

    Attributes
    ----------
    estimated_draft_m:
        Estimated submerged draft in metres.

    uncertainty_m:
        Uncertainty in metres.

        This prototype deliberately returns None because we have not yet
        calibrated an uncertainty model against real observations.

    shape_class:
        Shape used by the estimator.

    method:
        Estimation method.

    method_version:
        Reference/version associated with the method.

    status:
        SUCCESS, UNSUPPORTED_SHAPE, or other status.

    total_height_m:
        Estimated total iceberg height H = F + D.
    """

    estimated_draft_m: Optional[float]
    uncertainty_m: Optional[float]
    shape_class: str
    method: str
    method_version: str
    status: str
    total_height_m: Optional[float] = None


# ---------------------------------------------------------------------------
# El-Tahan relationships
# ---------------------------------------------------------------------------

TABULAR_COEFFICIENT = 198.0
TABULAR_EXPONENT = -0.235

DOMED_COEFFICIENT = 111.04
DOMED_EXPONENT = -0.111


def _validate_freeboard(freeboard_m: float) -> None:
    """Validate freeboard."""
    if not isinstance(freeboard_m, (int, float)):
        raise TypeError("freeboard_m must be numeric.")

    if freeboard_m <= 0:
        raise ValueError("freeboard_m must be greater than zero.")


def _tabular_draft_from_height(total_height_m: float) -> float:
    """
    El-Tahan tabular relationship:

        D = 198 * H^(-0.235)
    """
    return (
        TABULAR_COEFFICIENT
        * total_height_m ** TABULAR_EXPONENT
    )


def _domed_draft_from_height(total_height_m: float) -> float:
    """
    El-Tahan domed relationship:

        D = 111.04 * H^(-0.111)
    """
    return (
        DOMED_COEFFICIENT
        * total_height_m ** DOMED_EXPONENT
    )


def _solve_draft(
    freeboard_m: float,
    draft_function: Callable[[float], float],
    tolerance_m: float = 1e-8,
    max_iterations: int = 200,
) -> float:
    """
    Solve:

        D = f(F + D)

    using bisection.

    The solver finds a root of:

        g(D) = D - f(F + D)

    Parameters
    ----------
    freeboard_m:
        Freeboard F in metres.

    draft_function:
        Function returning D from total height H.

    tolerance_m:
        Absolute convergence tolerance in metres.

    max_iterations:
        Maximum bisection iterations.
    """
    _validate_freeboard(freeboard_m)

    if tolerance_m <= 0:
        raise ValueError("tolerance_m must be greater than zero.")

    if max_iterations <= 0:
        raise ValueError("max_iterations must be greater than zero.")

    def equation(draft_m: float) -> float:
        total_height_m = freeboard_m + draft_m
        return draft_m - draft_function(total_height_m)

    # Lower bound:
    # D must be > 0.
    lower = 0.0

    # A conservative upper bound for the root.
    #
    # We expand it if necessary rather than silently accepting a
    # non-bracketed solution.
    upper = max(100.0, freeboard_m * 10.0)

    lower_value = equation(lower)
    upper_value = equation(upper)

    expansion_count = 0

    while lower_value * upper_value > 0:
        upper *= 2.0
        upper_value = equation(upper)

        expansion_count += 1

        if expansion_count > 50:
            raise RuntimeError(
                "Could not bracket the El-Tahan draft solution."
            )

    for _ in range(max_iterations):
        midpoint = (lower + upper) / 2.0
        midpoint_value = equation(midpoint)

        if abs(midpoint_value) <= tolerance_m:
            return midpoint

        if lower_value * midpoint_value <= 0:
            upper = midpoint
            upper_value = midpoint_value
        else:
            lower = midpoint
            lower_value = midpoint_value

        if abs(upper - lower) <= tolerance_m:
            return (lower + upper) / 2.0

    raise RuntimeError(
        "El-Tahan draft solver did not converge within "
        f"{max_iterations} iterations."
    )


def estimate_tabular_draft(
    freeboard_m: float,
    tolerance_m: float = 1e-8,
) -> DraftEstimate:
    """
    Estimate draft for a TABULAR iceberg using the El-Tahan relationship.

    The equation solved is:

        D = 198 * (F + D)^(-0.235)

    Parameters
    ----------
    freeboard_m:
        Freeboard F in metres.

    tolerance_m:
        Numerical solver tolerance.

    Returns
    -------
    DraftEstimate
    """
    _validate_freeboard(freeboard_m)

    draft_m = _solve_draft(
        freeboard_m=freeboard_m,
        draft_function=_tabular_draft_from_height,
        tolerance_m=tolerance_m,
    )

    total_height_m = freeboard_m + draft_m

    return DraftEstimate(
        estimated_draft_m=draft_m,
        uncertainty_m=None,
        shape_class="TABULAR",
        method="El-Tahan",
        method_version="1982",
        status="SUCCESS",
        total_height_m=total_height_m,
    )


def estimate_domed_draft(
    freeboard_m: float,
    tolerance_m: float = 1e-8,
) -> DraftEstimate:
    """
    Estimate draft for a DOMED iceberg using the El-Tahan relationship.

    The equation solved is:

        D = 111.04 * (F + D)^(-0.111)

    Parameters
    ----------
    freeboard_m:
        Freeboard F in metres.

    tolerance_m:
        Numerical solver tolerance.

    Returns
    -------
    DraftEstimate
    """
    _validate_freeboard(freeboard_m)

    draft_m = _solve_draft(
        freeboard_m=freeboard_m,
        draft_function=_domed_draft_from_height,
        tolerance_m=tolerance_m,
    )

    total_height_m = freeboard_m + draft_m

    return DraftEstimate(
        estimated_draft_m=draft_m,
        uncertainty_m=None,
        shape_class="DOMED",
        method="El-Tahan",
        method_version="1982",
        status="SUCCESS",
        total_height_m=total_height_m,
    )


def estimate_draft(
    freeboard_m: float,
    shape_class: str,
    tolerance_m: float = 1e-8,
) -> DraftEstimate:
    """
    General draft-estimation entry point.

    Parameters
    ----------
    freeboard_m:
        Freeboard in metres.

    shape_class:
        Expected values:

            TABULAR
            DOMED
            IRREGULAR
            UNKNOWN

    Returns
    -------
    DraftEstimate

    Notes
    -----
    No invented El-Tahan relationship is used for IRREGULAR.
    UNKNOWN and IRREGULAR therefore return an explicit unsupported result.
    """
    _validate_freeboard(freeboard_m)

    normalized_shape = str(shape_class).strip().upper()

    if normalized_shape == "TABULAR":
        return estimate_tabular_draft(
            freeboard_m=freeboard_m,
            tolerance_m=tolerance_m,
        )

    if normalized_shape in {"DOMED", "REGULAR"}:
        return estimate_domed_draft(
            freeboard_m=freeboard_m,
            tolerance_m=tolerance_m,
        )

    if normalized_shape in {"IRREGULAR", "PINNACLED"}:
        return DraftEstimate(
            estimated_draft_m=None,
            uncertainty_m=None,
            shape_class="IRREGULAR",
            method="El-Tahan",
            method_version="1982",
            status="UNSUPPORTED_SHAPE",
            total_height_m=None,
        )

    if normalized_shape == "UNKNOWN":
        return DraftEstimate(
            estimated_draft_m=None,
            uncertainty_m=None,
            shape_class="UNKNOWN",
            method="El-Tahan",
            method_version="1982",
            status="INSUFFICIENT_DATA",
            total_height_m=None,
        )

    raise ValueError(
        "Unsupported shape_class. Expected one of: "
        "TABULAR, DOMED, IRREGULAR, UNKNOWN."
    )


def verify_tabular_solution(
    freeboard_m: float,
    draft_m: float,
    tolerance_m: float = 1e-6,
) -> bool:
    """
    Verify that a tabular draft satisfies the original equation.
    """
    _validate_freeboard(freeboard_m)

    if draft_m <= 0:
        raise ValueError("draft_m must be greater than zero.")

    expected = _tabular_draft_from_height(
        freeboard_m + draft_m
    )

    return abs(draft_m - expected) <= tolerance_m


def verify_domed_solution(
    freeboard_m: float,
    draft_m: float,
    tolerance_m: float = 1e-6,
) -> bool:
    """
    Verify that a domed draft satisfies the original equation.
    """
    _validate_freeboard(freeboard_m)

    if draft_m <= 0:
        raise ValueError("draft_m must be greater than zero.")

    expected = _domed_draft_from_height(
        freeboard_m + draft_m
    )

    return abs(draft_m - expected) <= tolerance_m