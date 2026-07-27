"""
Workspace page: project configuration, DEM/DTM upload, DEM validation,
DEM processing, slope/aspect analysis, flow direction, and flow accumulation.

This module contains NO terrain/hydrology math itself. It only:
  1. Collects user input (project name, study area, file upload).
  2. Calls src.terrain.dem_processor.analyze_dem() for DEM stats.
  3. Calls src.terrain.slope_analysis.compute_slope_aspect() for slope/aspect.
  4. Calls src.hydrology.flow_direction.compute_flow_direction() for D8 flow direction.
  5. Calls src.hydrology.flow_accumulation.compute_flow_accumulation() for accumulation.
  6. Stores results in st.session_state for the Results page and the
     Overview page to consume.
"""

from __future__ import annotations

import logging

import streamlit as st
from affine import Affine

from src.terrain.dem_processor import DEMAnalysis, analyze_dem
from src.terrain.slope_analysis import SlopeAnalysisError, compute_slope_aspect
from src.hydrology.flow_direction import FlowDirectionError, compute_flow_direction
from src.hydrology.flow_accumulation import (
    FlowAccumulationError,
    compute_flow_accumulation,
)
from src.utils.crs_utils import is_geographic_crs

logger = logging.getLogger(__name__)

SESSION_KEY_ELEVATION = "gd_elevation_array"
SESSION_KEY_DEM_ANALYSIS = "gd_dem_analysis"
SESSION_KEY_SLOPE_ASPECT = "gd_slope_aspect_result"
SESSION_KEY_FLOW_DIRECTION = "gd_flow_direction_result"
SESSION_KEY_FLOW_ACCUMULATION = "gd_flow_accumulation_result"
SESSION_KEY_UPLOAD_NAME = "gd_uploaded_dem_name"

LEGACY_KEY_PROJECT_INITIALIZED = "project_initialized"
LEGACY_KEY_PROJECT_NAME = "project_name"
LEGACY_KEY_STUDY_AREA = "study_area"
LEGACY_KEY_DEM_FILE_NAME = "dem_file_name"
LEGACY_KEY_TERRAIN_ANALYSIS = "terrain_analysis"
LEGACY_KEY_ELEVATION_ARRAY = "elevation_array"


def _build_transform_from_resolution(analysis: DEMAnalysis) -> Affine:
    """Construct a minimal Affine transform sufficient for slope/aspect math."""
    return Affine(analysis.resolution_x, 0, 0, 0, -analysis.resolution_y, 0)


