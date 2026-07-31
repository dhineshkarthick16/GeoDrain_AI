"""
Visualization helpers for terrain-based flood susceptibility results.
"""

from __future__ import annotations

import matplotlib.pyplot as plt
import numpy as np
from matplotlib.colors import ListedColormap, BoundaryNorm
from matplotlib.figure import Figure

from src.hydrology.flood_susceptibility import FloodSusceptibilityResult, HIGH, LOW, MODERATE


def plot_susceptibility_map(result: FloodSusceptibilityResult) -> Figure:
    """
    Render the Low/Moderate/High susceptibility classification as a
    discrete-colored map (green/yellow/red), which is more interpretable
    for non-technical stakeholders than a continuous score.
    """
    display = np.where(result.valid_mask, result.susceptibility_class, np.nan).astype(float)
    masked = np.ma.masked_invalid(display)

    cmap = ListedColormap(["#2E7D32", "#F9A825", "#C62828"])  # green, amber, red
    bounds = [LOW - 0.5, LOW + 0.5, MODERATE + 0.5, HIGH + 0.5]
    norm = BoundaryNorm(bounds, cmap.N)

    fig, ax = plt.subplots(figsize=(8, 6))
    im = ax.imshow(masked, cmap=cmap, norm=norm)
    cbar = fig.colorbar(im, ax=ax, ticks=[LOW, MODERATE, HIGH])
    cbar.ax.set_yticklabels(["Low", "Moderate", "High"])
    cbar.set_label("Terrain-Based Susceptibility Class")

    ax.set_title(
        "Flood Susceptibility Indicator (terrain-based screening only -\n"
        "NOT a validated flood-risk model)"
    )
    ax.set_xlabel("Column (pixel)")
    ax.set_ylabel("Row (pixel)")
    ax.set_facecolor("white")
    fig.tight_layout()
    return fig