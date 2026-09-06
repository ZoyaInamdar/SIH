from dataclasses import dataclass
from enum import Enum
from typing import Optional


# ============================================================
# FSICR REFERENCE CLASSES
# ============================================================

class FSICRClass(str, Enum):
    """
    Finnish-Swedish Ice Class Rules reference classes.

    These are reference calculation classes.
    They do NOT assign an FSICR class to MV Vasiliy Golovnin.
    """

    IA_SUPER = "IA Super"
    IA = "IA"
    IB = "IB"
    IC = "IC"


# ============================================================
# FSICR DESIGN PARAMETERS
# ============================================================

@dataclass(frozen=True)
class FSICRDesignParameters:
    """
    Design parameters used by the FSICR channel-resistance model.

    Hm:
        thickness of the consolidated ice layer.

    hi:
        thickness of the level ice layer.

    C5:
        FSICR coefficient associated with the ice class.
    """

    ice_class: FSICRClass
    Hm_m: float
    hi_m: float
    C5: float


FSICR_PARAMETERS = {
    FSICRClass.IA_SUPER: FSICRDesignParameters(
        ice_class=FSICRClass.IA_SUPER,
        Hm_m=1.0,
        hi_m=0.1,
        C5=825.6,
    ),

    FSICRClass.IA: FSICRDesignParameters(
        ice_class=FSICRClass.IA,
        Hm_m=1.0,
        hi_m=0.0,
        C5=825.6,
    ),

    FSICRClass.IB: FSICRDesignParameters(
        ice_class=FSICRClass.IB,
        Hm_m=0.8,
        hi_m=0.0,
        C5=660.5,
    ),

    FSICRClass.IC: FSICRDesignParameters(
        ice_class=FSICRClass.IC,
        Hm_m=0.6,
        hi_m=0.0,
        C5=495.4,
    ),
}


# ============================================================
# VESSEL GEOMETRY
# ============================================================

@dataclass
class VesselGeometry:
    """
    Vessel geometry required by the simplified FSICR
    channel-resistance calculation.

    Units:

        L        = metres
        B        = metres
        T        = metres
        Awf      = square metres
        alpha    = degrees
        phi_2    = degrees
        Lpar/L   = dimensionless
    """

    length_m: float
    beam_m: float
    draft_m: float

    waterline_bow_area_m2: float

    alpha_deg: float = 30.0
    phi_2_deg: float = 40.0

    Lpar_over_L: float = 0.45


# ============================================================
# FSICR CONSTANTS
# ============================================================

C1 = 0.0
C2 = 0.0

C3 = 845.0
C4 = 42.0


# ============================================================
# BASIC VALIDATION
# ============================================================

def validate_vessel_geometry(
    vessel: VesselGeometry,
) -> None:

    if vessel.length_m <= 0:
        raise ValueError(
            "Vessel length must be greater than zero."
        )

    if vessel.beam_m <= 0:
        raise ValueError(
            "Vessel beam must be greater than zero."
        )

    if vessel.draft_m <= 0:
        raise ValueError(
            "Vessel draft must be greater than zero."
        )

    if vessel.waterline_bow_area_m2 <= 0:
        raise ValueError(
            "Waterline bow area must be greater than zero."
        )

    if not 0 < vessel.Lpar_over_L <= 1:
        raise ValueError(
            "Lpar_over_L must be between 0 and 1."
        )


# ============================================================
# FSICR PARAMETERS
# ============================================================

def get_fsicr_parameters(
    ice_class: FSICRClass,
) -> FSICRDesignParameters:

    try:
        return FSICR_PARAMETERS[ice_class]

    except KeyError:
        raise ValueError(
            f"Unsupported FSICR class: {ice_class}"
        )


# ============================================================
# BOW ICE HEIGHT
# ============================================================

