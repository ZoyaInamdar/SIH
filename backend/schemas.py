from __future__ import annotations

from typing import List, Optional
from pydantic import BaseModel, Field
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


class CrewHazardReportRequest(BaseModel):
    description: str
    latitude: float = Field(ge=-90, le=90)
    longitude: float = Field(ge=-180, le=180)
    vessel_id: Optional[str] = "MV-VG-001"


class AISVessel(BaseModel):
    vessel_id: str
    name: str
    latitude: float = Field(ge=-90, le=90)
    longitude: float = Field(ge=-180, le=180)
    speed_knots: float = Field(default=0.0, ge=0)
    heading_degrees: float = Field(default=0.0, ge=0, lt=360)
    is_ncpor_fleet: bool = False
    timestamp: str


class RouteComparisonResponse(BaseModel):
    status: str
    standard_route: dict
    fuel_efficient_route: dict
    distance_increase_percent: float
    fuel_saved_percent: float
    summary: str


class RiskFusionRequest(BaseModel):
    run_id: str = "route_A"
    vessel_class: str = "PC4"
    corridor_km: float = Field(default=50.0, gt=0)
    iceberg_buffer_km: float = Field(default=10.0, gt=0)
    forecast_hours: float = Field(default=6.0, ge=0)
    enable_iceberg_prediction: bool = True


class DashboardSummary(BaseModel):
    status: str
    latest_ship_position: Optional[dict] = None
    iceberg_count: int = 0
    hazard_count: int = 0
    ais_vessel_count: int = 0
    route_count: int = 0
    freshness_status: str = "FRESH"
    system_health: dict = {}
    timestamp: str





@dataclass
class SonarTarget:
    """
    Represents one underwater target detected in an FLS sonar image.

    The detector provides:
        - bounding_box
        - detection_confidence
        - target_class

    The spatialization layer provides:
        - range_m
        - bearing_deg
        - latitude
        - longitude
    """

    # -------------------------
    # AI detection information
    # -------------------------

    bounding_box: Tuple[int, int, int, int]
    detection_confidence: float
    target_class: Optional[str] = None

    # -------------------------
    # Spatialization information
    # -------------------------

    range_m: Optional[float] = None
    bearing_deg: Optional[float] = None

    # Estimated geographic position
    latitude: Optional[float] = None
    longitude: Optional[float] = None

    def to_dict(self) -> dict:
        """
        Convert the sonar target into a JSON-compatible dictionary.
        """

        return {
            "bounding_box": list(self.bounding_box),

            "detection_confidence": round(
                float(self.detection_confidence),
                4,
            ),

            "target_class": self.target_class,

            "range_m": (
                round(float(self.range_m), 2)
                if self.range_m is not None
                else None
            ),

            "bearing_deg": (
                round(float(self.bearing_deg), 2)
                if self.bearing_deg is not None
                else None
            ),

            "latitude": (
                round(float(self.latitude), 7)
                if self.latitude is not None
                else None
            ),

            "longitude": (
                round(float(self.longitude), 7)
                if self.longitude is not None
                else None
            ),
        }


# ============================================================
# SONAR OBSERVATION
# ============================================================

@dataclass
class SonarObservation:
    """
    Represents one sonar observation generated by the vessel.

    One observation can contain multiple detected targets.
    """

    observation_id: str

    source_type: str

    targets: List[SonarTarget]

    # --------------------------------------------------------
    # These fields are retained for compatibility with the
    # original sonar observation structure.
    #
    # For multiple detections, the authoritative range/bearing
    # values are stored inside each SonarTarget.
    # --------------------------------------------------------

    range_m: Optional[float] = None
    bearing_deg: Optional[float] = None

    observed_at: str = ""

    def to_dict(self) -> dict:
        """
        Convert the complete sonar observation into a
        JSON-compatible dictionary.
        """

        return {
            "observation_id": self.observation_id,

            "source_type": self.source_type,

            "sonar": {
                "targets": [
                    target.to_dict()
                    for target in self.targets
                ],

                "range_m": (
                    round(float(self.range_m), 2)
                    if self.range_m is not None
                    else None
                ),

                "bearing_deg": (
                    round(float(self.bearing_deg), 2)
                    if self.bearing_deg is not None
                    else None
                ),
            },

            "observed_at": self.observed_at,
        }