def render_workspace_page() -> None:
    """Render the Workspace page: configure project, upload, validate, analyze."""
    st.header("Project Workspace")
    st.caption(
        "Configure a study area and upload a DEM/DTM GeoTIFF to compute "
        "elevation statistics, slope/aspect, flow direction, and flow "
        "accumulation analysis."
    )

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

    run_analysis = st.button("Run Full Terrain & Hydrology Analysis", type="primary")

    if not run_analysis:
        st.caption("File ready. Click the button above to run analysis.")
        return

    try:
        with st.spinner("Reading and validating DEM..."):
            elevation, analysis = analyze_dem(uploaded_file)
    except ValueError as exc:
        st.error(f"DEM validation failed: {exc}")
        logger.warning("DEM validation failed for %s: %s", uploaded_file.name, exc)
        return
    except Exception as exc:  # noqa: BLE001
        st.error(f"Could not read DEM file: {exc}")
        logger.exception("Unexpected error reading DEM %s", uploaded_file.name)
        return

    st.success("DEM validated and loaded successfully.")

    dem_is_geographic = is_geographic_crs(analysis.crs)
    if dem_is_geographic:
        st.warning(
            f"Detected CRS '{analysis.crs}' appears to be geographic (degrees), "
            "not projected (meters/feet). Slope, aspect, flow direction, AND flow "
            "accumulation results below will be INCORRECT because cell size is not "
            "in true ground units. Reproject the DEM to a projected CRS before "
            "relying on these results."
        )

    try:
        transform = _build_transform_from_resolution(analysis)
        with st.spinner("Computing slope and aspect (Horn's method)..."):
            slope_aspect_result = compute_slope_aspect(
                elevation=elevation,
                transform=transform,
                nodata=None,
            )
    except SlopeAnalysisError as exc:
        st.error(f"Slope/aspect analysis could not be completed: {exc}")
        logger.warning("Slope/aspect analysis failed: %s", exc)
        return

    st.success("Slope/aspect analysis complete.")

    try:
        with st.spinner("Computing flow direction (D8 method)..."):
            flow_direction_result = compute_flow_direction(
                elevation=elevation,
                cell_size_x=analysis.resolution_x,
                cell_size_y=analysis.resolution_y,
            )
    except FlowDirectionError as exc:
        st.error(f"Flow direction analysis could not be completed: {exc}")
        logger.warning("Flow direction analysis failed: %s", exc)
        return

    flow_stats = flow_direction_result.summary_statistics()
    st.success("Flow direction (D8) analysis complete.")

    if flow_stats["sink_count"] > 0 or flow_stats["flat_count"] > 0:
        st.info(
            f"Flow direction found {flow_stats['sink_count']} sink cell(s) and "
            f"{flow_stats['flat_count']} flat cell(s) with no defined downhill "
            "direction. This is expected on real-world DEMs and does not mean "
            "the analysis failed - these cells require DEM conditioning "
            "(sink-filling) in a future phase before flow accumulation can "
            "route through them correctly."
        )

    try:
        with st.spinner(
            "Computing flow accumulation (this pass is sequential and can take "
            "longer than earlier steps on large DEMs - please wait)..."
        ):
            flow_accumulation_result = compute_flow_accumulation(
                elevation=elevation,
                direction=flow_direction_result.direction,
                cell_size_x=analysis.resolution_x,
                cell_size_y=analysis.resolution_y,
            )
    except FlowAccumulationError as exc:
        st.error(f"Flow accumulation could not be completed: {exc}")
        logger.warning("Flow accumulation failed: %s", exc)
        return

    acc_stats = flow_accumulation_result.summary_statistics()
    st.success("Flow accumulation analysis complete.")

    if acc_stats["terminal_fraction"] > 0:
        st.info(
            f"Flow accumulation stops early at {acc_stats['terminal_cell_count']} "
            f"cell(s) ({acc_stats['terminal_fraction'] * 100:.1f}% of valid cells) "
            "where no defined downhill direction exists. Accumulation counts "
            "upstream of these points do not continue past them - this is an "
            "honest limitation of unconditioned terrain, not a computation error."
        )

    st.session_state[SESSION_KEY_ELEVATION] = elevation
    st.session_state[SESSION_KEY_DEM_ANALYSIS] = analysis
    st.session_state[SESSION_KEY_SLOPE_ASPECT] = slope_aspect_result
    st.session_state[SESSION_KEY_FLOW_DIRECTION] = flow_direction_result
    st.session_state[SESSION_KEY_FLOW_ACCUMULATION] = flow_accumulation_result
    st.session_state[SESSION_KEY_UPLOAD_NAME] = uploaded_file.name

    st.session_state[LEGACY_KEY_PROJECT_NAME] = project_name or "Unnamed Project"
    st.session_state[LEGACY_KEY_STUDY_AREA] = study_area or "Not specified"
    st.session_state[LEGACY_KEY_PROJECT_INITIALIZED] = True
    st.session_state[LEGACY_KEY_DEM_FILE_NAME] = uploaded_file.name
    st.session_state[LEGACY_KEY_TERRAIN_ANALYSIS] = analysis
    st.session_state[LEGACY_KEY_ELEVATION_ARRAY] = elevation

    st.info("Analysis stored. Open the Results page to view outputs.")
