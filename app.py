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
