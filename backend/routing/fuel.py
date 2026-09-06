from dataclasses import dataclass
from typing import Optional

@dataclass
class VesselProfile:
    vessel_id: str
    vessel_name: str
    vessel_type: str
    length_m: Optional[float] = None
    beam_m: Optional[float] = None
    gross_tonnage: Optional[float] = None
    deadweight_t: Optional[float] = None
    draft_m: Optional[float] = None
    ice_class: Optional[str] = None
    maximum_ice_thickness_m: Optional[float] = None
    fuel_rate_l_per_km: Optional[float] = None
    minimum_under_keel_clearance_m: float = 5.0
    source: Optional[str] = None
    notes: Optional[str] = None

MV_VASILIY_GOLOVNIN = VesselProfile(
    vessel_id="MV-VG-001",
    vessel_name="MV Vasiliy Golovnin",
    vessel_type="Research / Supply Vessel",
    draft_m=8.5,
    ice_class="Arc5",
    fuel_rate_l_per_km=45.0, 
    notes="Primary vessel profile for the Antarctic navigation prototype."
)

POLAR_CATEGORY_C = VesselProfile(
    vessel_id="CAT-C-001",
    vessel_name="Generic Category C Vessel",
    vessel_type="Light Ice Supply Vessel",
    draft_m=6.0,
    ice_class="Ice Class IC",
    fuel_rate_l_per_km=30.0,
    notes="Lighter ice capability profile to demonstrate FSICR rerouting logic."
)

VESSEL_PROFILES = {
    MV_VASILIY_GOLOVNIN.vessel_id: MV_VASILIY_GOLOVNIN,
    POLAR_CATEGORY_C.vessel_id: POLAR_CATEGORY_C
}

def get_vessel_profile(vessel_id: str) -> Optional[VesselProfile]:
    return VESSEL_PROFILES.get(vessel_id)

def get_primary_vessel() -> VesselProfile:
    return MV_VASILIY_GOLOVNIN

def calculate_environmental_multiplier(average_ice: float, average_wave_height_m: float) -> float:
    multiplier = 1.0
    if average_ice >= 0.80: multiplier += 0.50
    elif average_ice >= 0.60: multiplier += 0.30
    elif average_ice >= 0.30: multiplier += 0.15

    if average_wave_height_m >= 4.0: multiplier += 0.25
    elif average_wave_height_m >= 3.0: multiplier += 0.15
    elif average_wave_height_m >= 2.0: multiplier += 0.05
    return multiplier

def estimate_fuel(distance_km: float, vessel: VesselProfile, average_ice: float = 0.0, average_wave_height_m: float = 0.0) -> Optional[float]:
    if vessel.fuel_rate_l_per_km is None: return None
    multiplier = calculate_environmental_multiplier(average_ice, average_wave_height_m)
    return distance_km * vessel.fuel_rate_l_per_km * multiplier