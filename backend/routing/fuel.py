from dataclasses import dataclass
from typing import Optional


@dataclass
class VesselProfile:
    """
    Vessel-specific navigation profile.

    The profile is designed around MV Vasiliy Golovnin,
    the vessel used for Indian Antarctic expeditions.

    IMPORTANT:
    Values must come from verified vessel documentation.
    Do not invent missing specifications.
    """

    vessel_id: str

    # Basic vessel information
    vessel_name: str
    vessel_type: str

    # Dimensions / displacement
    length_m: Optional[float] = None
    beam_m: Optional[float] = None
    gross_tonnage: Optional[float] = None
    deadweight_t: Optional[float] = None

    # Navigation parameters
    draft_m: Optional[float] = None

    # Ice capability
    ice_class: Optional[str] = None
    maximum_ice_thickness_m: Optional[float] = None

    # Fuel model
    fuel_rate_l_per_km: Optional[float] = None

    # Safety parameters
    minimum_under_keel_clearance_m: float = 5.0

    # Metadata
    source: Optional[str] = None
    notes: Optional[str] = None


# ------------------------------------------------------------------
# PRIMARY VESSEL
# ------------------------------------------------------------------

MV_VASILIY_GOLOVNIN = VesselProfile(
    vessel_id="MV-VG-001",

    vessel_name="MV Vasiliy Golovnin",

    vessel_type="Research / Supply Vessel",

    # These values should be populated only from verified sources.
    length_m=None,
    beam_m=None,
    gross_tonnage=None,
    deadweight_t=None,

    draft_m=None,

    # Keep the certified Russian ice-class designation here once
    # verified from authoritative vessel documentation.
    ice_class=None,

    maximum_ice_thickness_m=None,

    # Do NOT use a guessed fuel consumption value.
    fuel_rate_l_per_km=None,

    minimum_under_keel_clearance_m=5.0,

    source="To be populated from verified vessel documentation",

    notes=(
        "Primary vessel profile for the Antarctic navigation "
        "decision-support prototype. Vessel-specific parameters "
        "must be verified before operational use."
    ),
)


# ------------------------------------------------------------------
# VESSEL PROFILE REGISTRY
# ------------------------------------------------------------------

VESSEL_PROFILES = {
    MV_VASILIY_GOLOVNIN.vessel_id: MV_VASILIY_GOLOVNIN
}


def get_vessel_profile(vessel_id: str) -> Optional[VesselProfile]:
    """
    Return a vessel profile from the registry.
    """

    return VESSEL_PROFILES.get(vessel_id)


def get_primary_vessel() -> VesselProfile:
    """
    Return the primary vessel used by the prototype.
    """

    return MV_VASILIY_GOLOVNIN


# ------------------------------------------------------------------
# ENVIRONMENTAL FUEL MODEL
# ------------------------------------------------------------------

def calculate_environmental_multiplier(
    average_ice: float,
    average_wave_height_m: float,
) -> float:
    """
    Prototype environmental multiplier.

    Higher ice concentration and wave height increase the estimated
    fuel requirement.

    These values are routing-model assumptions and should eventually
    be calibrated against real vessel performance data.
    """

    multiplier = 1.0

    # Sea-ice effect
    if average_ice >= 0.80:
        multiplier += 0.50

    elif average_ice >= 0.60:
        multiplier += 0.30

    elif average_ice >= 0.30:
        multiplier += 0.15

    # Wave effect
    if average_wave_height_m >= 4.0:
        multiplier += 0.25

    elif average_wave_height_m >= 3.0:
        multiplier += 0.15

    elif average_wave_height_m >= 2.0:
        multiplier += 0.05

    return multiplier


def estimate_fuel(
    distance_km: float,
    vessel: VesselProfile,
    average_ice: float = 0.0,
    average_wave_height_m: float = 0.0,
) -> Optional[float]:
    """
    Estimate fuel consumption for a route.

    Returns None when the vessel's verified fuel-rate information
    is unavailable.

    Formula:

        fuel =
            distance
            × base fuel rate
            × environmental multiplier
    """

    if vessel.fuel_rate_l_per_km is None:
        return None

    multiplier = calculate_environmental_multiplier(
        average_ice=average_ice,
        average_wave_height_m=average_wave_height_m,
    )

    return (
        distance_km
        * vessel.fuel_rate_l_per_km
        * multiplier
    )


def compare_routes(
    standard_distance_km: float,
    optimized_distance_km: float,
    standard_fuel_l: Optional[float],
    optimized_fuel_l: Optional[float],
) -> dict:
    """
    Compare a standard route with the optimized route.
    """

    result = {
        "standard_distance_km": round(
            standard_distance_km, 2
        ),

        "optimized_distance_km": round(
            optimized_distance_km, 2
        ),

        "distance_difference_km": round(
            optimized_distance_km - standard_distance_km,
            2,
        ),

        "standard_fuel_l": standard_fuel_l,
        "optimized_fuel_l": optimized_fuel_l,

        "fuel_saving_l": None,
        "fuel_saving_percent": None,
    }

    # We cannot calculate fuel savings without actual fuel data.
    if (
        standard_fuel_l is not None
        and optimized_fuel_l is not None
        and standard_fuel_l > 0
    ):
        saving = standard_fuel_l - optimized_fuel_l

        result["fuel_saving_l"] = round(
            saving,
            2,
        )

        result["fuel_saving_percent"] = round(
            (saving / standard_fuel_l) * 100,
            2,
        )

    return result