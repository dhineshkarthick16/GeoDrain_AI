"""
D8 flow accumulation analysis.

For each cell, flow accumulation counts how many upstream cells drain
through it (including itself), following the D8 direction assigned by
flow_direction.compute_flow_direction(). This is the step that turns
individual per-cell flow directions into an actual drainage network:
cells with high accumulation lie on channels where water concentrates.

Algorithm: process cells in descending elevation order (a standard,
well-established approach for D8 accumulation — used by GDAL/TauDEM-style
implementations), pushing each cell's accumulated count downstream to the
single neighbor its D8 direction points to. This guarantees every cell is
processed only after all of its upstream contributors, without needing an
explicit recursive graph traversal.

This module performs ANALYSIS only. It does not fill sinks or condition
the DEM. Cells with no defined D8 direction (sinks, flats, or cells
adjacent to nodata — see flow_direction.py) are treated as terminal: flow
reaching them is counted but does not propagate further. This is an
honest limitation, not a bug — see FlowAccumulationResult.summary_statistics
for how much of the DEM is affected.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

import numpy as np

from src.hydrology.flow_direction import DIRECTION_CODES, UNDEFINED_DIRECTION

logger = logging.getLogger(__name__)


class FlowAccumulationError(Exception):
    """Raised when flow accumulation computation cannot proceed safely."""


# Same (row_offset, col_offset) convention as flow_direction.py's
# _NEIGHBOR_OFFSETS, keyed by the public DIRECTION_CODES so this module
# does not depend on flow_direction.py's private internals.
_CODE_TO_OFFSET: dict[int, tuple[int, int]] = {
    DIRECTION_CODES["E"]: (0, 1),
    DIRECTION_CODES["SE"]: (1, 1),
    DIRECTION_CODES["S"]: (1, 0),
    DIRECTION_CODES["SW"]: (1, -1),
    DIRECTION_CODES["W"]: (0, -1),
    DIRECTION_CODES["NW"]: (-1, -1),
    DIRECTION_CODES["N"]: (-1, 0),
    DIRECTION_CODES["NE"]: (-1, 1),
}


@dataclass(frozen=True)
class FlowAccumulationResult:
    """
    Container for flow accumulation output.

    Attributes:
        accumulation: Integer count of upstream cells draining through each
            cell (including itself). Minimum value 1 for any valid cell.
        contributing_area: accumulation * cell_size_x * cell_size_y, i.e.
            the ground-unit area draining through each cell. Only
            meaningful if cell_size_x/y are true ground-unit values
            (projected CRS) — see the same CRS caveat as flow_direction.py.
        terminal_mask: True where flow reaching this cell does not
            propagate further — either because the cell itself has no
            defined D8 direction (sink/flat/nodata-adjacent) or because
            its downstream neighbor is nodata. This includes legitimate
            DEM-edge outlets, not only sinks/flats.
        valid_mask: True where the cell has finite elevation.
        cell_size_x: Pixel width in map units, carried through from input.
        cell_size_y: Pixel height in map units.
    """

    accumulation: np.ndarray
    contributing_area: np.ndarray
    terminal_mask: np.ndarray
    valid_mask: np.ndarray
    cell_size_x: float
    cell_size_y: float

    def summary_statistics(self) -> dict[str, float]:
        """Return basic counts/extremes describing the accumulation result."""
        valid_count = int(self.valid_mask.sum())
        if valid_count == 0:
            raise FlowAccumulationError(
                "No valid cells to summarize — DEM may be entirely nodata."
            )
        valid_acc = self.accumulation[self.valid_mask]
        return {
            "valid_cell_count": valid_count,
            "max_accumulation": int(valid_acc.max()),
            "mean_accumulation": float(valid_acc.mean()),
            "terminal_cell_count": int((self.terminal_mask & self.valid_mask).sum()),
            "terminal_fraction": float(
                (self.terminal_mask & self.valid_mask).sum()
            ) / valid_count,
            "max_contributing_area": float(
                self.contributing_area[self.valid_mask].max()
            ),
        }


def compute_flow_accumulation(
    elevation: np.ndarray,
    direction: np.ndarray,
    cell_size_x: float = 1.0,
    cell_size_y: float = 1.0,
) -> FlowAccumulationResult:
    """
    Compute D8 flow accumulation from elevation and a precomputed D8
    direction array (from flow_direction.compute_flow_direction).

    Args:
        elevation: 2D elevation array (rows, cols). NaN = nodata.
        direction: 2D D8 direction code array, same shape as elevation,
            using flow_direction.DIRECTION_CODES convention. Must come
            from flow_direction.compute_flow_direction() on this same
            elevation array — accumulation trusts that every defined
            direction points to a real, in-bounds, finite-elevation cell.
        cell_size_x: True ground-unit pixel width, used only to derive
            contributing_area (does not affect the accumulation count
            itself).
        cell_size_y: True ground-unit pixel height.

    Returns:
        FlowAccumulationResult.

    Raises:
        FlowAccumulationError: on shape mismatch or degenerate input.
    """
    if elevation.ndim != 2 or direction.ndim != 2:
        raise FlowAccumulationError(
            f"Expected 2D arrays, got elevation {elevation.shape}, "
            f"direction {direction.shape}."
        )
    if elevation.shape != direction.shape:
        raise FlowAccumulationError(
            f"elevation shape {elevation.shape} does not match "
            f"direction shape {direction.shape}."
        )
    if cell_size_x <= 0 or cell_size_y <= 0:
        raise FlowAccumulationError(
            f"Degenerate cell size: dx={cell_size_x}, dy={cell_size_y}."
        )

    rows, cols = elevation.shape
    valid_mask = np.isfinite(elevation)
    n_valid = int(valid_mask.sum())

    if n_valid == 0:
        raise FlowAccumulationError("DEM contains no valid (finite) cells.")

    # Process cells in descending elevation order. Invalid cells are
    # pushed to the back by treating them as -inf, then sliced off.
    sort_key = np.where(valid_mask, elevation, -np.inf)
    order = np.argsort(sort_key.ravel())[::-1][:n_valid]
    rows_idx, cols_idx = np.unravel_index(order, (rows, cols))

    # Precompute per-cell direction codes in the same processing order.
    direction_in_order = direction[rows_idx, cols_idx]

    # Drop into plain Python lists for the hot loop — measurably faster
    # than repeated NumPy scalar indexing in CPython for large arrays.
    rows_list = rows_idx.tolist()
    cols_list = cols_idx.tolist()
    dir_list = direction_in_order.tolist()

    acc_flat: list[int] = [0] * (rows * cols)
    valid_flat = valid_mask.ravel()
    for i in range(rows * cols):
        if valid_flat[i]:
            acc_flat[i] = 1

    terminal_flat: list[bool] = [False] * (rows * cols)

    logger.info(
        "Computing flow accumulation for %d valid cells (elevation-sorted, "
        "single pass).",
        n_valid,
    )

    for i in range(n_valid):
        r = rows_list[i]
        c = cols_list[i]
        code = dir_list[i]
        self_idx = r * cols + c

        if code == UNDEFINED_DIRECTION:
            terminal_flat[self_idx] = True
            continue

        dr, dc = _CODE_TO_OFFSET[code]
        nr, nc = r + dr, c + dc

        if 0 <= nr < rows and 0 <= nc < cols and valid_flat[nr * cols + nc]:
            down_idx = nr * cols + nc
            acc_flat[down_idx] += acc_flat[self_idx]
        else:
            # Direction pointed at a nodata/out-of-bounds cell — should not
            # happen given flow_direction.py's contract, but guarded rather
            # than silently propagating into an invalid cell.
            terminal_flat[self_idx] = True

    accumulation = np.array(acc_flat, dtype=np.int64).reshape(rows, cols)
    terminal_mask = np.array(terminal_flat, dtype=bool).reshape(rows, cols)

    accumulation = np.where(valid_mask, accumulation, 0)
    contributing_area = accumulation.astype(np.float64) * cell_size_x * cell_size_y
    terminal_mask = terminal_mask & valid_mask

    logger.info(
        "Flow accumulation complete: max=%d, terminal cells=%d.",
        int(accumulation.max()),
        int(terminal_mask.sum()),
    )

    return FlowAccumulationResult(
        accumulation=accumulation,
        contributing_area=contributing_area,
        terminal_mask=terminal_mask,
        valid_mask=valid_mask,
        cell_size_x=cell_size_x,
        cell_size_y=cell_size_y,
    )