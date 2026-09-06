from fastapi import FastAPI
from backend.schemas import (
    ShipPosition,
    Iceberg,
    SeaIceZone,
    Hazard,
    Route
)

app = FastAPI(
    title="Antarctic Navigation Decision Support System",
    version="1.0.0"
)


@app.get("/")
def home():
    return {
        "message": "Antarctic Navigation Backend is running"
    }


@app.get("/health")
def health():
    return {
        "status": "healthy"
    }

@app.post("/test/ship")
def test_ship(ship: ShipPosition):
    return ship

@app.post("/test/iceberg")
def test_iceberg(iceberg: Iceberg):
    return iceberg

@app.post("/test/sea-ice")
def test_sea_ice(sea_ice: SeaIceZone):
    return sea_ice


@app.post("/test/hazard")
def test_hazard(hazard: Hazard):
    return hazard


@app.post("/test/route")
def test_route(route: Route):
    return route