from datetime import datetime, timezone
from typing import Optional


DEFAULT_STALE_THRESHOLD_HOURS = 72


def calculate_age_hours(
    timestamp: str
) -> Optional[float]:

    try:

        observation_time = datetime.fromisoformat(
            timestamp
        )

        if observation_time.tzinfo is None:

            observation_time = observation_time.replace(
                tzinfo=timezone.utc
            )

        current_time = datetime.now(
            timezone.utc
        )

        age_seconds = (
            current_time - observation_time
        ).total_seconds()

        return max(
            0,
            age_seconds / 3600
        )

    except Exception:

        return None


def is_stale(
    timestamp: str,
    threshold_hours: float = DEFAULT_STALE_THRESHOLD_HOURS
) -> bool:

    age_hours = calculate_age_hours(timestamp)

    if age_hours is None:
        return True

    return age_hours > threshold_hours


def get_freshness_status(
    timestamp: str,
    threshold_hours: float = DEFAULT_STALE_THRESHOLD_HOURS
) -> dict:

    age_hours = calculate_age_hours(timestamp)

    if age_hours is None:

        return {
            "data_age_hours": None,
            "is_stale": True,
            "freshness_status": "unknown"
        }

    stale = (
        age_hours > threshold_hours
    )

    return {
        "data_age_hours": round(
            age_hours,
            2
        ),
        "is_stale": stale,
        "freshness_status": (
            "stale"
            if stale
            else "fresh"
        )
    }