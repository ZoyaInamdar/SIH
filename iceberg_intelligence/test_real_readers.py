from iceberg_wrapper.glorys_reader import create_glorys_reader
from iceberg_wrapper.era5_reader import create_era5_reader


glorys = create_glorys_reader(
    "data/environmental/glorys/D27.nc"
)

era5 = create_era5_reader(
    "data/environmental/era5/D27.nc"
)

print("Both readers created successfully!")
print()
print("===== GLORYS =====")
print(glorys)
print()
print("===== ERA5 =====")
print(era5)