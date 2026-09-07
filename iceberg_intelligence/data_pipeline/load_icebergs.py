from __future__ import annotations

from pathlib import Path

import pandas as pd


REQUIRED_COLUMNS = {
    "ascat_1",
    "ascat_2",
    "ascat_3",
    "date",
    "nic_1",
    "nic_2",
    "nic_3",
    "size_1",
    "size_2",
}


def yyyyddd_to_datetime(value: object) -> pd.Timestamp:
    """Convert BYU YYYYDDD date format to a pandas timestamp."""

    text = str(value)

    if len(text) != 7 or not text.isdigit():
        raise ValueError(f"Invalid BYU date: {value}")

    year = int(text[:4])
    day_of_year = int(text[4:])

    return pd.Timestamp(year=year, month=1, day=1) + pd.Timedelta(
        days=day_of_year - 1
    )


def _valid_position(lat: object, lon: object) -> bool:
    """Check whether a latitude/longitude pair is usable."""

    if pd.isna(lat) or pd.isna(lon):
        return False

    lat = float(lat)
    lon = float(lon)

    if lat == 0.0 and lon == 0.0:
        return False

    return -90.0 <= lat <= 90.0 and -180.0 <= lon <= 180.0


def load_byu_track(
    filename: str | Path,
    sensor_policy: str = "ascat_then_nic",
) -> pd.DataFrame:
    """
    Load one BYU/NIC consolidated iceberg track.

    The raw columns are preserved.

    A separate selected position is created for pipeline processing.
    """

    filename = Path(filename)

    if not filename.exists():
        raise FileNotFoundError(f"Iceberg file not found: {filename}")

    df = pd.read_csv(filename)

    missing = REQUIRED_COLUMNS - set(df.columns)

    if missing:
        raise ValueError(
            f"Missing required BYU columns: {sorted(missing)}"
        )

    if sensor_policy not in {"ascat_then_nic", "nic_then_ascat"}:
        raise ValueError(
            "sensor_policy must be 'ascat_then_nic' "
            "or 'nic_then_ascat'"
        )

    df = df.copy()

    df["timestamp"] = df["date"].apply(yyyyddd_to_datetime)

    ascat_valid = [
        _valid_position(lat, lon)
        for lat, lon in zip(df["ascat_1"], df["ascat_2"])
    ]

    nic_valid = [
        _valid_position(lat, lon)
        for lat, lon in zip(df["nic_1"], df["nic_2"])
    ]

    selected_lat = []
    selected_lon = []
    selected_sensor = []

    for a_valid, n_valid, a_lat, a_lon, n_lat, n_lon in zip(
        ascat_valid,
        nic_valid,
        df["ascat_1"],
        df["ascat_2"],
        df["nic_1"],
        df["nic_2"],
    ):

        if sensor_policy == "ascat_then_nic":
            if a_valid:
                selected_lat.append(float(a_lat))
                selected_lon.append(float(a_lon))
                selected_sensor.append("ASCAT")
            elif n_valid:
                selected_lat.append(float(n_lat))
                selected_lon.append(float(n_lon))
                selected_sensor.append("NIC")
            else:
                selected_lat.append(float("nan"))
                selected_lon.append(float("nan"))
                selected_sensor.append(None)

        else:
            if n_valid:
                selected_lat.append(float(n_lat))
                selected_lon.append(float(n_lon))
                selected_sensor.append("NIC")
            elif a_valid:
                selected_lat.append(float(a_lat))
                selected_lon.append(float(a_lon))
                selected_sensor.append("ASCAT")
            else:
                selected_lat.append(float("nan"))
                selected_lon.append(float("nan"))
                selected_sensor.append(None)

    df["latitude"] = selected_lat
    df["longitude"] = selected_lon
    df["sensor_source"] = selected_sensor

    # BYU size fields are nautical miles.
    df["length_m"] = pd.to_numeric(
        df["size_1"], errors="coerce"
    ) * 1852.0

    df["width_m"] = pd.to_numeric(
        df["size_2"], errors="coerce"
    ) * 1852.0

    df["position_available"] = (
        df["latitude"].notna()
        & df["longitude"].notna()
    )

    df["geometry_available"] = (
        df["length_m"].notna()
        & df["width_m"].notna()
        & (df["length_m"] > 0)
        & (df["width_m"] > 0)
    )

    # OpenBerg's documented geometry limit is 10,000 m.
    df["openberg_geometry_compatible"] = (
        df["geometry_available"]
        & (df["length_m"] >= 1)
        & (df["length_m"] <= 10_000)
        & (df["width_m"] >= 1)
        & (df["width_m"] <= 10_000)
    )

    return df