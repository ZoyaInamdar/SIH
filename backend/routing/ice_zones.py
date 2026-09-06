from dataclasses import dataclass
from typing import Optional, List, Dict


# ============================================================
# ICE ZONE
# ============================================================

@dataclass
class IceZone:
    """
    Navigation zone derived from sea-ice conditions.

    This is a decision-support classification.
    It is NOT an official maritime authorization.
    """

    zone: str
    concentration_min: float
    concentration_max: float
    description: str
    routing_action: str


# ============================================================
# GOLovNIN-ORIENTED ICE ZONES
# ============================================================

SAFE_ZONE = IceZone(
    zone="safe",
    concentration_min=0.0,
    concentration_max=0.15,
    description="Low sea-ice concentration.",
    routing_action="preferred",
)


CAUTION_ZONE = IceZone(
    zone="caution",
    concentration_min=0.15,
    concentration_max=0.30,
    description="Light sea-ice conditions. Increased monitoring required.",
    routing_action="allowed_with_caution",
)


RESTRICTED_ZONE = IceZone(
    zone="restricted",
    concentration_min=0.30,
    concentration_max=0.80,
    description=(
        "Moderate to heavy sea ice. Navigation should consider "
        "vessel-specific ice capability and updated ice information."
    ),
    routing_action="high_cost",
)


AVOID_ZONE = IceZone(
    zone="avoid",
    concentration_min=0.80,
    concentration_max=1.01,
    description=(
        "Very high sea-ice concentration. Area should normally "
        "be avoided unless specifically authorized and supported."
    ),
    routing_action="blocked_or_extreme_cost",
)


ICE_ZONES = [
    SAFE_ZONE,
    CAUTION_ZONE,
    RESTRICTED_ZONE,
    AVOID_ZONE,
]


# ============================================================
# BASIC ZONE CLASSIFICATION
# ============================================================

def classify_ice_zone(
    concentration: float,
) -> IceZone:
    """
    Convert sea-ice concentration into a navigation zone.

    concentration:
        0.0 = 0% ice
        1.0 = 100% ice
    """

    concentration = max(
        0.0,
        min(1.0, float(concentration))
    )

    if concentration < 0.15:
        return SAFE_ZONE

    if concentration < 0.30:
        return CAUTION_ZONE

    if concentration < 0.80:
        return RESTRICTED_ZONE

    return AVOID_ZONE


# ============================================================
# THICKNESS-BASED ESCALATION
# ============================================================

def apply_ice_thickness_escalation(
    zone: IceZone,
    thickness_m: Optional[float],
) -> IceZone:
    """
    Increase the risk zone when unusually thick ice is detected.

    Thickness is used as an additional warning signal.

    This does not establish a certified vessel operating limit.
    """

    if thickness_m is None:
        return zone

    thickness_m = max(
        0.0,
        float(thickness_m)
    )

    # Thick ice should never be treated as ordinary safe water.
    if thickness_m >= 1.0:

        if zone.zone == "safe":
            return CAUTION_ZONE

        if zone.zone == "caution":
            return RESTRICTED_ZONE

    return zone


# ============================================================
# COMPLETE ICE RISK ZONE ASSESSMENT
# ============================================================

def assess_ice_zone(
    concentration: float,
    thickness_m: Optional[float] = None,
) -> Dict:
    """
    Produce the complete sea-ice zone assessment.
    """

    base_zone = classify_ice_zone(
        concentration
    )

    final_zone = apply_ice_thickness_escalation(
        base_zone,
        thickness_m
    )

    return {
        "ice_concentration": round(
            float(concentration),
            3,
        ),

        "ice_concentration_percent": round(
            float(concentration) * 100,
            1,
        ),

        "ice_thickness_m": thickness_m,

        "zone": final_zone.zone,

        "description": final_zone.description,

        "routing_action": final_zone.routing_action,

        "is_preferred": (
            final_zone.zone == "safe"
        ),

        "is_restricted": (
            final_zone.zone == "restricted"
        ),

        "should_avoid": (
            final_zone.zone == "avoid"
        ),
    }


# ============================================================
# ROUTING COST
# ============================================================

def get_zone_routing_penalty(
    zone: IceZone,
) -> float:
    """
    Convert the risk zone into a routing penalty.

    These are prototype routing weights.

    They are deliberately separate from the official
    vessel certification and should be calibrated later.
    """

    if zone.zone == "safe":
        return 0.0

    if zone.zone == "caution":
        return 0.5

    if zone.zone == "restricted":
        return 5.0

    if zone.zone == "avoid":
        return float("inf")

    return float("inf")


# ============================================================
# GRID CELL ASSESSMENT
# ============================================================

def assess_grid_cell(
    latitude: float,
    longitude: float,
    concentration: float,
    thickness_m: Optional[float] = None,
) -> Dict:
    """
    Attach an ice-risk zone to one routing-grid cell.
    """

    assessment = assess_ice_zone(
        concentration=concentration,
        thickness_m=thickness_m,
    )

    zone = classify_ice_zone(
        concentration
    )

    zone = apply_ice_thickness_escalation(
        zone,
        thickness_m
    )

    penalty = get_zone_routing_penalty(
        zone
    )

    return {
        "latitude": latitude,
        "longitude": longitude,

        **assessment,

        "routing_penalty": penalty,

        "blocked_by_ice": (
            penalty == float("inf")
        ),
    }


# ============================================================
# PROCESS MULTIPLE GRID CELLS
# ============================================================

def classify_ice_grid(
    grid_cells: List[Dict],
) -> List[Dict]:
    """
    Add ice-zone information to a list of routing-grid cells.

    Expected input:

        {
            "latitude": ...,
            "longitude": ...,
            "sea_ice": ...,
            "ice_thickness_m": ...
        }
    """

    classified_cells = []

    for cell in grid_cells:

        concentration = cell.get(
            "sea_ice",
            0.0,
        )

        thickness = cell.get(
            "ice_thickness_m"
        )

        classified = assess_grid_cell(
            latitude=cell["latitude"],
            longitude=cell["longitude"],
            concentration=concentration,
            thickness_m=thickness,
        )

        # Preserve existing grid information.
        updated_cell = {
            **cell,
            **classified,
        }

        classified_cells.append(
            updated_cell
        )

    return classified_cells