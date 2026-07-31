"""
Visualization and click-target helpers for pour-point catchment delineation.

Two responsibilities:
  1. build_pour_point_selector_image() - produces a raw, pixel-exact PIL
     image from the flow accumulation array (no matplotlib axes/margins),
     so that click coordinates on the displayed image can be mapped back
     to exact array (row, col) indices.
  2. plot_catchment_map() - renders the delineated catchment as an
     overlay on the flow accumulation backdrop, for display after a pour
     point has been chosen.
"""

from __future__ import annotations

import matplotlib.pyplot as plt
import numpy as np
from matplotlib import colormaps
from matplotlib.colors import LogNorm
from matplotlib.figure import Figure
from PIL import Image

from src.hydrology.flow_accumulation import FlowAccumulationResult
from src.hydrology.watershed_delineation import CatchmentResult


def build_pour_point_selector_image(
    accumulation: np.ndarray,
    valid_mask: np.ndarray,
    max_dim: int = 800,
) -> tuple[Image.Image, int]:
    """
    Build a raw (axis-free) log-scaled image of the accumulation array for
    use as a click target, downsampled by simple striding if needed.

    Returns:
        (image, stride) - stride is the decimation factor applied, needed
        by the caller to map a clicked pixel in this image back to the
        corresponding index in the original full-resolution array:
        original_row = clicked_row_in_image * stride (clamped to bounds).
    """
    rows, cols = accumulation.shape
    stride = max(1, max(rows, cols) // max_dim)

    acc_small = accumulation[::stride, ::stride]
    valid_small = valid_mask[::stride, ::stride]

    if valid_small.any():
        vmax = max(float(acc_small[valid_small].max()), 1.0)
    else:
        vmax = 1.0

    norm = LogNorm(vmin=1, vmax=vmax)
    safe_values = np.where(valid_small, np.maximum(acc_small, 1), 1).astype(float)

    cmap = colormaps["Blues"]
    rgba = cmap(norm(safe_values))
    white = np.array([1.0, 1.0, 1.0, 1.0])
    rgba = np.where(valid_small[..., None], rgba, white)

    img_array = (rgba[..., :3] * 255).astype(np.uint8)
    image = Image.fromarray(img_array)
    return image, stride


def plot_catchment_map(
    accumulation_result: FlowAccumulationResult,
    catchment_result: CatchmentResult,
) -> Figure:
    """Render the delineated catchment highlighted over the accumulation map."""
    acc_display = np.where(
        accumulation_result.valid_mask, accumulation_result.accumulation, np.nan
    ).astype(float)
    acc_masked = np.ma.masked_invalid(acc_display)
    vmax = max(float(accumulation_result.accumulation[accumulation_result.valid_mask].max()), 1.0)

    fig, ax = plt.subplots(figsize=(8, 6))
    ax.imshow(acc_masked, cmap="Greys", norm=LogNorm(vmin=1, vmax=vmax), alpha=0.6)

    catchment_overlay = np.ma.masked_where(
        ~catchment_result.catchment_mask, catchment_result.catchment_mask
    )
    ax.imshow(catchment_overlay, cmap="cool", vmin=0, vmax=1, alpha=0.75)

    ax.plot(
        catchment_result.pour_col, catchment_result.pour_row,
        marker="*", markersize=18, color="red", markeredgecolor="black",
    )
    ax.set_title(
        f"Catchment for pour point (row {catchment_result.pour_row}, "
        f"col {catchment_result.pour_col}) - {catchment_result.cell_count:,} cells"
    )
    ax.set_xlabel("Column (pixel)")
    ax.set_ylabel("Row (pixel)")
    ax.set_facecolor("white")
    fig.tight_layout()
    return fig