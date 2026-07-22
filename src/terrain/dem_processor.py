from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np
import rasterio


@dataclass
class DEMAnalysis:
    min_elevation: float
    max_elevation: float
    mean_elevation: float
    elevation_range: float
    rows: int
    columns: int
    crs: str
    resolution_x: float
    resolution_y: float
    nodata_value: Any


def analyze_dem(file_object) -> tuple[np.ndarray, DEMAnalysis]:
    """
    Read a DEM/DTM GeoTIFF and calculate basic terrain statistics.

    Parameters
    ----------
    file_object:
        Streamlit UploadedFile or any file-like object accepted by rasterio.

    Returns
    -------
    elevation_array:
        2D NumPy elevation array.

    analysis:
        DEMAnalysis containing terrain metadata and statistics.
    """

    with rasterio.MemoryFile(file_object.getvalue()) as memory_file:

        with memory_file.open() as dataset:

            elevation = dataset.read(1).astype("float32")

            nodata = dataset.nodata

            if nodata is not None:

                elevation = np.where(
                    elevation == nodata,
                    np.nan,
                    elevation
                )

            valid_elevation = elevation[
                np.isfinite(elevation)
            ]

            if valid_elevation.size == 0:

                raise ValueError(
                    "The DEM does not contain valid elevation values."
                )

            analysis = DEMAnalysis(

                min_elevation=float(
                    np.min(valid_elevation)
                ),

                max_elevation=float(
                    np.max(valid_elevation)
                ),

                mean_elevation=float(
                    np.mean(valid_elevation)
                ),

                elevation_range=float(
                    np.max(valid_elevation)
                    - np.min(valid_elevation)
                ),

                rows=dataset.height,

                columns=dataset.width,

                crs=str(dataset.crs),

                resolution_x=float(
                    dataset.res[0]
                ),

                resolution_y=float(
                    dataset.res[1]
                ),

                nodata_value=nodata
            )

    return elevation, analysis