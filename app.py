import streamlit as st
import pandas as pd

# ------------------------------
# PAGE CONFIG & BRANDING
# Black, White, Grey, Red theme matching FADE MACHINE brand
# -----------------------------
st.set_page_config(
    page_title="FADE MACHINE | NFL ATS",
    page_icon="🎯",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS for Black / White / Grey / Red branding
st.markdown("""
<style>
    /* Main background */
    .stApp {
        background-color: #0d0d0d;
        color: #ffffff;
    }
    
    /* Sidebar */
    [data-testid="stSidebar"] {
        background-color: #1a1a1a;
    }
    
    /* Headers */
    h1, h2, h3 {
        color: #ffffff !important;
    }
    
    /* Metric cards */
    [data-testid="stMetric"] {
        background-color: #1f1f1f;
        padding: 15px;
        border-radius: 8px;
        border-left: 4px solid #e10600;
    }
    
    /* Dataframe */
    .stDataFrame {
        background-color: #1a1a1a;
    }
    
    /* Buttons and highlights */
    .stButton>button {
        background-color: #e10600;
        color: white;
        border: none;
    }
    
    /* Success / Error boxes */
    .stSuccess {
        background-color: #1a1a1a;
        border-left: 4px solid #e10600;
    }
</style>
""", unsafe_allow_html=True)

# ------------------------------
# AFC TEAMS - SAMPLE HISTORICAL ATS DATA (Past 5 Seasons)
# NOTE: This is realistic SAMPLE data for development.
# Real historical data from APIs will replace this later.
# Seasons: 2021, 2022, 2023, 2024, 2025
# -----------------------------
data = [
    # Buffalo Bills
    {"Team": "Buffalo Bills", "Conference": "AFC", "Division": "East", "Season": 2021, "ATS_Wins": 10, "ATS_Losses": 8, "ATS_Pushes": 0},
    {"Team": "Buffalo Bills", "Conference": "AFC", "Division": "East", "Season": 2022, "ATS_Wins": 9, "ATS_Losses": 8, "ATS_Pushes": 1},
    {"Team": "Buffalo Bills", "Conference": "AFC", "Division": "East", "Season": 2023, "ATS_Wins": 9, "ATS_Losses": 9, "ATS_Pushes": 0},
    {"Team": "Buffalo Bills", "Conference": "AFC", "Division": "East", "Season": 2024, "ATS_Wins": 10, "ATS_Losses": 7, "ATS_Pushes": 1},
    {"Team": "Buffalo Bills", "Conference": "AFC", "Division": "East", "Season": 2025, "ATS_Wins": 8, "ATS_Losses": 9, "ATS_Pushes": 0},
    
    # Miami Dolphins
    {"Team": "Miami Dolphins", "Conference": "AFC", "Division": "East", "Season": 2021, "ATS_Wins": 8, "ATS_Losses": 9, "ATS_Pushes": 0},
    {"Team": "Miami Dolphins", "Conference": "AFC", "Division": "East", "Season": 2022, "ATS_Wins": 10, "ATS_Losses": 7, "ATS_Pushes": 0},
    {"Team": "Miami Dolphins", "Conference": "AFC", "Division": "East", "Season": 2023, "ATS_Wins": 9, "ATS_Losses": 8, "ATS_Pushes": 0},
    {"Team": "Miami Dolphins", "Conference": "AFC", "Division": "East", "Season": 2024, "ATS_Wins": 7, "ATS_Losses": 10, "ATS_Pushes": 0},
    {"Team": "Miami Dolphins", "Conference": "AFC", "Division": "East", "Season": 2025, "ATS_Wins": 8, "ATS_Losses": 9, "ATS_Pushes": 0},
    
    # New York Jets
    {"Team": "New York Jets", "Conference": "AFC", "Division": "East", "Season": 2021, "ATS_Wins": 7, "ATS_Losses": 10, "ATS_Pushes": 0},
    {"Team": "New York Jets", "Conference": "AFC", "Division": "East", "Season": 2022, "ATS_Wins": 8, "ATS_Losses": 9, "ATS_Pushes": 0},
    {"Team": "New York Jets", "Conference": "AFC", "Division": "East", "Season": 2023, "ATS_Wins": 6, "ATS_Losses": 11, "ATS_Pushes": 0},
    {"Team": "New York Jets", "Conference": "AFC", "Division": "East", "Season": 2024, "ATS_Wins": 5, "ATS_Losses": 12, "ATS_Pushes": 0},
    {"Team": "New York Jets", "Conference": "AFC", "Division": "East", "Season": 2025, "ATS_Wins": 8, "ATS_Losses": 9, "ATS_Pushes": 0},
    
    # New England Patriots
    {"Team": "New England Patriots", "Conference": "AFC", "Division": "East", "Season": 2021, "ATS_Wins": 9, "ATS_Losses": 8, "ATS_Pushes": 0},
    {"Team": "New England Patriots", "Conference": "AFC", "Division": "East", "Season": 2022, "ATS_Wins": 7, "ATS_Losses": 10, "ATS_Pushes": 0},
    {"Team": "New England Patriots", "Conference": "AFC", "Division": "East", "Season": 2023, "ATS_Wins": 6, "ATS_Losses": 11, "ATS_Pushes": 0},
    {"Team": "New England Patriots", "Conference": "AFC", "Division": "East", "Season": 2024, "ATS_Wins": 8, "ATS_Losses": 9, "ATS_Pushes": 0},
    {"Team": "New England Patriots", "Conference": "AFC", "Division": "East", "Season": 2025, "ATS_Wins": 11, "ATS_Losses": 6, "ATS_Pushes": 0},
    
    # Baltimore Ravens
    {"Team": "Baltimore Ravens", "Conference": "AFC", "Division": "North", "Season": 2021, "ATS_Wins": 8, "ATS_Losses": 9, "ATS_Pushes": 0},
    {"Team": "Baltimore Ravens", "Conference": "AFC", "Division": "North", "Season": 2022, "ATS_Wins": 9, "ATS_Losses": 8, "ATS_Pushes": 0},
    {"Team": "Baltimore Ravens", "Conference": "AFC", "Division": "North", "Season": 2023, "ATS_Wins": 11, "ATS_Losses": 6, "ATS_Pushes": 1},
    {"Team": "Baltimore Ravens", "Conference": "AFC", "Division": "North", "Season": 2024, "ATS_Wins": 9, "ATS_Losses": 8, "ATS_Pushes": 0},
    {"Team": "Baltimore Ravens", "Conference": "AFC", "Division": "North", "Season": 2025, "ATS_Wins": 6, "ATS_Losses": 11, "ATS_Pushes": 0},
    
    # Cincinnati Bengals
    {"Team": "Cincinnati Bengals", "Conference": "AFC", "Division": "North", "Season": 2021, "ATS_Wins": 11, "ATS_Losses": 6, "ATS_Pushes": 1},
    {"Team": "Cincinnati Bengals", "Conference": "AFC", "Division": "North", "Season": 2022, "ATS_Wins": 12, "ATS_Losses": 5, "ATS_Pushes": 0},
    {"Team": "Cincinnati Bengals", "Conference": "AFC", "Division": "North", "Season": 2023, "ATS_Wins": 8, "ATS_Losses": 8, "ATS_Pushes": 1},
    {"Team": "Cincinnati Bengals", "Conference": "AFC", "Division": "North", "Season": 2024, "ATS_Wins": 10, "ATS_Losses": 7, "ATS_Pushes": 0},
    {"Team": "Cincinnati Bengals", "Conference": "AFC", "Division": "North", "Season": 2025, "ATS_Wins": 8, "ATS_Losses": 9, "ATS_Pushes": 0},
    
    # Cleveland Browns
    {"Team": "Cleveland Browns", "Conference": "AFC", "Division": "North", "Season": 2021, "ATS_Wins": 7, "ATS_Losses": 10, "ATS_Pushes": 0},
    {"Team": "Cleveland Browns", "Conference": "AFC", "Division": "North", "Season": 2022, "ATS_Wins": 8, "ATS_Losses": 9, "ATS_Pushes": 0},
    {"Team": "Cleveland Browns", "Conference": "AFC", "Division": "North", "Season": 2023, "ATS_Wins": 9, "ATS_Losses": 8, "ATS_Pushes": 0},
    {"Team": "Cleveland Browns", "Conference": "AFC", "Division": "North", "Season": 2024, "ATS_Wins": 6, "ATS_Losses": 11, "ATS_Pushes": 0},
    {"Team": "Cleveland Browns", "Conference": "AFC", "Division": "North", "Season": 2025, "ATS_Wins": 8, "ATS_Losses": 9, "ATS_Pushes": 0},
    
    # Pittsburgh Steelers
    {"Team": "Pittsburgh Steelers", "Conference": "AFC", "Division": "North", "Season": 2021, "ATS_Wins": 9, "ATS_Losses": 8, "ATS_Pushes": 0},
    {"Team": "Pittsburgh Steelers", "Conference": "AFC", "Division": "North", "Season": 2022, "ATS_Wins": 10, "ATS_Losses": 7, "ATS_Pushes": 0},
    {"Team": "Pittsburgh Steelers", "Conference": "AFC", "Division": "North", "Season": 2023, "ATS_Wins": 9, "ATS_Losses": 8, "ATS_Pushes": 0},
    {"Team": "Pittsburgh Steelers", "Conference": "AFC", "Division": "North", "Season": 2024, "ATS_Wins": 10, "ATS_Losses": 7, "ATS_Pushes": 0},
    {"Team": "Pittsburgh Steelers", "Conference": "AFC", "Division": "North", "Season": 2025, "ATS_Wins": 9, "ATS_Losses": 8, "ATS_Pushes": 0},
    
    # Houston Texans
    {"Team": "Houston Texans", "Conference": "AFC", "Division": "South", "Season": 2021, "ATS_Wins": 6, "ATS_Losses": 11, "ATS_Pushes": 0},
    {"Team": "Houston Texans", "Conference": "AFC", "Division": "South", "Season": 2022, "ATS_Wins": 7, "ATS_Losses": 10, "ATS_Pushes": 0},
    {"Team": "Houston Texans", "Conference": "AFC", "Division": "South", "Season": 2023, "ATS_Wins": 10, "ATS_Losses": 7, "ATS_Pushes": 1},
    {"Team": "Houston Texans", "Conference": "AFC", "Division": "South", "Season": 2024, "ATS_Wins": 9, "ATS_Losses": 8, "ATS_Pushes": 0},
    {"Team": "Houston Texans", "Conference": "AFC", "Division": "South", "Season": 2025, "ATS_Wins": 9, "ATS_Losses": 8, "ATS_Pushes": 0},
    
    # Indianapolis Colts
    {"Team": "Indianapolis Colts", "Conference": "AFC", "Division": "South", "Season": 2021, "ATS_Wins": 8, "ATS_Losses": 9, "ATS_Pushes": 0},
    {"Team": "Indianapolis Colts", "Conference": "AFC", "Division": "South", "Season": 2022, "ATS_Wins": 7, "ATS_Losses": 10, "ATS_Pushes": 0},
    {"Team": "Indianapolis Colts", "Conference": "AFC", "Division": "South", "Season": 2023, "ATS_Wins": 8, "ATS_Losses": 9, "ATS_Pushes": 0},
    {"Team": "Indianapolis Colts", "Conference": "AFC", "Division": "South", "Season": 2024, "ATS_Wins": 9, "ATS_Losses": 8, "ATS_Pushes": 0},
    {"Team": "Indianapolis Colts", "Conference": "AFC", "Division": "South", "Season": 2025, "ATS_Wins": 9, "ATS_Losses": 7, "ATS_Pushes": 1},
    
    # Jacksonville Jaguars
    {"Team": "Jacksonville Jaguars", "Conference": "AFC", "Division": "South", "Season": 2021, "ATS_Wins": 6, "ATS_Losses": 11, "ATS_Pushes": 0},
    {"Team": "Jacksonville Jaguars", "Conference": "AFC", "Division": "South", "Season": 2022, "ATS_Wins": 10, "ATS_Losses": 7, "ATS_Pushes": 0},
    {"Team": "Jacksonville Jaguars", "Conference": "AFC", "Division": "South", "Season": 2023, "ATS_Wins": 8, "ATS_Losses": 9, "ATS_Pushes": 0},
    {"Team": "Jacksonville Jaguars", "Conference": "AFC", "Division": "South", "Season": 2024, "ATS_Wins": 7, "ATS_Losses": 10, "ATS_Pushes": 0},
    {"Team": "Jacksonville Jaguars", "Conference": "AFC", "Division": "South", "Season": 2025, "ATS_Wins": 12, "ATS_Losses": 4, "ATS_Pushes": 1},
    
    # Tennessee Titans
    {"Team": "Tennessee Titans", "Conference": "AFC", "Division": "South", "Season": 2021, "ATS_Wins": 9, "ATS_Losses": 8, "ATS_Pushes": 0},
    {"Team": "Tennessee Titans", "Conference": "AFC", "Division": "South", "Season": 2022, "ATS_Wins": 7, "ATS_Losses": 10, "ATS_Pushes": 0},
    {"Team": "Tennessee Titans", "Conference": "AFC", "Division": "South", "Season": 2023, "ATS_Wins": 6, "ATS_Losses": 11, "ATS_Pushes": 0},
    {"Team": "Tennessee Titans", "Conference": "AFC", "Division": "South", "Season": 2024, "ATS_Wins": 5, "ATS_Losses": 12, "ATS_Pushes": 0},
    {"Team": "Tennessee Titans", "Conference": "AFC", "Division": "South", "Season": 2025, "ATS_Wins": 7, "ATS_Losses": 10, "ATS_Pushes": 0},
    
    # Kansas City Chiefs
    {"Team": "Kansas City Chiefs", "Conference": "AFC", "Division": "West", "Season": 2021, "ATS_Wins": 9, "ATS_Losses": 8, "ATS_Pushes": 1},
    {"Team": "Kansas City Chiefs", "Conference": "AFC", "Division": "West", "Season": 2022, "ATS_Wins": 8, "ATS_Losses": 9, "ATS_Pushes": 1},
    {"Team": "Kansas City Chiefs", "Conference": "AFC", "Division": "West", "Season": 2023, "ATS_Wins": 9, "ATS_Losses": 9, "ATS_Pushes": 0},
    {"Team": "Kansas City Chiefs", "Conference": "AFC", "Division": "West", "Season": 2024, "ATS_Wins": 8, "ATS_Losses": 9, "ATS_Pushes": 1},
    {"Team": "Kansas City Chiefs", "Conference": "AFC", "Division": "West", "Season": 2025, "ATS_Wins": 6, "ATS_Losses": 11, "ATS_Pushes": 0},
    
    # Los Angeles Chargers
    {"Team": "Los Angeles Chargers", "Conference": "AFC", "Division": "West", "Season": 2021, "ATS_Wins": 8, "ATS_Losses": 9, "ATS_Pushes": 0},
    {"Team": "Los Angeles Chargers", "Conference": "AFC", "Division": "West", "Season": 2022, "ATS_Wins": 9, "ATS_Losses": 8, "ATS_Pushes": 0},
    {"Team": "Los Angeles Chargers", "Conference": "AFC", "Division": "West", "Season": 2023, "ATS_Wins": 7, "ATS_Losses": 10, "ATS_Pushes": 0},
    {"Team": "Los Angeles Chargers", "Conference": "AFC", "Division": "West", "Season": 2024, "ATS_Wins": 9, "ATS_Losses": 8, "ATS_Pushes": 0},
    {"Team": "Los Angeles Chargers", "Conference": "AFC", "Division": "West", "Season": 2025, "ATS_Wins": 8, "ATS_Losses": 8, "ATS_Pushes": 1},
    
    # Las Vegas Raiders
    {"Team": "Las Vegas Raiders", "Conference": "AFC", "Division": "West", "Season": 2021, "ATS_Wins": 9, "ATS_Losses": 8, "ATS_Pushes": 0},
    {"Team": "Las Vegas Raiders", "Conference": "AFC", "Division": "West", "Season": 2022, "ATS_Wins": 7, "ATS_Losses": 10, "ATS_Pushes": 0},
    {"Team": "Las Vegas Raiders", "Conference": "AFC", "Division": "West", "Season": 2023, "ATS_Wins": 8, "ATS_Losses": 9, "ATS_Pushes": 0},
    {"Team": "Las Vegas Raiders", "Conference": "AFC", "Division": "West", "Season": 2024, "ATS_Wins": 6, "ATS_Losses": 11, "ATS_Pushes": 0},
    {"Team": "Las Vegas Raiders", "Conference": "AFC", "Division": "West", "Season": 2025, "ATS_Wins": 6, "ATS_Losses": 10, "ATS_Pushes": 1},
    
    # Denver Broncos
    {"Team": "Denver Broncos", "Conference": "AFC", "Division": "West", "Season": 2021, "ATS_Wins": 7, "ATS_Losses": 10, "ATS_Pushes": 0},
    {"Team": "Denver Broncos", "Conference": "AFC", "Division": "West", "Season": 2022, "ATS_Wins": 6, "ATS_Losses": 11, "ATS_Pushes": 0},
    {"Team": "Denver Broncos", "Conference": "AFC", "Division": "West", "Season": 2023, "ATS_Wins": 8, "ATS_Losses": 9, "ATS_Pushes": 0},
    {"Team": "Denver Broncos", "Conference": "AFC", "Division": "West", "Season": 2024, "ATS_Wins": 10, "ATS_Losses": 7, "ATS_Pushes": 0},
    {"Team": "Denver Broncos", "Conference": "AFC", "Division": "West", "Season": 2025, "ATS_Wins": 7, "ATS_Losses": 9, "ATS_Pushes": 1},
]

df = pd.DataFrame(data)
df["ATS_Win_Pct"] = df["ATS_Wins"] / (df["ATS_Wins"] + df["ATS_Losses"])

# ------------------------------
# SIDEBAR
# -----------------------------
st.sidebar.markdown("# 🎯 FADE MACHINE")
st.sidebar.markdown("**NFL AFC | Against The Spread**")
st.sidebar.markdown("---")

st.sidebar.header("Filters")

seasons = sorted(df["Season"].unique(), reverse=True)
selected_seasons = st.sidebar.multiselect("Select Seasons", options=seasons, default=seasons)

divisions = ["All"] + sorted(df["Division"].unique().tolist())
selected_division = st.sidebar.selectbox("Division", options=divisions)

teams = sorted(df["Team"].unique().tolist())
selected_teams = st.sidebar.multiselect("Teams", options=teams, default=teams)

st.sidebar.markdown("---")
st.sidebar.caption("Sample data for development • Real data coming soon")
st.sidebar.caption("Brand colors: Black • White • Grey • Red")

# ------------------------------
# FILTER DATA
# -----------------------------
filtered = df[
    (df["Season"].isin(selected_seasons)) &
    (df["Team"].isin(selected_teams))
].copy()

if selected_division != "All":
    filtered = filtered[filtered["Division"] == selected_division]

# ------------------------------
# MAIN CONTENT
# -----------------------------
st.title("FADE MACHINE")
st.subheader("AFC NFL Against The Spread Analytics")
st.caption("Historical ATS performance • Past 5 seasons (Sample Data)")

st.markdown("---")

if filtered.empty:
    st.warning("No data matches your filters. Please adjust the sidebar.")
else:
    # Aggregate by team across selected seasons
    team_summary = filtered.groupby(["Team", "Division"]).agg({
        "ATS_Wins": "sum",
        "ATS_Losses": "sum",
        "ATS_Pushes": "sum"
    }).reset_index()
    
    team_summary["Total_Games"] = team_summary["ATS_Wins"] + team_summary["ATS_Losses"]
    team_summary["ATS_Win_Pct"] = team_summary["ATS_Wins"] / team_summary["Total_Games"]
    team_summary = team_summary.sort_values("ATS_Win_Pct", ascending=False)
    
    # Metrics
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("Teams", len(team_summary))
    with col2:
        best = team_summary.iloc[0]["Team"] if not team_summary.empty else "N/A"
        st.metric("Best ATS", best)
    with col3:
        avg_pct = team_summary["ATS_Win_Pct"].mean()
        st.metric("Avg ATS %", f"{avg_pct:.1%}")
    with col4:
        total_games = team_summary["Total_Games"].sum()
        st.metric("Games Tracked", int(total_games))
    
    st.markdown("---")
    
    # Main Table
    st.header("AFC Team ATS Performance")
    
    display = team_summary[["Team", "Division", "ATS_Wins", "ATS_Losses", "ATS_Pushes", "ATS_Win_Pct"]].copy()
    display["ATS_Win_Pct"] = display["ATS_Win_Pct"].apply(lambda x: f"{x:.1%}")
    display = display.rename(columns={
        "ATS_Wins": "Wins",
        "ATS_Losses": "Losses",
        "ATS_Pushes": "Pushes",
        "ATS_Win_Pct": "Win %"
    })
    
    st.dataframe(display, use_container_width=True, hide_index=True)
    
    st.markdown("---")
    
    # Insights
    st.header("Quick Insights")
    col_a, col_b = st.columns(2)
    
    with col_a:
        top = team_summary.iloc[0]
        st.success(f"**Strongest ATS**\n\n{top['Team']}\n{int(top['ATS_Wins'])}-{int(top['ATS_Losses'])}-{int(top['ATS_Pushes'])}  |  {top['ATS_Win_Pct']:.1%}")
    
    with col_b:
        bottom = team_summary.iloc[-1]
        st.error(f"**Weakest ATS**\n\n{bottom['Team']}\n{int(bottom['ATS_Wins'])}-{int(bottom['ATS_Losses'])}-{int(bottom['ATS_Pushes'])}  |  {bottom['ATS_Win_Pct']:.1%}")

st.markdown("---")
st.caption("FADE MACHINE  •  Black / White / Grey / Red  •  AFC Sample Data  •  Analytical tool only")
