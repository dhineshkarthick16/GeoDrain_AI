"""
Visualization helpers for flow accumulation results.

Uses a log-scale color map, which is the standard industry convention for
flow accumulation (GDAL, ArcGIS, QGIS, TauDEM all default to log-scaled
display) — accumulation values typically span several orders of
magnitude, so a linear scale makes everything except a few outlet pixels
look identical.
"""

from __future__ import annotations

import matplotlib.pyplot as plt
import numpy as np
from matplotlib.colors import LogNorm
from matplotlib.figure import Figure

from src.hydrology.flow_accumulation import FlowAccumulationResult


def plot_flow_accumulation_map(result: FlowAccumulationResult) -> Figure:
    """
    Render a log-scaled flow accumulation map.

    Higher accumulation (darker blue) indicates cells where more upstream
    area drains through — the basis for identifying likely drainage
    channels in a later phase.
    """
    display = np.where(result.valid_mask, result.accumulation, np.nan).astype(float)
    masked = np.ma.masked_invalid(display)

    vmax = float(result.accumulation[result.valid_mask].max())
    vmax = max(vmax, 1.0)

    fig, ax = plt.subplots(figsize=(8, 6))
    im = ax.imshow(masked, cmap="Blues", norm=LogNorm(vmin=1, vmax=vmax))
    fig.colorbar(im, ax=ax, label="Upstream cell count (log scale)")
    ax.set_title("Flow Accumulation (D8, log scale)")
    ax.set_xlabel("Column (pixel)")
    ax.set_ylabel("Row (pixel)")
    ax.set_facecolor("white")
    fig.tight_layout()
    return fig