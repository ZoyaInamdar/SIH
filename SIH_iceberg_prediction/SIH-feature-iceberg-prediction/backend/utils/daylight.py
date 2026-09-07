import math
from datetime import date


def calculate_solar_declination(
    day_of_year: int
) -> float:

    return math.radians(
        23.44
        * math.sin(
            math.radians(
                (360 / 365)
                * (day_of_year - 81)
            )
        )
    )


def calculate_daylight_status(
    latitude: float,
    longitude: float,
    observation_date: date
) -> dict:

    latitude = max(
        -89.9,
        min(89.9, latitude)
    )

    day_of_year = (
        observation_date.timetuple()
        .tm_yday
    )

    declination = calculate_solar_declination(
        day_of_year
    )

    latitude_rad = math.radians(
        latitude
    )

    value = (
        -math.tan(latitude_rad)
        * math.tan(declination)
    )

    if value >= 1:

        return {
            "status": "polar_night",
            "daylight_hours": 0.0
        }

    if value <= -1:

        return {
            "status": "daylight",
            "daylight_hours": 24.0
        }

    hour_angle = math.acos(value)

    daylight_hours = (
        2
        * math.degrees(hour_angle)
        / 15
    )

    if daylight_hours >= 12:

        status = "daylight"

    elif daylight_hours >= 6:

        status = "reduced_daylight"

    elif daylight_hours > 0:

        status = "twilight"

    else:

        status = "polar_night"

    return {
        "status": status,
        "daylight_hours": round(
            daylight_hours,
            2
        )
    }