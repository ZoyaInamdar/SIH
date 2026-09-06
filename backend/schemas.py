from typing import List, Optional

from pydantic import BaseModel, Field


class ShipPosition(BaseModel):

    latitude: float = Field(
        ge=-90,
        le=90
    )

    longitude: float = Field(
        ge=-180,
        le=180
    )

    speed_knots: float = Field(
        ge=0
    )

    heading_degrees: float = Field(
        ge=0,
        lt=360
    )

    timestamp: str


class Iceberg(BaseModel):

    iceberg_id: str

    current_latitude: float = Field(
        ge=-90,
        le=90
    )

    current_longitude: float = Field(
        ge=-180,
        le=180
    )

    timestamp: str

    length_m: Optional[float] = None
    width_m: Optional[float] = None
    freeboard_m: Optional[float] = None

    shape_class: Optional[str] = None

    estimated_draft_m: Optional[float] = None
    draft_uncertainty_m: Optional[float] = None

    drift_speed_knots: Optional[float] = None

    drift_direction_degrees: Optional[float] = Field(
        default=None,
        ge=0,
        lt=360
    )

    predicted_latitude: Optional[float] = Field(
        default=None,
        ge=-90,
        le=90
    )

    predicted_longitude: Optional[float] = Field(
        default=None,
        ge=-180,
        le=180
    )

    forecast_time: Optional[str] = None

    bias_corrected_latitude: Optional[float] = Field(
        default=None,
        ge=-90,
        le=90
    )

    bias_corrected_longitude: Optional[float] = Field(
        default=None,
        ge=-180,
        le=180
    )

    bias_correction_applied: bool = False

    status: str = "estimated"

    confidence: float = Field(
        default=0.5,
        ge=0,
        le=1
    )

    source: str = "unknown"


class SeaIceZone(BaseModel):

    latitude: float = Field(
        ge=-90,
        le=90
    )

    longitude: float = Field(
        ge=-180,
        le=180
    )

    concentration: float = Field(
        ge=0,
        le=1
    )

    risk_level: str

    confidence: float = Field(
        default=0.5,
        ge=0,
        le=1
    )

    timestamp: str


class Hazard(BaseModel):

    id: str

    hazard_type: str

    latitude: float = Field(
        ge=-90,
        le=90
    )

    longitude: float = Field(
        ge=-180,
        le=180
    )

    radius_m: float = Field(
        ge=0
    )

    risk_level: str

    confidence: float = Field(
        default=0.5,
        ge=0,
        le=1
    )

    source: str

    timestamp: str


class RoutePoint(BaseModel):

    latitude: float = Field(
        ge=-90,
        le=90
    )

    longitude: float = Field(
        ge=-180,
        le=180
    )


class Route(BaseModel):

    route_id: str

    points: List[RoutePoint]

    distance_km: float

    estimated_fuel_cost: Optional[float] = None

    risk_level: str

    timestamp: str


class RouteRequest(BaseModel):

    start_latitude: float = Field(
        ge=-90,
        le=90
    )

    start_longitude: float = Field(
        ge=-180,
        le=180
    )

    destination_latitude: float = Field(
        ge=-90,
        le=90
    )

    destination_longitude: float = Field(
        ge=-180,
        le=180
    )

    vessel_draft_m: float = Field(
        default=6.0,
        ge=0
    )

    grid_resolution: float = Field(
        default=0.1,
        gt=0
    )


class VesselProfileRequest(BaseModel):

    vessel_id: str

    draft_m: float = Field(
        gt=0
    )

    fuel_rate_l_per_km: Optional[float] = Field(
        default=None,
        gt=0
    )

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

