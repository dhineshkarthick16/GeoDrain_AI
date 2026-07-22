"""
Visualization helpers for slope/aspect analysis results.

Produces matplotlib Figures only — no Streamlit calls here, so these
functions stay reusable from scripts, tests, or notebooks in addition to
the UI layer.
"""

from __future__ import annotations

import matplotlib.pyplot as plt
import numpy as np
from matplotlib.figure import Figure

from src.terrain.slope_analysis import SlopeAspectResult


def plot_slope_map(result: SlopeAspectResult, units: str = "percent") -> Figure:
    """
    Render a slope map.

    Args:
        result: Output of `compute_slope_aspect`.
        units: "percent" or "degrees".

    Returns:
        A matplotlib Figure. Caller is responsible for display/saving.
    """
    if units not in ("percent", "degrees"):
        raise ValueError(f"units must be 'percent' or 'degrees', got {units!r}")

    data = result.slope_percent if units == "percent" else result.slope_degrees
    masked = np.ma.masked_invalid(data)

    fig, ax = plt.subplots(figsize=(8, 6))
    im = ax.imshow(masked, cmap="YlOrRd")
    label = "Slope (%)" if units == "percent" else "Slope (degrees)"
    fig.colorbar(im, ax=ax, label=label)
    ax.set_title(f"Slope Analysis — {label}")
    ax.set_xlabel("Column (pixel)")
    ax.set_ylabel("Row (pixel)")
    fig.tight_layout()
    return fig


def plot_aspect_map(result: SlopeAspectResult) -> Figure:
    """Render an aspect map using a cyclic colormap (0-360 degrees)."""
    masked = np.ma.masked_invalid(result.aspect_degrees)

    fig, ax = plt.subplots(figsize=(8, 6))
    im = ax.imshow(masked, cmap="hsv", vmin=0, vmax=360)
    fig.colorbar(im, ax=ax, label="Aspect (degrees, 0=N, clockwise)")
    ax.set_title("Aspect Analysis")
    ax.set_xlabel("Column (pixel)")
    ax.set_ylabel("Row (pixel)")
    fig.tight_layout()
    return fig