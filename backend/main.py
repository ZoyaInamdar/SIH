import json
import math
import uuid
import numpy as np

from datetime import datetime, timezone, date

from fastapi import (
    FastAPI,
    HTTPException,
    WebSocket,
    WebSocketDisconnect
)
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response

from .database import get_connection, initialize_database
from .schemas import (
    ShipPosition, Iceberg, SeaIceZone, Hazard, Route, 
    RouteRequest, VesselProfileRequest, ForecastRequest,
    CrewHazardReportRequest, AISVessel, RouteComparisonResponse
)
from .routing.astar import AStarRouter
from .routing.grid import create_ocean_grid
from .routing.cost import haversine_distance_km
from .routing.rtz import route_to_rtz
from .routing.fuel import VesselProfile, estimate_fuel, get_vessel_profile
from .routing.ice_class import assess_fsicr_condition, VesselGeometry, FSICRClass
from .routing.ice_persistence import run_persistence_baseline, IceRasterObservation
from .routing.raster_to_geojson import raster_to_geojson
from .utils.freshness import get_freshness_status
from .utils.confidence import get_confidence_status
from .utils.daylight import calculate_daylight_status
from .utils.responses import build_data_response
from .services.nmea_services import nmea_service
from .sonar_api import router as sonar_router


app = FastAPI(title="Antarctic Navigation Decision Support API", version="1.0.0")
app.include_router(sonar_router)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"]
)

initialize_database()

# ---------------------------------------------------------
# GENERAL
# ---------------------------------------------------------
@app.get("/")
def root():
    return {"name": "Antarctic Navigation Decision Support", "status": "running", "advisory_only": True}

@app.get("/health")
def health():
    return {"status": "healthy"}

# ---------------------------------------------------------
# SHIP
# ---------------------------------------------------------
@app.post("/ship/position")
def update_ship_position(position: ShipPosition):
    connection = get_connection()
    cursor = connection.cursor()
    cursor.execute(
        """
        INSERT INTO ship_positions (latitude, longitude, speed_knots, heading_degrees, timestamp)
        VALUES (?, ?, ?, ?, ?)
        """,
        (position.latitude, position.longitude, position.speed_knots, position.heading_degrees, position.timestamp)
    )
    connection.commit()
    connection.close()
    return {"status": "success", "data": position.model_dump()}

@app.get("/ship/latest")
def get_latest_ship_position():
    connection = get_connection()
    cursor = connection.cursor()
    cursor.execute("SELECT * FROM ship_positions ORDER BY id DESC LIMIT 1")
    row = cursor.fetchone()
    connection.close()
    
    if row is None:
        return {"status": "success", "data": None}
    
    data = dict(row)
    data.update(get_freshness_status(data["timestamp"]))
    return {"status": "success", "data": data}

# ---------------------------------------------------------
# NMEA WEBSOCKET
# ---------------------------------------------------------
@app.websocket("/ws/nmea")
async def nmea_websocket(websocket: WebSocket):
    await websocket.accept()
    await nmea_service.register(websocket)
    try:
        while True:
            sentence = await websocket.receive_text()
            position = nmea_service.parse_sentence(sentence)
            if position is None:
                await websocket.send_json({"status": "error", "message": "Invalid or unsupported NMEA sentence."})
                continue
            
            try:
                validated = ShipPosition(**position)
            except Exception as error:
                await websocket.send_json({"status": "error", "message": str(error)})
                continue
            
            connection = get_connection()
            cursor = connection.cursor()
            cursor.execute(
                """
                INSERT INTO ship_positions (latitude, longitude, speed_knots, heading_degrees, timestamp)
                VALUES (?, ?, ?, ?, ?)
                """,
                (validated.latitude, validated.longitude, validated.speed_knots, validated.heading_degrees, datetime.now(timezone.utc).isoformat())
            )
            connection.commit()
            connection.close()
            await nmea_service.broadcast(validated.model_dump())
    
    except WebSocketDisconnect:
        await nmea_service.unregister(websocket)
    except Exception:
        await nmea_service.unregister(websocket)

