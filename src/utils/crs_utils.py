"""
Shared CRS validation helpers used across terrain and hydrology modules.

Centralized here so slope/aspect analysis and flow-direction analysis
apply the exact same geographic-CRS detection logic, rather than each
module maintaining its own copy.
"""

from __future__ import annotations


def is_geographic_crs(crs_string: str) -> bool:
    """
    Best-effort check for a geographic (degree-based) CRS string.

    This is a heuristic, not a full CRS parse — dem_processor.py stores
    the CRS as a string (str(dataset.crs)), not a pyproj CRS object, so
    we cannot query .is_geographic directly without changing that module.
    """
    lowered = crs_string.lower()
    return "epsg:4326" in lowered or "longlat" in lowered or "wgs84" in lowered