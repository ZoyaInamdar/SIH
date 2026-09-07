import os
import pytest
import pandas as pd
import numpy as np

def test_spatial_matching():
    dir_b = os.path.join("runs", "test_route_B")
    if not os.path.exists(dir_b):
        pytest.skip("test_route_B pipeline not run yet")
        
    df = pd.read_csv(os.path.join(dir_b, "polaris_grid.csv"))
    
    # Check coords are finite
    assert np.isfinite(df['latitude']).all()
    assert np.isfinite(df['longitude']).all()
    
    # Check SIC is normalized [0, 1]
    assert (df['SIC'] >= 0.0).all()
    assert (df['SIC'] <= 1.0).all()
    
    # No duplicate lat/lon
    assert len(df) == len(df.drop_duplicates(subset=['latitude', 'longitude']))
    
    # Verify SIT coordinate set
    df_sit = pd.read_csv(os.path.join(dir_b, "sit_grid.csv"))
    
    # No duplicates in SIT
    assert len(df_sit) == len(df_sit.drop_duplicates(subset=['latitude', 'longitude']))
    
    # Coordinate set equality
    set_polaris = set(zip(df['latitude'], df['longitude']))
    set_sit = set(zip(df_sit['latitude'], df_sit['longitude']))
    assert set_polaris == set_sit
    
    # Valid SIT values >= 0
    valid_sit = df['SIT'].dropna()
    if len(valid_sit) > 0:
        assert (valid_sit >= 0.0).all()

    # Ice Type matching method validation
    for _, row in df.iterrows():
        method = row['ice_type_match_method']
        dist = row['ice_type_match_distance_km']
        
        if method == 'exact':
            assert pd.notna(dist)
            assert np.isclose(dist, 0.0, atol=1e-5)
        elif method == 'nearest':
            assert pd.notna(dist)
            assert dist <= 15.0
        elif method == 'missing':
            assert pd.isna(dist)
        else:
            pytest.fail(f"Unknown ice type match method: {method}")
