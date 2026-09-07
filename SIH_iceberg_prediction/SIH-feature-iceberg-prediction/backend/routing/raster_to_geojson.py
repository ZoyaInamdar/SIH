from __future__ import annotations

import json
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
from pyproj import Transformer
from shapely.geometry import Polygon, mapping
from skimage import measure


def validate_raster(raster: np.ndarray) -> None:
    if not isinstance(raster, np.ndarray):
        raise TypeError("raster must be a numpy.ndarray")
    if raster.ndim != 2:
        raise ValueError("raster must be a 2D array")
    if raster.size == 0:
        raise ValueError("raster cannot be empty")


def pixel_to_coordinates(row: float, col: float, transform: Tuple[float, float, float, float]) -> Tuple[float, float]:
    x_origin, y_origin, pixel_width, pixel_height = transform
    x = x_origin + col * pixel_width
    y = y_origin + row * pixel_height
    return x, y


def transform_coordinates(coordinates: List[Tuple[float, float]], source_crs: str, target_crs: str) -> List[Tuple[float, float]]:
    if source_crs == target_crs:
        return coordinates
    transformer = Transformer.from_crs(source_crs, target_crs, always_xy=True)
    transformed = []
    for x, y in coordinates:
        new_x, new_y = transformer.transform(x, y)
        transformed.append((new_x, new_y))
    return transformed


def raster_to_polygons(raster: np.ndarray, transform: Tuple[float, float, float, float], threshold: float = 0.15, source_crs: str = "EPSG:3031", target_crs: str = "EPSG:4326", min_area: float = 0.0) -> List[Dict[str, Any]]:
    validate_raster(raster)
    if not 0.0 <= threshold <= 1.0:
        raise ValueError("threshold must be between 0 and 1")

    mask = np.isfinite(raster) & (raster >= threshold)
    if not np.any(mask):
        return []

    padded_mask = np.pad(mask.astype(float), pad_width=1, mode='constant', constant_values=0.0)
    contours = measure.find_contours(padded_mask, level=0.5)

    polygons = []
    for contour in contours:
        if len(contour) < 4:
            continue
        coordinates = []
        for row, col in contour:
            x, y = pixel_to_coordinates(row - 1, col - 1, transform)
            coordinates.append((x, y))

        if coordinates[0] != coordinates[-1]:
            coordinates.append(coordinates[0])

        transformed_coordinates = transform_coordinates(coordinates, source_crs, target_crs)
        polygon = Polygon(transformed_coordinates)

        if not polygon.is_valid:
            polygon = polygon.buffer(0)
        if polygon.is_empty:
            continue
        if polygon.area < min_area:
            continue

        polygons.append({
            "type": "Feature",
            "geometry": mapping(polygon),
            "properties": {
                "threshold": threshold,
            },
        })

    return polygons


def raster_to_geojson(raster: np.ndarray, transform: Tuple[float, float, float, float], threshold: float = 0.15, source_crs: str = "EPSG:3031", target_crs: str = "EPSG:4326", min_area: float = 0.0) -> Dict[str, Any]:
    polygons = raster_to_polygons(
        raster=raster,
        transform=transform,
        threshold=threshold,
        source_crs=source_crs,
        target_crs=target_crs,
        min_area=min_area,
    )
    return {
        "type": "FeatureCollection",
        "features": polygons,
    }


def save_geojson(geojson_data: Dict[str, Any], output_path: str) -> None:
    with open(output_path, "w", encoding="utf-8") as file:
        json.dump(geojson_data, file, indent=2)