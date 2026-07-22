import streamlit as st


def render_sidebar():

    with st.sidebar:

        # =========================
        # BRAND
        # =========================

        st.title("GeoDrainAI")

        st.caption(
            "Geospatial Intelligence Platform"
        )

        st.divider()

        # =========================
        # NAVIGATION
        # =========================

        st.caption("WORKSPACE")

        selected_page = st.radio(
            "Navigation",
            [
                "Overview",
                "Project Workspace",
                "Analysis Results",
                "Engineering Reports"
            ],
            label_visibility="collapsed"
        )

        st.divider()

        # =========================
        # SYSTEM STATUS
        # =========================

        st.caption("SYSTEM STATUS")

        st.success("Prototype Active")

        return selected_page