from pathlib import Path
import rasterio


def load_raster(file_path: str) -> dict:
    """
    Load a raster file such as a DEM GeoTIFF
    and return metadata and elevation statistics.
    """

    path = Path(file_path)

    if not path.exists():
        raise FileNotFoundError(f"Raster file not found: {file_path}")

    with rasterio.open(path) as src:
        data = src.read(1, masked=True)

        result = {
            "file_name": path.name,
            "width": src.width,
            "height": src.height,
            "crs": str(src.crs),
            "bounds": src.bounds,
            "min_elevation": float(data.min()),
            "max_elevation": float(data.max()),
            "mean_elevation": float(data.mean()),
            "nodata": src.nodata,
        }

    return result