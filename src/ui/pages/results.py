"""
Results page: reads analysis results from session state and displays them.
"""

from __future__ import annotations

import streamlit as st

from src.terrain.slope_analysis import compass_label
from src.terrain.slope_visualization import plot_aspect_map, plot_slope_map
from src.terrain.terrain_visualization import create_elevation_figure
from src.hydrology.flow_direction_visualization import (
    plot_flow_direction_map,
    plot_sink_flat_map,
)
from src.hydrology.flow_accumulation_visualization import plot_flow_accumulation_map
from src.ui.pages.workspace import (
    SESSION_KEY_DEM_ANALYSIS,
    SESSION_KEY_ELEVATION,
    SESSION_KEY_FLOW_ACCUMULATION,
    SESSION_KEY_FLOW_DIRECTION,
    SESSION_KEY_SLOPE_ASPECT,
    SESSION_KEY_UPLOAD_NAME,
)


def render_results_page() -> None:
    """Render the Results page: elevation, slope/aspect, flow direction, accumulation."""
    st.header("Analysis Results")

    dem_analysis = st.session_state.get(SESSION_KEY_DEM_ANALYSIS)
    slope_aspect_result = st.session_state.get(SESSION_KEY_SLOPE_ASPECT)
    flow_direction_result = st.session_state.get(SESSION_KEY_FLOW_DIRECTION)
    flow_accumulation_result = st.session_state.get(SESSION_KEY_FLOW_ACCUMULATION)
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

    st.subheader("Digital Elevation Model")
    if elevation is not None:
        try:
            elevation_fig = create_elevation_figure(elevation)
            st.pyplot(elevation_fig, width="stretch")
        except Exception as exc:  # noqa: BLE001
            st.error(f"Elevation visualization failed: {exc}")
    else:
        st.info("Elevation array not available for visualization.")

    st.divider()

    st.subheader("Slope Statistics")
    try:
        stats = slope_aspect_result.summary_statistics()
    except Exception as exc:  # noqa: BLE001
        st.error(f"Could not compute slope summary statistics: {exc}")
        return

    col1, col2, col3 = st.columns(3)
    col1.metric("Mean Slope (deg)", f"{stats['mean_slope_degrees']:.2f}")
    col2.metric("Max Slope (deg)", f"{stats['max_slope_degrees']:.2f}")
    col3.metric("Min Slope (deg)", f"{stats['min_slope_degrees']:.2f}")

    st.caption(
        f"Valid cells analyzed: {stats['valid_cell_count']} / "
        f"{stats['total_cell_count']} "
        f"(median {stats['median_slope_degrees']:.2f} deg, "
        f"std dev {stats['std_slope_degrees']:.2f} deg)"
    )

    st.subheader("Slope Map")
    slope_units = st.radio(
        "Units", options=["percent", "degrees"], horizontal=True, key="slope_units_radio"
    )
    slope_fig = plot_slope_map(slope_aspect_result, units=slope_units)
    st.pyplot(slope_fig)

    st.subheader("Aspect Map")
    aspect_fig = plot_aspect_map(slope_aspect_result)
    st.pyplot(aspect_fig)

    with st.expander("Aspect Sector Reference"):
        st.write({sector: compass_label(sector) for sector in range(8)})

    st.divider()

    if flow_direction_result is None:
        st.info("Flow direction has not been computed for this DEM yet.")
    else:
        st.subheader("Flow Direction (D8) Statistics")
        try:
            flow_stats = flow_direction_result.summary_statistics()
        except Exception as exc:  # noqa: BLE001
            st.error(f"Could not compute flow direction summary statistics: {exc}")
            flow_stats = None

        if flow_stats is not None:
            col1, col2, col3 = st.columns(3)
            col1.metric(
                "Defined Direction",
                f"{flow_stats['defined_direction_fraction'] * 100:.1f}%",
            )
            col2.metric("Sink Cells", flow_stats["sink_count"])
            col3.metric("Flat Cells", flow_stats["flat_count"])

            if flow_stats["sink_count"] > 0 or flow_stats["flat_count"] > 0:
                st.caption(
                    "Sinks and flats have no defined D8 direction. This is normal "
                    "for real-world DEMs and does not indicate an error - these "
                    "cells require DEM conditioning (sink-filling) before flow "
                    "accumulation can be computed through them."
                )

        st.subheader("Flow Direction Map")
        st.pyplot(plot_flow_direction_map(flow_direction_result))

        st.subheader("Sinks & Flats Map")
        st.pyplot(plot_sink_flat_map(flow_direction_result))

    st.divider()

    if flow_accumulation_result is None:
        st.info("Flow accumulation has not been computed for this DEM yet.")
    else:
        st.subheader("Flow Accumulation Statistics")
        try:
            acc_stats = flow_accumulation_result.summary_statistics()
        except Exception as exc:  # noqa: BLE001
            st.error(f"Could not compute flow accumulation summary statistics: {exc}")
            acc_stats = None

        if acc_stats is not None:
            col1, col2, col3 = st.columns(3)
            col1.metric("Max Accumulation (cells)", f"{acc_stats['max_accumulation']:,}")
            col2.metric("Mean Accumulation (cells)", f"{acc_stats['mean_accumulation']:.1f}")
            col3.metric(
                "Terminal Cells",
                f"{acc_stats['terminal_fraction'] * 100:.1f}%",
            )
            st.caption(
                f"Max contributing area: {acc_stats['max_contributing_area']:.6g} "
                "(map units squared - only meaningful for a projected CRS)."
            )

            if acc_stats["terminal_fraction"] > 0:
                st.caption(
                    "Terminal cells are where accumulation stops early due to "
                    "undefined flow direction (sinks/flats) or a downstream "
                    "nodata edge. This does not indicate a computation error."
                )

        st.subheader("Flow Accumulation Map")
        st.caption(
            "Displayed on a log scale (industry-standard convention), since "
            "accumulation values typically span several orders of magnitude."
        )
        st.pyplot(plot_flow_accumulation_map(flow_accumulation_result))

    st.caption(
        "This page presents terrain and hydrology ANALYSIS output only. "
        "Results are not engineering-certified and must be reviewed by a "
        "qualified engineer before use in any drainage design decision."
    )
