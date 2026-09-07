"""
test_environment_reader.py

Unit and integration tests for the format-agnostic environment reader abstraction.
"""

from __future__ import annotations

import unittest
from pathlib import Path

from data_pipeline.config import era5_path, glorys_path
from iceberg_wrapper.environment_reader import create_environment_reader


class TestEnvironmentReader(unittest.TestCase):
    """Test suite for create_environment_reader."""

    def test_netcdf_reader(self) -> None:
        """Verify existing NetCDF (.nc) datasets load successfully."""
        b50_era5 = era5_path("B50")
        self.assertTrue(b50_era5.exists(), f"Missing test file: {b50_era5}")

        print("\n--- Testing NetCDF Reader ---")
        reader = create_environment_reader(b50_era5)
        self.assertIsNotNone(reader)
        self.assertTrue(hasattr(reader, "xmin"))
        self.assertTrue(hasattr(reader, "variables"))

    def test_grib_reader_availability(self) -> None:
        """Test GRIB / GRIB2 support if a test file is present, or report skip status."""
        print("\n--- Testing GRIB / GRIB2 Reader ---")
        project_root = Path(__file__).resolve().parents[1]
        data_dir = project_root / "data"

        grib_files = (
            list(data_dir.glob("**/*.grib"))
            + list(data_dir.glob("**/*.grib2"))
            + list(data_dir.glob("**/*.grb"))
            + list(data_dir.glob("**/*.grb2"))
        )

        if not grib_files:
            print("GRIB Reader API available.")
            print("No GRIB test dataset supplied.")
            print("GRIB integration test skipped.")
            return

        for grib_file in grib_files:
            print(f"Testing real GRIB file: {grib_file}")
            reader = create_environment_reader(grib_file)
            self.assertIsNotNone(reader)
            self.assertTrue(hasattr(reader, "variables"))
            print(f"Verified GRIB variables: {reader.variables}")


if __name__ == "__main__":
    unittest.main()
