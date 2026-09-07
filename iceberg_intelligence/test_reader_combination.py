from iceberg_wrapper.glorys_reader import create_glorys_reader
from iceberg_wrapper.era5_reader import create_era5_reader


# Create the two real environmental readers
glorys = create_glorys_reader(
    "data/environmental/glorys/D27.nc"
)

era5 = create_era5_reader(
    "data/environmental/era5/D27.nc"
)

print("Both environmental readers loaded.")
print()

# Check what each reader provides
print("GLORYS provides:")
print(glorys.variables)
print()

print("ERA5 provides:")
print(era5.variables)
print()

# Check a D27 location at the beginning of the GLORYS period
lon = 0.0
lat = -70.0

print(f"Test location: lon={lon}, lat={lat}")
print("Test time: 2022-05-24 00:00:00")