from pathlib import Path
import xarray as xr

ERA5_DIR = Path("data/environmental/era5")

files = sorted(ERA5_DIR.rglob("*.nc"))

print(f"Found {len(files)} NetCDF files.\n")

for file in files:

    print("=" * 90)
    print(f"FILE: {file}")
    print("=" * 90)

    try:
        ds = xr.open_dataset(file)

        # Time
        if "valid_time" in ds.coords:
            time = ds["valid_time"]
        elif "time" in ds.coords:
            time = ds["time"]
        else:
            time = None

        if time is not None:
            print(f"Start time     : {time.values[0]}")
            print(f"End time       : {time.values[-1]}")
            print(f"Number of times: {len(time)}")

            if len(time) > 1:
                print(f"Time step      : {time.values[1] - time.values[0]}")

        # Variables
        print("\nVariables:")
        print("  " + ", ".join(ds.data_vars))

        # Spatial coverage
        if "latitude" in ds.coords:
            print(
                f"\nLatitude       : "
                f"{float(ds.latitude.min()):.2f} "
                f"to {float(ds.latitude.max()):.2f}"
            )

        if "longitude" in ds.coords:
            print(
                f"Longitude      : "
                f"{float(ds.longitude.min()):.2f} "
                f"to {float(ds.longitude.max()):.2f}"
            )

        # Wind
        print("\nWind:")
        print("  u10:", "YES" if "u10" in ds else "NO")
        print("  v10:", "YES" if "v10" in ds else "NO")

        ds.close()

    except Exception as e:
        print("ERROR:", e)

    print()