===============================================================================
SYNTHETIC DEMONSTRATION ENVIRONMENTAL DATASET FOR OPENBERG TESTING
===============================================================================

DISCLAIMER:
- THESE FILES ARE SYNTHETIC DEMONSTRATION DATASETS CREATED FOR PIPELINE TESTING.
- THEY ARE NOT REAL ERA5 ATMOSPHERIC OBSERVATIONS.
- THEY ARE NOT REAL GLORYS OCEANOGRAPHIC OBSERVATIONS.
- DO NOT USE FOR REAL-WORLD SCIENTIFIC OR NAVIGATION PURPOSES.
- ICEBERG TRAJECTORIES MUST BE COMPUTED DIRECTLY BY THE OPENBERG PHYSICS MODEL.
- NO PREDICTED TRAJECTORIES OR FAKE POSITION FILES ARE INCLUDED IN THIS DATASET.

===============================================================================
ICEBERG DEMONSTRATION CASES & INITIAL STATES
===============================================================================

1. IB_DEMO_001
   - Latitude: -65.0 deg
   - Longitude: 4.0 deg E
   - Geometry: Length = 500.0 m, Width = 300.0 m, Sail = 30.0 m, Draft = 67.5 m
   - Spatial Domain: Lat [-66.5, -63.5], Lon [2.0, 6.0]

2. IB_DEMO_002
   - Latitude: -65.0 deg
   - Longitude: 10.0 deg E
   - Geometry: Length = 450.0 m, Width = 280.0 m, Sail = 28.0 m, Draft = 66.0 m
   - Spatial Domain: Lat [-66.5, -63.5], Lon [8.0, 12.0]

3. IB_DEMO_003
   - Latitude: -65.0 deg
   - Longitude: 16.0 deg E
   - Geometry: Length = 400.0 m, Width = 250.0 m, Sail = 26.0 m, Draft = 64.5 m
   - Spatial Domain: Lat [-66.5, -63.5], Lon [14.0, 18.0]

===============================================================================
TEMPORAL COVERAGE & HORIZON
===============================================================================
- Start Time: 2026-01-01 00:00:00 UTC
- End Time: 2026-01-02 00:00:00 UTC
- Forecast Horizon: 24.0 Hours
- Time Resolution: Hourly (25 timesteps)

===============================================================================
VERTICAL DEPTH LEVELS (GLORYS)
===============================================================================
- Depth Levels (9 levels, extending deeper than max iceberg draft 67.5 m):
  0.5 m, 5.0 m, 10.0 m, 20.0 m, 40.0 m, 60.0 m, 80.0 m, 100.0 m, 150.0 m

===============================================================================
ENVIRONMENTAL VARIABLES & UNITS
===============================================================================

ERA5-style CSV Files (IB_DEMO_*_era5.csv):
  - latitude   : Latitude coordinate [degrees_north]
  - longitude  : Longitude coordinate [degrees_east]
  - valid_time : UTC Timestamp [YYYY-MM-DD HH:MM:SS]
  - u10        : 10-metre eastward wind component [m/s]
  - v10        : 10-metre northward wind component [m/s]

GLORYS-style CSV Files (IB_DEMO_*_glorys.csv):
  - time      : UTC Timestamp [YYYY-MM-DD HH:MM:SS]
  - latitude  : Latitude coordinate [degrees_north]
  - longitude : Longitude coordinate [degrees_east]
  - depth     : Depth below sea surface [m]
  - uo        : Eastward sea-water velocity [m/s]
  - vo        : Northward sea-water velocity [m/s]
  - thetao    : Sea-water temperature [deg C]
  - so        : Sea-water salinity [PSU]
  - zos       : Sea-surface height above geoid [m]
  - siconc    : Sea-ice area fraction [0-1]
  - sithick   : Sea-ice thickness [m]
  - usi       : Eastward sea-ice velocity [m/s]
  - vsi       : Northward sea-ice velocity [m/s]
