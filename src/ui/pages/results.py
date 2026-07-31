"""
Results page: reads analysis results from session state and displays them.
"""

from __future__ import annotations

import streamlit as st
from streamlit_image_coordinates import streamlit_image_coordinates

from src.terrain.slope_analysis import compass_label
from src.terrain.slope_visualization import plot_aspect_map, plot_slope_map
from src.terrain.terrain_visualization import create_elevation_figure
from src.hydrology.flow_direction_visualization import (
    plot_flow_direction_map,
    plot_sink_flat_map,
)
from src.hydrology.flow_accumulation_visualization import plot_flow_accumulation_map
from src.hydrology.stream_extraction import extract_stream_network, StreamExtractionError
from src.hydrology.stream_extraction_visualization import plot_stream_network_map
from src.hydrology.watershed_delineation import (
    delineate_catchment,
    WatershedDelineationError,
)
from src.hydrology.watershed_visualization import (
    build_pour_point_selector_image,
    plot_catchment_map,
)
from src.hydrology.flood_susceptibility import (
    compute_flood_susceptibility,
    FloodSusceptibilityError,
)
from src.hydrology.flood_susceptibility_visualization import plot_susceptibility_map
from src.ui.pages.workspace import (
    SESSION_KEY_DEM_ANALYSIS,
    SESSION_KEY_ELEVATION,
    SESSION_KEY_FLOW_ACCUMULATION,
    SESSION_KEY_FLOW_DIRECTION,
    SESSION_KEY_SLOPE_ASPECT,
    SESSION_KEY_UPLOAD_NAME,
)


