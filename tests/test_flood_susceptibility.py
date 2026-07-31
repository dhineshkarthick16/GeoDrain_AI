"""
Unit tests for terrain-based flood susceptibility.
"""

import numpy as np
import pytest

from src.hydrology.flood_susceptibility import (
    HIGH,
    LOW,
    FloodSusceptibilityError,
    compute_flood_susceptibility,
)


def _base_inputs(shape=(10, 10)):
    slope = np.full(shape, 5.0)
    accumulation = np.full(shape, 10, dtype=np.int64)
    stream_mask = np.zeros(shape, dtype=bool)
    stream_mask[0, 0] = True  # at least one stream cell required
    valid_mask = np.ones(shape, dtype=bool)
    return slope, accumulation, stream_mask, valid_mask


def test_lower_slope_increases_susceptibility():
    slope, accumulation, stream_mask, valid_mask = _base_inputs()
    slope[5, 5] = 0.0
    slope[5, 6] = 50.0
    result = compute_flood_susceptibility(slope, accumulation, stream_mask, valid_mask)
    assert result.susceptibility_score[5, 5] > result.susceptibility_score[5, 6]


def test_higher_accumulation_increases_susceptibility():
    slope, accumulation, stream_mask, valid_mask = _base_inputs()
    accumulation[5, 5] = 100000
    accumulation[5, 6] = 1
    result = compute_flood_susceptibility(slope, accumulation, stream_mask, valid_mask)
    assert result.susceptibility_score[5, 5] > result.susceptibility_score[5, 6]


def test_stream_cell_has_higher_susceptibility_than_far_cell():
    slope, accumulation, stream_mask, valid_mask = _base_inputs(shape=(20, 20))
    stream_mask[:, :] = False
    stream_mask[10, 10] = True
    result = compute_flood_susceptibility(slope, accumulation, stream_mask, valid_mask)
    near = result.susceptibility_score[10, 11]
    far = result.susceptibility_score[0, 0]
    assert near > far


def test_stream_cells_are_classified_high_with_full_stream_weight():
    slope, accumulation, stream_mask, valid_mask = _base_inputs(shape=(15, 15))
    stream_mask[:, :] = False
    stream_mask[7, 7] = True
    result = compute_flood_susceptibility(
        slope, accumulation, stream_mask, valid_mask,
        weight_slope=0.0, weight_accumulation=0.0, weight_stream_proximity=1.0,
    )
    assert result.susceptibility_class[7, 7] == HIGH
    assert result.susceptibility_class[0, 0] == LOW


def test_rejects_shape_mismatch():
    slope, accumulation, stream_mask, valid_mask = _base_inputs()
    bad_accumulation = np.zeros((5, 5), dtype=np.int64)
    with pytest.raises(FloodSusceptibilityError):
        compute_flood_susceptibility(slope, bad_accumulation, stream_mask, valid_mask)


def test_rejects_weights_not_summing_to_one():
    slope, accumulation, stream_mask, valid_mask = _base_inputs()
    with pytest.raises(FloodSusceptibilityError):
        compute_flood_susceptibility(
            slope, accumulation, stream_mask, valid_mask,
            weight_slope=0.5, weight_accumulation=0.5, weight_stream_proximity=0.5,
        )


def test_rejects_negative_weights():
    slope, accumulation, stream_mask, valid_mask = _base_inputs()
    with pytest.raises(FloodSusceptibilityError):
        compute_flood_susceptibility(
            slope, accumulation, stream_mask, valid_mask,
            weight_slope=-0.5, weight_accumulation=0.5, weight_stream_proximity=1.0,
        )


def test_rejects_empty_stream_mask():
    slope, accumulation, stream_mask, valid_mask = _base_inputs()
    stream_mask[:, :] = False
    with pytest.raises(FloodSusceptibilityError):
        compute_flood_susceptibility(slope, accumulation, stream_mask, valid_mask)


def test_summary_statistics():
    slope, accumulation, stream_mask, valid_mask = _base_inputs()
    result = compute_flood_susceptibility(slope, accumulation, stream_mask, valid_mask)
    stats = result.summary_statistics()
    assert stats["low_count"] + stats["moderate_count"] + stats["high_count"] == stats["valid_cell_count"]