def calculate_Hf(
    Hm_m: float,
    beam_m: float,
) -> float:
    """
    Calculate the equivalent ice height Hf.

    FSICR simplified formulation:

        Hf = 0.26 + sqrt(Hm * B)

    where:

        Hm = consolidated ice layer thickness
        B  = vessel beam
    """

    if Hm_m <= 0:
        raise ValueError(
            "Hm must be greater than zero."
        )

    if beam_m <= 0:
        raise ValueError(
            "Beam must be greater than zero."
        )

    return 0.26 + (Hm_m * beam_m) ** 0.5


# ============================================================
# BOW ANGLE COEFFICIENT
# ============================================================

def calculate_Cpsi(
    psi_deg: float,
) -> float:
    """
    Calculate C_psi.

    C_psi = 0 when psi <= 45 degrees.

    For larger angles:

        C_psi = 0.047 * psi - 2.115
    """

    if psi_deg <= 45.0:
        return 0.0

    return 0.047 * psi_deg - 2.115


# ============================================================
# ICE FRICTION COEFFICIENT
# ============================================================

def calculate_Cmu(
    psi_deg: float,
    alpha_deg: float,
    phi_deg: float,
) -> float:
    """
    Calculate the FSICR friction-related coefficient.

    The FSICR formulation requires C_mu to be no smaller
    than 0.45.
    """

    import math

    psi = math.radians(psi_deg)
    alpha = math.radians(alpha_deg)
    phi = math.radians(phi_deg)

    Cmu = (
        0.15 * math.cos(phi / 2.0)
        + math.sin(psi)
        * math.sin(alpha)
    )

    return max(
        0.45,
        Cmu,
    )


# ============================================================
# PSI ANGLE
# ============================================================

def calculate_psi(
    alpha_deg: float,
    phi_2_deg: float,
) -> float:
    """
    Calculate psi from the FSICR bow geometry.

        psi = atan(
            tan(phi_2) / sin(alpha)
        )
    """

    import math

    alpha = math.radians(alpha_deg)
    phi_2 = math.radians(phi_2_deg)

    if abs(math.sin(alpha)) < 1e-12:
        raise ValueError(
            "Invalid alpha angle."
        )

    psi = math.atan(
        math.tan(phi_2)
        / math.sin(alpha)
    )

    return math.degrees(psi)


# ============================================================
# RULE CHANNEL RESISTANCE
# ============================================================

def calculate_channel_resistance(
    vessel: VesselGeometry,
    ice_class: FSICRClass,
) -> float:
    """
    Calculate simplified FSICR rule channel resistance.

    Returns:

        Rch in Newtons.

    The implementation follows the simplified FSICR
    formulation used for rule-channel resistance.

    IMPORTANT:
    This is a reference engineering calculation.
    It is not a certification or classification calculation.
    """

    validate_vessel_geometry(vessel)

    params = get_fsicr_parameters(
        ice_class
    )

    L = vessel.length_m
    B = vessel.beam_m
    T = vessel.draft_m

    Hm = params.Hm_m
    hi = params.hi_m

    Hf = calculate_Hf(
        Hm_m=Hm,
        beam_m=B,
    )

    psi = calculate_psi(
        alpha_deg=vessel.alpha_deg,
        phi_2_deg=vessel.phi_2_deg,
    )

    Cpsi = calculate_Cpsi(
        psi_deg=psi
    )

    Cmu = calculate_Cmu(
        psi_deg=psi,
        alpha_deg=vessel.alpha_deg,
        phi_deg=vessel.phi_2_deg,
    )

    # FSICR simplified channel-resistance expression.
    term_1 = C1 + C2

    term_2 = (
        C3
        * (Hf + hi) ** 2
        * (
            B
            + Cpsi * Hf
        )
        * Cmu
    )

    term_3 = (
        C4
        * L
        * Hf ** 2
    )

    geometry_ratio = (
        (L * T)
        / (B ** 2)
    )

    # FSICR caps this geometric term to the applicable range.
    geometry_term = min(
        20.0,
        max(
            5.0,
            geometry_ratio ** 3,
        ),
    )

    term_4 = (
        params.C5
        * geometry_term
        * (B / 4.0)
    )

    resistance_N = (
        term_1
        + term_2
        + term_3
        + term_4
    )

    return resistance_N


