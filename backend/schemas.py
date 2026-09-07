from typing import List, Optional

from pydantic import BaseModel, Field

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import List, Optional, Tuple


class ShipPosition(BaseModel):
    latitude: float = Field(ge=-90, le=90)
    longitude: float = Field(ge=-180, le=180)
    speed_knots: float = Field(ge=0)
    heading_degrees: float = Field(ge=0, lt=360)
    timestamp: str


class Iceberg(BaseModel):
    iceberg_id: str
    current_latitude: float = Field(ge=-90, le=90)
    current_longitude: float = Field(ge=-180, le=180)
    timestamp: str
    length_m: Optional[float] = None
    width_m: Optional[float] = None
    freeboard_m: Optional[float] = None
    shape_class: Optional[str] = None
    estimated_draft_m: Optional[float] = None
    draft_uncertainty_m: Optional[float] = None
    drift_speed_knots: Optional[float] = None
    drift_direction_degrees: Optional[float] = Field(default=None, ge=0, lt=360)
    predicted_latitude: Optional[float] = Field(default=None, ge=-90, le=90)
    predicted_longitude: Optional[float] = Field(default=None, ge=-180, le=180)
    forecast_time: Optional[str] = None
    bias_corrected_latitude: Optional[float] = Field(default=None, ge=-90, le=90)
    bias_corrected_longitude: Optional[float] = Field(default=None, ge=-180, le=180)
    bias_correction_applied: bool = False
    status: str = "estimated"
    confidence: float = Field(default=0.5, ge=0, le=1)
    source: str = "unknown"


class SeaIceZone(BaseModel):
    latitude: float = Field(ge=-90, le=90)
    longitude: float = Field(ge=-180, le=180)
    concentration: float = Field(ge=0, le=1)
    risk_level: str
    confidence: float = Field(default=0.5, ge=0, le=1)
    timestamp: str


class Hazard(BaseModel):
    id: str
    hazard_type: str
    latitude: float = Field(ge=-90, le=90)
    longitude: float = Field(ge=-180, le=180)
    radius_m: float = Field(ge=0)
    risk_level: str
    confidence: float = Field(default=0.5, ge=0, le=1)
    source: str
    timestamp: str


class RoutePoint(BaseModel):
    latitude: float = Field(ge=-90, le=90)
    longitude: float = Field(ge=-180, le=180)


class Route(BaseModel):
    route_id: str
    points: List[RoutePoint]
    distance_km: float
    estimated_fuel_cost: Optional[float] = None
    risk_level: str
    timestamp: str


class RouteRequest(BaseModel):
    start_latitude: float = Field(ge=-90, le=90)
    start_longitude: float = Field(ge=-180, le=180)
    destination_latitude: float = Field(ge=-90, le=90)
    destination_longitude: float = Field(ge=-180, le=180)
    grid_resolution: float = Field(default=0.1, gt=0)
    vessel_id: str = Field(default="MV-VG-001")


class VesselProfileRequest(BaseModel):
    vessel_id: str
    draft_m: float = Field(gt=0)
    fuel_rate_l_per_km: Optional[float] = Field(default=None, gt=0)
    ice_class: Optional[str] = None


class SystemStatus(BaseModel):
    backend: str
    database: str
    modules: dict


class DataResponse(BaseModel):
    status: str
    count: int
    data: list
    system: dict


class ForecastObservation(BaseModel):
    timestamp_hours: float
    grid: List[List[float]]


class ForecastRequest(BaseModel):
    observations: List[ForecastObservation]
    horizon_hours: float = Field(default=24.0, ge=0)


@dataclass
class SonarTarget:
    """
    One detected sonar target.
    """

    bounding_box: Tuple[int, int, int, int]

    detection_confidence: float

    target_class: Optional[str] = None

    def to_dict(self):
        return {
            "bounding_box": list(
                self.bounding_box
            ),

            "detection_confidence": round(
                self.detection_confidence,
                4,
            ),

            "target_class": self.target_class,
        }


@dataclass
class SonarObservation:
    """
    Structured observation generated from an FLS sonar image.
    """

    observation_id: str

    source_type: str

    targets: List[SonarTarget]

    range_m: Optional[float]

    bearing_deg: Optional[float]

    observed_at: str

    def to_dict(self):

        return {
            "observation_id":
                self.observation_id,

            "source_type":
                self.source_type,

            "sonar": {

                "targets": [
                    target.to_dict()
                    for target in self.targets
                ],

                "range_m":
                    self.range_m,

                "bearing_deg":
                    self.bearing_deg,
            },

            "observed_at":
                self.observed_at,
        }


def create_observation(
    detections,
    observation_id: str,
    range_m: Optional[float] = None,
    bearing_deg: Optional[float] = None,
) -> SonarObservation:

    targets = [
        SonarTarget(
            bounding_box=detection.bbox,
            detection_confidence=(
                detection.detection_score
            ),
            target_class=(
                detection.target_class
            ),
        )

        for detection in detections
    ]

    return SonarObservation(
        observation_id=observation_id,

        source_type="SONAR",

        targets=targets,

        range_m=range_m,

        bearing_deg=bearing_deg,

        observed_at=datetime.now(
            timezone.utc
        ).isoformat(),
    )