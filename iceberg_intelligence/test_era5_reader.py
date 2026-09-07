from iceberg_wrapper.era5_reader import create_era5_reader

filename = "data/environmental/era5/D27.nc"

reader = create_era5_reader(filename)

print("ERA5 reader created successfully!")
print(reader)