# ============================================================
# PROPULSION POWER
# ============================================================

def calculate_required_propulsion_power_kw(
    channel_resistance_N: float,
    propeller_diameter_m: float,
    propeller_count: int = 1,
    propulsion_type: str = "fixed_pitch",
) -> float:
    """
    Calculate FSICR reference propulsion power.

    FSICR relationship:

        Ps = Kp * Rch^(3/2) / Dp

    where:

        Ps  = required propulsion power
        Rch = rule channel resistance
        Dp  = propeller diameter

    The published coefficients depend on propeller count
    and propulsion type.
    """

    if channel_resistance_N <= 0:
        raise ValueError(
            "Channel resistance must be greater than zero."
        )

    if propeller_diameter_m <= 0:
        raise ValueError(
            "Propeller diameter must be greater than zero."
        )

    if propeller_count not in (1, 2, 3):
        raise ValueError(
            "Propeller count must be 1, 2, or 3."
        )

    propulsion_type = propulsion_type.lower()

    KP = {
        1: {
            "fixed_pitch": 2.26,
            "controllable_pitch": 2.03,
        },
        2: {
            "fixed_pitch": 1.60,
            "controllable_pitch": 1.44,
        },
        3: {
            "fixed_pitch": 1.31,
            "controllable_pitch": 1.18,
        },
    }

    if propulsion_type not in KP[propeller_count]:
        raise ValueError(
            "Unsupported propulsion type."
        )

    Kp = KP[
        propeller_count
    ][propulsion_type]

    # Rch is converted from N to kN.
    Rch_kN = channel_resistance_N / 1000.0

    power_kw = (
        Kp
        * (Rch_kN ** 1.5)
        / propeller_diameter_m
    )

    return power_kw


# ============================================================
# COMPLETE FSICR ASSESSMENT
# ============================================================

def assess_fsicr_condition(
    vessel: VesselGeometry,
    reference_class: FSICRClass,
    propeller_diameter_m: Optional[float] = None,
    propeller_count: int = 1,
    propulsion_type: str = "fixed_pitch",
) -> dict:
    """
    Perform a deterministic FSICR reference calculation.

    No machine-learning model is used.

    The result is NOT a certification of the vessel.
    """

    resistance_N = calculate_channel_resistance(
        vessel=vessel,
        ice_class=reference_class,
    )

    result = {
        "framework": "FSICR",
        "reference_class": reference_class.value,

        "channel_resistance_N": round(
            resistance_N,
            2,
        ),

        "channel_resistance_kN": round(
            resistance_N / 1000.0,
            3,
        ),

        "propulsion_power_required_kw": None,

        "certification_status": (
            "reference_calculation_only"
        ),
    }

    if propeller_diameter_m is not None:

        result[
            "propulsion_power_required_kw"
        ] = round(
            calculate_required_propulsion_power_kw(
                channel_resistance_N=resistance_N,
                propeller_diameter_m=propeller_diameter_m,
                propeller_count=propeller_count,
                propulsion_type=propulsion_type,
            ),
            2,
        )

    return result


# ============================================================
# MV VASILIY GOLOVNIN
# ============================================================

MV_VASILIY_GOLOVNIN_FSICR = {
    "vessel_id": "MV-VG-001",
    "vessel_name": "MV Vasiliy Golovnin",

    # IMPORTANT:
    # Do not insert an FSICR class here.
    #
    # Golovnin's actual Russian classification should be
    # obtained from authoritative vessel documentation.
    "actual_ice_class": None,

    "classification_system": (
        "Russian classification / certification"
    ),

    "fsicr_reference_framework": True,

    "note": (
        "FSICR is used as a deterministic engineering "
        "reference framework. It does not assign an FSICR "
        "class to MV Vasiliy Golovnin."
    ),
}