import os
import sys
import copy
import pytest
from shapely.geometry import LineString, Polygon

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from config.master_config import MASTER_CONFIG
from master.route_manager import get_active_corridor

@pytest.fixture
def clean_config():
    return copy.deepcopy(MASTER_CONFIG)

def test_empty_route(clean_config):
    clean_config["route"] = []
    with pytest.raises(ValueError):
        get_active_corridor(clean_config)

def test_one_point_route(clean_config):
    clean_config["route"] = [(-67.0, -55.0)]
    with pytest.raises(ValueError):
        get_active_corridor(clean_config)

def test_invalid_coordinates(clean_config):
    clean_config["route"] = [(-67.0, -55.0), (float('nan'), -60.0)]
    with pytest.raises(ValueError):
        get_active_corridor(clean_config)

def test_out_of_bounds_coordinates(clean_config):
    clean_config["route"] = [(-67.0, -55.0), (-62.0, -95.0)] # -95 is invalid lat
    with pytest.raises(ValueError):
        get_active_corridor(clean_config)

def test_valid_route(clean_config):
    clean_config["route"] = [
        (-67.0, -55.0),
        (-62.0, -60.0)
    ]
    clean_config["corridor_km"] = 50
    gdf_route, corridor_polygon = get_active_corridor(clean_config)
    
    assert gdf_route is not None
    assert isinstance(gdf_route.geometry.iloc[0], LineString)
    assert not gdf_route.geometry.iloc[0].is_empty
    
    assert corridor_polygon is not None
    assert isinstance(corridor_polygon, Polygon)
    assert not corridor_polygon.is_empty
    
    # Coordinate ordering: (longitude, latitude)
    assert gdf_route.geometry.iloc[0].coords[0] == (-67.0, -55.0)
    
    # Bounds should be finite
    bounds = corridor_polygon.bounds
    for b in bounds:
        assert str(b).lower() not in ['nan', 'inf', '-inf']
        
    assert gdf_route.crs == "EPSG:4326"
