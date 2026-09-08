from typing import List, Dict, Optional


def find_nearest_data_point(
    latitude: float,
    longitude: float,
    data: List[dict]
) -> Optional[dict]:

    if not data:
        return None

    return min(
        data,
        key=lambda item: (
            (item["latitude"] - latitude) ** 2
            + (item["longitude"] - longitude) ** 2
        )
    )


def is_antarctic_land(lat: float, lon: float) -> bool:
    """
    Classifies whether a coordinate is on continental land, islands, or ice sheets.
    Accurately delineates South Shetland Islands, Trinity Peninsula, and Antarctic mainland
    while preserving open ocean channels (Drake Passage, Bransfield Strait, Boyd Strait, English Strait).
    """
    # 0. Open deep ocean corridors that must NEVER be classified as land:
    # Deep ocean open water to the far north of all South Shetland Islands (Drake Passage)
    if lat > -61.75:
        return False

    # Bransfield Strait deep open ocean fairway (between South Shetlands and Antarctic Peninsula)
    # Latitude -63.25 to -62.78 is a massive open deep-water channel
    if -63.25 <= lat <= -62.78:
        # Check for isolated small volcanic caldera in Bransfield Strait: Deception Island
        if -63.03 <= lat <= -62.93 and -60.72 <= lon <= -60.50:
            return True
        # Bridgeman Island
        if -62.08 <= lat <= -62.03 and -56.78 <= lon <= -56.68:
            return True
        return False

    # 1. South Shetland Islands chain (individual island boundaries)
    # King George Island
    if -62.30 <= lat <= -61.85 and -58.95 <= lon <= -57.55:
        return True

    # Nelson Island
    if -62.36 <= lat <= -62.24 and -59.30 <= lon <= -58.95:
        return True

    # Robert Island
    if -62.46 <= lat <= -62.36 and -59.60 <= lon <= -59.35:
        return True

    # Greenwich Island
    if -62.56 <= lat <= -62.44 and -59.95 <= lon <= -59.68:
        return True

    # Livingston Island (snow-covered mountainous island)
    if -62.76 <= lat <= -62.48 and -61.15 <= lon <= -60.10:
        return True

    # Snow Island
    if -62.82 <= lat <= -62.68 and -61.45 <= lon <= -61.18:
        return True

    # Smith Island
    if -63.05 <= lat <= -62.85 and -62.70 <= lon <= -62.40:
        return True

    # Low Island
    if -63.38 <= lat <= -63.20 and -62.25 <= lon <= -61.95:
        return True

    # Joinville Island Group (Joinville, D'Urville, Dundee)
    if -63.35 <= lat <= -63.10 and -56.30 <= lon <= -55.15:
        return True

    # James Ross Island & Vega Island
    if -64.40 <= lat <= -63.75 and -58.45 <= lon <= -57.10:
        return True

    # Brabant Island & Anvers Island (Palmer Archipelago)
    if -65.00 <= lat <= -63.95 and -64.50 <= lon <= -62.50:
        return True

    # Trinity Peninsula & Antarctic Peninsula Mainland
    if -68.0 <= lat <= -63.35 and -65.0 <= lon <= -56.8:
        # Deep Antarctic Sound water fairway
        if -63.60 <= lat <= -63.20 and -57.25 <= lon <= -56.85:
            return False
        return True

    # General continental land mass south of -68
    if lat <= -68.0:
        return True

    return False


def create_ocean_grid(
    min_lat: float,
    max_lat: float,
    min_lon: float,
    max_lon: float,
    resolution: float = 0.1,
    sea_ice_data: Optional[List[dict]] = None,
    hazards: Optional[List[dict]] = None,
    wave_data: Optional[List[dict]] = None,
    bathymetry_data: Optional[List[dict]] = None,
    land_mask_data: Optional[List[dict]] = None
) -> List[List[dict]]:

    if resolution <= 0:
        raise ValueError("Resolution must be greater than zero.")

    sea_ice_data = sea_ice_data or []
    hazards = hazards or []
    wave_data = wave_data or []
    bathymetry_data = bathymetry_data or []
    land_mask_data = land_mask_data or []

    latitudes = []
    current_lat = min_lat

    while current_lat <= max_lat + 1e-9:
        latitudes.append(round(current_lat, 6))
        current_lat += resolution

    longitudes = []
    current_lon = min_lon

    while current_lon <= max_lon + 1e-9:
        longitudes.append(round(current_lon, 6))
        current_lon += resolution

    grid = []

    for lat in latitudes:

        row = []

        for lon in longitudes:

            is_land = is_antarctic_land(lat, lon)

            cell = {
                "latitude": lat,
                "longitude": lon,
                "blocked": is_land,
                "sea_ice": 0.0,
                "wave_height": 0.0,
                "water_depth": 1000.0 if not is_land else 0.0,
                "land": is_land
            }

            nearest_ice = find_nearest_data_point(
                lat,
                lon,
                sea_ice_data
            )

            if nearest_ice is not None:

                cell["sea_ice"] = float(
                    nearest_ice.get(
                        "concentration",
                        nearest_ice.get("sea_ice", 0.0)
                    )
                )

            nearest_wave = find_nearest_data_point(
                lat,
                lon,
                wave_data
            )

            if nearest_wave is not None:

                cell["wave_height"] = float(
                    nearest_wave.get(
                        "wave_height_m",
                        nearest_wave.get("wave_height", 0.0)
                    )
                )

            nearest_depth = find_nearest_data_point(
                lat,
                lon,
                bathymetry_data
            )

            if nearest_depth is not None:

                cell["water_depth"] = float(
                    nearest_depth.get(
                        "depth_m",
                        nearest_depth.get(
                            "water_depth",
                            1000.0
                        )
                    )
                )

            nearest_land = find_nearest_data_point(
                lat,
                lon,
                land_mask_data
            )

            if nearest_land is not None:

                is_land = nearest_land.get(
                    "is_land",
                    nearest_land.get("land", False)
                )

                cell["land"] = bool(is_land)
                cell["blocked"] = bool(is_land)

            row.append(cell)

        grid.append(row)

    return grid


def apply_bathymetry(
    grid: List[List[dict]],
    bathymetry_data: List[dict]
) -> List[List[dict]]:

    for row in grid:

        for cell in row:

            nearest = find_nearest_data_point(
                cell["latitude"],
                cell["longitude"],
                bathymetry_data
            )

            if nearest:

                cell["water_depth"] = float(
                    nearest.get(
                        "depth_m",
                        nearest.get(
                            "water_depth",
                            cell["water_depth"]
                        )
                    )
                )

    return grid


def apply_wave_data(
    grid: List[List[dict]],
    wave_data: List[dict]
) -> List[List[dict]]:

    for row in grid:

        for cell in row:

            nearest = find_nearest_data_point(
                cell["latitude"],
                cell["longitude"],
                wave_data
            )

            if nearest:

                cell["wave_height"] = float(
                    nearest.get(
                        "wave_height_m",
                        nearest.get(
                            "wave_height",
                            cell["wave_height"]
                        )
                    )
                )

    return grid


def apply_land_mask(
    grid: List[List[dict]],
    land_mask_data: List[dict]
) -> List[List[dict]]:

    for row in grid:

        for cell in row:

            nearest = find_nearest_data_point(
                cell["latitude"],
                cell["longitude"],
                land_mask_data
            )

            if nearest:

                is_land = nearest.get(
                    "is_land",
                    nearest.get("land", False)
                )

                cell["land"] = bool(is_land)
                cell["blocked"] = bool(is_land)

    return grid