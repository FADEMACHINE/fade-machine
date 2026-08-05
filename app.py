import streamlit as st
import pandas as pd
from datetime import datetime

# ------------------------------
# PAGE CONFIG & BRANDING
# -----------------------------
st.set_page_config(
    page_title="FADE MACHINE | NFL Analytics",
    page_icon="🎯",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS - Black / White / Grey / Red
st.markdown("""
<style>
    .stApp { background-color: #0d0d0d; color: #ffffff; }
    [data-testid="stSidebar"] { background-color: #1a1a1a; }
    h1, h2, h3 { color: #ffffff !important; }
    [data-testid="stMetric"] {
        background-color: #1f1f1f;
        padding: 15px;
        border-radius: 8px;
        border-left: 4px solid #e10600;
    }
    .stButton>button {
        background-color: #e10600;
        color: white;
        border: none;
    }
    .highlight-box {
        background-color: #1a1a1a;
        border: 2px solid #e10600;
        border-radius: 10px;
        padding: 20px;
        margin-bottom: 20px;
    }
</style>
""", unsafe_allow_html=True)

# ------------------------------
# SIDEBAR
# -----------------------------
st.sidebar.markdown("# 🎯 FADE MACHINE")
st.sidebar.markdown("**NFL Analytics | Historical Trends**")
st.sidebar.markdown("---")
st.sidebar.info("Pure analytical tool — no real-money betting features.")
st.sidebar.caption("Brand: Black • White • Grey • Red")
st.sidebar.caption("Next game: Hall of Fame Game — Thu Aug 6")

# ------------------------------
# MAIN TITLE
# -----------------------------
st.title("🎯 FADE MACHINE")
st.subheader("NFL Historical Trends & Preseason Analysis")
st.caption("Analytical tool only • Sample data for development")

st.markdown("---")

# =====================================================
# HIGHLIGHTED GAME: 2026 HALL OF FAME GAME
# =====================================================
st.markdown("### 🔴 CLOSEST GAME — HALL OF FAME GAME")
st.markdown("**Thursday, August 6, 2026 • 8:00 PM ET • NBC / Peacock**")

col1, col2, col3 = st.columns([2, 1, 2])
with col1:
    st.markdown("### Carolina Panthers")
    st.markdown("**Away**")
    st.caption("Kenny Pickett expected to start")
with col2:
    st.markdown("### VS")
    st.markdown("**Tom Benson Hall of Fame Stadium**")
    st.caption("Canton, Ohio")
with col3:
    st.markdown("### Arizona Cardinals")
    st.markdown("**Home (Designated)**")
    st.caption("Rookie Carson Beck expected to start")

st.markdown("---")

# Game Context
st.markdown("#### Game Context")
st.write("""
This is the official kickoff of the **2026 NFL preseason**.  
The Cardinals are the designated home team.  
Two franchise icons will be inducted into the Pro Football Hall of Fame this weekend:  
**Larry Fitzgerald** (Cardinals) and **Luke Kuechly** (Panthers).  
Also being enshrined: Drew Brees, Adam Vinatieri, and Roger Craig.
""")

# Current Odds (approximate from public sources as of early Aug 2026)
st.markdown("#### Approximate Market Odds (as of early August)")
odds_col1, odds_col2, odds_col3 = st.columns(3)
with odds_col1:
    st.metric("Spread", "Panthers -1.5")
with odds_col2:
    st.metric("Moneyline", "Panthers -125 / Cardinals +105")
with odds_col3:
    st.metric("Total", "36.5")

st.markdown("---")

# =====================================================
# HISTORICAL TRENDS & REASONING
# =====================================================
st.header("Historical Trends & Analytical Reasoning")

st.markdown("#### Key Preseason / Hall of Fame Game Trends")
st.write("""
- **Underdogs have performed well** in recent Hall of Fame Games.  
  Since 2013, underdogs are roughly **7-4 straight up** and **8-2-1 ATS**, including several consecutive underdog wins.
- Hall of Fame Games are evaluation contests. Starters usually play limited snaps (or not at all).  
  Results often come down to depth, coaching staff preparation, and who is more invested in early evaluation.
- **Panthers recent preseason form** has been weak (multiple sources note poor ATS results under current staff and as favorites).
- **Cardinals** have shown better recent preseason results in some seasons and have a new head coach (Mike LaFleur) who may want to set an early tone.
- The teams met in the **2025 regular season** (Week 2). Arizona built a large lead and held on for a 27-22 win.
""")

st.markdown("#### Reasoning Summary (Analytical View)")

reason_col1, reason_col2 = st.columns(2)

with reason_col1:
    st.success("""
**Lean toward Cardinals (as underdog / +1.5)**  

- Strong recent underdog trend in HOF Games  
- New coaching staff incentive to look sharp early  
- Panthers have struggled ATS as favorites in recent preseason  
- Cardinals won the most recent regular-season meeting  
- Preseason games are noisy — this is a soft lean only
""")

with reason_col2:
    st.info("""
**Counter points / Fade caution**  

- Preseason results have very low predictive value for the regular season  
- Both teams will rotate heavily — starters may play 1–2 series  
- Low total (36.5) suggests limited scoring and heavy backups  
- Any "edge" here is small and based on historical patterns, not guaranteed  
- Treat this as research, not a recommendation to bet
""")

st.warning("**Disclaimer**: This is historical trend analysis only. Preseason games are for evaluation. FADE MACHINE does not place or encourage real-money wagers.")

st.markdown("---")

# =====================================================
# 2026 SCHEDULE SECTION
# =====================================================
st.header("2026 NFL Schedule Snapshot")

st.markdown("#### Preseason — Hall of Fame Game + Week 1 Highlights")

preseason_data = [
    {"Date": "Thu, Aug 6", "Matchup": "Carolina Panthers @ Arizona Cardinals", "Time (ET)": "8:00 PM", "TV": "NBC / Peacock", "Type": "Hall of Fame Game"},
    {"Date": "Thu, Aug 13", "Matchup": "Detroit Lions @ Cincinnati Bengals", "Time (ET)": "7:00 PM", "TV": "Local", "Type": "Preseason Week 1"},
    {"Date": "Thu, Aug 13", "Matchup": "Green Bay Packers @ Pittsburgh Steelers", "Time (ET)": "7:00 PM", "TV": "NFL Network", "Type": "Preseason Week 1"},
    {"Date": "Thu, Aug 13", "Matchup": "Arizona Cardinals @ Las Vegas Raiders", "Time (ET)": "8:00 PM", "TV": "Local", "Type": "Preseason Week 1"},
    {"Date": "Sat, Aug 15", "Matchup": "Carolina Panthers @ Buffalo Bills", "Time (ET)": "1:00 PM", "TV": "Local", "Type": "Preseason Week 1"},
    {"Date": "Sat, Aug 15", "Matchup": "Dallas Cowboys @ Seattle Seahawks", "Time (ET)": "8:00 PM", "TV": "Local", "Type": "Preseason Week 1"},
]

preseason_df = pd.DataFrame(preseason_data)
st.dataframe(preseason_df, use_container_width=True, hide_index=True)

st.markdown("#### Regular Season — Week 1 Highlights")

week1_data = [
    {"Date": "Wed, Sep 9", "Matchup": "New England Patriots @ Seattle Seahawks", "Time (ET)": "8:20 PM", "TV": "NBC / Peacock", "Note": "Super Bowl LX rematch / Kickoff Game"},
    {"Date": "Thu, Sep 10", "Matchup": "San Francisco 49ers vs Los Angeles Rams", "Time (ET)": "8:35 PM", "TV": "Netflix", "Note": "Melbourne, Australia"},
    {"Date": "Sun, Sep 13", "Matchup": "Chicago Bears @ Carolina Panthers", "Time (ET)": "1:00 PM", "TV": "FOX", "Note": ""},
    {"Date": "Sun, Sep 13", "Matchup": "Buffalo Bills @ Houston Texans", "Time (ET)": "1:00 PM", "TV": "CBS", "Note": ""},
    {"Date": "Mon, Sep 14", "Matchup": "Denver Broncos @ Kansas City Chiefs", "Time (ET)": "8:15 PM", "TV": "ESPN / ABC", "Note": "Monday Night Football"},
]

week1_df = pd.DataFrame(week1_data)
st.dataframe(week1_df, use_container_width=True, hide_index=True)

st.info("Full 18-week regular season schedule (272 games) is available from NFL.com. This section currently shows the nearest games and key openers. We can expand the full schedule into the app in a later update.")

st.markdown("---")

# =====================================================
# EXISTING AFC ATS SECTION (kept for continuity)
# =====================================================
st.header("AFC Historical ATS Performance (Sample Data)")
st.caption("Past 5 seasons • Sample data for development — will be replaced with real feeds later")

# Simplified sample for display (same structure as before)
afc_summary = pd.DataFrame([
    {"Team": "Cincinnati Bengals", "Division": "North", "ATS_W": 49, "ATS_L": 35, "ATS_Pct": "58.3%"},
    {"Team": "Jacksonville Jaguars", "Division": "South", "ATS_W": 43, "ATS_L": 41, "ATS_Pct": "51.2%"},
    {"Team": "Buffalo Bills", "Division": "East", "ATS_W": 46, "ATS_L": 41, "ATS_Pct": "52.9%"},
    {"Team": "Pittsburgh Steelers", "Division": "North", "ATS_W": 47, "ATS_L": 38, "ATS_Pct": "55.3%"},
    {"Team": "Houston Texans", "Division": "South", "ATS_W": 41, "ATS_L": 44, "ATS_Pct": "48.2%"},
    {"Team": "Baltimore Ravens", "Division": "North", "ATS_W": 43, "ATS_L": 42, "ATS_Pct": "50.6%"},
    {"Team": "Denver Broncos", "Division": "West", "ATS_W": 38, "ATS_L": 46, "ATS_Pct": "45.2%"},
    {"Team": "Kansas City Chiefs", "Division": "West", "ATS_W": 40, "ATS_L": 46, "ATS_Pct": "46.5%"},
])

st.dataframe(afc_summary, use_container_width=True, hide_index=True)

st.markdown("---")
st.caption("FADE MACHINE • Black / White / Grey / Red • Analytical tool only • No real-money features")
