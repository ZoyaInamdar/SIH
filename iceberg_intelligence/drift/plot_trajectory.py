import matplotlib.pyplot as plt
from datetime import datetime

from opendrift_model import run_openberg_simulation
from opendrift_model import _build_demo_synthetic_reader


def plot_trajectory(dataset, iceberg_id="IB001"):
    """Plot the raw OpenBerg trajectory for one iceberg."""

    lon = dataset.lon.values[0]
    lat = dataset.lat.values[0]

    plt.figure(figsize=(8, 6))

    # Predicted trajectory
    plt.plot(
        lon,
        lat,
        marker="o",
        label=f"{iceberg_id} predicted trajectory"
    )

    # Start point
    plt.scatter(
        lon[0],
        lat[0],
        s=100,
        marker="o",
        label="Start"
    )

    # End point
    plt.scatter(
        lon[-1],
        lat[-1],
        s=100,
        marker="X",
        label="End"
    )

    # Number each trajectory point
    for i, (x, y) in enumerate(zip(lon, lat)):
        plt.annotate(
            str(i),
            (x, y),
            xytext=(5, 5),
            textcoords="offset points"
        )

    plt.xlabel("Longitude (°)")
    plt.ylabel("Latitude (°)")
    plt.title(f"OpenBerg Predicted Iceberg Trajectory — {iceberg_id}")

    plt.grid(True)
    plt.legend()
    plt.tight_layout()

    plt.show()


if __name__ == "__main__":

    # Use the SAME synthetic environment that successfully
    # produced your previous OpenBerg trajectory.
    reader = _build_demo_synthetic_reader()

    result = run_openberg_simulation(
        lat=-65.0,
        lon=10.0,
        time=datetime(2026, 1, 1, 12, 0, 0),
        length=500.0,
        width=300.0,
        sail=30.0,
        draft=270.0,
        duration_hours=6,
        readers=[reader],
    )

    plot_trajectory(result, "IB001")