from __future__ import annotations

import math
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from typing import Dict, List, Optional, Tuple

from .cost import haversine_distance_km


# ---------------------------------------------------------------------
# Metric EPSG:3031 Projection Helper (Antarctic Polar Stereographic)
# ---------------------------------------------------------------------
def latlon_to_epsg3031(lat: float, lon: float) -> Tuple[float, float]:
    """
    Project (latitude, longitude) to EPSG:3031 Antarctic Polar Stereographic meters.
    Standard parallel: -71 S. Central meridian: 0 E. WGS84 ellipsoid.
    """
    lat_rad = math.radians(lat)
    lon_rad = math.radians(lon)
    
    # WGS84 parameters
    a = 6378137.0
    f = 1.0 / 298.257223563
    e = math.sqrt(2 * f - f * f)
    
    # Standard parallel phi_c = -71 deg
    phi_c = math.radians(-71.0)
    tc = math.tan(math.pi / 4.0 + phi_c / 2.0) * ((1.0 - e * math.sin(phi_c)) / (1.0 + e * math.sin(phi_c))) ** (e / 2.0)
    mc = math.cos(phi_c) / math.sqrt(1.0 - e * e * (math.sin(phi_c) ** 2))
    
    # Target point
    t = math.tan(math.pi / 4.0 + lat_rad / 2.0) * ((1.0 - e * math.sin(lat_rad)) / (1.0 + e * math.sin(lat_rad))) ** (e / 2.0)
    
    if abs(tc) < 1e-15:
        rho = 0.0
    else:
        rho = a * mc * t / tc
        
    x = rho * math.sin(lon_rad)
    y = -rho * math.cos(lon_rad)
    return x, y


