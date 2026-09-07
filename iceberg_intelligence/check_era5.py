import xarray as xr

file = "data/environmental/era5/B39+D28/data_stream-oper_stepType-instant.nc"

ds = xr.open_dataset(file)

print(ds)

print("\n================ VARIABLES ================")
for var in ds.data_vars:
    print(var)

print("\n================ COORDINATES ================")
for coord in ds.coords:
    print(coord)

print("\n================ TIME ================")
if "time" in ds.coords:
    print("Start:", ds.time.values[0])
    print("End:  ", ds.time.values[-1])

print("\n================ LATITUDE ================")
if "latitude" in ds.coords:
    print(float(ds.latitude.min()), "to", float(ds.latitude.max()))

print("\n================ LONGITUDE ================")
if "longitude" in ds.coords:
    print(float(ds.longitude.min()), "to", float(ds.longitude.max()))

ds.close()