import os
import sys
import copy
import pytest
import pandas as pd
import xarray as xr
import numpy as np
from unittest.mock import patch

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
import pipeline.run_pipeline as run_pipeline
from config.master_config import MASTER_CONFIG
from master.route_manager import get_active_corridor

@pytest.fixture
def config_a():
    cfg = copy.deepcopy(MASTER_CONFIG)
    cfg["route"] = [(-67.0, -55.0), (-62.0, -60.0), (-60.0, -65.0), (-58.0, -70.0)]
    cfg["run_id"] = "test_route_A"
    return cfg

@pytest.fixture
def config_b():
    cfg = copy.deepcopy(MASTER_CONFIG)
    cfg["route"] = [(-40.0, -70.0), (-45.0, -75.0)]
    cfg["run_id"] = "test_route_B"
    return cfg

def test_route_ab_isolation(config_a, config_b):
    # Mock MASTER_CONFIG using patch so run_pipeline reads the patched config
    with patch('pipeline.run_pipeline.MASTER_CONFIG', config_a):
        with patch('extract_sic.get_active_corridor', return_value=get_active_corridor(config_a)):
            with patch('extract_sit.get_active_corridor', return_value=get_active_corridor(config_a)):
                with patch('extract_ice_type.get_active_corridor', return_value=get_active_corridor(config_a)):
                    with patch('calculate_polaris.get_active_corridor', return_value=get_active_corridor(config_a)):
                        run_pipeline.run_pipeline()
    
    with patch('pipeline.run_pipeline.MASTER_CONFIG', config_b):
        with patch('extract_sic.get_active_corridor', return_value=get_active_corridor(config_b)):
            with patch('extract_sit.get_active_corridor', return_value=get_active_corridor(config_b)):
                with patch('extract_ice_type.get_active_corridor', return_value=get_active_corridor(config_b)):
                    with patch('calculate_polaris.get_active_corridor', return_value=get_active_corridor(config_b)):
                        run_pipeline.run_pipeline()
    
    dir_a = os.path.join("runs", "test_route_A")
    dir_b = os.path.join("runs", "test_route_B")
    
    assert os.path.exists(dir_a)
    assert os.path.exists(dir_b)
    
    df_a = pd.read_csv(os.path.join(dir_a, "polaris_grid.csv"))
    df_b = pd.read_csv(os.path.join(dir_b, "polaris_grid.csv"))
    
    _, corridor_a = get_active_corridor(config_a)
    _, corridor_b = get_active_corridor(config_b)
    
    assert corridor_a.bounds != corridor_b.bounds
    
    set_a = set(zip(df_a['latitude'], df_a['longitude']))
    set_b = set(zip(df_b['latitude'], df_b['longitude']))
    
    # Assert disjoint as the two corridors are far apart
    assert len(set_a.intersection(set_b)) == 0

def test_reproducibility(config_b):
    with patch('pipeline.run_pipeline.MASTER_CONFIG', config_b):
        with patch('extract_sic.get_active_corridor', return_value=get_active_corridor(config_b)):
            with patch('extract_sit.get_active_corridor', return_value=get_active_corridor(config_b)):
                with patch('extract_ice_type.get_active_corridor', return_value=get_active_corridor(config_b)):
                    with patch('calculate_polaris.get_active_corridor', return_value=get_active_corridor(config_b)):
                        run_pipeline.run_pipeline()
                        
    dir_b = os.path.join("runs", "test_route_B")
    df_b1 = pd.read_csv(os.path.join(dir_b, "polaris_grid.csv"))
    
    with patch('pipeline.run_pipeline.MASTER_CONFIG', config_b):
        with patch('extract_sic.get_active_corridor', return_value=get_active_corridor(config_b)):
            with patch('extract_sit.get_active_corridor', return_value=get_active_corridor(config_b)):
                with patch('extract_ice_type.get_active_corridor', return_value=get_active_corridor(config_b)):
                    with patch('calculate_polaris.get_active_corridor', return_value=get_active_corridor(config_b)):
                        run_pipeline.run_pipeline()
                        
    df_b2 = pd.read_csv(os.path.join(dir_b, "polaris_grid.csv"))
    
    pd.testing.assert_frame_equal(df_b1, df_b2)

def test_csv_netcdf_consistency(config_b):
    dir_b = os.path.join("runs", "test_route_B")
    
    df_csv = pd.read_csv(os.path.join(dir_b, "polaris_grid.csv"))
    ds_nc = xr.open_dataset(os.path.join(dir_b, "polaris_grid.nc"))
    df_nc = ds_nc.to_dataframe().reset_index()
    
    # We must sort both to ensure order doesn't affect equality
    df_csv = df_csv.sort_values(by=['latitude', 'longitude']).reset_index(drop=True)
    df_nc = df_nc.sort_values(by=['latitude', 'longitude']).reset_index(drop=True)
    
    np.testing.assert_allclose(df_csv['latitude'], df_nc['latitude'], atol=1e-5)
    np.testing.assert_allclose(df_csv['longitude'], df_nc['longitude'], atol=1e-5)
    np.testing.assert_allclose(df_csv['SIC'], df_nc['SIC'], atol=1e-5)
    
    # Check SIT (could be NaN)
    np.testing.assert_allclose(df_csv['SIT'].fillna(-999), df_nc['SIT'].fillna(-999), atol=1e-5)
    np.testing.assert_allclose(df_csv['DLIRI'].fillna(-999), df_nc['DLIRI'].fillna(-999), atol=1e-5)
