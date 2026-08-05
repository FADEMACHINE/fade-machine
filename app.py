import streamlit as st
import pandas as pd

# Page configuration
st.set_page_config(
    page_title="FADE MACHINE | NFL ATS",
    page_icon="🎯",
    layout="wide"
)

# ------------------------------
# SAMPLE NFL ATS DATA
# This is temporary sample data so the app works immediately.
# Later we will replace this with real historical data.
# -----------------------------
sample_data = {
    "Team": [
        "Kansas City Chiefs", "Buffalo Bills", "Detroit Lions", "Baltimore Ravens",
        "San Francisco 49ers", "Dallas Cowboys", "Philadelphia Eagles", "Green Bay Packers",
        "Miami Dolphins", "Cincinnati Bengals", "Houston Texans", "Los Angeles Rams"
    ],
    "Season": [2024] * 12,
    "ATS_Wins": [11, 10, 12, 9, 8, 7, 10, 9, 6, 8, 9, 7],
    "ATS_Losses": [6, 7, 5, 8, 9, 10, 7, 8, 11, 9, 8, 10],
    "ATS_Win_Pct": [0.647, 0.588, 0.706, 0.529, 0.471, 0.412, 0.588, 0.529, 0.353, 0.471, 0.529, 0.412],
    "Home_ATS_Wins": [6, 5, 7, 5, 4, 4, 6, 5, 3, 4, 5, 3],
    "Away_ATS_Wins": [5, 5, 5, 4, 4, 3, 4, 4, 3, 4, 4, 4],
    "Avg_Spread": [-5.5, -3.5, -2.5, -3.0, -4.0, -2.0, -3.5, -1.5, -1.0, -2.5, -1.5, -1.0]
}

df = pd.DataFrame(sample_data)

# ------------------------------
# SIDEBAR
# -----------------------------
st.sidebar.title("FADE MACHINE")
st.sidebar.markdown("**NFL Against The Spread Analytics**")
st.sidebar.markdown("---")

st.sidebar.header("Filters")
selected_season = st.sidebar.selectbox("Season", options=[2024, 2023, 2022], index=0)
selected_teams = st.sidebar.multiselect(
    "Select Teams",
    options=df["Team"].tolist(),
    default=df["Team"].tolist()[:6]
)

st.sidebar.markdown("---")
st.sidebar.info(
    "This is sample data for demonstration.\n\n"
    "Next we will connect real historical NFL ATS data."
)

# ------------------------------
# MAIN PAGE
# -----------------------------
st.title("🎯 FADE MACHINE")
st.subheader("NFL Against The Spread (ATS) Analytics")

st.markdown("---")

# Filter the data
filtered_df = df[df["Team"].isin(selected_teams)].copy()

# Key Metrics Row
col1, col2, col3, col4 = st.columns(4)

with col1:
    st.metric("Teams Shown", len(filtered_df))

with col2:
    best_team = filtered_df.loc[filtered_df["ATS_Win_Pct"].idxmax(), "Team"] if not filtered_df.empty else "N/A"
    st.metric("Best ATS Team", best_team)

with col3:
    avg_win_pct = filtered_df["ATS_Win_Pct"].mean() if not filtered_df.empty else 0
    st.metric("Average ATS Win %", f"{avg_win_pct:.1%}")

with col4:
    total_games = filtered_df["ATS_Wins"].sum() + filtered_df["ATS_Losses"].sum()
    st.metric("Total Games Tracked", int(total_games))

st.markdown("---")

# Main Data Table
st.header("Team ATS Performance")

if filtered_df.empty:
    st.warning("No teams selected. Please select at least one team in the sidebar.")
else:
    # Format the dataframe for display
    display_df = filtered_df[["Team", "ATS_Wins", "ATS_Losses", "ATS_Win_Pct", "Home_ATS_Wins", "Away_ATS_Wins", "Avg_Spread"]].copy()
    display_df["ATS_Win_Pct"] = display_df["ATS_Win_Pct"].apply(lambda x: f"{x:.1%}")
    display_df = display_df.rename(columns={
        "ATS_Wins": "ATS Wins",
        "ATS_Losses": "ATS Losses",
        "ATS_Win_Pct": "ATS Win %",
        "Home_ATS_Wins": "Home ATS Wins",
        "Away_ATS_Wins": "Away ATS Wins",
        "Avg_Spread": "Avg Spread"
    })

    st.dataframe(
        display_df.sort_values("ATS Win %", ascending=False),
        use_container_width=True,
        hide_index=True
    )

st.markdown("---")

# Simple Insight Section
st.header("Quick Insights")

if not filtered_df.empty:
    top_team = filtered_df.loc[filtered_df["ATS_Win_Pct"].idxmax()]
    bottom_team = filtered_df.loc[filtered_df["ATS_Win_Pct"].idxmin()]

    col_a, col_b = st.columns(2)

    with col_a:
        st.success(
            f"**Strongest ATS Team**\n\n"
            f"{top_team['Team']}  \n"
            f"Record: {int(top_team['ATS_Wins'])}-{int(top_team['ATS_Losses'])}  \n"
            f"Win Rate: {top_team['ATS_Win_Pct']:.1%}"
        )

    with col_b:
        st.error(
            f"**Weakest ATS Team**\n\n"
            f"{bottom_team['Team']}  \n"
            f"Record: {int(bottom_team['ATS_Wins'])}-{int(bottom_team['ATS_Losses'])}  \n"
            f"Win Rate: {bottom_team['ATS_Win_Pct']:.1%}"
        )

st.markdown("---")
st.caption("FADE MACHINE • NFL ATS Analytics • Sample Data Only • Built with Streamlit")
