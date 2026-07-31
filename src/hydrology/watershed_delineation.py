"""
Watershed / catchment delineation via pour-point upstream tracing.

Given a single "pour point" (row, col), finds every cell whose D8 flow
path eventually passes through that point — the catchment/upstream
drainage area for that specific location. This answers the practical
question "what area drains to here", which is what most drainage-planning
decisions actually need.

This is deliberately scoped as single-pour-point delineation rather than
automatic whole-DEM basin labeling: on an unconditioned DEM (see
flow_direction.py / flow_accumulation.py notes on sinks and flats),
automatic basin labeling would fragment into a very large number of tiny,
mostly-artifactual micro-basins. Pour-point delineation sidesteps that by
letting the user choose one meaningful location, matching how real GIS
tools (ArcGIS Watershed, QGIS/SAGA Upslope Area) are typically used in
practice.

Algorithm: reverse breadth-first search on the D8 direction graph. A
neighbor is included in the catchment if its own D8 direction points
back toward an already-included cell. This mirrors flow_accumulation.py's
forward traversal but starts from a single point instead of every cell.
"""

from __future__ import annotations

import logging
from collections import deque
from dataclasses import dataclass

import numpy as np

from src.hydrology.flow_direction import DIRECTION_CODES, UNDEFINED_DIRECTION

logger = logging.getLogger(__name__)


class WatershedDelineationError(Exception):
    """Raised when catchment delineation cannot proceed safely."""


# For a neighbor at offset (dr, dc) from the current cell, the neighbor's
# own D8 direction must equal _OFFSET_TO_CODE[(-dr, -dc)] for its flow to
# point back toward the current cell.
_OFFSET_TO_CODE: dict[tuple[int, int], int] = {
    (0, 1): DIRECTION_CODES["E"],
    (1, 1): DIRECTION_CODES["SE"],
    (1, 0): DIRECTION_CODES["S"],
    (1, -1): DIRECTION_CODES["SW"],
    (0, -1): DIRECTION_CODES["W"],
    (-1, -1): DIRECTION_CODES["NW"],
    (-1, 0): DIRECTION_CODES["N"],
    (-1, 1): DIRECTION_CODES["NE"],
}
_NEIGHBOR_OFFSETS = list(_OFFSET_TO_CODE.keys())


@dataclass(frozen=True)
class CatchmentResult:
    """
    Container for pour-point catchment delineation output.

    Attributes:
        catchment_mask: Boolean array, True for every cell whose D8 flow
            path drains through the pour point (including the pour point
            itself).
        pour_row: Row index of the pour point.
        pour_col: Column index of the pour point.
        cell_count: Number of cells in the catchment.
        area: cell_count * cell_size_x * cell_size_y (ground-unit area,
            only meaningful for a projected CRS).
    """

    catchment_mask: np.ndarray
    pour_row: int
    pour_col: int
    cell_count: int
    area: float


def delineate_catchment(
    direction: np.ndarray,
    valid_mask: np.ndarray,
    pour_row: int,
    pour_col: int,
    cell_size_x: float = 1.0,
    cell_size_y: float = 1.0,
) -> CatchmentResult:
    """
    Trace the upstream catchment draining to a single pour point.

    Args:
        direction: 2D D8 direction array (from
            flow_direction.compute_flow_direction()).
        valid_mask: 2D boolean array, True where the cell has a defined
            elevation (from the same flow direction result).
        pour_row: Row index of the chosen pour point.
        pour_col: Column index of the chosen pour point.
        cell_size_x: True ground-unit pixel width, used only for area.
        cell_size_y: True ground-unit pixel height, used only for area.

    Returns:
        CatchmentResult.

    Raises:
        WatershedDelineationError: if shapes mismatch, the pour point is
            out of bounds, or it is not a valid (finite-elevation) cell.
    """
    if direction.shape != valid_mask.shape:
        raise WatershedDelineationError(
            f"direction shape {direction.shape} does not match "
            f"valid_mask shape {valid_mask.shape}."
        )

    rows, cols = direction.shape

    if not (0 <= pour_row < rows and 0 <= pour_col < cols):
        raise WatershedDelineationError(
            f"Pour point ({pour_row}, {pour_col}) is out of bounds for "
            f"a {rows}x{cols} array."
        )
    if not valid_mask[pour_row, pour_col]:
        raise WatershedDelineationError(
            f"Pour point ({pour_row}, {pour_col}) is not a valid "
            "(finite-elevation) cell — choose a different location."
        )

    catchment = np.zeros((rows, cols), dtype=bool)
    catchment[pour_row, pour_col] = True

    queue: deque[tuple[int, int]] = deque()
    queue.append((pour_row, pour_col))

    while queue:
        r, c = queue.popleft()
        for dr, dc in _NEIGHBOR_OFFSETS:
            nr, nc = r + dr, c + dc
            if not (0 <= nr < rows and 0 <= nc < cols):
                continue
            if catchment[nr, nc] or not valid_mask[nr, nc]:
                continue
            neighbor_code = direction[nr, nc]
            if neighbor_code == UNDEFINED_DIRECTION:
                continue
            required_code = _OFFSET_TO_CODE[(-dr, -dc)]
            if neighbor_code == required_code:
                catchment[nr, nc] = True
                queue.append((nr, nc))

    cell_count = int(catchment.sum())
    area = cell_count * cell_size_x * cell_size_y

    logger.info(
        "Catchment delineated for pour point (%d, %d): %d cells, area=%.2f.",
        pour_row, pour_col, cell_count, area,
    )

    return CatchmentResult(
        catchment_mask=catchment,
        pour_row=pour_row,
        pour_col=pour_col,
        cell_count=cell_count,
        area=area,
    )