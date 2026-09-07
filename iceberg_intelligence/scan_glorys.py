from pathlib import Path
import xarray as xr
import numpy as np


# ============================================================
# CONFIGURATION
# ============================================================

GLORYS_DIR = Path("data/environmental/glorys")


# Your selected validation cases
ICEBERG_CASES = {
    "B39": {
        "start": "2021-04-12",
        "end": "2021-10-08",
        "lat_min": -72.96,
        "lat_max": -67.96,
        "lon_min": -21.07,
        "lon_max": 40.669,
    },

    "D21B": {
        "start": "2018-03-06",
        "end": "2018-09-01",
        "lat_min": -71.049,
        "lat_max": -66.451,
        "lon_min": -11.973,
        "lon_max": 48.304,
    },

    "D27": {
        "start": "2022-05-24",
        "end": "2022-11-19",
        "lat_min": -73.25,
        "lat_max": -66.705,
        "lon_min": -20.933,
        "lon_max": 11.689,
    },

    "D28": {
        "start": "2021-04-09",
        "end": "2021-10-05",
        "lat_min": -70.764,
        "lat_max": -67.30,
        "lon_min": -11.738,
        "lon_max": 42.63,
    },

    "B50": {
        "start": "2022-03-21",
        "end": "2022-09-16",
        "lat_min": -66.513,
        "lat_max": -57.85,
        "lon_min": -166.374,
        "lon_max": -149.11,
    },
}


# Variables characteristic of GLORYS
GLORYS_VARIABLES = {
    "uo",
    "vo",
    "thetao",
    "so",
    "zos",
    "siconc",
    "sithick",
    "usi",
    "vsi",
}

# Variables characteristic of ERA5
ERA5_VARIABLES = {
    "u10",
    "v10",
}

# OpenBerg-relevant GLORYS variables
OPENBERG_VARIABLES = {
    "uo": "Ocean eastward velocity",
    "vo": "Ocean northward velocity",
    "thetao": "Ocean temperature",
    "so": "Ocean salinity",
    "zos": "Sea surface height",
    "siconc": "Sea ice concentration",
    "sithick": "Sea ice thickness",
    "usi": "Sea ice eastward velocity",
    "vsi": "Sea ice northward velocity",
}


# ============================================================
# HELPER FUNCTIONS
# ============================================================

def get_time_coordinate(ds):
    """
    Detect the time coordinate.

    GLORYS usually uses 'time'.
    ERA5 often uses 'valid_time'.
    """

    for name in ["time", "valid_time", "datetime"]:
        if name in ds.coords:
            return ds[name], name

    for name in ["time", "valid_time", "datetime"]:
        if name in ds.variables:
            return ds[name], name

    return None, None


def get_coordinate(ds, possible_names):
    """Return the first matching coordinate."""

    for name in possible_names:
        if name in ds.coords:
            return ds[name]

    for name in possible_names:
        if name in ds.variables:
            return ds[name]

    return None


def detect_dataset_type(ds):
    """
    Detect whether dataset looks like GLORYS, ERA5, or UNKNOWN.
    """

    variables = set(ds.data_vars)

    glorys_score = len(variables.intersection(GLORYS_VARIABLES))
    era5_score = len(variables.intersection(ERA5_VARIABLES))

    # Strong GLORYS signature
    if {"uo", "vo"}.issubset(variables):
        return "GLORYS"

    # Strong ERA5 signature
    if {"u10", "v10"}.issubset(variables):
        return "ERA5"

    # Partial signatures
    if glorys_score >= 3 and era5_score == 0:
        return "GLORYS?"

    if era5_score >= 1 and glorys_score == 0:
        return "ERA5?"

    return "UNKNOWN"


def parse_time_range(ds):
    """Return start/end time and number of timesteps."""

    time, time_name = get_time_coordinate(ds)

    if time is None:
        return None, None, 0, None

    try:
        values = time.values

        if len(values) == 0:
            return None, None, 0, time_name

        start = np.datetime64(values[0])
        end = np.datetime64(values[-1])

        step = None

        if len(values) > 1:
            step = values[1] - values[0]

        return start, end, len(values), step

    except Exception:
        return None, None, 0, time_name


def get_spatial_coverage(ds):
    """Return latitude and longitude ranges."""

    lat = get_coordinate(
        ds,
        ["latitude", "lat", "nav_lat"]
    )

    lon = get_coordinate(
        ds,
        ["longitude", "lon", "nav_lon"]
    )

    lat_range = None
    lon_range = None

    try:
        if lat is not None:
            lat_range = (
                float(np.nanmin(lat.values)),
                float(np.nanmax(lat.values))
            )
    except Exception:
        pass

    try:
        if lon is not None:
            lon_range = (
                float(np.nanmin(lon.values)),
                float(np.nanmax(lon.values))
            )
    except Exception:
        pass

    return lat_range, lon_range


