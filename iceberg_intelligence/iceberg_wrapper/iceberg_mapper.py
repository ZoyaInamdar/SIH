"""
iceberg_mapper.py
 
Converts the project's iceberg schema into the exact properties OpenBerg's
IcebergObj element type expects. This is the ONLY place that mapping lives —
if the team changes what freeboard_m means, or how it should map to OpenBerg's
`sail`, this is the only file that needs to change.
 
IMPORTANT (see project notes): `freeboard_m -> sail` is used here because it
lets us test the architecture now, with synthetic data. It is NOT confirmed to
be the final, physically-correct mapping for the real project — freeboard and
sail are related but not always identical in the iceberg literature. Revisit
this once the team's real data definitions are confirmed.
 
`drift_speed_knots`, `drift_direction_degrees`, `status`, and `confidence` are
deliberately NOT mapped to any OpenBerg field here — they are project
metadata / validation data, not seeding inputs. See the design doc for the
full field classification.
 
Bounds below (min/max for sail, draft, length, width) are copied from
OpenBerg's own `IcebergObj` element definition in
opendrift/models/openberg.py, so an iceberg that fails validation here would
also fail (or be silently clamped) inside OpenBerg itself.
"""
 
from __future__ import annotations
 
from typing import Any, Dict, List
 
# Copied from opendrift.models.openberg.IcebergObj.variables (OpenDrift 1.14.x)
OPENBERG_BOUNDS = {
    "sail": (1, 100),      # metres
    "draft": (1, 1000),    # metres
    "length": (1, 10000),  # metres
    "width": (1, 10000),   # metres
}
 
 
class IcebergMappingError(ValueError):
    """Raised when a project iceberg record cannot be safely mapped to OpenBerg."""
 
 
def _get_first(record: Dict[str, Any], *keys: str):
    """Return the first present, non-None key from `record`."""
    for k in keys:
        if k in record and record[k] is not None:
            return record[k]
    return None
 
 
def _require_number(value: Any, field_name: str) -> float:
    if value is None:
        raise IcebergMappingError(f"missing required field: {field_name}")
    try:
        num = float(value)
    except (TypeError, ValueError):
        raise IcebergMappingError(f"field {field_name!r} is not numeric: {value!r}")
    if num != num:  # NaN check without importing math
        raise IcebergMappingError(f"field {field_name!r} is NaN")
    return num
 
 
def _check_bounds(value: float, field_name: str, openberg_name: str) -> None:
    lo, hi = OPENBERG_BOUNDS[openberg_name]
    if not (lo <= value <= hi):
        raise IcebergMappingError(
            f"{field_name}={value} maps to OpenBerg '{openberg_name}', which "
            f"requires {lo} <= value <= {hi}"
        )
 
 
def map_iceberg(iceberg: Dict[str, Any]) -> Dict[str, Any]:
    """Map one project iceberg record to OpenBerg-compatible seeding fields.
 
    Input (minimum shape expected):
        {
            "id": ...,
            "latitude": ... (or "current_latitude"),
            "longitude": ... (or "current_longitude"),
            "length_m": ...,
            "width_m": ...,
            "freeboard_m": ...,
            "estimated_draft_m": ...,
        }
 
    Returns:
        {
            "id": <original project iceberg_id, untouched>,
            "lon": float,
            "lat": float,
            "length": float,
            "width": float,
            "sail": float,      # from freeboard_m -- see module docstring
            "draft": float,     # from estimated_draft_m
        }
 
    Raises:
        IcebergMappingError on any missing/invalid field. Never silently
        substitutes or clamps a bad value.
    """
    iceberg_id = _get_first(iceberg, "id", "iceberg_id")
    if iceberg_id is None:
        raise IcebergMappingError("missing required field: id (or iceberg_id)")
 
    lat = _require_number(_get_first(iceberg, "latitude", "current_latitude"), "latitude")
    lon = _require_number(_get_first(iceberg, "longitude", "current_longitude"), "longitude")
    length = _require_number(iceberg.get("length_m"), "length_m")
    width = _require_number(iceberg.get("width_m"), "width_m")
    freeboard = _require_number(iceberg.get("freeboard_m"), "freeboard_m")
    draft = _require_number(iceberg.get("estimated_draft_m"), "estimated_draft_m")
 
    if not (-90.0 <= lat <= 90.0):
        raise IcebergMappingError(f"latitude {lat} out of range [-90, 90]")
    if not (-180.0 <= lon <= 180.0):
        raise IcebergMappingError(f"longitude {lon} out of range [-180, 180]")
    if lat >= 0:
        raise IcebergMappingError(
            f"latitude {lat} is not south of the equator -- this prototype "
            f"only validates Antarctic (southern hemisphere) positions"
        )
 
    if draft <= freeboard:
        raise IcebergMappingError(
            f"estimated_draft_m ({draft}) must be greater than freeboard_m "
            f"({freeboard}) -- a draft smaller than the freeboard usually "
            f"indicates a unit or data error"
        )
 
    _check_bounds(length, "length_m", "length")
    _check_bounds(width, "width_m", "width")
    _check_bounds(freeboard, "freeboard_m", "sail")
    _check_bounds(draft, "estimated_draft_m", "draft")
 
    return {
        "id": iceberg_id,
        "lon": lon,
        "lat": lat,
        "length": length,
        "width": width,
        "sail": freeboard,
        "draft": draft,
    }
 
 
def map_icebergs(icebergs: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Map a list of project iceberg records. Order is preserved -- this
    order is what IcebergDriftModel uses to associate OpenBerg's trajectory
    index with each project iceberg_id, so do not reorder or deduplicate here.
    """
    if not icebergs:
        raise IcebergMappingError("icebergs list is empty")
    return [map_iceberg(rec) for rec in icebergs]
 