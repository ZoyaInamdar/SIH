import numpy as np

from backend.routing.ice_persistence import (
    IceRasterObservation,
    run_persistence_baseline,
)

from backend.routing.ice_zones import (
    classify_ice_grid,
)

from backend.routing.raster_to_geojson import (
    raster_to_geojson,
)


def main():
    # ---------------------------------------------------------
    # 1. Simulated historical sea-ice observations
    # ---------------------------------------------------------

    observations = []

    for i in range(6):
        concentration = np.full(
            (20, 20),
            0.20 + (0.04 * i),
            dtype=float,
        )

        observations.append(
            IceRasterObservation(
                timestamp_hours=i * 24.0,
                concentration=concentration,
            )
        )

    # ---------------------------------------------------------
    # 2. Predict sea-ice concentration 24 hours ahead
    # ---------------------------------------------------------

    forecast = run_persistence_baseline(
        observations=observations,
        forecast_horizon_hours=24.0,
        window_size=6,
    )

    predicted = forecast.predicted_concentration

    print("=== SEA-ICE PERSISTENCE ===")
    print("Predicted raster shape:", predicted.shape)
    print(
        "Predicted concentration:",
        round(float(predicted[0, 0]), 4),
    )

    # ---------------------------------------------------------
    # 3. Convert raster into grid-cell dictionaries
    # ---------------------------------------------------------
    #
    # ice_zones.py expects:
    #
    # [
    #   {
    #       "latitude": ...,
    #       "longitude": ...,
    #       "sea_ice": ...
    #   },
    #   ...
    # ]
    #
    # We create a simple test grid here.
    # ---------------------------------------------------------

    grid_cells = []

    for row in range(predicted.shape[0]):
        for col in range(predicted.shape[1]):

            grid_cells.append(
                {
                    "latitude": -60.0 + row * 0.1,
                    "longitude": 70.0 + col * 0.1,
                    "sea_ice": float(predicted[row, col]),
                }
            )

    # ---------------------------------------------------------
    # 4. Classify sea-ice risk zones
    # ---------------------------------------------------------

    zones = classify_ice_grid(grid_cells)

    print("\n=== SEA-ICE RISK ZONES ===")
    print("Number of classified cells:", len(zones))

    if zones:
        print("Example classified cell:")
        print(zones[0])

    # ---------------------------------------------------------
    # 5. Convert forecast raster to GeoJSON
    # ---------------------------------------------------------

    transform = (
        -500000,
        1000000,
        1000,
        -1000,
    )

    geojson = raster_to_geojson(
        raster=predicted,
        transform=transform,
        threshold=0.15,
        source_crs="EPSG:3031",
        target_crs="EPSG:4326",
    )

    print("\n=== RASTER → GEOJSON ===")
    print("GeoJSON type:", geojson["type"])
    print("Number of features:", len(geojson["features"]))

    if geojson["features"]:
        print(
            "Geometry type:",
            geojson["features"][0]["geometry"]["type"],
        )

    print("\nPIPELINE TEST PASSED")


if __name__ == "__main__":
    main()