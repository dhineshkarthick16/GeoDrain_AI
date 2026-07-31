"""
Unit tests for DEM conditioning (priority-flood sink filling).

Uses flow_direction.compute_flow_direction as an independent oracle for
several tests: a DEM is "conditioned correctly" if running the
already-tested D8 algorithm on the filled output reports zero sinks.
"""

import numpy as np
import pytest

from src.preprocessing.dem_conditioning import (
    DEMConditioningError,
    fill_sinks,
)
from src.hydrology.flow_direction import compute_flow_direction


def test_single_interior_pit_is_eliminated():
    dem = np.full((9, 9), 100.0)
    dem[4, 4] = 1.0  # deep pit, fully interior
    result = fill_sinks(dem)

    assert result.filled_elevation[4, 4] > 1.0
    assert result.cells_modified >= 1
    assert result.max_fill_depth > 0

    fd = compute_flow_direction(result.filled_elevation, cell_size_x=1.0, cell_size_y=1.0)
    assert not fd.is_sink[4, 4]


def test_no_sinks_remain_after_filling_multiple_pits():
    rng = np.random.default_rng(7)
    dem = 100.0 + rng.random((15, 15)) * 5.0
    dem[3, 3] = 1.0
    dem[10, 11] = 2.0
    dem[7, 2] = 0.5

    result = fill_sinks(dem)
    fd = compute_flow_direction(result.filled_elevation, cell_size_x=1.0, cell_size_y=1.0)

    interior_valid = fd.valid_mask[1:-1, 1:-1]
    assert not np.any(fd.is_sink[1:-1, 1:-1][interior_valid])


def test_monotonic_slope_is_unchanged():
    dem = np.tile(np.arange(10)[::-1] * 1.0, (10, 1))
    result = fill_sinks(dem)
    assert np.allclose(result.filled_elevation, dem)
    assert result.cells_modified == 0
    assert result.max_fill_depth == 0.0


def test_edge_cell_is_never_raised():
    dem = np.full((6, 6), 50.0)
    dem[0, 3] = 1.0  # low point directly on the boundary — a valid outlet
    result = fill_sinks(dem)
    assert result.filled_elevation[0, 3] == 1.0


def test_valid_cell_next_to_nodata_is_treated_as_outlet():
    dem = np.full((7, 7), 50.0)
    dem[3, 3] = 1.0
    dem[3, 4] = np.nan  # nodata directly adjacent to the low cell
    result = fill_sinks(dem)
    # The low cell drains through the adjacent nodata "edge" and should
    # not be raised.
    assert result.filled_elevation[3, 3] == 1.0


def test_nodata_cells_remain_nan():
    dem = np.full((6, 6), 50.0)
    dem[2, 2] = np.nan
    result = fill_sinks(dem)
    assert np.isnan(result.filled_elevation[2, 2])


def test_rejects_non_2d_input():
    with pytest.raises(DEMConditioningError):
        fill_sinks(np.zeros((5, 5, 2)))


def test_rejects_too_small_dem():
    with pytest.raises(DEMConditioningError):
        fill_sinks(np.zeros((1, 1)))


def test_rejects_all_nodata():
    dem = np.full((5, 5), np.nan)
    with pytest.raises(DEMConditioningError):
        fill_sinks(dem)


def test_summary_statistics():
    dem = np.full((9, 9), 100.0)
    dem[4, 4] = 1.0
    result = fill_sinks(dem)
    stats = result.summary_statistics()
    assert stats["cells_modified"] >= 1
    assert stats["max_fill_depth"] > 0