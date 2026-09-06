from pydantic import BaseModel, Field
from typing import List, Optional


# --------------------------------------------------
# SHIP
# --------------------------------------------------

class ShipPosition(BaseModel):
    latitude: float = Field(ge=-90, le=90)
    longitude: float = Field(ge=-180, le=180)
    speed_knots: float = Field(ge=0)
    heading_degrees: float = Field(ge=0, lt=360)
    timestamp: str


# --------------------------------------------------
# ICEBERG
# --------------------------------------------------

class Iceberg(BaseModel):
    id: str
    latitude: float = Field(ge=-90, le=90)
    longitude: float = Field(ge=-180, le=180)

    length_m: Optional[float] = None
    width_m: Optional[float] = None
    freeboard_m: Optional[float] = None
    estimated_draft_m: Optional[float] = None

    drift_speed_knots: Optional[float] = None
    drift_direction_degrees: Optional[float] = None

    status: str = "estimated"
    confidence: float = Field(default=0.5, ge=0, le=1)

    timestamp: str


# --------------------------------------------------
# SEA ICE
# --------------------------------------------------

class SeaIceZone(BaseModel):
    latitude: float = Field(ge=-90, le=90)
    longitude: float = Field(ge=-180, le=180)

    concentration: float = Field(ge=0, le=1)

    risk_level: str
    confidence: float = Field(default=0.5, ge=0, le=1)

    timestamp: str


# --------------------------------------------------
# HAZARD
# --------------------------------------------------

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


# --------------------------------------------------
# ROUTE
# --------------------------------------------------

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