import time
import rasterio
import numpy as np
from src.preprocessing.dem_conditioning import fill_sinks

path = input("Enter path to your DEM file: ").strip().strip('"').strip("'")

with rasterio.open(path) as ds:
    elevation = ds.read(1).astype("float32")
    nodata = ds.nodata
    if nodata is not None:
        elevation = np.where(elevation == nodata, np.nan, elevation)

print(f"DEM shape: {elevation.shape}, valid cells: {int(np.isfinite(elevation).sum()):,}")

start = time.perf_counter()
result = fill_sinks(elevation)
elapsed = time.perf_counter() - start

stats = result.summary_statistics()
print(f"Elapsed: {elapsed:.2f} seconds")
print(f"Cells modified: {stats['cells_modified']:,} ({stats['cells_modified_fraction']*100:.2f}%)")
print(f"Max fill depth: {stats['max_fill_depth']:.4f}")
