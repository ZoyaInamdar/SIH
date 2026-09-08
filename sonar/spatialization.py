import math
from typing import Tuple


EARTH_RADIUS_M = 6_378_137.0


def localize_bounding_box(
    bbox: tuple[int, int, int, int],
    img_width: int,
    img_height: int,
    vessel_lat: float,
    vessel_lon: float,
    vessel_heading: float,
    max_range_m: float = 100.0,
    fov_deg: float = 90.0,
) -> Tuple[float, float, float, float]:
    """
    Estimate the real-world location of a sonar detection.

    IMPORTANT:
    This is a prototype approximation.

    Assumptions:
    - Sonar origin is at the bottom-center of the image.
    - Vertical image position maps linearly to range.
    - Horizontal image position maps linearly to bearing.
    - The center of the image corresponds to vessel heading.
    - The sonar field of view is symmetric around vessel heading.

    Returns:
        (
            range_m,
            bearing_deg,
            latitude,
            longitude
        )
    """

    if img_width <= 0 or img_height <= 0:
        raise ValueError("Image dimensions must be positive.")

    if max_range_m <= 0:
        raise ValueError("max_range_m must be greater than zero.")

    if fov_deg <= 0 or fov_deg > 360:
        raise ValueError("fov_deg must be between 0 and 360 degrees.")

    vessel_lat = float(vessel_lat)
    vessel_lon = float(vessel_lon)
    vessel_heading = float(vessel_heading)

    if not -90.0 <= vessel_lat <= 90.0:
        raise ValueError("vessel_lat must be between -90 and 90.")

    if not -180.0 <= vessel_lon <= 180.0:
        raise ValueError("vessel_lon must be between -180 and 180.")

    x, y, width, height = bbox

    if width <= 0 or height <= 0:
        raise ValueError("Bounding-box width and height must be positive.")

    # ---------------------------------------------------------
    # 1. Bounding-box center in image coordinates
    # ---------------------------------------------------------

    center_x = x + width / 2.0
    center_y = y + height / 2.0

    # ---------------------------------------------------------
    # 2. Image space -> approximate range
    #
    # Bottom of image = 0 m
    # Top of image    = max_range_m
    # ---------------------------------------------------------

    relative_y = img_height - center_y

    relative_y = max(0.0, min(float(img_height), relative_y))

    range_m = (relative_y / img_height) * max_range_m

    # ---------------------------------------------------------
    # 3. Image space -> bearing offset
    #
    # Left edge  = -FOV/2
    # Centre     = 0
    # Right edge = +FOV/2
    # ---------------------------------------------------------

    normalized_x = center_x / img_width

    normalized_x = max(0.0, min(1.0, normalized_x))

    bearing_offset = (normalized_x - 0.5) * fov_deg

    target_bearing = (vessel_heading + bearing_offset) % 360.0

    # ---------------------------------------------------------
    # 4. Forward geodesic calculation
    #
    # Starting point:
    #     vessel latitude/longitude
    #
    # Travel:
    #     range_m
    #
    # Direction:
    #     target_bearing
    # ---------------------------------------------------------

    lat1 = math.radians(vessel_lat)
    lon1 = math.radians(vessel_lon)
    bearing = math.radians(target_bearing)

    angular_distance = range_m / EARTH_RADIUS_M

    lat2 = math.asin(
        math.sin(lat1) * math.cos(angular_distance)
        + math.cos(lat1)
        * math.sin(angular_distance)
        * math.cos(bearing)
    )

    lon2 = lon1 + math.atan2(
        math.sin(bearing) * math.sin(angular_distance) * math.cos(lat1),
        math.cos(angular_distance)
        - math.sin(lat1) * math.sin(lat2),
    )

    latitude = math.degrees(lat2)
    longitude = math.degrees(lon2)

    # Normalize longitude to [-180, 180]
    longitude = (longitude + 180.0) % 360.0 - 180.0

    return (
        round(range_m, 2),
        round(target_bearing, 2),
        round(latitude, 7),
        round(longitude, 7),
    )