def get_depth_info(ds):
    """Return depth information if present."""

    depth = get_coordinate(
        ds,
        ["depth", "deptht", "lev", "level"]
    )

    if depth is None:
        return None

    try:
        values = np.asarray(depth.values).astype(float)

        if len(values) == 0:
            return None

        return {
            "count": len(values),
            "min": float(np.nanmin(values)),
            "max": float(np.nanmax(values)),
            "values": values,
        }

    except Exception:
        return None


def overlaps_time(file_start, file_end, case_start, case_end):
    """Check whether file time period overlaps iceberg case."""

    if file_start is None or file_end is None:
        return False

    case_start = np.datetime64(case_start)
    case_end = np.datetime64(case_end)

    return (
        file_start <= case_end
        and file_end >= case_start
    )


def overlaps_space(lat_range, lon_range, case):
    """Check whether file spatial coverage overlaps iceberg region."""

    if lat_range is None or lon_range is None:
        return False

    file_lat_min, file_lat_max = lat_range
    file_lon_min, file_lon_max = lon_range

    lat_overlap = (
        file_lat_min <= case["lat_max"]
        and file_lat_max >= case["lat_min"]
    )

    lon_overlap = (
        file_lon_min <= case["lon_max"]
        and file_lon_max >= case["lon_min"]
    )

    return lat_overlap and lon_overlap


def identify_icebergs(file, file_start, file_end, lat_range, lon_range):
    """
    Determine which validation cases are likely represented
    by this dataset.
    """

    filename = file.stem.lower()

    results = []

    for iceberg, case in ICEBERG_CASES.items():

        filename_match = iceberg.lower() in filename

        time_match = overlaps_time(
            file_start,
            file_end,
            case["start"],
            case["end"]
        )

        space_match = overlaps_space(
            lat_range,
            lon_range,
            case
        )

        score = 0

        if filename_match:
            score += 3

        if time_match:
            score += 2

        if space_match:
            score += 2

        if score >= 2:

            reasons = []

            if filename_match:
                reasons.append("filename")

            if time_match:
                reasons.append("time")

            if space_match:
                reasons.append("location")

            results.append(
                (
                    iceberg,
                    score,
                    reasons
                )
            )

    results.sort(
        key=lambda x: x[1],
        reverse=True
    )

    return results


# ============================================================
# MAIN SCANNER
# ============================================================

files = sorted(GLORYS_DIR.rglob("*.nc"))

print()
print("=" * 100)
print("GLORYS / ERA5 DATASET SCANNER")
print("=" * 100)
print(f"Folder: {GLORYS_DIR}")
print(f"Found {len(files)} NetCDF files.")
print()


if not files:
    print("No .nc files found.")
    raise SystemExit


