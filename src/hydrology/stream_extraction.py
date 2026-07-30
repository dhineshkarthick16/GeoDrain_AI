"""
Raster-based drainage stream identification.

Classifies each cell as "channel" (likely drainage path) or not, by
thresholding the flow accumulation array at a given percentile. This is
the standard approach used by GIS stream-extraction tools (QGIS, ArcGIS,
TauDEM): cells whose accumulation exceeds a chosen percentile of the
accumulation distribution are treated as channels, since a small fraction
of cells (the ones many other cells drain through) concentrate the
overwhelming majority of upstream area.

This module produces a RASTER classification only — a boolean mask, not
vector line geometry. Converting this mask into connected vector stream
lines (with junctions, segment topology, and pruning of spurious short
branches) is a separate, future phase.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

import numpy as np

logger = logging.getLogger(__name__)


class StreamExtractionError(Exception):
    """Raised when stream extraction cannot proceed safely."""


@dataclass(frozen=True)
class StreamNetworkResult:
    """
    Container for raster stream-identification output.

    Attributes:
        stream_mask: Boolean array, True where a cell is classified as a
            likely drainage channel (accumulation >= threshold_value).
        threshold_value: The accumulation value corresponding to
            percentile_used, computed from the valid-cell accumulation
            distribution. Cells at or above this value are streams.
        percentile_used: The percentile (0-100) used to derive
            threshold_value. E.g. 99.0 means "top 1% of cells by
            accumulation."
        stream_cell_count: Number of cells classified as stream.
        valid_mask: Boolean array, True where the underlying accumulation
            value is meaningful (carried through from flow accumulation).
    """

    stream_mask: np.ndarray
    threshold_value: float
    percentile_used: float
    stream_cell_count: int
    valid_mask: np.ndarray

    def summary_statistics(self) -> dict[str, float]:
        """Return basic counts describing the extracted stream network."""
        valid_count = int(self.valid_mask.sum())
        if valid_count == 0:
            raise StreamExtractionError(
                "No valid cells to summarize — accumulation array may be "
                "entirely nodata."
            )
        return {
            "valid_cell_count": valid_count,
            "stream_cell_count": self.stream_cell_count,
            "stream_fraction": self.stream_cell_count / valid_count,
            "threshold_value": self.threshold_value,
            "percentile_used": self.percentile_used,
        }


def extract_stream_network(
    accumulation: np.ndarray,
    valid_mask: np.ndarray,
    percentile_threshold: float = 99.0,
) -> StreamNetworkResult:
    """
    Classify cells as drainage channels by thresholding flow accumulation.

    Args:
        accumulation: 2D flow accumulation array (e.g.
            FlowAccumulationResult.accumulation). Higher values indicate
            more upstream cells draining through that cell.
        valid_mask: 2D boolean array, True where the cell has a
            meaningful accumulation value (e.g.
            FlowAccumulationResult.valid_mask). Must match accumulation's
            shape.
        percentile_threshold: Percentile (0-100, exclusive of values that
            would select zero cells at 100) of the valid-cell accumulation
            distribution above which a cell is classified as a stream.
            Default 99.0 selects roughly the top 1% of cells by
            accumulation — a common starting convention. Lower values
            produce a denser (more permissive) network; higher values
            produce a sparser one.

    Returns:
        StreamNetworkResult.

    Raises:
        StreamExtractionError: on shape mismatch, no valid cells, or an
            out-of-range percentile.
    """
    if accumulation.shape != valid_mask.shape:
        raise StreamExtractionError(
            f"accumulation shape {accumulation.shape} does not match "
            f"valid_mask shape {valid_mask.shape}."
        )
    if not (0.0 <= percentile_threshold < 100.0):
        raise StreamExtractionError(
            f"percentile_threshold must be in [0, 100), got {percentile_threshold}."
        )

    valid_values = accumulation[valid_mask]
    if valid_values.size == 0:
        raise StreamExtractionError(
            "No valid cells in accumulation array — cannot compute threshold."
        )

    threshold_value = float(np.percentile(valid_values, percentile_threshold))
    stream_mask = valid_mask & (accumulation >= threshold_value)
    stream_cell_count = int(stream_mask.sum())

    logger.info(
        "Stream extraction: percentile=%.2f -> threshold=%.2f -> %d stream cells.",
        percentile_threshold,
        threshold_value,
        stream_cell_count,
    )

    return StreamNetworkResult(
        stream_mask=stream_mask,
        threshold_value=threshold_value,
        percentile_used=percentile_threshold,
        stream_cell_count=stream_cell_count,
        valid_mask=valid_mask,
    )