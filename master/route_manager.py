import os
import sys
import geopandas as gpd
from shapely.geometry import LineString

# Ensure config can be imported from parent
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from config.master_config import MASTER_CONFIG

def get_active_corridor(config=None):
    """
    Parses configuration, creates LineString, and generates 50-km corridor polygon.
    Returns:
        gdf_route: GeoDataFrame of the route in EPSG:4326
        corridor_polygon: Shapely Polygon of the buffered corridor in EPSG:4326
    """
    if config is None:
        config = MASTER_CONFIG

    route_coords = config.get("route", [])
    if not route_coords or len(route_coords) < 2:
        raise ValueError("Route must contain at least 2 coordinate pairs.")

    buffer_distance_km = config.get("corridor_km", 50)
    buffer_distance_m = buffer_distance_km * 1000

    # 1. Coordinate Ordering: (longitude, latitude)
    for i, (lon, lat) in enumerate(route_coords):
        if not (-90.0 <= lat <= 90.0):
            raise ValueError(f"Waypoint {i}: latitude {lat} is outside valid range [-90°, 90°].")
        if not (-180.0 <= lon <= 180.0):
            raise ValueError(f"Waypoint {i}: longitude {lon} is outside valid range [-180°, 180°].")

    route_line = LineString(route_coords)
    gdf_route = gpd.GeoDataFrame(index=[0], crs="EPSG:4326", geometry=[route_line])

    # 2. Buffer Generation using metric EPSG:3031
    gdf_route_3031 = gdf_route.to_crs("EPSG:3031")
    gdf_buffer_3031 = gdf_route_3031.buffer(buffer_distance_m)
    
    # Project back to WGS84
    gdf_buffer_4326 = gdf_buffer_3031.to_crs("EPSG:4326")
    corridor_polygon = gdf_buffer_4326.geometry.iloc[0]

    return gdf_route, corridor_polygon

def validate_route(config=None):
    """
    Validates that the route generates a valid corridor and prints its bounds.
    """
    gdf_route, corridor_polygon = get_active_corridor(config)
    min_lon, min_lat, max_lon, max_lat = corridor_polygon.bounds
    print(f"✓ Route is valid. Active Corridor Bounds:")
    print(f"    Latitude : [{min_lat:.4f}°N, {max_lat:.4f}°N]")
    print(f"    Longitude: [{min_lon:.4f}°E, {max_lon:.4f}°E]")
    return True

if __name__ == "__main__":
    validate_route()