for file in files:

    print()
    print("=" * 100)
    print(f"FILE: {file}")
    print("=" * 100)

    try:

        ds = xr.open_dataset(file)

        # ----------------------------------------------------
        # DATASET TYPE
        # ----------------------------------------------------

        dataset_type = detect_dataset_type(ds)

        print()
        print(f"DATASET TYPE : {dataset_type}")

        # ----------------------------------------------------
        # VARIABLES
        # ----------------------------------------------------

        variables = set(ds.data_vars)

        print()
        print("VARIABLES:")

        for variable in sorted(variables):
            print(f"  {variable}")

        # ----------------------------------------------------
        # TIME
        # ----------------------------------------------------

        file_start, file_end, time_count, time_step = parse_time_range(ds)

        print()
        print("TIME:")

        if file_start is not None:

            print(f"  Coordinate     : detected")
            print(f"  Start          : {file_start}")
            print(f"  End            : {file_end}")
            print(f"  Number of times: {time_count}")

            if time_step is not None:
                print(f"  Time step      : {time_step}")

        else:

            print("  No usable time coordinate found.")

        # ----------------------------------------------------
        # SPATIAL COVERAGE
        # ----------------------------------------------------

        lat_range, lon_range = get_spatial_coverage(ds)

        print()
        print("SPATIAL COVERAGE:")

        if lat_range is not None:
            print(
                f"  Latitude       : "
                f"{lat_range[0]:.3f} to {lat_range[1]:.3f}"
            )
        else:
            print("  Latitude       : NOT FOUND")

        if lon_range is not None:
            print(
                f"  Longitude      : "
                f"{lon_range[0]:.3f} to {lon_range[1]:.3f}"
            )
        else:
            print("  Longitude      : NOT FOUND")

        # ----------------------------------------------------
        # DEPTH
        # ----------------------------------------------------

        depth_info = get_depth_info(ds)

        print()
        print("DEPTH:")

        if depth_info is not None:

            print(f"  Number of levels: {depth_info['count']}")
            print(
                f"  Range           : "
                f"{depth_info['min']:.3f} "
                f"to "
                f"{depth_info['max']:.3f} m"
            )

            print(
                f"  Values          : "
                f"{depth_info['values']}"
            )

        else:

            print("  No depth coordinate found.")

        # ----------------------------------------------------
        # OPENBERG VARIABLES
        # ----------------------------------------------------

        print()
        print("OPENBERG-RELEVANT VARIABLES:")

        for variable, description in OPENBERG_VARIABLES.items():

            status = "YES" if variable in variables else "NO"

            print(
                f"  {variable:8} : "
                f"{status:3} - {description}"
            )

        # ----------------------------------------------------
        # ICEBERG IDENTIFICATION
        # ----------------------------------------------------

        matches = identify_icebergs(
            file,
            file_start,
            file_end,
            lat_range,
            lon_range
        )

        print()
        print("LIKELY ICEBERG MATCHES:")

        if matches:

            for iceberg, score, reasons in matches:

                print(
                    f"  {iceberg:5} "
                    f"(score={score}) "
                    f"[{', '.join(reasons)}]"
                )

        else:

            print("  No strong match to selected validation cases.")

        # ----------------------------------------------------
        # COMPATIBILITY
        # ----------------------------------------------------

        print()
        print("OPENBERG SUITABILITY:")

        if dataset_type.startswith("GLORYS"):

            missing = [
                v
                for v in OPENBERG_VARIABLES
                if v not in variables
            ]

            if missing:

                print("  Status : PARTIAL")
                print(
                    "  Missing variables:",
                    ", ".join(missing)
                )

            else:

                print("  Status : GOOD VARIABLE COVERAGE")

                if depth_info is not None:

                    if depth_info["count"] == 1:

                        print(
                            "  WARNING: Only ONE depth level."
                        )

                        print(
                            "  This is suitable for initial "
                            "integration testing but NOT full "
                            "vertical OpenBerg forcing."
                        )

                    else:

                        print(
                            "  Vertical levels available: "
                            f"{depth_info['count']}"
                        )

        elif dataset_type.startswith("ERA5"):

            print(
                "  Status : ERA5 atmospheric dataset."
            )

            print(
                "  Contains wind forcing "
                "(u10/v10), not GLORYS ocean forcing."
            )

        else:

            print(
                "  Status : UNKNOWN DATASET TYPE"
            )

        # ----------------------------------------------------
        # FILE SIZE
        # ----------------------------------------------------

        size_mb = file.stat().st_size / (1024 * 1024)

        print()
        print(
            f"FILE SIZE: {size_mb:.2f} MB"
        )

        # ----------------------------------------------------
        # DIMENSIONS
        # ----------------------------------------------------

        print()
        print("DIMENSIONS:")

        for dimension, size in ds.sizes.items():

            print(
                f"  {dimension:15} : {size}"
            )

        # ----------------------------------------------------
        # GLOBAL METADATA
        # ----------------------------------------------------

        print()
        print("IMPORTANT METADATA:")

        interesting_attrs = [
            "title",
            "institution",
            "source",
            "references",
            "Conventions",
            "history",
            "subset:productId",
            "subset:datasetId",
        ]

        for attr in interesting_attrs:

            if attr in ds.attrs:

                print(
                    f"  {attr}: {ds.attrs[attr]}"
                )

        ds.close()

    except Exception as e:

        print()
        print(f"ERROR READING FILE: {e}")


# ============================================================
# SUMMARY
# ============================================================

print()
print("=" * 100)
print("SUMMARY")
print("=" * 100)

print()

for file in files:

    try:

        ds = xr.open_dataset(file)

        dataset_type = detect_dataset_type(ds)

        file_start, file_end, _, _ = parse_time_range(ds)

        lat_range, lon_range = get_spatial_coverage(ds)

        matches = identify_icebergs(
            file,
            file_start,
            file_end,
            lat_range,
            lon_range
        )

        iceberg_names = [
            m[0]
            for m in matches
        ]

        if iceberg_names:
            iceberg_text = ", ".join(iceberg_names)
        else:
            iceberg_text = "NONE"

        print(
            f"{file.name:25} | "
            f"{dataset_type:9} | "
            f"Iceberg: {iceberg_text}"
        )

        if file_start is not None:

            print(
                f"{'':25} | "
                f"{'':9} | "
                f"{str(file_start)[:10]} -> "
                f"{str(file_end)[:10]}"
            )

        ds.close()

    except Exception as e:

        print(
            f"{file.name:25} | ERROR: {e}"
        )


print()
print("=" * 100)
print("SCAN COMPLETE")
print("=" * 100)