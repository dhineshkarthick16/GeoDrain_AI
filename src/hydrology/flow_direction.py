"""
D8 flow direction analysis.

Implements the standard D8 algorithm (O'Callaghan & Mark, 1984): for each
cell, compare elevation to its 8 immediate neighbors and route flow toward
the neighbor with the steepest descent. This is the same convention used
by ArcGIS/GDAL/QGIS, using ESRI's power-of-two direction codes so results
are directly comparable to those tools.

This module performs ANALYSIS only — it does not fill sinks or condition
the DEM. Flat areas and sinks (no lower neighbor) are explicitly marked as
undefined rather than assigned a fabricated direction. Proper hydrological
conditioning (sink-filling) is a separate, future processing step.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

import numpy as np

logger = logging.getLogger(__name__)


class FlowDirectionError(Exception):
    """Raised when flow direction computation cannot proceed safely."""


# ESRI-style D8 direction codes: powers of two, clockwise from East.
# Index order matches the 8 neighbor offsets used below.
DIRECTION_CODES = {
    "E": 1,
    "SE": 2,
    "S": 4,
    "SW": 8,
    "W": 16,
    "NW": 32,
    "N": 64,
    "NE": 128,
}
UNDEFINED_DIRECTION = 0  # flat, sink, or nodata-adjacent cell

# (row_offset, col_offset, direction_code, is_diagonal)
_NEIGHBOR_OFFSETS = [
    (0, 1, DIRECTION_CODES["E"], False),
    (1, 1, DIRECTION_CODES["SE"], True),
    (1, 0, DIRECTION_CODES["S"], False),
    (1, -1, DIRECTION_CODES["SW"], True),
    (0, -1, DIRECTION_CODES["W"], False),
    (-1, -1, DIRECTION_CODES["NW"], True),
    (-1, 0, DIRECTION_CODES["N"], False),
    (-1, 1, DIRECTION_CODES["NE"], True),
]


@dataclass(frozen=True)
class FlowDirectionResult:
    """
    Container for D8 flow direction output.

    Attributes:
        direction: Integer D8 direction code per cell (see DIRECTION_CODES).
            0 (UNDEFINED_DIRECTION) marks flat cells, sinks (local minima
            with no lower neighbor), or cells adjacent to nodata.
        is_sink: Boolean array, True where a cell has no lower neighbor
            (a local minimum / depression) and is not nodata.
        is_flat: Boolean array, True where a cell's lowest neighbor is at
            an equal elevation (ambiguous flow direction).
        valid_mask: Boolean array, True where the cell itself and its full
            3x3 neighborhood are free of nodata.
        cell_size_x: Pixel width in map units, carried through for
            downstream flow-accumulation distance weighting.
        cell_size_y: Pixel height in map units.
    """

    direction: np.ndarray
    is_sink: np.ndarray
    is_flat: np.ndarray
    valid_mask: np.ndarray
    cell_size_x: float
    cell_size_y: float

    def summary_statistics(self) -> dict[str, float]:
        """Return basic counts describing the flow direction result."""
        valid_count = int(self.valid_mask.sum())
        if valid_count == 0:
            raise FlowDirectionError(
                "No valid cells to summarize — DEM may be entirely nodata."
            )
        defined = self.valid_mask & (self.direction != UNDEFINED_DIRECTION)
        return {
            "valid_cell_count": valid_count,
            "total_cell_count": int(self.valid_mask.size),
            "defined_direction_count": int(defined.sum()),
            "sink_count": int((self.is_sink & self.valid_mask).sum()),
            "flat_count": int((self.is_flat & self.valid_mask).sum()),
            "defined_direction_fraction": float(defined.sum()) / valid_count,
        }


def direction_code_to_label(code: int) -> str:
    """Map a D8 direction code back to its compass label (e.g. 1 -> 'E')."""
    for label, value in DIRECTION_CODES.items():
        if value == code:
            return label
    return "Undefined" if code == UNDEFINED_DIRECTION else f"Unknown({code})"


def compute_flow_direction(
    elevation: np.ndarray,
    cell_size_x: float,
    cell_size_y: float,
) -> FlowDirectionResult:
    """
    Compute D8 flow direction from a DEM elevation array.

    Args:
        elevation: 2D array of elevation values (rows, cols). NaN cells
            are treated as nodata (matching dem_processor.py's convention
            of converting nodata to np.nan).
        cell_size_x: True ground-unit pixel width (e.g. meters). Must be
            a projected-CRS value — see CRS validity note below.
        cell_size_y: True ground-unit pixel height.

    Returns:
        FlowDirectionResult with direction/sink/flat arrays matching the
        input shape.

    Raises:
        FlowDirectionError: if the input array is not 2D, too small for
            a 3x3 neighborhood, or cell sizes are degenerate.

    Note on CRS:
        This function does not itself validate CRS — callers (e.g. the
        Workspace page) are responsible for warning the user if the DEM
        is in a geographic CRS, since cell_size_x/cell_size_y would not
        be true ground distances in that case and the diagonal-distance
        weighting below would be scientifically invalid.
    """
    if elevation.ndim != 2:
        raise FlowDirectionError(
            f"Expected a 2D elevation array, got shape {elevation.shape}."
        )
    if elevation.shape[0] < 3 or elevation.shape[1] < 3:
        raise FlowDirectionError(
            "DEM must be at least 3x3 cells to compute flow direction "
            f"(got {elevation.shape})."
        )
    if cell_size_x <= 0 or cell_size_y <= 0:
        raise FlowDirectionError(
            f"Degenerate cell size: dx={cell_size_x}, dy={cell_size_y}."
        )

    dem = elevation.astype(np.float64, copy=True)
    nodata_mask = ~np.isfinite(dem)

    rows, cols = dem.shape
    # Pad with NaN so any cell touching the DEM boundary is correctly
    # treated as having an undefined neighbor, not a fabricated one.
    padded = np.pad(dem, pad_width=1, mode="constant", constant_values=np.nan)

    direction = np.full((rows, cols), UNDEFINED_DIRECTION, dtype=np.int16)
    is_sink = np.zeros((rows, cols), dtype=bool)
    is_flat = np.zeros((rows, cols), dtype=bool)

    # Track steepest descent (drop per unit distance) found so far.
    best_drop_per_distance = np.zeros((rows, cols), dtype=np.float64)
    neighbor_seen = np.zeros((rows, cols), dtype=bool)
    equal_elevation_seen = np.zeros((rows, cols), dtype=bool)

    center = padded[1:-1, 1:-1]

    for row_off, col_off, code, is_diagonal in _NEIGHBOR_OFFSETS:
        neighbor = padded[1 + row_off : 1 + row_off + rows, 1 + col_off : 1 + col_off + cols]

        neighbor_valid = np.isfinite(neighbor) & np.isfinite(center)

        distance = (
            np.sqrt((cell_size_x**2) + (cell_size_y**2))
            if is_diagonal
            else (cell_size_x if row_off == 0 else cell_size_y)
        )

        drop = center - neighbor  # positive means neighbor is lower
        drop_per_distance = np.where(neighbor_valid, drop / distance, -np.inf)

        is_lower = neighbor_valid & (drop_per_distance > 0)
        is_equal = neighbor_valid & np.isclose(drop, 0.0)

        improves = is_lower & (
            (~neighbor_seen) | (drop_per_distance > best_drop_per_distance)
        )
        direction = np.where(improves, code, direction)
        best_drop_per_distance = np.where(improves, drop_per_distance, best_drop_per_distance)
        neighbor_seen = neighbor_seen | is_lower

        equal_elevation_seen = equal_elevation_seen | is_equal

    is_sink = (~neighbor_seen) & (~equal_elevation_seen) & np.isfinite(dem)
    is_flat = (~neighbor_seen) & equal_elevation_seen & np.isfinite(dem)
    direction = np.where(is_sink, UNDEFINED_DIRECTION, direction)

    # A cell is only "valid" for reporting if it and its full 3x3
    # neighborhood are nodata-free (matches slope_analysis.py convention).
    kernel_invalid = np.zeros((rows, cols), dtype=bool)
    if nodata_mask.any():
        padded_invalid = np.pad(nodata_mask, pad_width=1, mode="edge")
        for dr in range(3):
            for dc in range(3):
                kernel_invalid |= padded_invalid[dr : dr + rows, dc : dc + cols]

    valid_mask = ~kernel_invalid & np.isfinite(dem)
    direction = np.where(valid_mask, direction, UNDEFINED_DIRECTION)
    is_sink = is_sink & valid_mask
    is_flat = is_flat & valid_mask

    logger.info(
        "Flow direction computed: %d valid cells, %d sinks, %d flats.",
        int(valid_mask.sum()),
        int(is_sink.sum()),
        int(is_flat.sum()),
    )

    return FlowDirectionResult(
        direction=direction,
        is_sink=is_sink,
        is_flat=is_flat,
        valid_mask=valid_mask,
        cell_size_x=cell_size_x,
        cell_size_y=cell_size_y,
    )