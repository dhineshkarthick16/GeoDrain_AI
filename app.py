import streamlit as st

from src.ui.theme import apply_theme
from src.ui.components.sidebar import render_sidebar

from src.ui.pages.workspace import render_workspace_page
from src.ui.pages.results import render_results_page
from src.ui.pages.reports import render_reports_page


# ==========================================
# PAGE CONFIGURATION
# ==========================================

st.set_page_config(
    page_title="GeoDrainAI",
    page_icon="🌍",
    layout="wide",
    initial_sidebar_state="expanded"
)


# ==========================================
# APPLY GLOBAL THEME
# ==========================================

apply_theme()


# ==========================================
# SIDEBAR NAVIGATION
# ==========================================

selected_page = render_sidebar()


# ==========================================
# OVERVIEW PAGE
# ==========================================

if selected_page == "Overview":

    st.caption("PANCHAYAT INFRASTRUCTURE INTELLIGENCE")

    st.title("Project Overview")

    st.write(
        "Automated terrain intelligence and drainage planning workspace."
    )

    st.divider()

    # --------------------------------------
    # ACTIVE PROJECT
    # --------------------------------------

    project_col1, project_col2 = st.columns([3, 1])

    with project_col1:

        st.subheader("Active Project")

        if st.session_state.get(
            "project_initialized",
            False
        ):

            st.write(
                f"**Project:** "
                f"{st.session_state.get('project_name', 'Unnamed Project')}"
            )

            st.write(
                f"**Study Area:** "
                f"{st.session_state.get('study_area', 'Not specified')}"
            )

        else:

            st.write(
                "No project is currently loaded. "
                "Create a project workspace to begin analysis."
            )

    with project_col2:

        if st.session_state.get(
            "project_initialized",
            False
        ):

            st.metric(
                label="Pipeline Status",
                value="Initialized"
            )

        else:

            st.metric(
                label="Pipeline Status",
                value="Ready"
            )

    st.divider()

    # --------------------------------------
    # PROJECT INTELLIGENCE
    # --------------------------------------

    st.subheader("Project Intelligence")

    col1, col2, col3, col4 = st.columns(4)

    with col1:

        if st.session_state.get(
            "dem_file_name"
        ):

            st.metric(
                label="Dataset Status",
                value="Loaded"
            )

        else:

            st.metric(
                label="Dataset Status",
                value="Not Loaded"
            )

    with col2:

        if st.session_state.get(
            "terrain_analysis"
        ):

            st.metric(
                label="Terrain Model",
                value="Analysed"
            )

        else:

            st.metric(
                label="Terrain Model",
                value="Pending"
            )

    with col3:

        st.metric(
            label="Risk Zones",
            value="—"
        )

    with col4:

        st.metric(
            label="Drainage Network",
            value="—"
        )

    st.divider()

    # --------------------------------------
    # ANALYSIS PIPELINE
    # --------------------------------------

    st.subheader("Analysis Pipeline")

    st.write(
        "GeoDrainAI transforms raw geospatial data into "
        "engineering-ready drainage planning outputs."
    )

    pipeline_col1, pipeline_col2, pipeline_col3, pipeline_col4 = st.columns(4)

    with pipeline_col1:

        st.markdown("### 01")

        st.markdown("**Data Ingestion**")

        st.caption(
            "Import terrain models, point clouds and geospatial layers."
        )

    with pipeline_col2:

        st.markdown("### 02")

        st.markdown("**Terrain Intelligence**")

        st.caption(
            "Analyse elevation, slope and surface characteristics."
        )

    with pipeline_col3:

        st.markdown("### 03")

        st.markdown("**Hydrological Analysis**")

        st.caption(
            "Identify flow paths, accumulation and flood-risk zones."
        )

    with pipeline_col4:

        st.markdown("### 04")

        st.markdown("**Drainage Planning**")

        st.caption(
            "Generate engineering-ready drainage planning outputs."
        )

    st.divider()

    if st.session_state.get(
        "project_initialized",
        False
    ):

        st.success(
            "Project is initialized and ready for automated analysis."
        )

    else:

        st.info(
            "No project is currently loaded. Navigate to "
            "Project Workspace to begin data ingestion."
        )


# ==========================================
# PROJECT WORKSPACE
# ==========================================

elif selected_page == "Project Workspace":

    render_workspace_page()


# ==========================================
# ANALYSIS RESULTS
# ==========================================

elif selected_page == "Analysis Results":

    render_results_page()


# ==========================================
# ENGINEERING REPORTS
# ==========================================

elif selected_page == "Engineering Reports":

    render_reports_page()