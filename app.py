import streamlit as st
import pandas as pd
import requests
from datetime import datetime
import bcrypt
import json
import os
from fantasy_models import render_fantasy_tab

st.set_page_config(
    page_title="FADE MACHINE | NFL Analytics",
    page_icon="🎯",
    layout="wide",
    initial_sidebar_state="expanded"
)

st.markdown("""
<style>
    .stApp, [data-testid="stAppViewContainer"] {
        background-color: #0d0d0d !important;
        color: #ffffff !important;
    }
    body, p, span, div, label, .stMarkdown, .stText,
    [data-testid="stMarkdownContainer"],
    [data-testid="stWidgetLabel"] {
        color: #ffffff !important;
    }
    h1, h2, h3, h4, h5, h6 { color: #ffffff !important; }
    [data-testid="stSidebar"] { background-color: #1a1a1a !important; }
    [data-testid="stSidebar"] * { color: #ffffff !important; }
    .stTabs [data-baseweb="tab-list"] { background-color: #1a1a1a; gap: 4px; flex-wrap: wrap; }
    .stTabs [data-baseweb="tab"] { color: #cccccc !important; padding: 10px 12px !important; font-size: 0.85rem !important; }
    .stTabs [aria-selected="true"] { color: #e10600 !important; border-bottom: 2px solid #e10600; }
    .stButton > button {
        background-color: #e10600 !important; color: #ffffff !important; border: none;
        min-height: 44px !important; padding: 0.6rem 1.2rem !important; font-size: 1rem !important; border-radius: 8px !important;
    }
    .stCaptionContainer { color: #aaaaaa !important; }
    div[data-testid="stExpander"] {
        border: 1.5px solid #e10600 !important; border-radius: 10px !important;
        background-color: rgba(225, 6, 0, 0.12) !important; margin-top: 8px; margin-bottom: 16px;
    }
    div[data-testid="stExpander"] summary,
    div[data-testid="stExpander"] summary span,
    div[data-testid="stExpander"] summary p { color: #ff4d4d !important; font-weight: 600 !important; font-size: 0.95rem !important; }
    div[data-testid="stExpander"] svg { fill: #e10600 !important; }
    @media (max-width: 768px) {
        .stTabs [data-baseweb="tab"] { font-size: 0.75rem !important; padding: 8px 6px !important; }
        h1 { font-size: 1.6rem !important; }
        h2 { font-size: 1.3rem !important; }
        h3 { font-size: 1.1rem !important; }
    }
    [data-testid="stMetricValue"] { color: #ffffff !important; font-size: 1.4rem !important; }
    [data-testid="stMetricLabel"] { color: #cccccc !important; }
    .steel-balance-bar {
        border: 2px solid #e10600; border-radius: 10px; background-color: rgba(225, 6, 0, 0.18);
        padding: 10px 18px; display: inline-block; text-align: right; min-width: 140px;
    }
    .steel-balance-bar .steel-label { font-size: 0.7rem; color: #ffffff !important; font-weight: 600; letter-spacing: 0.5px; text-transform: uppercase; }
    .steel-balance-bar .steel-amount { font-size: 1.25rem; color: #ffffff !important; font-weight: 700; line-height: 1.3; }

    /* High-contrast dropdowns */
    div[data-baseweb="select"] > div,
    div[data-baseweb="select"] > div > div {
        background-color: #1f1f1f !important;
        border: 1.5px solid #e10600 !important;
        border-radius: 8px !important;
        color: #ffffff !important;
        min-height: 42px !important;
    }
    div[data-baseweb="select"] span {
        color: #ffffff !important;
    }
    ul[role="listbox"],
    div[data-baseweb="popover"] div[data-baseweb="menu"] {
        background-color: #1a1a1a !important;
        border: 1.5px solid #e10600 !important;
    }
    li[role="option"] {
        color: #ffffff !important;
        background-color: #1a1a1a !important;
    }
    li[role="option"]:hover,
    li[aria-selected="true"] {
        background-color: #e10600 !important;
        color: #ffffff !important;
    }
    span[data-baseweb="tag"] {
        background-color: #e10600 !important;
        color: #ffffff !important;
    }
</style>
""", unsafe_allow_html=True)

st.title("🎯 FADE MACHINE")
st.success("App is restoring. Full update with prop Steel bets, removed HOF tab, and HOF data in Results/Trends is ready in the next deploy.")
st.info("If you see this message, the previous broken partial file was replaced. Refresh in ~30s after the full commit lands.")
