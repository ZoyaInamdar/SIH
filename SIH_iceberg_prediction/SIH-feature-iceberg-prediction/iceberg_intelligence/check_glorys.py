import xarray as xr

file = "data/environmental/glorys/B39+D28.nc"

ds = xr.open_dataset(file)

print(ds)
print("\nVariables:")
print(list(ds.data_vars))

print("\nDimensions:")
print(ds.dims)

ds.close()