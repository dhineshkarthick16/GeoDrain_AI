"""
Vector stream network export.

Converts the raster stream classification (boolean mask, one pixel = one
"is this a stream cell" decision) into connected vector line geometry
(GeoJSON LineStrings), suitable for import into QGIS, ArcGIS, or as input
geometry for HEC-RAS.

Approach: skeletonize the stream mask down to 1-pixel-wide centerlines,
then convert the skeleton into a graph (nodes = junctions/endpoints,
edges = pixel paths between them) using `sknw`, and export each edge as
a real-world-coordinate LineString using the DEM's affine transform.
"""

from __future__ import annotations

import json
from dataclasses import dataclass

import numpy as np
import sknw
from skimage.morphology import skeletonize


class StreamVectorizationError(Exception):
    """Raised when the stream mask cannot be vectorized."""


@dataclass
class StreamVectorizationResult:
    geojson: dict
    line_count: int
    total_length: float  # sum of line lengths, in the DEM's CRS units (meters for a projected CRS)


def _pixel_to_world(transform, row: int, col: int) -> tuple[float, float]:
    """Convert a (row, col) pixel index to real-world (x, y) using the
    DEM's affine transform. Uses pixel-center convention (+0.5, +0.5)."""
    x, y = transform * (col + 0.5, row + 0.5)
    return float(x), float(y)


def vectorize_stream_network(
    stream_mask: np.ndarray,
    transform,
    crs: str,
) -> StreamVectorizationResult:
    """
    Convert a boolean stream-cell raster mask into a GeoJSON
    FeatureCollection of LineStrings.

    Parameters
    ----------
    stream_mask:
        2D boolean array, True where a cell is classified as a stream
        (e.g. StreamExtractionResult.stream_mask).
    transform:
        The DEM's real-world affine transform (rasterio/affine.Affine),
        e.g. DEMAnalysis.transform. Must not be None - a synthetic
        origin-at-zero transform will silently mislocate the output.
    crs:
        The DEM's CRS string (e.g. DEMAnalysis.crs), included in the
        GeoJSON as a property on each feature for traceability. GeoJSON
        itself is CRS-agnostic (no CRS member is written to the file, per
        current GeoJSON spec, RFC 7946, which assumes WGS84) - if the
        source CRS is not WGS84 (EPSG:4326), the exported coordinates will
        be in the source CRS's units (e.g. UTM meters), NOT lon/lat. Most
        GIS software (QGIS, ArcGIS) will still import this correctly if
        the user specifies the correct source CRS on import.

    Returns
    -------
    StreamVectorizationResult with the GeoJSON dict, line count, and
    total network length.
    """

    if transform is None:
        raise StreamVectorizationError(
            "DEM transform is missing (None) - cannot produce "
            "georeferenced vector output. Re-run analysis on a freshly "
            "uploaded DEM (older session state may predate transform "
            "capture)."
        )

    if stream_mask is None or not np.any(stream_mask):
        raise StreamVectorizationError(
            "Stream mask is empty - no stream cells to vectorize."
        )

    skeleton = skeletonize(stream_mask.astype(bool))

    if not np.any(skeleton):
        raise StreamVectorizationError(
            "Skeletonization produced no centerline pixels from the "
            "stream mask."
        )

    try:
        graph = sknw.build_sknw(skeleton)
    except Exception as exc:  # noqa: BLE001
        raise StreamVectorizationError(
            f"Skeleton-to-graph conversion failed: {exc}"
        ) from exc

    features = []
    total_length = 0.0

    for start_node, end_node, edge_data in graph.edges(data=True):
        # 'pts' is an array of (row, col) pixel coordinates along this
        # edge, in skeleton pixel space, ordered along the path.
        pixel_path = edge_data.get("pts")
        if pixel_path is None or len(pixel_path) < 2:
            continue

        world_coords = [
            _pixel_to_world(transform, int(r), int(c)) for r, c in pixel_path
        ]

        # Length in real-world units (meters, for a projected CRS).
        segment_length = float(
            np.sum(
                np.sqrt(
                    np.sum(
                        np.diff(np.array(world_coords), axis=0) ** 2, axis=1
                    )
                )
            )
        )
        total_length += segment_length

        features.append(
            {
                "type": "Feature",
                "geometry": {
                    "type": "LineString",
                    "coordinates": world_coords,
                },
                "properties": {
                    "length": round(segment_length, 2),
                    "source_crs": crs,
                },
            }
        )

    if not features:
        raise StreamVectorizationError(
            "No line segments could be extracted from the stream "
            "skeleton graph."
        )

    geojson = {
        "type": "FeatureCollection",
        "features": features,
    }

    return StreamVectorizationResult(
        geojson=geojson,
        line_count=len(features),
        total_length=total_length,
    )


def geojson_bytes(result: StreamVectorizationResult) -> bytes:
    """Serialize the GeoJSON FeatureCollection to UTF-8 encoded bytes,
    ready for a file download."""
    return json.dumps(result.geojson, indent=2).encode("utf-8")