# ---------------------------------------------------------
# ICEBERGS
# ---------------------------------------------------------
@app.post("/icebergs")
def add_iceberg(iceberg: Iceberg):
    connection = get_connection()
    cursor = connection.cursor()
    cursor.execute(
        """
        INSERT OR REPLACE INTO icebergs
        (iceberg_id, current_latitude, current_longitude, timestamp, length_m, width_m, freeboard_m, shape_class, estimated_draft_m, draft_uncertainty_m, drift_speed_knots, drift_direction_degrees, predicted_latitude, predicted_longitude, forecast_time, bias_corrected_latitude, bias_corrected_longitude, bias_correction_applied, status, confidence, source, last_updated)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (iceberg.iceberg_id, iceberg.current_latitude, iceberg.current_longitude, iceberg.timestamp, iceberg.length_m, iceberg.width_m, iceberg.freeboard_m, iceberg.shape_class, iceberg.estimated_draft_m, iceberg.draft_uncertainty_m, iceberg.drift_speed_knots, iceberg.drift_direction_degrees, iceberg.predicted_latitude, iceberg.predicted_longitude, iceberg.forecast_time, iceberg.bias_corrected_latitude, iceberg.bias_corrected_longitude, int(iceberg.bias_correction_applied), iceberg.status, iceberg.confidence, iceberg.source, datetime.now(timezone.utc).isoformat())
    )
    connection.commit()
    connection.close()
    return {"status": "success", "data": iceberg.model_dump()}

@app.get("/icebergs")
def get_icebergs():
    connection = get_connection()
    cursor = connection.cursor()
    cursor.execute("SELECT * FROM icebergs ORDER BY iceberg_id")
    rows = cursor.fetchall()
    connection.close()
    
    result = []
    for row in rows:
        data = dict(row)
        data.update(get_freshness_status(data["timestamp"]))
        data.update(get_confidence_status(data.get("confidence")))
        result.append(data)
    return build_data_response(result)

# ---------------------------------------------------------
# SEA ICE
# ---------------------------------------------------------
@app.post("/sea-ice")
def add_sea_ice(zone: SeaIceZone):
    connection = get_connection()
    cursor = connection.cursor()
    cursor.execute(
        "INSERT INTO sea_ice (latitude, longitude, concentration, risk_level, confidence, timestamp) VALUES (?, ?, ?, ?, ?, ?)",
        (zone.latitude, zone.longitude, zone.concentration, zone.risk_level, zone.confidence, zone.timestamp)
    )
    connection.commit()
    connection.close()
    return {"status": "success", "data": zone.model_dump()}

@app.get("/sea-ice")
def get_sea_ice():
    connection = get_connection()
    cursor = connection.cursor()
    cursor.execute("SELECT * FROM sea_ice ORDER BY id")
    rows = cursor.fetchall()
    connection.close()
    
    result = []
    for row in rows:
        data = dict(row)
        data.update(get_freshness_status(data["timestamp"]))
        data.update(get_confidence_status(data["confidence"]))
        result.append(data)
    return build_data_response(result)

@app.post("/sea-ice/forecast")
def forecast_sea_ice(request: ForecastRequest):
    if len(request.observations) < 2:
        raise HTTPException(status_code=400, detail="At least 2 historical grids required for baseline.")
    
    obs_list = [
        IceRasterObservation(
            timestamp_hours=obs.timestamp_hours,
            concentration=np.array(obs.grid, dtype=float)
        )
        for obs in request.observations
    ]

    forecast = run_persistence_baseline(obs_list, request.horizon_hours)
    
    transform = (-500000, 1000000, 1000, -1000) 
    
    geojson = raster_to_geojson(
        raster=forecast.predicted_concentration,
        transform=transform,
        threshold=0.15,
        source_crs="EPSG:3031",
        target_crs="EPSG:4326"
    )

    return {
        "status": "success",
        "forecast_time_hours": forecast.forecast_time_hours,
        "hazard_polygons": geojson
    }

# ---------------------------------------------------------
# HAZARDS
# ---------------------------------------------------------
@app.post("/hazards")
def add_hazard(hazard: Hazard):
    connection = get_connection()
    cursor = connection.cursor()
    cursor.execute(
        "INSERT OR REPLACE INTO hazards (id, hazard_type, latitude, longitude, radius_m, risk_level, confidence, source, timestamp) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (hazard.id, hazard.hazard_type, hazard.latitude, hazard.longitude, hazard.radius_m, hazard.risk_level, hazard.confidence, hazard.source, hazard.timestamp)
    )
    connection.commit()
    connection.close()
    return {"status": "success", "data": hazard.model_dump()}

@app.get("/hazards")
def get_hazards():
    connection = get_connection()
    cursor = connection.cursor()
    cursor.execute("SELECT * FROM hazards ORDER BY id")
    rows = cursor.fetchall()
    connection.close()
    
    result = []
    for row in rows:
        data = dict(row)
        data.update(get_freshness_status(data["timestamp"]))
        data.update(get_confidence_status(data["confidence"]))
        result.append(data)
    return build_data_response(result)

@app.post("/hazards/crew-report")
def create_crew_hazard_report(request: CrewHazardReportRequest):
    hazard_id = "CREW-HZ-" + uuid.uuid4().hex[:8].upper()
    now_iso = datetime.now(timezone.utc).isoformat()
    
    hazard_data = {
        "id": hazard_id,
        "hazard_type": "CREW_REPORTED_HAZARD",
        "latitude": request.latitude,
        "longitude": request.longitude,
        "radius_m": 500.0,  # Prototype conservative safety buffer: 500 m
        "risk_level": "caution",
        "confidence": 0.5,
        "source": "CREW_REPORT",
        "status": "UNVALIDATED_OBSERVATION",
        "description": request.description,
        "timestamp": now_iso
    }
    
    connection = get_connection()
    cursor = connection.cursor()
    cursor.execute(
        "INSERT OR REPLACE INTO hazards (id, hazard_type, latitude, longitude, radius_m, risk_level, confidence, source, timestamp) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (hazard_data["id"], hazard_data["hazard_type"], hazard_data["latitude"], hazard_data["longitude"], hazard_data["radius_m"], hazard_data["risk_level"], hazard_data["confidence"], hazard_data["source"], hazard_data["timestamp"])
    )
    connection.commit()
    connection.close()
    return {"status": "success", "hazard": hazard_data}


# ---------------------------------------------------------
# HELPER FUNCTIONS
# ---------------------------------------------------------
def find_nearest_grid_point(grid, latitude, longitude):
    best_point = None
    best_distance = float("inf")
    for row_index, row in enumerate(grid):
        for col_index, cell in enumerate(row):
            distance = ((cell["latitude"] - latitude) ** 2 + (cell["longitude"] - longitude) ** 2)
            if distance < best_distance:
                best_distance = distance
                best_point = (row_index, col_index)
    return best_point

def calculate_route_risk(path, grid):
    if not path:
        return "unknown"
    ice_values = []
    for row, col in path:
        cell = grid[row][col]
        ice_values.append(cell.get("sea_ice", 0))

    max_ice = max(ice_values, default=0)
    average_ice = sum(ice_values) / len(ice_values) if ice_values else 0
    
    if max_ice >= 0.80: return "restricted"
    if max_ice >= 0.30 or average_ice >= 0.15: return "caution"
    return "safe"

def calculate_route_distance(path, grid):
    total_distance = 0.0
    for index in range(1, len(path)):
        previous = grid[path[index - 1][0]][path[index - 1][1]]
        current = grid[path[index][0]][path[index][1]]
        total_distance += haversine_distance_km(previous["latitude"], previous["longitude"], current["latitude"], current["longitude"])
    return total_distance

def get_environmental_values(path, grid):
    ice_values = []
    wave_values = []
    for row, col in path:
        cell = grid[row][col]
        ice_values.append(cell.get("sea_ice", 0))
        wave_values.append(cell.get("wave_height", 0))
    return (sum(ice_values) / len(ice_values) if ice_values else 0.0, sum(wave_values) / len(wave_values) if wave_values else 0.0)

# ---------------------------------------------------------
# ROUTING
# ---------------------------------------------------------
@app.post("/routes/calculate")
def calculate_route(request: RouteRequest):
    connection = get_connection()
    cursor = connection.cursor()
    cursor.execute("SELECT * FROM sea_ice")
    sea_ice_rows = [dict(row) for row in cursor.fetchall()]
    cursor.execute("SELECT * FROM hazards")
    hazard_rows = [dict(row) for row in cursor.fetchall()]
    connection.close()

    vessel = get_vessel_profile(request.vessel_id)
    if not vessel:
        raise HTTPException(status_code=404, detail=f"Vessel ID {request.vessel_id} not found in registry.")

    min_lat = min(request.start_latitude, request.destination_latitude) - 1.0
    max_lat = max(request.start_latitude, request.destination_latitude) + 1.0
    min_lon = min(request.start_longitude, request.destination_longitude) - 1.0
    max_lon = max(request.start_longitude, request.destination_longitude) + 1.0

    grid = create_ocean_grid(
        min_lat=min_lat, max_lat=max_lat, min_lon=min_lon, max_lon=max_lon,
        resolution=request.grid_resolution, sea_ice_data=sea_ice_rows, hazards=hazard_rows
    )

    start = find_nearest_grid_point(grid, request.start_latitude, request.start_longitude)
    goal = find_nearest_grid_point(grid, request.destination_latitude, request.destination_longitude)

    # 1. Fuel-Efficient Route (A* with environmental ice & wave penalties)
    router_fe = AStarRouter(grid, hazards=hazard_rows, ignore_environmental_penalties=False)
    path_fe = router_fe.find_route(start, goal)

    if path_fe is None:
        raise HTTPException(status_code=404, detail="No safe route could be found.")

    points_fe = [{"latitude": grid[r][c]["latitude"], "longitude": grid[r][c]["longitude"]} for r, c in path_fe]
    dist_fe = calculate_route_distance(path_fe, grid)
    ice_fe, wave_fe = get_environmental_values(path_fe, grid)
    risk_fe = calculate_route_risk(path_fe, grid)
    fuel_fe = estimate_fuel(dist_fe, vessel, ice_fe, wave_fe)

    fe_route = {
        "route_id": "FE-" + uuid.uuid4().hex[:8].upper(),
        "points": points_fe,
        "distance_km": round(dist_fe, 3),
        "estimated_fuel_cost": round(fuel_fe, 2) if fuel_fe else None,
        "risk_level": risk_fe,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "algorithm": "A* (Fuel-Efficient)",
        "average_ice_concentration": round(ice_fe, 4),
        "average_wave_height_m": round(wave_fe, 3),
        "vessel_id": vessel.vessel_id
    }

    # 2. Standard Route (Shortest path ignoring environmental ice penalties)
    router_std = AStarRouter(grid, hazards=hazard_rows, ignore_environmental_penalties=True)
    path_std = router_std.find_route(start, goal) or path_fe
    points_std = [{"latitude": grid[r][c]["latitude"], "longitude": grid[r][c]["longitude"]} for r, c in path_std]
    dist_std = calculate_route_distance(path_std, grid)
    ice_std, wave_std = get_environmental_values(path_std, grid)
    risk_std = calculate_route_risk(path_std, grid)
    fuel_std = estimate_fuel(dist_std, vessel, ice_std, wave_std)

    std_route = {
        "route_id": "STD-" + uuid.uuid4().hex[:8].upper(),
        "points": points_std,
        "distance_km": round(dist_std, 3),
        "estimated_fuel_cost": round(fuel_std, 2) if fuel_std else None,
        "risk_level": risk_std,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "algorithm": "A* (Shortest Distance)",
        "average_ice_concentration": round(ice_std, 4),
        "average_wave_height_m": round(wave_std, 3),
        "vessel_id": vessel.vessel_id
    }

    # Calculate comparison metrics
    dist_increase_pct = max(0.0, round(((dist_fe - dist_std) / dist_std) * 100, 1)) if dist_std > 0 else 0.0
    fuel_saved_pct = max(0.0, round(((fuel_std - fuel_fe) / fuel_std) * 100, 1)) if fuel_std and fuel_fe and fuel_std > 0 else 0.0

    summary_text = (
        f"The recommended route is {dist_increase_pct}% longer but is estimated to use {fuel_saved_pct}% less fuel "
        f"by avoiding heavier ice conditions."
        if fuel_saved_pct > 0 else
        f"The recommended route provides optimal passage distance ({dist_fe:.1f} km) under current conditions."
    )

    # Save fuel efficient route to database
    connection = get_connection()
    cursor = connection.cursor()
    cursor.execute(
        "INSERT INTO routes (route_id, points, distance_km, estimated_fuel_cost, risk_level, timestamp) VALUES (?, ?, ?, ?, ?, ?)",
        (fe_route["route_id"], json.dumps(points_fe), fe_route["distance_km"], fe_route["estimated_fuel_cost"], fe_route["risk_level"], fe_route["timestamp"])
    )
    connection.commit()
    connection.close()

    return {
        "status": "success",
        "standard_route": std_route,
        "fuel_efficient_route": fe_route,
        "distance_increase_percent": dist_increase_pct,
        "fuel_saved_percent": fuel_saved_pct,
        "summary": summary_text,
        "note": "Prototype estimated fuel saving based on configured environmental fuel model."
    }


@app.post("/routes")
def save_route(route: Route):
    connection = get_connection()
    cursor = connection.cursor()
    cursor.execute(
        "INSERT OR REPLACE INTO routes (route_id, points, distance_km, estimated_fuel_cost, risk_level, timestamp) VALUES (?, ?, ?, ?, ?, ?)",
        (route.route_id, json.dumps([point.model_dump() for point in route.points]), route.distance_km, route.estimated_fuel_cost, route.risk_level, route.timestamp)
    )
    connection.commit()
    connection.close()
    return {"status": "success", "route": route.model_dump()}

@app.get("/routes")
def get_routes():
    connection = get_connection()
    cursor = connection.cursor()
    cursor.execute("SELECT * FROM routes ORDER BY timestamp DESC")
    rows = cursor.fetchall()
    connection.close()
    
    result = []
    for row in rows:
        data = dict(row)
        data["points"] = json.loads(data["points"])
        data.update(get_freshness_status(data["timestamp"]))
        result.append(data)
    return build_data_response(result)

@app.get("/routes/{route_id}/rtz")
def export_route_rtz(route_id: str):
    connection = get_connection()
    cursor = connection.cursor()
    cursor.execute("SELECT * FROM routes WHERE route_id = ?", (route_id,))
    row = cursor.fetchone()
    connection.close()
    
    if row is None:
        raise HTTPException(status_code=404, detail="Route not found.")
    
    points = json.loads(row["points"])
    xml = route_to_rtz(route_id=route_id, points=points)
    return Response(content=xml, media_type="application/xml")

# ---------------------------------------------------------
# VESSEL / FUEL
# ---------------------------------------------------------
@app.post("/vessels/profile")
def calculate_vessel_fuel_profile(request: VesselProfileRequest):
    profile = get_vessel_profile(request.vessel_id)
    if not profile:
        raise HTTPException(status_code=404, detail="Vessel profile not found.")

    geom = VesselGeometry(
        length_m=134.0, beam_m=21.0, draft_m=profile.draft_m or 8.5,
        waterline_bow_area_m2=30.0, alpha_deg=30.0, phi_2_deg=40.0, Lpar_over_L=0.45
    )

    fsicr_ref = FSICRClass.IA_SUPER if profile.ice_class and "Arc5" in profile.ice_class else FSICRClass.IC
    fsicr_assessment = assess_fsicr_condition(geom, fsicr_ref, propeller_diameter_m=4.0)

    return {
        "status": "success",
        "vessel_profile": profile.__dict__,
        "fsicr_assessment": fsicr_assessment
    }

# ---------------------------------------------------------
# DAYLIGHT
# ---------------------------------------------------------
@app.get("/navigation/daylight")
def daylight(latitude: float, longitude: float):
    result = calculate_daylight_status(latitude, longitude, date.today())
    return {"status": "success", "latitude": latitude, "longitude": longitude, **result}

# ---------------------------------------------------------
# AIS VESSELS & NCPOR FLEET
# ---------------------------------------------------------
@app.post("/ais/vessels")
def update_ais_vessel(vessel: AISVessel):
    connection = get_connection()
    cursor = connection.cursor()
    cursor.execute(
        """
        INSERT OR REPLACE INTO ais_vessels
        (vessel_id, name, latitude, longitude, speed_knots, heading_degrees, is_ncpor_fleet, timestamp)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (vessel.vessel_id, vessel.name, vessel.latitude, vessel.longitude, vessel.speed_knots, vessel.heading_degrees, int(vessel.is_ncpor_fleet), vessel.timestamp)
    )
    connection.commit()
    connection.close()
    return {"status": "success", "vessel": vessel.model_dump()}

