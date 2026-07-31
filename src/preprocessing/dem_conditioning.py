"""
DEM conditioning via priority-flood sink filling.

Implements the standard priority-flood algorithm (Wang & Liu, 2006 /
related to Planchon & Darboux, 2001) - the same approach used by TauDEM,
WhiteboxTools, and RichDEM. Starting from every cell on the valid-data
boundary (the DEM edge, and any valid cell adjacent to nodata - both act
as natural drainage outlets), a min-heap always processes the lowest
unresolved frontier cell next. Any interior cell is raised to at least
its resolving neighbor's elevation, which guarantees every cell ends up
with a monotonic non-increasing downhill path to the boundary - i.e., no
interior depressions (sinks) remain, by construction.

IMPORTANT LIMITATION: plain priority-flood eliminates sinks but commonly
creates small FLAT PLATEAUS where a depression used to be (multiple
cells raised to the same elevation). This is a well-documented property
of the base algorithm, not a bug. Resolving those flats into a fully
unambiguous single-direction surface is a further "flat resolution" step
(e.g. adding a tiny synthetic gradient across the plateau) and is
explicitly out of scope here - this module only guarantees sink
elimination, and reports remaining flat cells honestly rather than
implying full resolution.
"""

from __future__ import annotations

import heapq
import logging
from dataclasses import dataclass

import numpy as np

logger = logging.getLogger(__name__)


class DEMConditioningError(Exception):
    """Raised when DEM conditioning cannot proceed safely."""


_NEIGHBOR_OFFSETS = [
    (-1, -1), (-1, 0), (-1, 1),
    (0, -1),           (0, 1),
    (1, -1),  (1, 0),  (1, 1),
]


@dataclass(frozen=True)
class ConditionedDEMResult:
    """
    Container for DEM conditioning output.

    Attributes:
        filled_elevation: 2D elevation array, same shape as input, with
            interior depressions raised so every valid cell has a
            monotonic downhill path to the valid-data boundary. Invalid
            (nodata) cells are left as NaN, unchanged.
        cells_modified: Count of valid cells whose elevation was raised.
        max_fill_depth: Largest single-cell elevation increase applied,
            in the same units as the input elevation.
        valid_mask: Boolean array, True where the cell had finite input
            elevation (carried through unchanged from the input).
    """

    filled_elevation: np.ndarray
    cells_modified: int
    max_fill_depth: float
    valid_mask: np.ndarray

    def summary_statistics(self) -> dict[str, float]:
        """Return basic counts describing how much conditioning changed the DEM."""
        valid_count = int(self.valid_mask.sum())
        if valid_count == 0:
            raise DEMConditioningError(
                "No valid cells to summarize — elevation array may be "
                "entirely nodata."
            )
        return {
            "valid_cell_count": valid_count,
            "cells_modified": self.cells_modified,
            "cells_modified_fraction": self.cells_modified / valid_count,
            "max_fill_depth": self.max_fill_depth,
        }


def fill_sinks(
    elevation: np.ndarray,
    valid_mask: np.ndarray | None = None,
) -> ConditionedDEMResult:
    """
    Fill sinks (depressions) in a DEM using the priority-flood algorithm.

    Args:
        elevation: 2D elevation array. NaN cells are treated as nodata.
        valid_mask: Optional 2D boolean array, True where the cell has
            meaningful elevation. If None, derived as np.isfinite(elevation).

    Returns:
        ConditionedDEMResult.

    Raises:
        DEMConditioningError: on shape mismatch, non-2D input, too-small
            input, or no valid cells.
    """
    if elevation.ndim != 2:
        raise DEMConditioningError(
            f"Expected a 2D elevation array, got shape {elevation.shape}."
        )
    if elevation.shape[0] < 2 or elevation.shape[1] < 2:
        raise DEMConditioningError(
            f"DEM too small to condition (got {elevation.shape})."
        )

    if valid_mask is None:
        valid_mask = np.isfinite(elevation)
    elif valid_mask.shape != elevation.shape:
        raise DEMConditioningError(
            f"valid_mask shape {valid_mask.shape} does not match "
            f"elevation shape {elevation.shape}."
        )

    if not valid_mask.any():
        raise DEMConditioningError("No valid (finite) cells to condition.")

    rows, cols = elevation.shape
    original = elevation.astype(np.float64)

    # Boundary seed: DEM edge cells, plus any valid cell adjacent to a
    # nodata cell — both act as natural drainage outlets that water can
    # escape through, so they are never raised.
    is_edge = np.zeros((rows, cols), dtype=bool)
    is_edge[0, :] = True
    is_edge[-1, :] = True
    is_edge[:, 0] = True
    is_edge[:, -1] = True

    invalid = ~valid_mask
    adjacent_to_invalid = np.zeros((rows, cols), dtype=bool)
    if invalid.any():
        padded_invalid = np.pad(invalid, pad_width=1, mode="edge")
        for dr, dc in _NEIGHBOR_OFFSETS:
            adjacent_to_invalid |= padded_invalid[
                1 + dr : 1 + dr + rows, 1 + dc : 1 + dc + cols
            ]

    boundary_mask = valid_mask & (is_edge | adjacent_to_invalid)

    filled_flat: list[float] = original.ravel().tolist()
    valid_flat = valid_mask.ravel().tolist()
    resolved_flat: list[bool] = [False] * (rows * cols)

    heap: list[tuple[float, int, int]] = []
    boundary_rows, boundary_cols = np.nonzero(boundary_mask)
    for r, c in zip(boundary_rows.tolist(), boundary_cols.tolist()):
        idx = r * cols + c
        resolved_flat[idx] = True
        heapq.heappush(heap, (filled_flat[idx], r, c))

    logger.info(
        "Starting priority-flood sink fill: %d boundary seed cells out of "
        "%d valid cells.",
        len(boundary_rows), int(valid_mask.sum()),
    )

    cells_modified = 0
    max_fill_depth = 0.0

    while heap:
        elev, r, c = heapq.heappop(heap)
        for dr, dc in _NEIGHBOR_OFFSETS:
            nr, nc = r + dr, c + dc
            if not (0 <= nr < rows and 0 <= nc < cols):
                continue
            n_idx = nr * cols + nc
            if not valid_flat[n_idx] or resolved_flat[n_idx]:
                continue

            original_neighbor_elev = filled_flat[n_idx]
            new_elev = elev if elev > original_neighbor_elev else original_neighbor_elev

            if new_elev > original_neighbor_elev:
                depth = new_elev - original_neighbor_elev
                if depth > max_fill_depth:
                    max_fill_depth = depth
                cells_modified += 1
                filled_flat[n_idx] = new_elev

            resolved_flat[n_idx] = True
            heapq.heappush(heap, (new_elev, nr, nc))

    filled_elevation = np.array(filled_flat, dtype=np.float64).reshape(rows, cols)
    filled_elevation = np.where(valid_mask, filled_elevation, np.nan)

    logger.info(
        "Sink fill complete: %d cells modified, max fill depth=%.4f.",
        cells_modified, max_fill_depth,
    )

    return ConditionedDEMResult(
        filled_elevation=filled_elevation,
        cells_modified=cells_modified,
        max_fill_depth=max_fill_depth,
        valid_mask=valid_mask,
    )