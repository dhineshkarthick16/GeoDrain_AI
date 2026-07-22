"""
Unit tests for slope/aspect analysis.

Uses a synthetic tilted-plane DEM with a known analytical slope/aspect so
correctness can be verified exactly, rather than only checking "it runs".
"""

import numpy as np
import pytest
from affine import Affine

from src.terrain.slope_analysis import (
    SlopeAnalysisError,
    compute_slope_aspect,
)


def _tilted_plane(rows: int, cols: int, cell_size: float, grade_percent: float) -> np.ndarray:
    """Build a DEM that slopes uniformly downhill toward +x (east)."""
    x = np.arange(cols) * cell_size
    z_row = x * (grade_percent / 100.0)
    return np.tile(z_row, (rows, 1))


def test_flat_dem_has_zero_slope():
    dem = np.full((10, 10), 100.0)
    transform = Affine(1.0, 0, 0, 0, -1.0, 0)
    result = compute_slope_aspect(dem, transform, nodata=None)
    interior = result.slope_degrees[1:-1, 1:-1]
    assert np.all(interior < 0.1)
    assert np.all(result.aspect_compass[1:-1, 1:-1] == -1)


def test_known_grade_matches_analytical_slope():
    grade_percent = 10.0  # 10% grade == atan(0.10) degrees
    dem = _tilted_plane(rows=10, cols=10, cell_size=1.0, grade_percent=grade_percent)
    transform = Affine(1.0, 0, 0, 0, -1.0, 0)
    result = compute_slope_aspect(dem, transform, nodata=None)

    interior_percent = result.slope_percent[2:-2, 2:-2]
    assert np.allclose(interior_percent, grade_percent, atol=0.5)

    expected_degrees = np.degrees(np.arctan(grade_percent / 100.0))
    interior_degrees = result.slope_degrees[2:-2, 2:-2]
    assert np.allclose(interior_degrees, expected_degrees, atol=0.5)


def test_nodata_cells_are_masked_and_propagate_to_neighbors():
    dem = _tilted_plane(rows=10, cols=10, cell_size=1.0, grade_percent=10.0)
    dem[5, 5] = -9999.0
    transform = Affine(1.0, 0, 0, 0, -1.0, 0)
    result = compute_slope_aspect(dem, transform, nodata=-9999.0)

    assert not result.valid_mask[5, 5]
    assert not result.valid_mask[4, 4]
    assert not result.valid_mask[6, 6]
    assert result.valid_mask[0, 0]


def test_rejects_non_2d_input():
    transform = Affine(1.0, 0, 0, 0, -1.0, 0)
    with pytest.raises(SlopeAnalysisError):
        compute_slope_aspect(np.zeros((5, 5, 3)), transform)


def test_rejects_too_small_dem():
    transform = Affine(1.0, 0, 0, 0, -1.0, 0)
    with pytest.raises(SlopeAnalysisError):
        compute_slope_aspect(np.zeros((2, 2)), transform)


def test_summary_statistics():
    dem = _tilted_plane(rows=10, cols=10, cell_size=1.0, grade_percent=10.0)
    transform = Affine(1.0, 0, 0, 0, -1.0, 0)
    result = compute_slope_aspect(dem, transform, nodata=None)
    stats = result.summary_statistics()
    assert stats["valid_cell_count"] > 0
    assert stats["min_slope_degrees"] >= 0