@app.get("/ais/vessels")
def get_ais_vessels():
    connection = get_connection()
    cursor = connection.cursor()
    cursor.execute("SELECT * FROM ais_vessels ORDER BY vessel_id")
    rows = cursor.fetchall()
    
    cursor.execute("SELECT latitude, longitude FROM ship_positions ORDER BY id DESC LIMIT 1")
    ship_row = cursor.fetchone()
    connection.close()

    ship_lat = ship_row["latitude"] if ship_row else None
    ship_lon = ship_row["longitude"] if ship_row else None

    result = []
    for row in rows:
        data = dict(row)
        data["is_ncpor_fleet"] = bool(data["is_ncpor_fleet"])
        data.update(get_freshness_status(data["timestamp"]))
        
        if ship_lat is not None and ship_lon is not None:
            distance_km = haversine_distance_km(ship_lat, ship_lon, data["latitude"], data["longitude"])
            data["distance_to_ship_km"] = round(distance_km, 2)
            data["proximity_alert"] = distance_km <= 20.0
        else:
            data["distance_to_ship_km"] = None
            data["proximity_alert"] = False

        result.append(data)

    return build_data_response(result)

# ---------------------------------------------------------
# SYSTEM STATUS
# ---------------------------------------------------------

@app.get("/system/status")
def system_status():
    connection = get_connection()
    cursor = connection.cursor()
    cursor.execute("SELECT 1")
    database_ok = cursor.fetchone() is not None
    connection.close()
    
    return {
        "backend": "running",
        "database": "connected" if database_ok else "error",
        "modules": {
            "astar": "ready",
            "routing_grid": "ready",
            "routing_costs": "ready",
            "fuel_framework": "ready",
            "rtz_export": "ready",
            "nmea_websocket": "ready",
            "freshness": "ready",
            "confidence": "ready",
            "daylight": "ready",
            "advisory_only": True
        }
    }