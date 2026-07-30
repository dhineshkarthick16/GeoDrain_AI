"""
Unit tests for raster stream extraction.
"""

import numpy as np
import pytest

from src.hydrology.stream_extraction import (
    StreamExtractionError,
    extract_stream_network,
)


def test_known_percentile_matches_numpy_reference():
    accumulation = np.arange(1, 101, dtype=np.int64).reshape(10, 10)
    valid_mask = np.ones((10, 10), dtype=bool)
    result = extract_stream_network(accumulation, valid_mask, percentile_threshold=90.0)

    expected_threshold = float(np.percentile(accumulation, 90.0))
    assert result.threshold_value == pytest.approx(expected_threshold)
    assert result.stream_mask.sum() == np.sum(accumulation >= expected_threshold)


def test_higher_percentile_produces_sparser_network():
    accumulation = np.random.default_rng(42).integers(1, 1000, size=(20, 20)).astype(np.int64)
    valid_mask = np.ones((20, 20), dtype=bool)

    loose = extract_stream_network(accumulation, valid_mask, percentile_threshold=90.0)
    strict = extract_stream_network(accumulation, valid_mask, percentile_threshold=99.0)

    assert strict.stream_cell_count <= loose.stream_cell_count


def test_invalid_cells_are_never_classified_as_stream():
    accumulation = np.full((10, 10), 500, dtype=np.int64)
    valid_mask = np.ones((10, 10), dtype=bool)
    valid_mask[5, 5] = False
    result = extract_stream_network(accumulation, valid_mask, percentile_threshold=0.0)

    assert not result.stream_mask[5, 5]


def test_rejects_shape_mismatch():
    accumulation = np.ones((5, 5), dtype=np.int64)
    valid_mask = np.ones((4, 4), dtype=bool)
    with pytest.raises(StreamExtractionError):
        extract_stream_network(accumulation, valid_mask)


def test_rejects_out_of_range_percentile():
    accumulation = np.ones((5, 5), dtype=np.int64)
    valid_mask = np.ones((5, 5), dtype=bool)
    with pytest.raises(StreamExtractionError):
        extract_stream_network(accumulation, valid_mask, percentile_threshold=100.0)
    with pytest.raises(StreamExtractionError):
        extract_stream_network(accumulation, valid_mask, percentile_threshold=-1.0)


def test_rejects_no_valid_cells():
    accumulation = np.ones((5, 5), dtype=np.int64)
    valid_mask = np.zeros((5, 5), dtype=bool)
    with pytest.raises(StreamExtractionError):
        extract_stream_network(accumulation, valid_mask)


def test_summary_statistics():
    accumulation = np.arange(1, 101, dtype=np.int64).reshape(10, 10)
    valid_mask = np.ones((10, 10), dtype=bool)
    result = extract_stream_network(accumulation, valid_mask, percentile_threshold=95.0)
    stats = result.summary_statistics()
    assert stats["stream_cell_count"] == result.stream_cell_count
    assert 0.0 <= stats["stream_fraction"] <= 1.0