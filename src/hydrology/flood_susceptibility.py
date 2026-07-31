"""
Terrain-based flood susceptibility indicator.

IMPORTANT SCOPE NOTE: this module computes a TERRAIN-BASED SUSCEPTIBILITY
INDICATOR, not a validated flood-risk model. A real flood-risk assessment
requires rainfall intensity, soil infiltration characteristics, land use,
and historical flood records — none of which are inputs here. This module
combines three terrain signals that are known correlates of where surface
water tends to concentrate:

  - Low slope (water drains away slowly)
  - High flow accumulation (many upstream cells route through this point)
  - Proximity to an extracted stream cell (nearer to likely channels)

...into a single normalized score and a coarse Low/Moderate/High
classification. The combination weights are an explicit, stated
assumption (default: equal weights), not calibrated against any
observed flood data. This must be presented to users as a screening-level
indicator requiring engineering validation, never as a certified
flood-risk assessment.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

import numpy as np
from scipy.ndimage import distance_transform_edt

logger = logging.getLogger(__name__)

LOW = 0
MODERATE = 1
HIGH = 2
_CLASS_LABELS = {LOW: "Low", MODERATE: "Moderate", HIGH: "High"}


class FloodSusceptibilityError(Exception):
    """Raised when flood susceptibility computation cannot proceed safely."""


def class_label(class_code: int) -> str:
    """Map a susceptibility class code back to its label."""
    return _CLASS_LABELS.get(class_code, "Unknown")


@dataclass(frozen=True)
class FloodSusceptibilityResult:
    """
    Container for flood susceptibility output.

    Attributes:
        susceptibility_score: Float array in [0, 1], higher = more
            terrain-driven susceptibility to water concentration.
        susceptibility_class: Integer array (LOW/MODERATE/HIGH, or -1 for
            invalid cells) from fixed thresholds on susceptibility_score
            (< 1/3 Low, < 2/3 Moderate, else High).
        valid_mask: Boolean array, True where the score is meaningful.
        weight_slope: Weight applied to the inverted-slope component.
        weight_accumulation: Weight applied to the log-accumulation component.
        weight_stream_proximity: Weight applied to the inverted-distance-to-stream component.
    """

    susceptibility_score: np.ndarray
    susceptibility_class: np.ndarray
    valid_mask: np.ndarray
    weight_slope: float
    weight_accumulation: float
    weight_stream_proximity: float

    def summary_statistics(self) -> dict[str, float]:
        """Return class-count breakdown and score extremes over valid cells."""
        valid_count = int(self.valid_mask.sum())
        if valid_count == 0:
            raise FloodSusceptibilityError(
                "No valid cells to summarize — inputs may be entirely nodata."
            )
        valid_classes = self.susceptibility_class[self.valid_mask]
        valid_scores = self.susceptibility_score[self.valid_mask]
        return {
            "valid_cell_count": valid_count,
            "low_count": int((valid_classes == LOW).sum()),
            "moderate_count": int((valid_classes == MODERATE).sum()),
            "high_count": int((valid_classes == HIGH).sum()),
            "high_fraction": float((valid_classes == HIGH).sum()) / valid_count,
            "mean_score": float(valid_scores.mean()),
            "max_score": float(valid_scores.max()),
        }


def _normalize(values: np.ndarray, valid_mask: np.ndarray) -> np.ndarray:
    """Min-max normalize valid values to [0, 1]. Invalid cells set to 0."""
    result = np.zeros_like(values, dtype=np.float64)
    valid_values = values[valid_mask]
    if valid_values.size == 0:
        return result
    vmin = float(valid_values.min())
    vmax = float(valid_values.max())
    if vmax - vmin < 1e-12:
        result[valid_mask] = 0.0
        return result
    result[valid_mask] = (values[valid_mask] - vmin) / (vmax - vmin)
    return result


def _classify(score: np.ndarray, valid_mask: np.ndarray) -> np.ndarray:
    """Classify a [0, 1] score into LOW/MODERATE/HIGH using fixed thresholds."""
    classes = np.full(score.shape, -1, dtype=np.int8)
    classes[valid_mask & (score < 1.0 / 3.0)] = LOW
    classes[valid_mask & (score >= 1.0 / 3.0) & (score < 2.0 / 3.0)] = MODERATE
    classes[valid_mask & (score >= 2.0 / 3.0)] = HIGH
    return classes


def compute_flood_susceptibility(
    slope_percent: np.ndarray,
    accumulation: np.ndarray,
    stream_mask: np.ndarray,
    valid_mask: np.ndarray,
    weight_slope: float = 1.0 / 3.0,
    weight_accumulation: float = 1.0 / 3.0,
    weight_stream_proximity: float = 1.0 / 3.0,
) -> FloodSusceptibilityResult:
    """
    Compute a terrain-based flood susceptibility indicator.

    Args:
        slope_percent: 2D slope array in percent (e.g.
            SlopeAspectResult.slope_percent). Lower slope contributes
            higher susceptibility.
        accumulation: 2D flow accumulation array (e.g.
            FlowAccumulationResult.accumulation). Higher accumulation
            contributes higher susceptibility (log-scaled before
            normalizing, since accumulation spans orders of magnitude).
        stream_mask: 2D boolean array of extracted stream cells (e.g.
            StreamNetworkResult.stream_mask). Must contain at least one
            True cell. Proximity to these cells contributes higher
            susceptibility.
        valid_mask: 2D boolean array, True where all inputs are meaningful.
        weight_slope: Weight for the inverted-slope component.
        weight_accumulation: Weight for the log-accumulation component.
        weight_stream_proximity: Weight for the inverted-distance-to-stream
            component.

    Returns:
        FloodSusceptibilityResult.

    Raises:
        FloodSusceptibilityError: on shape mismatch, invalid weights, or
            an empty stream mask.
    """
    shapes = {slope_percent.shape, accumulation.shape, stream_mask.shape, valid_mask.shape}
    if len(shapes) != 1:
        raise FloodSusceptibilityError(
            f"All inputs must share the same shape, got: "
            f"slope={slope_percent.shape}, accumulation={accumulation.shape}, "
            f"stream_mask={stream_mask.shape}, valid_mask={valid_mask.shape}."
        )

    weights = (weight_slope, weight_accumulation, weight_stream_proximity)
    if any(w < 0 for w in weights):
        raise FloodSusceptibilityError("Weights must be non-negative.")
    weight_sum = sum(weights)
    if abs(weight_sum - 1.0) > 1e-6:
        raise FloodSusceptibilityError(
            f"Weights must sum to 1.0, got {weight_sum:.6f}."
        )

    if not stream_mask.any():
        raise FloodSusceptibilityError(
            "stream_mask contains no True cells — cannot compute distance to "
            "stream. Lower the stream extraction percentile threshold."
        )

    # Slope: lower slope -> higher susceptibility, so invert after normalizing.
    slope_valid = valid_mask & np.isfinite(slope_percent)
    norm_slope = _normalize(np.where(slope_valid, slope_percent, 0.0), slope_valid)
    slope_component = np.where(slope_valid, 1.0 - norm_slope, 0.0)

    # Accumulation: log-scale first (spans orders of magnitude), then normalize.
    acc_safe = np.where(valid_mask, np.maximum(accumulation, 0), 0).astype(np.float64)
    log_acc = np.log1p(acc_safe)
    accumulation_component = _normalize(log_acc, valid_mask)

    # Distance to nearest stream cell: distance_transform_edt gives, for
    # each cell, distance to the nearest zero-valued cell in its input.
    # Passing ~stream_mask means stream cells (False there) are the
    # "targets", so non-stream cells get their true distance to the
    # nearest stream cell, and stream cells themselves correctly get 0.
    distance_to_stream = distance_transform_edt(~stream_mask)
    norm_distance = _normalize(distance_to_stream, valid_mask)
    proximity_component = np.where(valid_mask, 1.0 - norm_distance, 0.0)

    score = (
        weight_slope * slope_component
        + weight_accumulation * accumulation_component
        + weight_stream_proximity * proximity_component
    )
    score = np.where(valid_mask, np.clip(score, 0.0, 1.0), 0.0)

    classes = _classify(score, valid_mask)

    logger.info(
        "Flood susceptibility computed: weights=(slope=%.3f, acc=%.3f, "
        "stream=%.3f), mean score=%.3f over %d valid cells.",
        weight_slope, weight_accumulation, weight_stream_proximity,
        float(score[valid_mask].mean()) if valid_mask.any() else float("nan"),
        int(valid_mask.sum()),
    )

    return FloodSusceptibilityResult(
        susceptibility_score=score,
        susceptibility_class=classes,
        valid_mask=valid_mask,
        weight_slope=weight_slope,
        weight_accumulation=weight_accumulation,
        weight_stream_proximity=weight_stream_proximity,
    )