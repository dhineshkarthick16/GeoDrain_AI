"""
Engineering Reports page: packages the last completed analysis run into a
downloadable PDF. Performs no new analysis - reads whatever is already in
session state from the Workspace/Results pages.
"""

from __future__ import annotations

import streamlit as st

from src.reporting.pdf_report import ReportInputs, build_pdf_report
from src.ui.pages.results import (
    SESSION_KEY_CATCHMENT_POUR_POINT,
    SESSION_KEY_CATCHMENT_RESULT,
    SESSION_KEY_REPORT_IMAGES,
    SESSION_KEY_STREAM_RESULT,
    SESSION_KEY_SUSCEPTIBILITY_RESULT,
)
from src.ui.pages.workspace import (
    LEGACY_KEY_PROJECT_NAME,
    LEGACY_KEY_STUDY_AREA,
    SESSION_KEY_DEM_ANALYSIS,
    SESSION_KEY_FLOW_ACCUMULATION,
    SESSION_KEY_FLOW_DIRECTION,
    SESSION_KEY_SLOPE_ASPECT,
    SESSION_KEY_UPLOAD_NAME,
    SESSION_KEY_USED_CONDITIONED,
)


def render_reports_page() -> None:
    """Render the Engineering Reports page."""

    st.caption("ENGINEERING OUTPUT")
    st.title("Engineering Reports")
    st.write(
        "Generate a PDF summary of the terrain and hydrology analysis "
        "completed on the Results page - elevation, slope, flow "
        "direction/accumulation, streams, watershed, and flood "
        "susceptibility, where available."
    )
    st.divider()

    dem_analysis = st.session_state.get(SESSION_KEY_DEM_ANALYSIS)
    slope_aspect_result = st.session_state.get(SESSION_KEY_SLOPE_ASPECT)
    flow_direction_result = st.session_state.get(SESSION_KEY_FLOW_DIRECTION)
    flow_accumulation_result = st.session_state.get(SESSION_KEY_FLOW_ACCUMULATION)

    if dem_analysis is None or slope_aspect_result is None or flow_direction_result is None or flow_accumulation_result is None:
        st.info(
            "No engineering report can be generated yet. Go to the "
            "Workspace page, upload a DEM/DTM, and run the analysis "
            "first — then visit Results before returning here."
        )
        return

    stream_result = st.session_state.get(SESSION_KEY_STREAM_RESULT)
    susceptibility_result = st.session_state.get(SESSION_KEY_SUSCEPTIBILITY_RESULT)
    catchment_result = st.session_state.get(SESSION_KEY_CATCHMENT_RESULT)
    catchment_pour_point = st.session_state.get(SESSION_KEY_CATCHMENT_POUR_POINT)
    report_images = st.session_state.get(SESSION_KEY_REPORT_IMAGES, {})

    missing_optional = []
    if stream_result is None:
        missing_optional.append("stream network")
    if susceptibility_result is None:
        missing_optional.append("flood susceptibility")
    if catchment_result is None:
        missing_optional.append("watershed/catchment")

    if missing_optional:
        st.warning(
            "Visit the Results page first so these sections are computed "
            "and included in the report: " + ", ".join(missing_optional) + "."
        )

    project_name = st.session_state.get(LEGACY_KEY_PROJECT_NAME, "Unnamed Project")
    study_area = st.session_state.get(LEGACY_KEY_STUDY_AREA, "Not specified")
    dem_file_name = st.session_state.get(SESSION_KEY_UPLOAD_NAME, "Unknown")
    used_conditioned = st.session_state.get(SESSION_KEY_USED_CONDITIONED, False)

    if st.button("Generate PDF Report", type="primary"):
        inputs = ReportInputs(
            project_name=project_name,
            study_area=study_area,
            dem_file_name=dem_file_name,
            used_conditioned=used_conditioned,
            dem_analysis=dem_analysis,
            slope_aspect_result=slope_aspect_result,
            flow_direction_result=flow_direction_result,
            flow_accumulation_result=flow_accumulation_result,
            stream_result=stream_result,
            susceptibility_result=susceptibility_result,
            catchment_result=catchment_result,
            catchment_pour_point=catchment_pour_point,
            images=report_images,
        )
        try:
            pdf_bytes = build_pdf_report(inputs)
        except Exception as exc:  # noqa: BLE001
            st.error(f"Report generation failed: {exc}")
        else:
            st.success("Report generated.")
            st.download_button(
                "Download PDF Report",
                data=pdf_bytes,
                file_name=f"{project_name.replace(' ', '_')}_geodrainai_report.pdf",
                mime="application/pdf",
            )