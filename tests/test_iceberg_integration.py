import os
import sys
import unittest
import pandas as pd
import shutil
import warnings

# Suppress annoying warnings
warnings.filterwarnings("ignore")

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from config.master_config import MASTER_CONFIG
import extract_icebergs
import calculate_polaris

class TestIcebergIntegration(unittest.TestCase):
    def setUp(self):
        self.run_id = "test_iceberg_run"
        self.run_dir = os.path.join("runs", self.run_id)
        os.makedirs(self.run_dir, exist_ok=True)
        
        # Override config for testing
        MASTER_CONFIG["run_id"] = self.run_id
        MASTER_CONFIG["enable_iceberg_prediction"] = True
        MASTER_CONFIG["iceberg_buffer_km"] = 10.0
        
        # Create a mock sic_today.csv (grid template)
        # We place a 3x3 grid around (-62.5, -62.5)
        lats = [-62.4, -62.5, -62.6]
        lons = [-62.4, -62.5, -62.6]
        grid = []
        for lat in lats:
            for lon in lons:
                grid.append({
                    "latitude": lat,
                    "longitude": lon,
                    "siconc": 0.5  # 50% concentration
                })
        self.df_sic = pd.DataFrame(grid)
        self.df_sic.to_csv(os.path.join(self.run_dir, "sic_today.csv"), index=False)
        
        # Create mock sit_grid.csv
        self.df_sit = self.df_sic.copy()
        self.df_sit["SIT"] = 1.0  # 1 meter thick
        self.df_sit.to_csv(os.path.join(self.run_dir, "sit_grid.csv"), index=False)
        
        # Create mock ice_type_latest.csv
        self.df_ice = self.df_sic.copy()
        self.df_ice["ice_type_label"] = "first_year_ice"
        self.df_ice.to_csv(os.path.join(self.run_dir, "ice_type_latest.csv"), index=False)

    def tearDown(self):
        if os.path.exists(self.run_dir):
            shutil.rmtree(self.run_dir)

    def test_iceberg_extraction_and_override(self):
        # 1. Run iceberg extraction
        # This will create synthetic trajectory at (-62.5, -62.5) intersecting our grid
        extract_icebergs.run(self.run_dir)
        
        hazard_file = os.path.join(self.run_dir, "iceberg_hazard_grid.csv")
        self.assertTrue(os.path.exists(hazard_file), "Iceberg hazard grid was not created.")
        
        df_hazard = pd.read_csv(hazard_file)
        self.assertIn("iceberg_presence", df_hazard.columns)
        
        # 2. Run calculate_polaris
        calculate_polaris.run(vessel_class="PC4", run_dir=self.run_dir)
        
        polaris_file = os.path.join(self.run_dir, "polaris_grid.csv")
        self.assertTrue(os.path.exists(polaris_file), "Polaris grid was not created.")
        
        df_polaris = pd.read_csv(polaris_file)
        self.assertIn("iceberg_presence", df_polaris.columns)
        
        # Assertions
        # 1. Synthetic iceberg inside corridor produces presence=True
        self.assertGreater(df_polaris["iceberg_presence"].sum(), 0)
        
        # 3. 10km buffer applied and 5. distance is in km
        self.assertIn("iceberg_distance_km", df_polaris.columns)
        
        # 6. forecast time is retained
        self.assertIn("iceberg_forecast_time", df_polaris.columns)
        hazard_cells = df_polaris[df_polaris["iceberg_presence"] == True]
        for _, cell in hazard_cells.iterrows():
            self.assertIsNotNone(cell["iceberg_forecast_time"])
            self.assertEqual(cell["iceberg_risk"], "EXTREME")
            self.assertEqual(cell["operational_risk"], "EXTREME")
            self.assertEqual(cell["risk_source"], "ICEBERG_COLLISION_ZONE")
            self.assertEqual(cell["risk_score"], 100)
            self.assertEqual(cell["risk_score_type"], "ICEBERG_COLLISION_ZONE")
            # 10. Check unchanged values
            self.assertEqual(cell["sea_ice_risk_source"], "POLARIS")
            
        # 8. Base coordinates exactly match
        self.assertEqual(len(df_polaris), len(self.df_sic))
        
        # Disable prediction and run again (Test 13)
        MASTER_CONFIG["enable_iceberg_prediction"] = False
        if os.path.exists(hazard_file):
            os.remove(hazard_file)
        calculate_polaris.run(vessel_class="PC4", run_dir=self.run_dir)
        df_polaris_disabled = pd.read_csv(polaris_file)
        self.assertEqual(df_polaris_disabled["iceberg_presence"].sum(), 0)
        self.assertEqual(df_polaris_disabled["iceberg_risk"].iloc[0], "NONE")
        self.assertEqual(df_polaris_disabled["risk_source"].iloc[0], "POLARIS")

if __name__ == "__main__":
    unittest.main()
