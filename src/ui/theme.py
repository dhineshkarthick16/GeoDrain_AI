import streamlit as st


def apply_theme():
    st.markdown(
        """
        <style>

        /* =========================
           GLOBAL
        ========================= */

        .stApp {
            background-color: #0B1120;
            color: #E5E7EB;
        }

        .block-container {
            padding-top: 2rem;
            padding-left: 3rem;
            padding-right: 3rem;
            max-width: 1600px;
        }

        /* =========================
           SIDEBAR
        ========================= */

        section[data-testid="stSidebar"] {
            background-color: #0F172A;
            border-right: 1px solid #1E293B;
        }

        /* =========================
           TEXT
        ========================= */

        h1, h2, h3 {
            color: #F8FAFC !important;
        }

        p {
            color: #94A3B8;
        }

        /* =========================
           METRIC CARDS
        ========================= */

        div[data-testid="stMetric"] {
            background-color: #111827;
            border: 1px solid #1E293B;
            border-radius: 12px;
            padding: 1.2rem;
        }

        div[data-testid="stMetricLabel"] {
            color: #94A3B8;
        }

        div[data-testid="stMetricValue"] {
            color: #F8FAFC;
        }

        /* =========================
           BUTTONS
        ========================= */

        .stButton > button {
            width: 100%;
            border-radius: 8px;
            border: 1px solid #334155;
            background-color: #1E293B;
            color: #F8FAFC;
            font-weight: 600;
            padding: 0.65rem 1rem;
        }

        .stButton > button:hover {
            border-color: #38BDF8;
            color: #38BDF8;
        }

        /* =========================
           INFO BOX
        ========================= */

        div[data-testid="stAlert"] {
            border-radius: 10px;
        }

        /* =========================
           HIDE STREAMLIT BRANDING
        ========================= */

        #MainMenu {
            visibility: hidden;
        }

        footer {
            visibility: hidden;
        }

        </style>
        """,
        unsafe_allow_html=True
    )