import os
import sys
import copy
import pytest
import numpy as np
import pandas as pd
from unittest.mock import patch

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from config.master_config import MASTER_CONFIG
from nmea.risk_lookup import RiskLookup

@pytest.fixture
def config_b():
    cfg = copy.deepcopy(MASTER_CONFIG)
    cfg["route"] = [(-40.0, -70.0), (-45.0, -75.0)]
    cfg["run_id"] = "test_route_B"
    return cfg

def test_nmea_lookup_hit(config_b):
    dir_b = os.path.join("runs", "test_route_B")
    if not os.path.exists(dir_b):
        pytest.skip("test_route_B pipeline not run yet")
        
    with patch('nmea.risk_lookup.MASTER_CONFIG', config_b):
        with patch('nmea.risk_lookup.get_active_corridor') as mock_gac:
            # We must provide the correct polygon. We can just import and call it with config_b.
            from master.route_manager import get_active_corridor
            mock_gac.return_value = get_active_corridor(config_b)
            
            lookup = RiskLookup(run_id="test_route_B")
    
    # We know route B is from (-40, -70) to (-45, -75). 
    # Pick a point clearly inside:
    res = lookup.get_risk(-72.5, -42.5)
    
    assert res['status'] != "outside_polaris_grid"
    assert 'latitude' in res
    assert 'longitude' in res
    assert 'SIC' in res
    assert 'SIT' in res
    assert 'Ice_Type' in res
    assert 'polaris_ice_category' in res
    assert 'vessel_class' in res
    assert 'RIV' in res
    assert 'RIO' in res
    assert 'rio_method' in res
    assert 'rio_available' in res
    assert 'DLIRI' in res
    assert 'DLIRI_category' in res
    assert 'operational_risk' in res
    assert 'risk_source' in res
    assert 'confidence' in res
    assert 'ice_type_match_method' in res

def test_nmea_lookup_miss(config_b):
    dir_b = os.path.join("runs", "test_route_B")
    if not os.path.exists(dir_b):
        pytest.skip("test_route_B pipeline not run yet")
        
    with patch('nmea.risk_lookup.MASTER_CONFIG', config_b):
        with patch('nmea.risk_lookup.get_active_corridor') as mock_gac:
            from master.route_manager import get_active_corridor
            mock_gac.return_value = get_active_corridor(config_b)
            
            lookup = RiskLookup(run_id="test_route_B")
    
    # Point outside
    res = lookup.get_risk(0.0, 0.0)
    assert res['status'] == "outside_polaris_grid"
    assert res['latitude'] == 0.0
    assert res['longitude'] == 0.0

def test_nearest_cell_lookup(config_b):
    dir_b = os.path.join("runs", "test_route_B")
    if not os.path.exists(dir_b):
        pytest.skip("test_route_B pipeline not run yet")
        
    with patch('nmea.risk_lookup.MASTER_CONFIG', config_b):
        with patch('nmea.risk_lookup.get_active_corridor') as mock_gac:
            from master.route_manager import get_active_corridor
            mock_gac.return_value = get_active_corridor(config_b)
            
            lookup = RiskLookup(run_id="test_route_B")
            
    df = lookup.df
    
    # Take two adjacent cells
    row1 = df.iloc[0]
    row2 = df.iloc[1]
    
    mid_lat = (row1['latitude'] + row2['latitude']) / 2.0
    mid_lon = (row1['longitude'] + row2['longitude']) / 2.0
    
    # Add a tiny epsilon to ensure it's strictly closer to row1
    test_lat = mid_lat + 1e-6 if row1['latitude'] > row2['latitude'] else mid_lat - 1e-6
    test_lon = mid_lon + 1e-6 if row1['longitude'] > row2['longitude'] else mid_lon - 1e-6
    
    res = lookup.get_risk(test_lat, test_lon)
    
    # Verify no interpolation occurred (exact match with row1)
    assert np.isclose(res['latitude'], row1['latitude'])
    assert np.isclose(res['longitude'], row1['longitude'])
    assert np.isclose(res['SIC'], row1['SIC'])
    
    if pd.notna(row1['DLIRI']):
        assert np.isclose(res['DLIRI'], row1['DLIRI'])
        
    assert res['risk_source'] == row1['risk_source']
