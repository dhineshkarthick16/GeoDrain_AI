"""
Visualization helpers for D8 flow direction results.

Produces matplotlib Figures only — no Streamlit calls here.
"""

from __future__ import annotations

import matplotlib.pyplot as plt
import numpy as np
from matplotlib.figure import Figure

from src.hydrology.flow_direction import DIRECTION_CODES, UNDEFINED_DIRECTION, FlowDirectionResult

# Angle (degrees, standard math convention: 0=East, CCW) for each D8 code,
# used to draw direction arrows via matplotlib's quiver.
_CODE_TO_ANGLE_DEG = {
    DIRECTION_CODES["E"]: 0,
    DIRECTION_CODES["SE"]: -45,
    DIRECTION_CODES["S"]: -90,
    DIRECTION_CODES["SW"]: -135,
    DIRECTION_CODES["W"]: 180,
    DIRECTION_CODES["NW"]: 135,
    DIRECTION_CODES["N"]: 90,
    DIRECTION_CODES["NE"]: 45,
}


def plot_flow_direction_map(result: FlowDirectionResult) -> Figure:
    """
    Render a categorical flow-direction map (8 colors + sink/flat markers).

    Undefined cells (sinks, flats, nodata) are shown in a neutral gray so
    they are visually distinguishable from any real direction, rather
    than being silently colored as if they were a valid direction.
    """
    display = np.where(result.valid_mask, result.direction, np.nan).astype(float)
    display = np.where(display == UNDEFINED_DIRECTION, np.nan, display)

    fig, ax = plt.subplots(figsize=(8, 6))
    masked = np.ma.masked_invalid(display)
    im = ax.imshow(masked, cmap="tab10", vmin=1, vmax=128)
    cbar = fig.colorbar(im, ax=ax, ticks=list(DIRECTION_CODES.values()))
    cbar.ax.set_yticklabels(list(DIRECTION_CODES.keys()))
    cbar.set_label("Flow Direction (D8)")

    ax.set_title("D8 Flow Direction (gray = undefined: sink, flat, or nodata)")
    ax.set_xlabel("Column (pixel)")
    ax.set_ylabel("Row (pixel)")
    ax.set_facecolor("lightgray")
    fig.tight_layout()
    return fig


def plot_sink_flat_map(result: FlowDirectionResult) -> Figure:
    """Render a map highlighting sinks (red) and flats (yellow) separately."""
    rows, cols = result.direction.shape
    overlay = np.zeros((rows, cols, 3))
    overlay[..., :] = 0.9  # light gray background

    overlay[result.is_flat] = [1.0, 0.85, 0.0]  # yellow
    overlay[result.is_sink] = [0.85, 0.1, 0.1]  # red
    overlay[~result.valid_mask] = [1.0, 1.0, 1.0]  # white for nodata

    fig, ax = plt.subplots(figsize=(8, 6))
    ax.imshow(overlay)
    ax.set_title("Sinks (red) and Flats (yellow) — require DEM conditioning")
    ax.set_xlabel("Column (pixel)")
    ax.set_ylabel("Row (pixel)")
    fig.tight_layout()
    return fig