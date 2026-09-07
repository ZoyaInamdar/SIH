from __future__ import annotations

from pathlib import Path

import numpy as np
import xarray as xr


def format_value(value) -> str:
    """Convert an xarray/NumPy value into readable text."""
    try:
        if np.ndim(value) == 0:
            return str(value.item())
        return str(value)
    except Exception:
        return str(value)


def inspect_file(path: Path) -> None:
    """Print useful metadata for one NetCDF file."""

    print("=" * 80)
    print(f"FILE: {path}")
    print("=" * 80)

    if not path.exists():
        print(f"ERROR: File not found: {path}")
        return

    try:
        with xr.open_dataset(path) as ds:

            print("\nDIMENSIONS")
            print("-" * 80)
            for name, size in ds.sizes.items():
                print(f"{name}: {size}")

            print("\nCOORDINATES")
            print("-" * 80)

            for name, coord in ds.coords.items():
                print(f"\n{name}")
                print(f"  dimensions: {coord.dims}")
                print(f"  shape:      {coord.shape}")
                print(f"  dtype:      {coord.dtype}")

                if coord.size > 0:
                    try:
                        print(f"  first:      {format_value(coord.values.flat[0])}")
                        print(f"  last:       {format_value(coord.values.flat[-1])}")
                    except Exception:
                        pass

                if coord.attrs:
                    print("  attributes:")
                    for key, value in coord.attrs.items():
                        print(f"    {key}: {format_value(value)}")

            print("\nDATA VARIABLES")
            print("-" * 80)

            for name, variable in ds.data_vars.items():
                print(f"\n{name}")
                print(f"  dimensions: {variable.dims}")
                print(f"  shape:      {variable.shape}")
                print(f"  dtype:      {variable.dtype}")

                # Safely handle both normal and scalar variables.
                if variable.size > 0:
                    try:
                        values = variable.values

                        if np.ndim(values) == 0:
                            print(
                                f"  sample:     {format_value(values)}"
                            )
                        else:
                            print(
                                f"  first:      "
                                f"{format_value(values.flat[0])}"
                            )
                            print(
                                f"  last:       "
                                f"{format_value(values.flat[-1])}"
                            )
                    except Exception as exc:
                        print(f"  sample:     unavailable ({exc})")

                if variable.attrs:
                    print("  attributes:")
                    for key, value in variable.attrs.items():
                        print(f"    {key}: {format_value(value)}")

            print("\nGLOBAL ATTRIBUTES")
            print("-" * 80)

            if ds.attrs:
                for key, value in ds.attrs.items():
                    print(f"{key}: {format_value(value)}")
            else:
                print("(none)")

            print("\nSUCCESS: Metadata inspection completed.")

    except Exception as exc:
        print(f"\nERROR while reading {path}:")
        print(f"{type(exc).__name__}: {exc}")


def main() -> None:
    """Inspect all NetCDF files in the environmental data folders."""

    search_roots = [
        Path("data/environmental/era5"),
        Path("data/environmental/glorys"),
    ]

    files: list[Path] = []

    for root in search_roots:
        if root.exists():
            files.extend(sorted(root.rglob("*.nc")))

    if not files:
        raise FileNotFoundError(
            "No .nc files found under data/environmental/era5 "
            "or data/environmental/glorys."
        )

    print(f"Found {len(files)} NetCDF file(s).")

    for path in files:
        inspect_file(path)


if __name__ == "__main__":
    main()