"""
Visualization helpers for raster stream-extraction results.

Renders the identified stream network as an overlay on the underlying
flow accumulation map, so channels can be seen in their terrain context.
"""

from __future__ import annotations

import matplotlib.pyplot as plt
import numpy as np
from matplotlib.colors import LogNorm
from matplotlib.figure import Figure

from src.hydrology.flow_accumulation import FlowAccumulationResult
from src.hydrology.stream_extraction import StreamNetworkResult


def plot_stream_network_map(
    accumulation_result: FlowAccumulationResult,
    stream_result: StreamNetworkResult,
) -> Figure:
    """
    Render the accumulation map (log scale, faint) with identified stream
    cells overlaid in a distinct high-contrast color.
    """
    acc_display = np.where(
        accumulation_result.valid_mask, accumulation_result.accumulation, np.nan
    ).astype(float)
    acc_masked = np.ma.masked_invalid(acc_display)
    vmax = max(float(accumulation_result.accumulation[accumulation_result.valid_mask].max()), 1.0)

    fig, ax = plt.subplots(figsize=(8, 6))
    ax.imshow(acc_masked, cmap="Greys", norm=LogNorm(vmin=1, vmax=vmax), alpha=0.6)

    stream_overlay = np.ma.masked_where(~stream_result.stream_mask, stream_result.stream_mask)
    ax.imshow(stream_overlay, cmap="autumn_r", vmin=0, vmax=1)

    ax.set_title(
        f"Extracted Stream Network (top "
        f"{100 - stream_result.percentile_used:.1f}% by accumulation)"
    )
    ax.set_xlabel("Column (pixel)")
    ax.set_ylabel("Row (pixel)")
    ax.set_facecolor("white")
    fig.tight_layout()
    return fig