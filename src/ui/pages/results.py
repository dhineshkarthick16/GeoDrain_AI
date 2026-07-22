"""
Results page: reads analysis results from session state and displays them.

This module contains NO terrain-analysis math and NO slope/aspect
algorithm logic. It only reads already-computed results
(DEMAnalysis, SlopeAspectResult, elevation array) from st.session_state
and renders them via src.terrain.slope_visualization and
src.terrain.terrain_visualization.
"""

from __future__ import annotations

import streamlit as st

from src.terrain.slope_analysis import compass_label
from src.terrain.slope_visualization import plot_aspect_map, plot_slope_map
from src.terrain.terrain_visualization import create_elevation_figure
from src.ui.pages.workspace import (
    SESSION_KEY_DEM_ANALYSIS,
    SESSION_KEY_ELEVATION,
    SESSION_KEY_SLOPE_ASPECT,
    SESSION_KEY_UPLOAD_NAME,
)


def render_results_page() -> None:
    """Render the Results page: elevation stats, elevation map, slope map, aspect map."""
    st.header("Analysis Results")

    dem_analysis = st.session_state.get(SESSION_KEY_DEM_ANALYSIS)
    slope_aspect_result = st.session_state.get(SESSION_KEY_SLOPE_ASPECT)
    elevation = st.session_state.get(SESSION_KEY_ELEVATION)
    uploaded_name = st.session_state.get(SESSION_KEY_UPLOAD_NAME)

    if dem_analysis is None or slope_aspect_result is None:
        st.info(
            "No analysis results available yet. Go to the Workspace page, "
            "upload a DEM/DTM, and run the analysis first."
        )
        return

    if uploaded_name:
        st.caption(f"Source file: {uploaded_name}")

    # --- Elevation statistics (already computed by dem_processor) ---
    st.subheader("Elevation Statistics")
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Min Elevation (m)", f"{dem_analysis.min_elevation:.2f}")
    col2.metric("Max Elevation (m)", f"{dem_analysis.max_elevation:.2f}")
    col3.metric("Mean Elevation (m)", f"{dem_analysis.mean_elevation:.2f}")
    col4.metric("Elevation Range (m)", f"{dem_analysis.elevation_range:.2f}")

    with st.expander("DEM Metadata"):
        st.write(
            {
                "Rows": dem_analysis.rows,
                "Columns": dem_analysis.columns,
                "CRS": dem_analysis.crs,
                "Resolution X": dem_analysis.resolution_x,
                "Resolution Y": dem_analysis.resolution_y,
                "NoData Value": dem_analysis.nodata_value,
            }
        )

    # --- Elevation visualization ---
    st.subheader("Digital Elevation Model")
    if elevation is not None:
        try:
            elevation_fig = create_elevation_figure(elevation)
            st.pyplot(elevation_fig, use_container_width=True)
        except Exception as exc:  # noqa: BLE001 - surface to user, don't fabricate a map
            st.error(f"Elevation visualization failed: {exc}")
    else:
        st.info("Elevation array not available for visualization.")

    st.divider()

    # --- Slope statistics ---
    st.subheader("Slope Statistics")
    try:
        stats = slope_aspect_result.summary_statistics()
    except Exception as exc:  # noqa: BLE001 - surface to user, don't fabricate stats
        st.error(f"Could not compute slope summary statistics: {exc}")
        return

    col1, col2, col3 = st.columns(3)
    col1.metric("Mean Slope (°)", f"{stats['mean_slope_degrees']:.2f}")
    col2.metric("Max Slope (°)", f"{stats['max_slope_degrees']:.2f}")
    col3.metric("Min Slope (°)", f"{stats['min_slope_degrees']:.2f}")

    st.caption(
        f"Valid cells analyzed: {stats['valid_cell_count']} / "
        f"{stats['total_cell_count']} "
        f"(median {stats['median_slope_degrees']:.2f}°, "
        f"std dev {stats['std_slope_degrees']:.2f}°)"
    )

    # --- Slope map ---
    st.subheader("Slope Map")
    slope_units = st.radio(
        "Units", options=["percent", "degrees"], horizontal=True, key="slope_units_radio"
    )
    slope_fig = plot_slope_map(slope_aspect_result, units=slope_units)
    st.pyplot(slope_fig)

    # --- Aspect map ---
    st.subheader("Aspect Map")
    aspect_fig = plot_aspect_map(slope_aspect_result)
    st.pyplot(aspect_fig)

    with st.expander("Aspect Sector Reference"):
        st.write(
            {
                sector: compass_label(sector)
                for sector in range(8)
            }
        )

    st.caption(
        "This page presents terrain ANALYSIS output only. Results are not "
        "engineering-certified and must be reviewed by a qualified engineer "
        "before use in any drainage design decision."
    )