from __future__ import annotations

import math
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

from ..schemas import RiskState
from ..routing.cost import haversine_distance_km, movement_cost, sea_ice_penalty
from ..routing.risk_fusion import metric_distance_epsg3031
from ..routing.ice_zones import classify_ice_zone
from ..routing.grid import is_antarctic_land


# ---------------------------------------------------------------------
# In-Memory RiskState Central Store (indexed by run_id)
# ---------------------------------------------------------------------
_RISK_STATE_STORE: Dict[str, List[RiskState]] = {}


# ---------------------------------------------------------------------
# Single Node / Cell RiskState Evaluator
# ---------------------------------------------------------------------
def evaluate_node_risk_state(
    latitude: float,
    longitude: float,
    sic: float = 0.0,
    sit_m: Optional[float] = None,
    ice_type: Optional[str] = None,
    ice_trend_slope: Optional[float] = None,
    sea_ice_risk: Optional[str] = None,
    sea_ice_confidence: float = 0.8,
    iceberg_trajectories: Optional[List[dict]] = None,
    iceberg_buffer_km: float = 10.0,
    forecast_hours: float = 6.0,
    vessel_class: str = "PC4",
    rio: Optional[float] = None,
    dliri: Optional[float] = None,
    node_id: Optional[str] = None,
    timestamp: Optional[str] = None,
) -> RiskState:
    """
    Evaluates and returns a single converged RiskState for a specific geographic coordinate.
    Pure interception: does not alter model math, but synthesizes outputs from:
      1. Sea-ice forecast (SIC, SIT, slope, WMO zone)
      2. Iceberg drift & draft (trajectories, sonar-corrected draft/confidence, buffer)
      3. Vessel & routing capability (POLARIS RIO, FSICR, speed penalty, land blockage)
    """
    if timestamp is None:
        timestamp = datetime.now(timezone.utc).isoformat()
    if node_id is None:
        node_id = f"node_{latitude:.4f}_{longitude:.4f}"

    # 1. Land / Navigation Check
    is_land = is_antarctic_land(latitude, longitude)
    if is_land:
        return RiskState(
            node_id=node_id,
            latitude=latitude,
            longitude=longitude,
            timestamp=timestamp,
            sic=1.0,
            wmo_zone="AVOID",
            sea_ice_risk="RESTRICTED",
            sea_ice_confidence=1.0,
            iceberg_presence=False,
            iceberg_risk="NONE",
            vessel_class=vessel_class,
            navigable=False,
            speed_penalty_factor=999.0,
            operational_risk="BLOCKED",
            risk_score=100.0,
            primary_risk_source="LAND",
            overall_confidence=1.0,
            data_freshness="FRESH",
        )

    # 2. Sea-Ice Sub-state
    sic_clamped = max(0.0, min(1.0, float(sic)))
    wmo_ice_zone = classify_ice_zone(sic_clamped)

    if not sea_ice_risk:
        if sic_clamped >= 0.80 or (dliri is not None and dliri >= 75):
            sea_ice_risk = "RESTRICTED"
        elif sic_clamped >= 0.30 or (dliri is not None and dliri >= 40):
            sea_ice_risk = "CAUTION"
        else:
            sea_ice_risk = "SAFE"

    # 3. Iceberg Hazard & Sonar Feedback Sub-state
    buffer_meters = iceberg_buffer_km * 1000.0
    valid_trajectories = [
        pt for pt in (iceberg_trajectories or [])
        if float(pt.get("forecast_hour", 0.0)) <= forecast_hours
    ]

    nearest_dist_m = float("inf")
    nearest_berg_id = None
    nearest_draft_m = None
    nearest_confidence = None
    nearest_forecast_time = None

    for traj in valid_trajectories:
        t_lat = float(traj.get("latitude", 0.0))
        t_lon = float(traj.get("longitude", 0.0))
        dist_m = metric_distance_epsg3031(latitude, longitude, t_lat, t_lon)
        if dist_m < nearest_dist_m:
            nearest_dist_m = dist_m
            nearest_berg_id = traj.get("iceberg_id") or traj.get("id")
            # Sonar-updated draft & confidence propagate directly here
            nearest_draft_m = traj.get("estimated_draft_m")
            nearest_confidence = traj.get("confidence")
            nearest_forecast_time = traj.get("forecast_time") or traj.get("timestamp")

    iceberg_presence = False
    iceberg_distance_km = None
    iceberg_risk = "NONE"

    if nearest_dist_m <= buffer_meters:
        iceberg_presence = True
        iceberg_distance_km = round(nearest_dist_m / 1000.0, 3)
        iceberg_risk = "EXTREME"
    elif not math.isinf(nearest_dist_m):
        iceberg_distance_km = round(nearest_dist_m / 1000.0, 3)

    # 4. Routing Speed / Movement Cost Penalty
    penalty = sea_ice_penalty(sic_clamped)
    if iceberg_presence:
        penalty += 50.0  # Massive penalty for pathfinder avoidance

    # 5. Converged Unified Risk Evaluation
    if iceberg_presence:
        operational_risk = "EXTREME"
        risk_score = 100.0
        primary_risk_source = "ICEBERG_COLLISION_ZONE"
        overall_conf = nearest_confidence if nearest_confidence is not None else 0.90
    elif rio is not None:
        risk_score = float(rio)
        primary_risk_source = "POLARIS_RIO"
        operational_risk = sea_ice_risk
        overall_conf = sea_ice_confidence
    elif dliri is not None:
        risk_score = float(dliri)
        primary_risk_source = "DLIRI"
        operational_risk = sea_ice_risk
        overall_conf = sea_ice_confidence
    else:
        risk_score = round(sic_clamped * 100.0, 1)
        primary_risk_source = "SIC_ONLY" if sic_clamped > 0.0 else "OPEN_WATER"
        operational_risk = sea_ice_risk
        overall_conf = sea_ice_confidence

    return RiskState(
        node_id=node_id,
        latitude=latitude,
        longitude=longitude,
        timestamp=timestamp,
        sic=sic_clamped,
        sit_m=sit_m,
        ice_type=ice_type,
        ice_trend_slope=ice_trend_slope,
        wmo_zone=wmo_ice_zone.zone.upper(),
        sea_ice_risk=sea_ice_risk,
        sea_ice_confidence=sea_ice_confidence,
        iceberg_presence=iceberg_presence,
        nearest_iceberg_id=nearest_berg_id,
        iceberg_distance_km=iceberg_distance_km,
        estimated_draft_m=nearest_draft_m,
        iceberg_confidence=nearest_confidence,
        iceberg_risk=iceberg_risk,
        iceberg_forecast_time=nearest_forecast_time,
        vessel_class=vessel_class,
        polaris_rio=rio,
        polaris_riv=None,
        fsicr_channel_resistance_kn=None,
        navigable=not is_land and (operational_risk != "EXTREME"),
        speed_penalty_factor=round(penalty, 2),
        operational_risk=operational_risk,
        risk_score=risk_score,
        primary_risk_source=primary_risk_source,
        overall_confidence=round(overall_conf, 2),
        data_freshness="FRESH",
    )


