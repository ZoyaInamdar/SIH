# Antarctic Navigation — Cached Data

This folder contains small cached datasets used for the Antarctic navigation prototype.

## Data folders

### nsidc/

Sea-ice concentration data.

Source:
NSIDC

Used for:

* Sea-ice concentration
* Sea-ice forecast

### copernicus/

Ocean and marine environmental data.

Used for:

* Ocean currents
* Sea surface temperature
* Wind
* Waves

### era5/

Atmospheric/weather data.

Used for:

* Wind
* Weather conditions

### iceberg/

Iceberg observations/tracks.

Used for:

* Iceberg position
* Iceberg trajectory prediction
* Iceberg hazard zones

### bathymetry/

Seafloor depth data.

Used for:

* Grounding-risk calculation

### waves/

Wave observations.

Used for:

* Wave conditions
* Navigation/fuel calculations

### sonar/

AUV/sonar sample data.

Used for:

* Underwater iceberg detection
* Sonar-based iceberg measurements

### ais/

AIS vessel data.

Used for:

* Nearby-vessel detection
* Traffic awareness

## Important

Only small demo/cache datasets should be stored in this repository.

Large raw datasets should NOT be uploaded directly to GitHub.

The application should be able to use cached data when live data sources are unavailable.
