"""
Unit tests for pour-point watershed/catchment delineation.
"""

import numpy as np
import pytest

from src.hydrology.flow_direction import compute_flow_direction
from src.hydrology.watershed_delineation import (
    WatershedDelineationError,
    delineate_catchment,
)


def test_pit_catchment_includes_exactly_its_immediate_neighbors():
    # Flat plane except a single deep pit: only the 8 direct neighbors of
    # the pit have a defined (non-flat) direction toward it. Everything
    # farther out is mutually flat and correctly has no defined path.
    dem = np.full((7, 7), 100.0)
    dem[3, 3] = 1.0
    fd = compute_flow_direction(dem, cell_size_x=1.0, cell_size_y=1.0)

    result = delineate_catchment(fd.direction, fd.valid_mask, pour_row=3, pour_col=3)

    assert result.cell_count == 9  # pit itself + 8 immediate neighbors
    assert result.catchment_mask[3, 3]
    assert result.catchment_mask[2, 2]
    assert result.catchment_mask[2, 3]
    assert not result.catchment_mask[0, 0]


def test_catchment_on_uniform_east_flow_respects_direction():
    rows, cols = 7, 10
    dem = np.tile(np.arange(cols)[::-1] * 1.0, (rows, 1))
    fd = compute_flow_direction(dem, cell_size_x=1.0, cell_size_y=1.0)

    pour_row, pour_col = 3, 7
    result = delineate_catchment(fd.direction, fd.valid_mask, pour_row, pour_col)

    # Directly upstream in the same row (flow moves east) must be included.
    assert result.catchment_mask[pour_row, pour_col - 1]
    # A cell in an adjacent row is flat relative to its row-neighbors and
    # has no defined path into this row — must NOT be included.
    assert not result.catchment_mask[pour_row - 1, pour_col]
    # A cell downstream of the pour point must NOT be included.
    assert not result.catchment_mask[pour_row, pour_col + 1]


def test_area_scales_with_cell_size():
    dem = np.full((7, 7), 100.0)
    dem[3, 3] = 1.0
    fd = compute_flow_direction(dem, cell_size_x=2.0, cell_size_y=2.0)
    result = delineate_catchment(
        fd.direction, fd.valid_mask, pour_row=3, pour_col=3,
        cell_size_x=2.0, cell_size_y=2.0,
    )
    assert result.area == pytest.approx(result.cell_count * 4.0)


def test_rejects_out_of_bounds_pour_point():
    dem = np.full((5, 5), 100.0)
    fd = compute_flow_direction(dem, cell_size_x=1.0, cell_size_y=1.0)
    with pytest.raises(WatershedDelineationError):
        delineate_catchment(fd.direction, fd.valid_mask, pour_row=10, pour_col=10)


def test_rejects_invalid_pour_point():
    dem = np.full((5, 5), 100.0)
    dem[2, 2] = np.nan
    fd = compute_flow_direction(dem, cell_size_x=1.0, cell_size_y=1.0)
    with pytest.raises(WatershedDelineationError):
        delineate_catchment(fd.direction, fd.valid_mask, pour_row=2, pour_col=2)


def test_rejects_shape_mismatch():
    direction = np.zeros((5, 5), dtype=np.int16)
    valid_mask = np.ones((4, 4), dtype=bool)
    with pytest.raises(WatershedDelineationError):
        delineate_catchment(direction, valid_mask, pour_row=0, pour_col=0)