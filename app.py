import streamlit as st

# Page configuration
st.set_page_config(
    page_title="FADE MACHINE",
    page_icon="🎯",
    layout="wide"
)

# Title
st.title("FADE MACHINE")
st.subheader("Sports Analytics Powered by Historical Data & Trends")

st.markdown("---")

# Sidebar
st.sidebar.header("Navigation")
st.sidebar.info("This is the very first version of FADE MACHINE. We are building it step by step with AI help.")

# Main content
st.header("Welcome")
st.write("""
This is the starting point of **FADE MACHINE** — a pure analytical tool for sports betting trends.

**Current focus:**
- Historical data for moneylines, spreads, totals, and player props
- Starting small with one sport and one market type
- Using AI to help build everything

More features will be added soon.
""")

st.info("Next step: We will add sample historical data and simple trend views.")

# Footer
st.markdown("---")
st.caption("FADE MACHINE • Built with Streamlit • Analytical tool only")
