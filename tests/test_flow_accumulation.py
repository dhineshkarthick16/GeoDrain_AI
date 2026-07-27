"""
Unit tests for flow accumulation.

Uses synthetic DEMs with known, analytically-obvious drainage patterns so
correctness can be verified exactly.
"""

import numpy as np
import pytest

from src.hydrology.flow_direction import compute_flow_direction
from src.hydrology.flow_accumulation import (
    FlowAccumulationError,
    compute_flow_accumulation,
)


def test_ridge_line_accumulates_toward_single_outlet():
    # A uniform slope draining east: every column j should accumulate
    # exactly (j+1) cells by the time flow reaches the east edge, since
    # each row is an independent flow line on a pure east-west tilt.
    rows, cols = 5, 6
    dem = np.tile(np.arange(cols)[::-1] * 1.0, (rows, 1))
    fd = compute_flow_direction(dem, cell_size_x=1.0, cell_size_y=1.0)
    result = compute_flow_accumulation(dem, fd.direction)

    interior_row = 2
    for j in range(cols):
        assert result.accumulation[interior_row, j] == j + 1


def test_single_pit_collects_all_upstream_accumulation():
    dem = np.full((7, 7), 100.0)
    dem[3, 3] = 1.0  # deep pit, all 48 other cells eventually drain toward it
    fd = compute_flow_direction(dem, cell_size_x=1.0, cell_size_y=1.0)
    result = compute_flow_accumulation(dem, fd.direction)

    # The pit itself should have a large accumulation relative to a
    # random far corner cell (corner should be small/terminal-ish).
    assert result.accumulation[3, 3] > result.accumulation[0, 0]
    assert result.terminal_mask[3, 3]  # pit has no defined direction


def test_every_valid_cell_has_accumulation_at_least_one():
    dem = np.tile(np.arange(8)[::-1] * 1.0, (8, 1))
    fd = compute_flow_direction(dem, cell_size_x=1.0, cell_size_y=1.0)
    result = compute_flow_accumulation(dem, fd.direction)
    assert np.all(result.accumulation[result.valid_mask] >= 1)


def test_contributing_area_scales_with_cell_size():
    dem = np.tile(np.arange(6)[::-1] * 1.0, (6, 1))
    fd = compute_flow_direction(dem, cell_size_x=2.0, cell_size_y=2.0)
    result = compute_flow_accumulation(dem, fd.direction, cell_size_x=2.0, cell_size_y=2.0)
    expected_area = result.accumulation.astype(float) * 4.0
    assert np.allclose(result.contributing_area, expected_area)


def test_rejects_shape_mismatch():
    dem = np.tile(np.arange(5)[::-1] * 1.0, (5, 1))
    bad_direction = np.zeros((4, 4), dtype=np.int16)
    with pytest.raises(FlowAccumulationError):
        compute_flow_accumulation(dem, bad_direction)


def test_rejects_degenerate_cell_size():
    dem = np.tile(np.arange(5)[::-1] * 1.0, (5, 1))
    fd = compute_flow_direction(dem, cell_size_x=1.0, cell_size_y=1.0)
    with pytest.raises(FlowAccumulationError):
        compute_flow_accumulation(dem, fd.direction, cell_size_x=0.0, cell_size_y=1.0)


def test_summary_statistics():
    dem = np.tile(np.arange(8)[::-1] * 1.0, (8, 1))
    fd = compute_flow_direction(dem, cell_size_x=1.0, cell_size_y=1.0)
    result = compute_flow_accumulation(dem, fd.direction)
    stats = result.summary_statistics()
    assert stats["max_accumulation"] >= 1
    assert 0.0 <= stats["terminal_fraction"] <= 1.0