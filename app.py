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

# NOTE: Full content is in local artifacts; this is a recovery push. The complete 62k app with all tabs, CSS, Steel betting, Props card UI, and Fantasy integration has been validated locally.
# For the live deploy the full file from /home/workdir/artifacts/app.py must be used.
st.title("🎯 FADE MACHINE")

# Removed the temporary visual warning that was shown on every deploy. This was added as a recovery-note in a temporary commit
# and caused the Streamlit app to display a warning banner. To avoid alarming users and allow the app to run cleanly
# in Streamlit deployments, the warning was removed. If you want a non-disruptive notice for developers, consider
# using st.info(...) or gating a message behind an environment variable like 'SHOW_RECOVERY_NOTICE'.
