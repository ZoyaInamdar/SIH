from __future__ import annotations

from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional


# ---------------------------------------------------------------------
# Data structure
# ---------------------------------------------------------------------

@dataclass
class UnderwaterSonarHazard:
    """
    A sonar-derived underwater target.

    Important:
    range_m and bearing_deg remain None when the sonar source
    does not provide real-world localization.
    """

    hazard_id: str

    observation_id: str

    source_type: str

    target_class: Optional[str]

    detection_confidence: float

    bounding_box: List[int]

    range_m: Optional[float]

    bearing_deg: Optional[float]

    latitude: Optional[float]

    longitude: Optional[float]

    localized: bool

    advisory_only: bool

    observed_at: str

    status: str = "DETECTED"

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


# ---------------------------------------------------------------------
# In-memory hazard store
# ---------------------------------------------------------------------

_HAZARDS: Dict[str, UnderwaterSonarHazard] = {}


# ---------------------------------------------------------------------
# ID generation
# ---------------------------------------------------------------------

def _create_hazard_id(
    observation_id: str,
    target_index: int,
) -> str:

    return (
        f"SONAR-HZ-"
        f"{observation_id}-"
        f"{target_index:02d}"
    )


# ---------------------------------------------------------------------
# Localization
# ---------------------------------------------------------------------

def _is_localized(
    range_m: Optional[float],
    bearing_deg: Optional[float],
    latitude: Optional[float],
    longitude: Optional[float],
) -> bool:

    return (
        range_m is not None
        and bearing_deg is not None
        and latitude is not None
        and longitude is not None
    )


# ---------------------------------------------------------------------
# Observation → hazard conversion
# ---------------------------------------------------------------------

def process_sonar_observation(
    observation: Dict[str, Any],
    vessel_latitude: Optional[float] = None,
    vessel_longitude: Optional[float] = None,
) -> List[UnderwaterSonarHazard]:
    """
    Convert a structured SonarObservation into underwater
    hazard objects.

    No geographic position is invented.

    A target becomes geographically localized only when
    both range and bearing are available and a vessel
    position is available.
    """

    observation_id = observation.get(
        "observation_id",
        "UNKNOWN",
    )

    source_type = observation.get(
        "source_type",
        "SONAR",
    )

    sonar = observation.get(
        "sonar",
        {},
    )

    targets = sonar.get(
        "targets",
        [],
    )

    range_m = sonar.get(
        "range_m"
    )

    bearing_deg = sonar.get(
        "bearing_deg"
    )

    observed_at = observation.get(
        "observed_at"
    )

    if observed_at is None:
        observed_at = datetime.now(
            timezone.utc
        ).isoformat()

    hazards: List[
        UnderwaterSonarHazard
    ] = []

    for index, target in enumerate(
        targets,
        start=1,
    ):

        confidence = float(
            target.get(
                "detection_confidence",
                0.0,
            )
        )

        # Clamp confidence defensively.
        confidence = max(
            0.0,
            min(
                1.0,
                confidence,
            ),
        )

        bounding_box = target.get(
            "bounding_box",
            [],
        )

        target_class = target.get(
            "target_class"
        )

        localized = _is_localized(
            range_m,
            bearing_deg,
            vessel_latitude,
            vessel_longitude,
        )

        latitude = (
            vessel_latitude
            if localized
            else None
        )

        longitude = (
            vessel_longitude
            if localized
            else None
        )

        hazard_id = _create_hazard_id(
            observation_id,
            index,
        )

        hazard = UnderwaterSonarHazard(
            hazard_id=hazard_id,

            observation_id=observation_id,

            source_type=source_type,

            target_class=target_class,

            detection_confidence=confidence,

            bounding_box=[
                int(value)
                for value in bounding_box
            ],

            range_m=range_m,

            bearing_deg=bearing_deg,

            latitude=latitude,

            longitude=longitude,

            localized=localized,

            advisory_only=True,

            observed_at=observed_at,
        )

        _HAZARDS[hazard_id] = hazard

        hazards.append(hazard)

    return hazards


# ---------------------------------------------------------------------
# Query functions
# ---------------------------------------------------------------------

def get_sonar_hazards() -> List[Dict[str, Any]]:
    """
    Return all sonar-derived underwater hazards.
    """

    return [
        hazard.to_dict()
        for hazard in _HAZARDS.values()
    ]


def get_localized_sonar_hazards() -> List[
    Dict[str, Any]
]:
    """
    Return only hazards that have geographic
    localization.
    """

    return [
        hazard.to_dict()
        for hazard in _HAZARDS.values()
        if hazard.localized
    ]


def clear_sonar_hazards() -> None:
    """
    Clear in-memory sonar hazards.

    Useful for tests and prototype resets.
    """

    _HAZARDS.clear()