def render_results_page() -> None:
    """Render the Results page: elevation, slope/aspect, flow direction, accumulation, streams, watershed, susceptibility."""
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

    st.divider()

    stream_result = None
    if flow_accumulation_result is None:
        st.info(
            "Stream network extraction requires flow accumulation results, "
            "which have not been computed for this DEM yet."
        )
    else:
        st.subheader("Stream Network Extraction")
        st.caption(
            "Cells are classified as drainage channels when their flow "
            "accumulation exceeds a percentile threshold of the accumulation "
            "distribution. This is a raster classification, not a vector "
            "stream network - connected line geometry (for GIS/HEC-RAS "
            "export) is a planned future phase."
        )

        percentile = st.slider(
            "Stream threshold percentile (higher = sparser, more selective network)",
            min_value=90.0,
            max_value=99.9,
            value=99.0,
            step=0.1,
            key="stream_percentile_slider",
        )

        try:
            stream_result = extract_stream_network(
                accumulation=flow_accumulation_result.accumulation,
                valid_mask=flow_accumulation_result.valid_mask,
                percentile_threshold=percentile,
            )
        except StreamExtractionError as exc:
            st.error(f"Stream extraction could not be completed: {exc}")
            stream_result = None

        if stream_result is not None:
            stream_stats = stream_result.summary_statistics()
            col1, col2, col3 = st.columns(3)
            col1.metric("Stream Cells", f"{stream_stats['stream_cell_count']:,}")
            col2.metric("Stream Fraction", f"{stream_stats['stream_fraction'] * 100:.2f}%")
            col3.metric("Accumulation Threshold", f"{stream_stats['threshold_value']:.1f}")

            st.pyplot(
                plot_stream_network_map(flow_accumulation_result, stream_result)
            )

    st.divider()

    if flow_direction_result is None or flow_accumulation_result is None:
        st.info(
            "Watershed / catchment delineation requires flow direction and "
            "flow accumulation results, which have not been computed for "
            "this DEM yet."
        )
    else:
        st.subheader("Watershed / Catchment Delineation")
        st.caption(
            "Click a point on the map below to select a pour point. The "
            "catchment (every cell whose flow path drains through that "
            "point) will be delineated and highlighted. This delineates a "
            "single chosen catchment, not automatic whole-DEM basin "
            "labeling - see engineering notes for why."
        )

        click_image, click_stride = build_pour_point_selector_image(
            flow_accumulation_result.accumulation,
            flow_accumulation_result.valid_mask,
        )
        coords = streamlit_image_coordinates(click_image, key="pour_point_selector")

        if coords is None:
            st.info("Click anywhere on the map above to select a pour point.")
        else:
            img_w, img_h = click_image.size
            disp_w = coords.get("width") or img_w
            disp_h = coords.get("height") or img_h
            scale_x = img_w / disp_w if disp_w else 1.0
            scale_y = img_h / disp_h if disp_h else 1.0

            thumb_col = int(coords["x"] * scale_x)
            thumb_row = int(coords["y"] * scale_y)

            max_row = flow_direction_result.direction.shape[0] - 1
            max_col = flow_direction_result.direction.shape[1] - 1
            pour_row = min(thumb_row * click_stride, max_row)
            pour_col = min(thumb_col * click_stride, max_col)

            st.caption(f"Selected pour point: row {pour_row}, column {pour_col}")

            try:
                catchment_result = delineate_catchment(
                    direction=flow_direction_result.direction,
                    valid_mask=flow_direction_result.valid_mask,
                    pour_row=pour_row,
                    pour_col=pour_col,
                    cell_size_x=dem_analysis.resolution_x,
                    cell_size_y=dem_analysis.resolution_y,
                )
            except WatershedDelineationError as exc:
                st.error(
                    f"Could not delineate catchment at this point: {exc} "
                    "Try clicking a different location."
                )
                catchment_result = None

            if catchment_result is not None:
                col1, col2 = st.columns(2)
                col1.metric("Catchment Cells", f"{catchment_result.cell_count:,}")
                col2.metric(
                    "Catchment Area",
                    f"{catchment_result.area:.6g} (map units squared)",
                )
                st.pyplot(
                    plot_catchment_map(flow_accumulation_result, catchment_result)
                )

    st.divider()

    if flow_accumulation_result is None or stream_result is None:
        st.info(
            "Flood susceptibility requires flow accumulation and stream "
            "extraction results, which are not both available yet."
        )
    else:
        st.subheader("Flood Susceptibility Indicator")
        st.warning(
            "SCOPE NOTE: this is a TERRAIN-BASED SUSCEPTIBILITY SCREENING "
            "INDICATOR, not a validated flood-risk model. It combines slope, "
            "flow accumulation, and proximity to the extracted stream network "
            "above using equal, assumption-based weights - it does NOT use "
            "rainfall, soil, or land-use data, and has not been calibrated "
            "against any observed flood record. Use for screening/discussion "
            "only; any real decision requires engineering validation."
        )

        try:
            susceptibility_result = compute_flood_susceptibility(
                slope_percent=slope_aspect_result.slope_percent,
                accumulation=flow_accumulation_result.accumulation,
                stream_mask=stream_result.stream_mask,
                valid_mask=flow_accumulation_result.valid_mask,
            )
        except FloodSusceptibilityError as exc:
            st.error(f"Flood susceptibility could not be computed: {exc}")
            susceptibility_result = None

        if susceptibility_result is not None:
            sus_stats = susceptibility_result.summary_statistics()
            col1, col2, col3 = st.columns(3)
            col1.metric(
                "Low Susceptibility",
                f"{sus_stats['low_count']:,} "
                f"({sus_stats['low_count'] / sus_stats['valid_cell_count'] * 100:.1f}%)",
            )
            col2.metric(
                "Moderate Susceptibility",
                f"{sus_stats['moderate_count']:,} "
                f"({sus_stats['moderate_count'] / sus_stats['valid_cell_count'] * 100:.1f}%)",
            )
            col3.metric(
                "High Susceptibility",
                f"{sus_stats['high_count']:,} "
                f"({sus_stats['high_fraction'] * 100:.1f}%)",
            )
            st.caption(
                "Weights used: slope=1/3, flow accumulation=1/3, stream "
                "proximity=1/3 (equal weighting, not calibrated to real data)."
            )
            st.pyplot(plot_susceptibility_map(susceptibility_result))

    st.caption(
        "This page presents terrain and hydrology ANALYSIS output only. "
        "Results are not engineering-certified and must be reviewed by a "
        "qualified engineer before use in any drainage design decision."
    )
