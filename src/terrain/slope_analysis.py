"""
Slope and aspect analysis for DEM terrain data.

Implements Horn's method (Horn, 1981, "Hill Shading and the Reflectance Map",
Proceedings of the IEEE) — the same 3x3 weighted finite-difference kernel used
by GDAL's gdaldem, QGIS, and ArcGIS Spatial Analyst. Using this method (rather
than a naive central-difference gradient) means slope/aspect values here are
directly comparable to those tools.

This module performs ANALYSIS only. It does not make engineering
recommendations and does not certify any result for construction use.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

import numpy as np
from affine import Affine

logger = logging.getLogger(__name__)


class SlopeAnalysisError(Exception):
    """Raised when slope/aspect computation cannot proceed safely."""


@dataclass(frozen=True)
class SlopeAspectResult:
    """
    Container for slope/aspect analysis output.

    Attributes:
        slope_degrees: Slope magnitude in degrees (0-90), NaN at nodata/edge cells.
        slope_percent: Slope magnitude as percent grade (rise/run * 100).
        aspect_degrees: Downslope direction in compass degrees (0-360, 0=North,
            clockwise), NaN where slope is ~0 (flat, aspect undefined) or nodata.
        aspect_compass: Integer compass sector 0-7 (0=N, 1=NE, ... 7=NW), -1 where
            aspect is undefined (flat or nodata).
        valid_mask: Boolean array, True where slope/aspect values are valid.
        cell_size_x: Pixel width in map units (from transform).
        cell_size_y: Pixel height in map units (from transform).
    """

    slope_degrees: np.ndarray
    slope_percent: np.ndarray
    aspect_degrees: np.ndarray
    aspect_compass: np.ndarray
    valid_mask: np.ndarray
    cell_size_x: float
    cell_size_y: float

    def summary_statistics(self) -> dict[str, float]:
        """Return basic descriptive statistics over valid cells only."""
        valid_slope = self.slope_degrees[self.valid_mask]
        if valid_slope.size == 0:
            raise SlopeAnalysisError(
                "No valid cells to summarize — DEM may be entirely nodata/flat."
            )
        return {
            "min_slope_degrees": float(np.min(valid_slope)),
            "max_slope_degrees": float(np.max(valid_slope)),
            "mean_slope_degrees": float(np.mean(valid_slope)),
            "median_slope_degrees": float(np.median(valid_slope)),
            "std_slope_degrees": float(np.std(valid_slope)),
            "valid_cell_count": int(self.valid_mask.sum()),
            "total_cell_count": int(self.valid_mask.size),
        }


_COMPASS_SECTORS = 8
_COMPASS_LABELS = ["N", "NE", "E", "SE", "S", "SW", "W", "NW"]


def compass_label(sector: int) -> str:
    """Map a compass sector index (0-7, or -1) to its label."""
    if sector < 0:
        return "Flat/Undefined"
    return _COMPASS_LABELS[sector % _COMPASS_SECTORS]


def compute_slope_aspect(
    elevation: np.ndarray,
    transform: Affine,
    nodata: float | None = None,
    flat_slope_threshold_degrees: float = 0.05,
) -> SlopeAspectResult:
    """
    Compute slope and aspect from a DEM elevation array using Horn's method.

    Args:
        elevation: 2D array of elevation values (rows, cols), e.g. from
            `rasterio_dataset.read(1)`.
        transform: Affine transform of the DEM (e.g. `rasterio_dataset.transform`).
            Used to derive real-world cell size (dx, dy) so slope is computed in
            true units, not pixel units.
        nodata: Nodata value to mask out. If None, no nodata masking is applied
            beyond NaN/inf detection.
        flat_slope_threshold_degrees: Slopes below this value are treated as
            flat; aspect is undefined (NaN/-1) for such cells, matching
            standard GIS convention (a perfectly flat cell has no downslope
            direction).

    Returns:
        SlopeAspectResult with slope/aspect arrays matching the input shape.

    Raises:
        SlopeAnalysisError: if the input array is not 2D, too small for a 3x3
            kernel, or the transform has zero/degenerate cell size.
    """
    if elevation.ndim != 2:
        raise SlopeAnalysisError(
            f"Expected a 2D elevation array, got shape {elevation.shape}."
        )
    if elevation.shape[0] < 3 or elevation.shape[1] < 3:
        raise SlopeAnalysisError(
            "DEM must be at least 3x3 cells to compute slope/aspect "
            f"(got {elevation.shape})."
        )

    cell_size_x = abs(transform.a)
    cell_size_y = abs(transform.e)
    if cell_size_x <= 0 or cell_size_y <= 0:
        raise SlopeAnalysisError(
            f"Degenerate cell size derived from transform: "
            f"dx={cell_size_x}, dy={cell_size_y}."
        )

    dem = elevation.astype(np.float64, copy=True)

    nodata_mask = np.zeros(dem.shape, dtype=bool)
    if nodata is not None:
        nodata_mask |= np.isclose(dem, nodata)
    nodata_mask |= ~np.isfinite(dem)

    if nodata_mask.any():
        logger.info(
            "Masking %d nodata/invalid cells out of %d before slope computation.",
            int(nodata_mask.sum()),
            dem.size,
        )
        # Fill nodata with local edge-replicated values so the 3x3 kernel
        # doesn't propagate garbage into neighboring valid cells; those
        # neighbor cells are still excluded via valid_mask below only if
        # they touch a nodata cell.
        dem[nodata_mask] = np.nan

    # Pad by 1 with edge replication so every real cell has a full 3x3
    # neighborhood (standard boundary handling used by GDAL).
    padded = np.pad(dem, pad_width=1, mode="edge")

    z1 = padded[0:-2, 0:-2]
    z2 = padded[0:-2, 1:-1]
    z3 = padded[0:-2, 2:]
    z4 = padded[1:-1, 0:-2]
    z6 = padded[1:-1, 2:]
    z7 = padded[2:, 0:-2]
    z8 = padded[2:, 1:-1]
    z9 = padded[2:, 2:]

    # Horn (1981) weighted kernel.
    dz_dx = ((z3 + 2 * z6 + z9) - (z1 + 2 * z4 + z7)) / (8 * cell_size_x)
    dz_dy = ((z7 + 2 * z8 + z9) - (z1 + 2 * z2 + z3)) / (8 * cell_size_y)

    rise_run = np.sqrt(dz_dx**2 + dz_dy**2)
    slope_degrees = np.degrees(np.arctan(rise_run))
    slope_percent = rise_run * 100.0

    # Aspect: 0=North, clockwise, matching GDAL/QGIS convention.
    aspect_rad = np.arctan2(dz_dy, -dz_dx)
    aspect_degrees = np.degrees(aspect_rad)
    aspect_degrees = np.mod(90.0 - aspect_degrees, 360.0)

    flat_mask = slope_degrees < flat_slope_threshold_degrees
    aspect_degrees = np.where(flat_mask, np.nan, aspect_degrees)

    # Any cell whose 3x3 neighborhood touched a nodata cell is invalid.
    kernel_invalid = np.zeros(dem.shape, dtype=bool)
    if nodata_mask.any():
        padded_invalid = np.pad(nodata_mask, pad_width=1, mode="edge")
        for dr in range(3):
            for dc in range(3):
                kernel_invalid |= padded_invalid[dr : dr + dem.shape[0], dc : dc + dem.shape[1]]

    valid_mask = ~kernel_invalid & np.isfinite(slope_degrees)

    slope_degrees = np.where(valid_mask, slope_degrees, np.nan)
    slope_percent = np.where(valid_mask, slope_percent, np.nan)
    aspect_degrees = np.where(valid_mask, aspect_degrees, np.nan)

    aspect_compass = np.full(dem.shape, -1, dtype=np.int8)
    defined_aspect = valid_mask & ~flat_mask
    sector = np.mod(np.round(aspect_degrees / 45.0), _COMPASS_SECTORS)
    aspect_compass = np.where(defined_aspect, sector, -1).astype(np.int8)

    logger.info(
        "Slope/aspect computed: %d valid cells, cell size dx=%.4f dy=%.4f (map units).",
        int(valid_mask.sum()),
        cell_size_x,
        cell_size_y,
    )

    return SlopeAspectResult(
        slope_degrees=slope_degrees,
        slope_percent=slope_percent,
        aspect_degrees=aspect_degrees,
        aspect_compass=aspect_compass,
        valid_mask=valid_mask,
        cell_size_x=cell_size_x,
        cell_size_y=cell_size_y,
    )