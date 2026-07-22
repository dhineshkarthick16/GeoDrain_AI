"""
Workspace page: project configuration, DEM/DTM upload, DEM validation,
DEM processing, and slope/aspect analysis trigger.

This module contains NO terrain-analysis math itself. It only:
  1. Collects user input (project name, study area, file upload).
  2. Calls src.terrain.dem_processor.analyze_dem() for DEM stats.
  3. Calls src.terrain.slope_analysis.compute_slope_aspect() for slope/aspect.
  4. Stores results in st.session_state for the Results page and the
     Overview page to consume.
"""

from __future__ import annotations

import logging

import streamlit as st
from affine import Affine

from src.terrain.dem_processor import DEMAnalysis, analyze_dem
from src.terrain.slope_analysis import SlopeAnalysisError, compute_slope_aspect

logger = logging.getLogger(__name__)

# Session state keys — centralized here so Results page (or any other
# consumer) references the same constants rather than magic strings.
SESSION_KEY_ELEVATION = "gd_elevation_array"
SESSION_KEY_DEM_ANALYSIS = "gd_dem_analysis"
SESSION_KEY_SLOPE_ASPECT = "gd_slope_aspect_result"
SESSION_KEY_UPLOAD_NAME = "gd_uploaded_dem_name"

# Legacy keys, read by app.py's Overview page. Kept for backward
# compatibility so Overview's project-status metrics keep working
# now that Workspace/Results logic lives in this module instead of
# inline in app.py.
LEGACY_KEY_PROJECT_INITIALIZED = "project_initialized"
LEGACY_KEY_PROJECT_NAME = "project_name"
LEGACY_KEY_STUDY_AREA = "study_area"
LEGACY_KEY_DEM_FILE_NAME = "dem_file_name"
LEGACY_KEY_TERRAIN_ANALYSIS = "terrain_analysis"
LEGACY_KEY_ELEVATION_ARRAY = "elevation_array"


def _build_transform_from_resolution(analysis: DEMAnalysis) -> Affine:
    """
    Construct a minimal Affine transform sufficient for slope/aspect math.

    compute_slope_aspect() only reads transform.a (pixel width) and
    transform.e (pixel height) to derive real-world cell size — it never
    uses the transform's origin or rotation terms. Because dem_processor.py
    does not currently expose the dataset's full transform, we build a
    synthetic one from the resolution values it already returns.

    This is only valid for DEMs in a projected CRS (units = meters/feet).
    For geographic CRS (degrees), resolution values are NOT true ground
    distances and slope results would be wrong — see workspace warning.
    """
    return Affine(analysis.resolution_x, 0, 0, 0, -analysis.resolution_y, 0)


def _is_geographic_crs(crs_string: str) -> bool:
    """
    Best-effort check for a geographic (degree-based) CRS string.

    This is a heuristic, not a full CRS parse — dem_processor.py stores
    the CRS as a string (str(dataset.crs)), not a pyproj CRS object, so
    we cannot query .is_geographic directly without changing that module.
    """
    lowered = crs_string.lower()
    return "epsg:4326" in lowered or "longlat" in lowered or "wgs84" in lowered


def render_workspace_page() -> None:
    """Render the Workspace page: configure project, upload, validate, analyze."""
    st.header("Project Workspace")
    st.caption(
        "Configure a study area and upload a DEM/DTM GeoTIFF to compute "
        "elevation statistics and slope/aspect terrain analysis."
    )

    # --- Project configuration (feeds Overview page status only) ---
    st.subheader("Project Configuration")
    config_col1, config_col2 = st.columns(2)
    with config_col1:
        project_name = st.text_input(
            "Project Name",
            placeholder="Example: Kanchipuram Panchayat Drainage Plan",
        )
    with config_col2:
        study_area = st.text_input(
            "Study Area",
            placeholder="Example: Kanchipuram, Tamil Nadu",
        )

    st.divider()
    st.subheader("Terrain Model")

    uploaded_file = st.file_uploader(
        label="DEM / DTM GeoTIFF",
        type=["tif", "tiff"],
        help="Single-band GeoTIFF elevation raster.",
    )

    if uploaded_file is None:
        st.info("Upload a DEM/DTM GeoTIFF to begin.")
        return

    run_analysis = st.button("Run DEM & Slope/Aspect Analysis", type="primary")

    if not run_analysis:
        st.caption("File ready. Click the button above to run analysis.")
        return

    # --- Step 1: DEM validation + processing ---
    try:
        with st.spinner("Reading and validating DEM..."):
            elevation, analysis = analyze_dem(uploaded_file)
    except ValueError as exc:
        st.error(f"DEM validation failed: {exc}")
        logger.warning("DEM validation failed for %s: %s", uploaded_file.name, exc)
        return
    except Exception as exc:  # noqa: BLE001 - surface unexpected read errors to user
        st.error(f"Could not read DEM file: {exc}")
        logger.exception("Unexpected error reading DEM %s", uploaded_file.name)
        return

    st.success("DEM validated and loaded successfully.")

    if _is_geographic_crs(analysis.crs):
        st.warning(
            f"Detected CRS '{analysis.crs}' appears to be geographic (degrees), "
            "not projected (meters/feet). Slope/aspect results below will be "
            "INCORRECT because cell size is not in true ground units. "
            "Reproject the DEM to a projected CRS before relying on these results."
        )

    # --- Step 2: Slope/aspect analysis (only after successful validation) ---
    try:
        transform = _build_transform_from_resolution(analysis)
        with st.spinner("Computing slope and aspect (Horn's method)..."):
            slope_aspect_result = compute_slope_aspect(
                elevation=elevation,
                transform=transform,
                nodata=None,  # dem_processor already converted nodata -> NaN
            )
    except SlopeAnalysisError as exc:
        st.error(f"Slope/aspect analysis could not be completed: {exc}")
        logger.warning("Slope/aspect analysis failed: %s", exc)
        return

    st.success("Slope/aspect analysis complete.")

    # --- Step 3: Store results in session state for the Results page ---
    st.session_state[SESSION_KEY_ELEVATION] = elevation
    st.session_state[SESSION_KEY_DEM_ANALYSIS] = analysis
    st.session_state[SESSION_KEY_SLOPE_ASPECT] = slope_aspect_result
    st.session_state[SESSION_KEY_UPLOAD_NAME] = uploaded_file.name

    # --- Legacy keys for Overview page compatibility ---
    st.session_state[LEGACY_KEY_PROJECT_NAME] = project_name or "Unnamed Project"
    st.session_state[LEGACY_KEY_STUDY_AREA] = study_area or "Not specified"
    st.session_state[LEGACY_KEY_PROJECT_INITIALIZED] = True
    st.session_state[LEGACY_KEY_DEM_FILE_NAME] = uploaded_file.name
    st.session_state[LEGACY_KEY_TERRAIN_ANALYSIS] = analysis
    st.session_state[LEGACY_KEY_ELEVATION_ARRAY] = elevation

    st.info("Analysis stored. Open the Results page to view outputs.")