"""
Unit tests for D8 flow direction.

Uses synthetic DEMs with known, analytically-obvious drainage patterns
so correctness can be verified exactly.
"""

import numpy as np
import pytest

from src.hydrology.flow_direction import (
    DIRECTION_CODES,
    UNDEFINED_DIRECTION,
    FlowDirectionError,
    compute_flow_direction,
)


def test_uniform_slope_flows_downhill_east_to_west_ridge():
    # Elevation decreases left-to-right -> every interior cell should flow East.
    rows, cols = 10, 10
    dem = np.tile(np.arange(cols)[::-1] * 1.0, (rows, 1))
    result = compute_flow_direction(dem, cell_size_x=1.0, cell_size_y=1.0)

    interior = result.direction[2:-2, 2:-2]
    assert np.all(interior == DIRECTION_CODES["E"])


def test_flat_dem_is_entirely_undefined_and_marked_flat():
    dem = np.full((8, 8), 50.0)
    result = compute_flow_direction(dem, cell_size_x=1.0, cell_size_y=1.0)

    interior_valid = result.valid_mask[1:-1, 1:-1]
    assert np.all(result.direction[1:-1, 1:-1][interior_valid] == UNDEFINED_DIRECTION)
    assert np.all(result.is_flat[1:-1, 1:-1][interior_valid])
    assert not np.any(result.is_sink[1:-1, 1:-1][interior_valid])


def test_single_pit_is_detected_as_sink():
    dem = np.full((7, 7), 100.0)
    dem[3, 3] = 1.0  # a deep pit surrounded by higher ground
    result = compute_flow_direction(dem, cell_size_x=1.0, cell_size_y=1.0)

    assert result.is_sink[3, 3]
    assert result.direction[3, 3] == UNDEFINED_DIRECTION
    # Neighbors of the pit should flow toward it, not be marked as sinks themselves.
    assert not result.is_sink[2, 3]


def test_nodata_neighborhood_is_invalid():
    dem = np.tile(np.arange(10)[::-1] * 1.0, (10, 1))
    dem[5, 5] = np.nan
    result = compute_flow_direction(dem, cell_size_x=1.0, cell_size_y=1.0)

    assert not result.valid_mask[5, 5]
    assert not result.valid_mask[4, 4]
    assert result.valid_mask[0, 0]


def test_rejects_non_2d_input():
    with pytest.raises(FlowDirectionError):
        compute_flow_direction(np.zeros((5, 5, 2)), cell_size_x=1.0, cell_size_y=1.0)


def test_rejects_too_small_dem():
    with pytest.raises(FlowDirectionError):
        compute_flow_direction(np.zeros((2, 2)), cell_size_x=1.0, cell_size_y=1.0)


def test_rejects_degenerate_cell_size():
    dem = np.tile(np.arange(5)[::-1] * 1.0, (5, 1))
    with pytest.raises(FlowDirectionError):
        compute_flow_direction(dem, cell_size_x=0.0, cell_size_y=1.0)


def test_summary_statistics():
    dem = np.tile(np.arange(10)[::-1] * 1.0, (10, 1))
    result = compute_flow_direction(dem, cell_size_x=1.0, cell_size_y=1.0)
    stats = result.summary_statistics()
    assert stats["valid_cell_count"] > 0
    assert 0.0 <= stats["defined_direction_fraction"] <= 1.0