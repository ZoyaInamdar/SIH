from math import radians, sin, cos, sqrt, atan2, inf


EARTH_RADIUS_KM = 6371.0


def haversine_distance_km(
    lat1: float,
    lon1: float,
    lat2: float,
    lon2: float
) -> float:

    lat1_rad = radians(lat1)
    lat2_rad = radians(lat2)

    delta_lat = radians(lat2 - lat1)
    delta_lon = radians(lon2 - lon1)

    a = (
        sin(delta_lat / 2) ** 2
        + cos(lat1_rad)
        * cos(lat2_rad)
        * sin(delta_lon / 2) ** 2
    )

    c = 2 * atan2(sqrt(a), sqrt(1 - a))

    return EARTH_RADIUS_KM * c


def sea_ice_penalty(concentration: float) -> float:
    """
    Returns additional routing cost caused by sea ice.

    Concentration is expected in the range 0.0 to 1.0.
    """

    concentration = max(0.0, min(1.0, concentration))

    if concentration < 0.15:
        return 0.0

    if concentration < 0.30:
        return 0.5

    if concentration < 0.60:
        return 2.0

    if concentration < 0.80:
        return 5.0

    return 15.0


def wave_penalty(wave_height_m: float) -> float:
    """
    Returns additional routing cost caused by waves.
    """

    wave_height_m = max(0.0, wave_height_m)

    if wave_height_m <= 1.0:
        return 0.0

    if wave_height_m <= 2.0:
        return 0.5

    if wave_height_m <= 3.0:
        return 1.5

    if wave_height_m <= 4.0:
        return 3.0

    return 6.0


def grounding_penalty(
    water_depth_m: float,
    vessel_draft_m: float,
    safety_margin_m: float = 5.0
) -> float:

    if water_depth_m <= vessel_draft_m:
        return inf

    if water_depth_m < vessel_draft_m + safety_margin_m:
        return 10.0

    if water_depth_m < vessel_draft_m + safety_margin_m + 10.0:
        return 2.0

    return 0.0


def movement_cost(
    distance_km: float,
    sea_ice_concentration: float = 0.0,
    wave_height_m: float = 0.0,
    water_depth_m: float = 1000.0,
    vessel_draft_m: float = 6.0
) -> float:

    grounding = grounding_penalty(
        water_depth_m,
        vessel_draft_m
    )

    if grounding == inf:
        return inf

    return (
        distance_km
        + sea_ice_penalty(sea_ice_concentration)
        + wave_penalty(wave_height_m)
        + grounding
    )