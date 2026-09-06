from dataclasses import dataclass
from enum import Enum
from typing import Optional


# ============================================================
# ICE RISK LEVEL
# ============================================================

class IceRiskLevel(str, Enum):
    SAFE = "safe"
    CAUTION = "caution"
    RESTRICTED = "restricted"
    AVOID = "avoid"


# ============================================================
# ICE CONDITION
# ============================================================

@dataclass
class IceCondition:
    """
    Represents the current sea-ice environment.

    concentration is expressed as a fraction:

        0.0 = 0% ice
        1.0 = 100% ice

    thickness is the estimated ice thickness in metres.
    """

    concentration: float
    thickness_m: Optional[float] = None
    snow_cover_m: Optional[float] = None


# ============================================================
# VESSEL ICE CAPABILITY
# ============================================================

@dataclass
class VesselIceCapability:
    """
    Vessel-specific ice capability.

    This is deliberately separate from FSICR classification.

    For MV Vasiliy Golovnin, the values must ultimately come from
    verified Russian Maritime Register / vessel documentation.

    Do not interpret this class as assigning an FSICR ice class
    to the vessel.
    """

    vessel_id: str

    vessel_name: str

    # Actual certified / verified ice classification.
    russian_ice_class: Optional[str] = None

    # Maximum operational ice thickness that has been verified
    # for this particular vessel/operational condition.
    maximum_operational_ice_thickness_m: Optional[float] = None

    # Whether the vessel requires an icebreaker or convoy
    # under particular conditions.
    icebreaker_assistance_required: bool = False

    source: Optional[str] = None


# ============================================================
# FSICR-STYLE ICE SEVERITY
# ============================================================

def classify_ice_severity(
    concentration: float,
    thickness_m: Optional[float] = None,
) -> str:
    """
    Classify the severity of sea-ice conditions.

    This is a simplified decision-support classification inspired
    by established ice-navigation concepts.

    It is NOT an official FSICR compliance calculation.

    Returns:

        open_water
        light
        moderate
        heavy
        very_heavy
    """

    concentration = max(
        0.0,
        min(1.0, float(concentration))
    )

    # Open / very low concentration
    if concentration < 0.15:
        return "open_water"

    # Light ice
    if concentration < 0.30:
        return "light"

    # Moderate ice
    if concentration < 0.60:
        if thickness_m is not None and thickness_m >= 1.0:
            return "heavy"

        return "moderate"

    # Heavy ice
    if concentration < 0.80:
        return "heavy"

    # Very heavy concentration
    return "very_heavy"


# ============================================================
# RISK LEVEL
# ============================================================

def determine_ice_risk(
    concentration: float,
    thickness_m: Optional[float] = None,
) -> IceRiskLevel:
    """
    Convert sea-ice conditions into a navigation risk level.

    This is a prototype decision-support classification.
    """

    severity = classify_ice_severity(
        concentration=concentration,
        thickness_m=thickness_m,
    )

    if severity == "open_water":
        return IceRiskLevel.SAFE

    if severity == "light":
        return IceRiskLevel.CAUTION

    if severity == "moderate":
        return IceRiskLevel.CAUTION

    if severity == "heavy":
        return IceRiskLevel.RESTRICTED

    if severity == "very_heavy":
        return IceRiskLevel.AVOID

    return IceRiskLevel.RESTRICTED


# ============================================================
# VESSEL-SPECIFIC ASSESSMENT
# ============================================================

def assess_vessel_ice_capability(
    vessel: VesselIceCapability,
    ice: IceCondition,
) -> dict:
    """
    Assess whether the current ice condition is compatible with
    the known vessel capability.

    Important:

    If the vessel's verified maximum ice thickness is unknown,
    the system does NOT assume that the vessel can safely operate
    in that condition.

    Instead, the result becomes 'unknown_capability'.
    """

    environmental_risk = determine_ice_risk(
        concentration=ice.concentration,
        thickness_m=ice.thickness_m,
    )

    result = {
        "vessel_id": vessel.vessel_id,
        "vessel_name": vessel.vessel_name,

        "ice_concentration": round(
            ice.concentration,
            3,
        ),

        "ice_thickness_m": ice.thickness_m,

        "environmental_risk": environmental_risk.value,

        "vessel_capability_status": "unknown_capability",

        "navigation_advisory": (
            "Vessel-specific ice capability is not verified "
            "for this condition."
        ),
    }

    # --------------------------------------------------------
    # No verified thickness capability
    # --------------------------------------------------------

    if vessel.maximum_operational_ice_thickness_m is None:

        # Open water is still environmentally low-risk, but
        # vessel-specific ice capability remains unknown.
        if environmental_risk == IceRiskLevel.SAFE:
            result["vessel_capability_status"] = "not_required"

            result["navigation_advisory"] = (
                "Low ice concentration. No vessel-specific "
                "ice-thickness limit is required for this "
                "condition."
            )

        return result

    # --------------------------------------------------------
    # Thickness is unavailable
    # --------------------------------------------------------

    if ice.thickness_m is None:

        result["navigation_advisory"] = (
            "Ice concentration is available, but ice thickness "
            "is unavailable. Do not assume compliance with the "
            "vessel's thickness capability."
        )

        return result

    # --------------------------------------------------------
    # Compare actual ice thickness with vessel capability
    # --------------------------------------------------------

    if (
        ice.thickness_m
        <= vessel.maximum_operational_ice_thickness_m
    ):

        result["vessel_capability_status"] = "within_limit"

        result["navigation_advisory"] = (
            "Estimated ice thickness is within the verified "
            "vessel operational limit. Continue monitoring "
            "ice conditions."
        )

    else:

        result["vessel_capability_status"] = "exceeds_limit"

        result["navigation_advisory"] = (
            "Estimated ice thickness exceeds the verified "
            "vessel operational limit. Route should be "
            "restricted or avoided unless authorized ice "
            "support is available."
        )

    return result


# ============================================================
# MV VASILIY GOLOVNIN
# ============================================================

MV_VASILIY_GOLOVNIN_ICE_CAPABILITY = VesselIceCapability(

    vessel_id="MV-VG-001",

    vessel_name="MV Vasiliy Golovnin",

    # Populate only after verification from authoritative
    # Russian vessel documentation.
    russian_ice_class=None,

    maximum_operational_ice_thickness_m=None,

    icebreaker_assistance_required=False,

    source=(
        "Russian Maritime Register / vessel documentation "
        "to be verified"
    ),
)


# ============================================================
# CONVENIENCE FUNCTION
# ============================================================

def assess_golovnin_ice_condition(
    concentration: float,
    thickness_m: Optional[float] = None,
    snow_cover_m: Optional[float] = None,
) -> dict:
    """
    Assess the current ice environment for MV Vasiliy Golovnin.
    """

    ice = IceCondition(
        concentration=concentration,
        thickness_m=thickness_m,
        snow_cover_m=snow_cover_m,
    )

    return assess_vessel_ice_capability(
        vessel=MV_VASILIY_GOLOVNIN_ICE_CAPABILITY,
        ice=ice,
    )