def metric_distance_epsg3031(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Calculate distance in meters using EPSG:3031 projection."""
    x1, y1 = latlon_to_epsg3031(lat1, lon1)
    x2, y2 = latlon_to_epsg3031(lat2, lon2)
    return math.sqrt((x2 - x1) ** 2 + (y2 - y1) ** 2)


# ---------------------------------------------------------------------
# Fused Risk Grid Cell Model
# ---------------------------------------------------------------------
@dataclass
class FusedRiskCell:
    latitude: float
    longitude: float

    # Sea-ice environmental fields (UNMUTATED BY ICEBERG FUSION)
    SIC: float
    SIT: Optional[float] = None
    Ice_Type: Optional[str] = None
    Ice_Type_Norm: Optional[str] = None
    polaris_ice_category: Optional[str] = None

    RIO: Optional[float] = None
    RIV: Optional[float] = None
    rio_method: Optional[str] = None
    rio_available: bool = False

    DLIRI: Optional[float] = None
    DLIRI_category: Optional[str] = None
    effective_thickness: Optional[float] = None
    thickness_factor: Optional[float] = None

    # Iceberg hazard fields
    iceberg_presence: bool = False
    iceberg_distance_km: Optional[float] = None
    iceberg_forecast_time: Optional[str] = None

    # Risk provenance fields
    sea_ice_risk: str = "SAFE"
    sea_ice_risk_source: str = "UNKNOWN"
    iceberg_risk: str = "NONE"

    # Unified risk metrics
    risk_score: float = 0.0
    risk_score_type: str = "SIC_ONLY"

    operational_risk: str = "SAFE"
    risk_source: str = "UNKNOWN"
    confidence: float = 0.5
    status: str = "FRESH"
    fallback_used: bool = False
    fallback_reason: Optional[str] = None

    ice_type_match_method: Optional[str] = None
    ice_type_match_distance_km: Optional[float] = None
    vessel_class: str = "PC4"

    def to_dict(self) -> dict:
        return asdict(self)


# ---------------------------------------------------------------------
# In-memory Fused Risk Store (per run_id)
# ---------------------------------------------------------------------
_FUSED_GRID_STORE: Dict[str, List[FusedRiskCell]] = {}


def fuse_iceberg_and_sea_ice_risk(
    sea_ice_grid: List[dict],
    iceberg_trajectories: List[dict],
    corridor_km: float = 50.0,
    iceberg_buffer_km: float = 10.0,
    forecast_hours: float = 6.0,
    vessel_class: str = "PC4",
    run_id: str = "default_run"
) -> List[FusedRiskCell]:
    """
    Fuse iceberg hazard predictions into the master sea-ice grid (50km corridor).
    
    Guarantees:
    1. Single Source of Truth: Master SIC grid coordinates define spatial cells.
    2. Zero Mutation: Sea-ice fields (SIC, SIT, RIO, DLIRI) are preserved unchanged.
    3. Metric Buffer: EPSG:3031 metric distance <= iceberg_buffer_km * 1000.
    4. Fusion Hierarchy:
       - operational_risk = EXTREME if iceberg_presence else sea_ice_risk.
       - risk_score: Priority 1 (Iceberg=100) -> Priority 2 (RIO) -> Priority 3 (DLIRI) -> Priority 4 (100*SIC).
    """
    buffer_meters = iceberg_buffer_km * 1000.0
    fused_cells: List[FusedRiskCell] = []

    # Filter trajectory points within requested forecast_hours horizon
    valid_trajectories = [
        pt for pt in iceberg_trajectories
        if float(pt.get("forecast_hour", 0.0)) <= forecast_hours
    ]

    for cell in sea_ice_grid:
        lat = float(cell["latitude"])
        lon = float(cell["longitude"])

        sic = float(cell.get("SIC", cell.get("sea_ice", 0.0)))
        sit = cell.get("SIT")
        ice_type = cell.get("Ice_Type")
        rio = cell.get("RIO")
        dliri = cell.get("DLIRI")

        # Determine pre-iceberg sea-ice risk
        sea_ice_risk = cell.get("sea_ice_risk")
        if not sea_ice_risk:
            if sic >= 0.80 or (dliri is not None and dliri >= 75):
                sea_ice_risk = "RESTRICTED"
            elif sic >= 0.30 or (dliri is not None and dliri >= 40):
                sea_ice_risk = "CAUTION"
            else:
                sea_ice_risk = "SAFE"

        sea_ice_risk_source = cell.get("sea_ice_risk_source")
        if not sea_ice_risk_source:
            if rio is not None:
                sea_ice_risk_source = "POLARIS_RIO"
            elif dliri is not None:
                sea_ice_risk_source = "DLIRI"
            else:
                sea_ice_risk_source = "SIC_ONLY"

        # Calculate distance to nearest predicted iceberg trajectory point
        nearest_distance_m = float("inf")
        nearest_forecast_time = None

        for traj in valid_trajectories:
            t_lat = float(traj["latitude"])
            t_lon = float(traj["longitude"])
            
            # Metric EPSG:3031 distance
            dist_m = metric_distance_epsg3031(lat, lon, t_lat, t_lon)
            if dist_m < nearest_distance_m:
                nearest_distance_m = dist_m
                nearest_forecast_time = traj.get("forecast_time", traj.get("timestamp"))

        # Determine iceberg presence & risk
        iceberg_presence = False
        iceberg_distance_km = None
        iceberg_risk = "NONE"

        if nearest_distance_m <= buffer_meters:
            iceberg_presence = True
            iceberg_distance_km = round(nearest_distance_m / 1000.0, 3)
            iceberg_risk = "EXTREME"
        elif not math.isinf(nearest_distance_m):
            iceberg_distance_km = round(nearest_distance_m / 1000.0, 3)

        # Apply Fusion Rules
        if iceberg_presence:
            operational_risk = "EXTREME"
            risk_source = "ICEBERG_COLLISION_ZONE"
        else:
            operational_risk = sea_ice_risk
            risk_source = sea_ice_risk_source

        # Evaluate Priority Risk Score (0 - 100)
        if iceberg_presence:
            risk_score = 100.0
            risk_score_type = "ICEBERG_COLLISION_ZONE"
        elif cell.get("rio_available") and rio is not None:
            risk_score = float(rio)
            risk_score_type = "POLARIS_RIO"
        elif dliri is not None:
            risk_score = float(dliri)
            risk_score_type = "DLIRI"
        else:
            risk_score = round(sic * 100.0, 1)
            risk_score_type = "SIC_ONLY"

        fused_cell = FusedRiskCell(
            latitude=lat,
            longitude=lon,
            SIC=sic,
            SIT=sit,
            Ice_Type=ice_type,
            Ice_Type_Norm=cell.get("Ice_Type_Norm"),
            polaris_ice_category=cell.get("polaris_ice_category"),
            RIO=rio,
            RIV=cell.get("RIV"),
            rio_method=cell.get("rio_method"),
            rio_available=bool(cell.get("rio_available", False)),
            DLIRI=dliri,
            DLIRI_category=cell.get("DLIRI_category"),
            effective_thickness=cell.get("effective_thickness"),
            thickness_factor=cell.get("thickness_factor"),
            iceberg_presence=iceberg_presence,
            iceberg_distance_km=iceberg_distance_km,
            iceberg_forecast_time=nearest_forecast_time,
            sea_ice_risk=sea_ice_risk,
            sea_ice_risk_source=sea_ice_risk_source,
            iceberg_risk=iceberg_risk,
            risk_score=risk_score,
            risk_score_type=risk_score_type,
            operational_risk=operational_risk,
            risk_source=risk_source,
            confidence=float(cell.get("confidence", 0.8)),
            status=cell.get("status", "FRESH"),
            fallback_used=bool(cell.get("fallback_used", False)),
            fallback_reason=cell.get("fallback_reason"),
            ice_type_match_method=cell.get("ice_type_match_method"),
            ice_type_match_distance_km=cell.get("ice_type_match_distance_km"),
            vessel_class=vessel_class,
        )
        fused_cells.append(fused_cell)

    _FUSED_GRID_STORE[run_id] = fused_cells
    return fused_cells


def get_fused_risk(
    latitude: float,
    longitude: float,
    run_id: str = "default_run",
    max_lookup_distance_km: float = 50.0
) -> Optional[dict]:
    """
    NMEA Lookup: Queries the single fused risk grid for the specified run_id.
    Finds nearest grid cell within 50 km corridor and returns fused risk.
    """
    grid = _FUSED_GRID_STORE.get(run_id)
    if not grid:
        return None

    best_cell = None
    best_distance = float("inf")

    for cell in grid:
        dist_km = haversine_distance_km(latitude, longitude, cell.latitude, cell.longitude)
        if dist_km < best_distance:
            best_distance = dist_km
            best_cell = cell

    if best_cell is None or best_distance > max_lookup_distance_km:
        return None

    cell_dict = best_cell.to_dict()
    cell_dict["lookup_distance_km"] = round(best_distance, 3)
    return cell_dict


def clear_fused_grid_store(run_id: Optional[str] = None) -> None:
    """Clear fused grid store for tests or reset."""
    if run_id:
        _FUSED_GRID_STORE.pop(run_id, None)
    else:
        _FUSED_GRID_STORE.clear()
