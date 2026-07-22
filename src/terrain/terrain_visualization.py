from __future__ import annotations

import matplotlib.pyplot as plt
import numpy as np


def create_elevation_figure(
    elevation: np.ndarray
):
    """
    Create a terrain elevation visualization.
    """

    figure, axis = plt.subplots(
        figsize=(12, 7)
    )

    image = axis.imshow(
        elevation,
        interpolation="nearest"
    )

    axis.set_title(
        "Digital Elevation Model"
    )

    axis.set_xlabel(
        "Raster Column"
    )

    axis.set_ylabel(
        "Raster Row"
    )

    figure.colorbar(
        image,
        ax=axis,
        label="Elevation"
    )

    figure.tight_layout()

    return figure