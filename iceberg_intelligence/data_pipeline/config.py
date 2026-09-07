from __future__ import annotations

from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]

ICEBERG_DATA_DIR = (
    PROJECT_ROOT
    / "data"
    / "iceberg"
    / "byu_nic_v8"
    / "raw"
)

ERA5_DIR = (
    PROJECT_ROOT
    / "data"
    / "environmental"
    / "era5"
)

GLORYS_DIR = (
    PROJECT_ROOT
    / "data"
    / "environmental"
    / "glorys"
)

OUTPUT_DIR = PROJECT_ROOT / "pipeline_output"


CASES = {
    "B39": {
        "iceberg_file": "b39.csv",
        "era5_file": "B39+D28.nc",
        "glorys_file": "B39+D28.nc",
    },
    "D28": {
        "iceberg_file": "d28.csv",
        "era5_file": "B39+D28.nc",
        "glorys_file": "B39+D28.nc",
    },
    "B50": {
        "iceberg_file": "b50.csv",
        "era5_file": "B50.nc",
        "glorys_file": "B50.nc",
    },
    "D21B": {
        "iceberg_file": "d21b.csv",
        "era5_file": "D21B.nc",
        "glorys_file": "D21B.nc",
    },
    "D27": {
        "iceberg_file": "d27.csv",
        "era5_file": "D27.nc",
        "glorys_file": "D27.nc",
    },
    "A73": {
        "iceberg_file": "a73.csv",
        "era5_file": "A73.grib",
        "glorys_file": "A73.nc",
    },
    "B40": {
        "iceberg_file": "b40.csv",
        "era5_file": "B40.grib",
        "glorys_file": "B40.nc",
    },
    "A69B": {
        "iceberg_file": "a69b.csv",
        "era5_file": "A69B.grib",
        "glorys_file": "A69B.nc",
    },
    "C13": {
        "iceberg_file": "c13.csv",
        "era5_file": "C13.grib",
        "glorys_file": "C13.nc",
    },
}


def get_case(case_name: str) -> dict:
    """Return configuration for one iceberg case."""

    case_name = case_name.upper()

    if case_name not in CASES:
        available = ", ".join(CASES)
        raise ValueError(
            f"Unknown case '{case_name}'. "
            f"Available cases: {available}"
        )

    return CASES[case_name]


def iceberg_path(case_name: str) -> Path:
    return ICEBERG_DATA_DIR / get_case(case_name)["iceberg_file"]


def era5_path(case_name: str) -> Path:
    return ERA5_DIR / get_case(case_name)["era5_file"]


def glorys_path(case_name: str) -> Path:
    return GLORYS_DIR / get_case(case_name)["glorys_file"]


def ensure_output_directory() -> Path:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    return OUTPUT_DIR