# ---------------------------------------------------------------------
# Central Aggregation Controller
# ---------------------------------------------------------------------
def aggregate_risk_state_grid(
    sea_ice_grid: List[dict],
    iceberg_records: List[dict],
    corridor_km: float = 50.0,
    iceberg_buffer_km: float = 10.0,
    forecast_hours: float = 6.0,
    vessel_class: str = "PC4",
    run_id: str = "default_run",
) -> List[RiskState]:
    """
    Main Aggregation Controller:
    Takes raw model outputs (Sea Ice Forecast, Iceberg Records with Sonar feedback, Vessel profile),
    computes the unified RiskState for each geographic cell, and saves to the central store.
    """
    # Build trajectory points from iceberg records (propagating sonar-corrected draft and confidence)
    trajectories = []
    for icb in iceberg_records:
        lat = icb.get("predicted_latitude") if icb.get("predicted_latitude") is not None else icb.get("current_latitude")
        lon = icb.get("predicted_longitude") if icb.get("predicted_longitude") is not None else icb.get("current_longitude")
        if lat is not None and lon is not None:
            trajectories.append({
                "iceberg_id": icb.get("iceberg_id") or icb.get("id"),
                "latitude": float(lat),
                "longitude": float(lon),
                "forecast_hour": float(icb.get("forecast_hour", 0.0)),
                "forecast_time": icb.get("forecast_time") or icb.get("timestamp"),
                "estimated_draft_m": icb.get("estimated_draft_m"),
                "confidence": icb.get("confidence"),
                "source": icb.get("source", "unknown"),
            })

    now_iso = datetime.now(timezone.utc).isoformat()
    risk_states: List[RiskState] = []

    for cell in sea_ice_grid:
        lat = float(cell["latitude"])
        lon = float(cell["longitude"])
        sic = float(cell.get("SIC", cell.get("sea_ice", cell.get("concentration", 0.0))))
        sit_m = cell.get("SIT") or cell.get("ice_thickness_m")
        ice_type = cell.get("Ice_Type") or cell.get("ice_type")
        ice_slope = cell.get("ice_trend_slope") or cell.get("slope_per_hour")
        sea_ice_risk = cell.get("sea_ice_risk")
        sea_ice_conf = float(cell.get("confidence", 0.8))
        rio = cell.get("RIO")
        dliri = cell.get("DLIRI")
        node_id = cell.get("id") or cell.get("node_id")

        rs = evaluate_node_risk_state(
            latitude=lat,
            longitude=lon,
            sic=sic,
            sit_m=sit_m,
            ice_type=ice_type,
            ice_trend_slope=ice_slope,
            sea_ice_risk=sea_ice_risk,
            sea_ice_confidence=sea_ice_conf,
            iceberg_trajectories=trajectories,
            iceberg_buffer_km=iceberg_buffer_km,
            forecast_hours=forecast_hours,
            vessel_class=vessel_class,
            rio=rio,
            dliri=dliri,
            node_id=str(node_id) if node_id else None,
            timestamp=now_iso,
        )
        risk_states.append(rs)

    _RISK_STATE_STORE[run_id] = risk_states
    return risk_states


