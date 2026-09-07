from __future__ import annotations

from pathlib import Path
import pandas as pd

from data_pipeline.config import get_case, era5_path, glorys_path
from data_pipeline.load_icebergs import load_iceberg_csv


CASE = "B50"
REQUIRED_HOURS = 6


def main() -> None:
    print(f"Searching for a B50 observation with a {REQUIRED_HOURS}-hour forward window...")

    case = get_case(CASE)

    iceberg_file = Path(case["iceberg_file"])
    era5_file = Path(era5_path(CASE))
    glorys_file = Path(glorys_path(CASE))

    print(f"Iceberg file: {iceberg_file}")
    print(f"ERA5 file:    {era5_file}")
    print(f"GLORYS file:  {glorys_file}")

    if not iceberg_file.exists():
        raise FileNotFoundError(f"Missing iceberg file: {iceberg_file}")

    if not era5_file.exists():
        raise FileNotFoundError(f"Missing ERA5 file: {era5_file}")

    if not glorys_file.exists():
        raise FileNotFoundError(f"Missing GLORYS file: {glorys_file}")

    df = load_iceberg_csv(iceberg_file)

    # Only observations that actually have a usable position and geometry
    # should be considered for OpenBerg.
    candidates = df[
        df["position_available"]
        & df["geometry_available"]
        & df["openberg_geometry_compatible"]
    ].copy()

    if candidates.empty:
        print("No OpenBerg-compatible B50 observations found.")
        return

    candidates = candidates.sort_values("timestamp")

    print(f"OpenBerg-compatible B50 observations: {len(candidates)}")

    # Inspect environmental time coverage.
    era5 = pd.read_csv(
        era5_file,
        engine="python",
    ) if era5_file.suffix.lower() == ".csv" else None

    # NetCDF inspection is deliberately done with xarray here.
    import xarray as xr

    era5_ds = xr.open_dataset(era5_file)
    glorys_ds = xr.open_dataset(glorys_file)

    try:
        era5_time = pd.to_datetime(era5_ds["valid_time"].values)
        glorys_time = pd.to_datetime(glorys_ds["time"].values)

        era5_start = era5_time.min()
        era5_end = era5_time.max()
        glorys_start = glorys_time.min()
        glorys_end = glorys_time.max()

        print(f"ERA5 time:   {era5_start} -> {era5_end}")
        print(f"GLORYS time: {glorys_start} -> {glorys_end}")

        required_end = candidates["timestamp"] + pd.Timedelta(hours=REQUIRED_HOURS)

        valid = candidates[
            (candidates["timestamp"] >= era5_start)
            & (required_end <= era5_end)
            & (candidates["timestamp"] >= glorys_start)
            & (required_end <= glorys_end)
        ].copy()

        if valid.empty:
            print()
            print("No suitable observation found.")
            print(
                "There is no B50 observation with a complete "
                f"{REQUIRED_HOURS}-hour forward ERA5 + GLORYS window."
            )
            return

        print()
        print("Suitable observation(s):")
        print(
            valid[
                [
                    "timestamp",
                    "latitude",
                    "longitude",
                    "size_1_m",
                    "size_2_m",
                ]
            ].to_string(index=False)
        )

        best = valid.iloc[0]

        print()
        print("SELECTED B50 RUN:")
        print(f"timestamp : {best['timestamp']}")
        print(f"latitude  : {best['latitude']}")
        print(f"longitude : {best['longitude']}")
        print(f"length_m  : {best['size_1_m']}")
        print(f"width_m   : {best['size_2_m']}")
        print(
            f"forecast  : {best['timestamp']} -> "
            f"{best['timestamp'] + pd.Timedelta(hours=REQUIRED_HOURS)}"
        )

    finally:
        era5_ds.close()
        glorys_ds.close()


if __name__ == "__main__":
    main()