# ---------------------------------------------------------------------
# Unified Consumer Data-Access Methods
# ---------------------------------------------------------------------
def get_risk_state_at(
    latitude: float,
    longitude: float,
    run_id: str = "default_run",
    max_lookup_distance_km: float = 50.0,
) -> Optional[RiskState]:
    """
    NMEA / Telemetry Data Access:
    Queries the exact precomputed RiskState for the given position.
    Finds nearest node within max_lookup_distance_km corridor.
    """
    grid = _RISK_STATE_STORE.get(run_id)
    if not grid:
        return None

    best_node = None
    best_dist = float("inf")

    for node in grid:
        dist_km = haversine_distance_km(latitude, longitude, node.latitude, node.longitude)
        if dist_km < best_dist:
            best_dist = dist_km
            best_node = node

    if best_node is None or best_dist > max_lookup_distance_km:
        return None

    return best_node


def get_risk_state_grid(run_id: str = "default_run") -> List[RiskState]:
    """
    Routing & Map Data Access:
    Returns the complete precomputed RiskState grid for the given run_id.
    """
    return _RISK_STATE_STORE.get(run_id, [])


def get_risk_state_geojson(run_id: str = "default_run") -> dict:
    """
    2D Map & 3D Globe Data Access:
    Returns a GeoJSON FeatureCollection of all precomputed RiskState nodes.
    """
    nodes = get_risk_state_grid(run_id)
    return {
        "type": "FeatureCollection",
        "features": [node.to_geojson_feature() for node in nodes]
    }


def clear_risk_state_store(run_id: Optional[str] = None) -> None:
    """Clears store for testing or pipeline reset."""
    if run_id:
        _RISK_STATE_STORE.pop(run_id, None)
    else:
        _RISK_STATE_STORE.clear()
