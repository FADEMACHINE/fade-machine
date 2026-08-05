import streamlit as st
import pandas as pd

# ------------------------------
# PAGE CONFIG & BRANDING
# -----------------------------
st.set_page_config(
    page_title="FADE MACHINE | NFL Analytics",
    page_icon="🎯",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Strong white text + smaller odds fonts
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
    
    [data-testid="stMetric"] {
        background-color: #1f1f1f !important;
        padding: 12px;
        border-radius: 8px;
        border-left: 4px solid #e10600;
    }
    [data-testid="stMetricLabel"], [data-testid="stMetricValue"] {
        color: #ffffff !important;
        font-size: 0.85rem !important;
    }
    [data-testid="stMetricValue"] {
        font-size: 1.1rem !important;
    }
    
    /* Smaller table / odds text */
    .stDataFrame, [data-testid="stDataFrame"] {
        font-size: 0.82rem !important;
    }
    
    .stTabs [data-baseweb="tab-list"] { background-color: #1a1a1a; gap: 6px; }
    .stTabs [data-baseweb="tab"] { color: #cccccc !important; }
    .stTabs [aria-selected="true"] {
        color: #e10600 !important;
        border-bottom: 2px solid #e10600;
    }
    .stButton > button {
        background-color: #e10600 !important;
        color: #ffffff !important;
        border: none;
    }
    .stCaptionContainer { color: #cccccc !important; }
</style>
""", unsafe_allow_html=True)

# ------------------------------
# SIDEBAR
# -----------------------------
st.sidebar.markdown("# 🎯 FADE MACHINE")
st.sidebar.markdown("**NFL Analytics | Odds + Trends**")
st.sidebar.markdown("---")
st.sidebar.info("Analytical tool only — research & education.")
st.sidebar.caption("Brand: Black • White • Grey • Red")
st.sidebar.caption("Next game: HOF — Thu Aug 6, 8 PM ET")

# ------------------------------
# TITLE
# -----------------------------
st.title("🎯 FADE MACHINE")
st.caption("NFL Historical Trends • Live Odds Snapshot • Schedule")

# =====================================================
# TABS
# =====================================================
tab1, tab2, tab3, tab4, tab5, tab6 = st.tabs([
    "🔴 HOF Game",
    "📈 Odds Board",
    "📅 Preseason Schedule",
    "📆 Regular Season",
    "📊 HOF Trends",
    "📰 Headlines"
])

# =====================================================
# TAB 1: HALL OF FAME GAME
# =====================================================
with tab1:
    st.header("Hall of Fame Game — Closest Game")
    st.markdown("**Thursday, August 6, 2026 • 8:00 PM ET • NBC / Peacock**")
    st.markdown("**Tom Benson Hall of Fame Stadium • Canton, Ohio**")
    
    col1, col2, col3 = st.columns([2, 1, 2])
    with col1:
        st.subheader("Carolina Panthers")
        st.write("**Away**")
        st.caption("Expected starter: Kenny Pickett")
    with col2:
        st.markdown("### VS")
    with col3:
        st.subheader("Arizona Cardinals")
        st.write("**Home (Designated)**")
        st.caption("Expected starter: Rookie Carson Beck")
    
    st.markdown("---")
    st.markdown("#### Quick Odds Snapshot")
    o1, o2, o3, o4 = st.columns(4)
    o1.metric("Spread", "CAR -1.5")
    o2.metric("Moneyline", "CAR -120")
    o3.metric("Total", "35.5")
    o4.metric("Lean", "ARI +1.5")
    
    st.caption("Full multi-book odds are on the Odds Board tab.")

# =====================================================
# TAB 2: ODDS BOARD
# =====================================================
with tab2:
    st.header("Odds Board")
    st.caption("Public odds compiled from DraftKings, FanDuel, Action Network, VegasInsider, Kalshi & consensus sources (as of early Aug 5, 2026). Odds move constantly.")
    
    st.subheader("Hall of Fame Game — Multi-Book View")
    
    odds_data = [
        {
            "Book / Source": "Consensus",
            "Spread": "CAR -1.5",
            "Spread Odds": "-102 / -118",
            "Moneyline": "CAR -120 / ARI +100",
            "Total": "35.5",
            "Over": "-110",
            "Under": "-110"
        },
        {
            "Book / Source": "DraftKings",
            "Spread": "CAR -1.5",
            "Spread Odds": "-102 / -118",
            "Moneyline": "CAR -118 / ARI -102",
            "Total": "35.5",
            "Over": "-110",
            "Under": "-110"
        },
        {
            "Book / Source": "FanDuel",
            "Spread": "CAR -1.5",
            "Spread Odds": "-105 / -115",
            "Moneyline": "CAR -116 / ARI -102",
            "Total": "35.5",
            "Over": "-106",
            "Under": "-114"
        },
        {
            "Book / Source": "BetMGM / Consensus",
            "Spread": "CAR -1.5",
            "Spread Odds": "-110 / -110",
            "Moneyline": "CAR -125 / ARI +105",
            "Total": "35.5",
            "Over": "-110",
            "Under": "-110"
        },
        {
            "Book / Source": "Action Network",
            "Spread": "CAR -1.5",
            "Spread Odds": "-110 / -115",
            "Moneyline": "CAR -125 / ARI +105",
            "Total": "35.5",
            "Over": "-106",
            "Under": "-110"
        },
        {
            "Book / Source": "Kalshi (Prediction Market)",
            "Spread": "~ -1.5",
            "Spread Odds": "~50¢ / 50¢",
            "Moneyline": "~51% / 49%",
            "Total": "35.5",
            "Over": "~51¢",
            "Under": "~49¢"
        },
    ]
    
    odds_df = pd.DataFrame(odds_data)
    st.dataframe(odds_df, use_container_width=True, hide_index=True)
    
    st.markdown("---")
    st.subheader("Public Betting Notes")
    st.write("""
    - Significant money has been reported on **Cardinals +1.5**
    - Over has also been popular in several books
    - Kalshi prediction market shows the game essentially even (~50/50)
    """)
    
    st.markdown("---")
    st.subheader("Odds API Status")
    st.info("""
    **Current status:** Manual / public snapshot only.  
    **Next step:** Connect a live Odds API (The Odds API is recommended for beginners).  
    Once connected, this tab can auto-refresh spreads, totals, and moneylines for every game.
    """)
    
    st.caption("Odds are approximate and change frequently. Always verify on the sportsbook or prediction market before any decision. FADE MACHINE is for research only.")

# =====================================================
# TAB 3: PRESEASON SCHEDULE
# =====================================================
with tab3:
    st.header("2026 NFL Preseason Schedule")
    
    st.subheader("Hall of Fame Game")
    hof = pd.DataFrame([
        {"Date": "Thu, Aug 6", "Away": "Carolina Panthers", "Home": "Arizona Cardinals", "Time (ET)": "8:00 PM", "TV": "NBC / Peacock", "Note": "Canton, Ohio"}
    ])
    st.dataframe(hof, use_container_width=True, hide_index=True)
    
    st.subheader("Preseason Week 1 (Aug 13–15)")
    week1_pre = pd.DataFrame([
        {"Date": "Thu, Aug 13", "Away": "Detroit Lions", "Home": "Cincinnati Bengals", "Time (ET)": "7:00 PM", "TV": "Local"},
        {"Date": "Thu, Aug 13", "Away": "Green Bay Packers", "Home": "Pittsburgh Steelers", "Time (ET)": "7:00 PM", "TV": "NFL Network"},
        {"Date": "Thu, Aug 13", "Away": "Indianapolis Colts", "Home": "New England Patriots", "Time (ET)": "7:30 PM", "TV": "Local"},
        {"Date": "Thu, Aug 13", "Away": "Los Angeles Chargers", "Home": "Houston Texans", "Time (ET)": "8:00 PM", "TV": "Local"},
        {"Date": "Thu, Aug 13", "Away": "Arizona Cardinals", "Home": "Las Vegas Raiders", "Time (ET)": "8:00 PM", "TV": "Local"},
        {"Date": "Thu, Aug 13", "Away": "Tennessee Titans", "Home": "San Francisco 49ers", "Time (ET)": "9:00 PM", "TV": "NFL Network"},
        {"Date": "Fri, Aug 14", "Away": "Denver Broncos", "Home": "Atlanta Falcons", "Time (ET)": "7:00 PM", "TV": "Local"},
        {"Date": "Fri, Aug 14", "Away": "Tampa Bay Buccaneers", "Home": "New York Jets", "Time (ET)": "7:00 PM", "TV": "NFL Network"},
        {"Date": "Fri, Aug 14", "Away": "Miami Dolphins", "Home": "Washington Commanders", "Time (ET)": "7:00 PM", "TV": "Local"},
        {"Date": "Sat, Aug 15", "Away": "Carolina Panthers", "Home": "Buffalo Bills", "Time (ET)": "1:00 PM", "TV": "Local"},
        {"Date": "Sat, Aug 15", "Away": "Cleveland Browns", "Home": "Chicago Bears", "Time (ET)": "1:00 PM", "TV": "Local"},
        {"Date": "Sat, Aug 15", "Away": "Minnesota Vikings", "Home": "New York Giants", "Time (ET)": "1:00 PM", "TV": "Local"},
        {"Date": "Sat, Aug 15", "Away": "Los Angeles Rams", "Home": "Kansas City Chiefs", "Time (ET)": "4:00 PM", "TV": "Local"},
        {"Date": "Sat, Aug 15", "Away": "Jacksonville Jaguars", "Home": "New Orleans Saints", "Time (ET)": "4:00 PM", "TV": "Local"},
        {"Date": "Sat, Aug 15", "Away": "Philadelphia Eagles", "Home": "Baltimore Ravens", "Time (ET)": "7:00 PM", "TV": "Local"},
        {"Date": "Sat, Aug 15", "Away": "Dallas Cowboys", "Home": "Seattle Seahawks", "Time (ET)": "8:00 PM", "TV": "Local"},
    ])
    st.dataframe(week1_pre, use_container_width=True, hide_index=True)

# =====================================================
# TAB 4: REGULAR SEASON
# =====================================================
with tab4:
    st.header("2026 NFL Regular Season — Key Weeks")
    st.subheader("Week 1 (Sep 9–14)")
    week1_reg = pd.DataFrame([
        {"Date": "Wed, Sep 9", "Away": "New England Patriots", "Home": "Seattle Seahawks", "Time (ET)": "8:20 PM", "TV": "NBC", "Note": "Kickoff – Super Bowl LX rematch"},
        {"Date": "Thu, Sep 10", "Away": "San Francisco 49ers", "Home": "Los Angeles Rams", "Time (ET)": "8:35 PM", "TV": "Netflix", "Note": "Melbourne, Australia"},
        {"Date": "Sun, Sep 13", "Away": "Chicago Bears", "Home": "Carolina Panthers", "Time (ET)": "1:00 PM", "TV": "FOX", "Note": ""},
        {"Date": "Sun, Sep 13", "Away": "Buffalo Bills", "Home": "Houston Texans", "Time (ET)": "1:00 PM", "TV": "CBS", "Note": ""},
        {"Date": "Mon, Sep 14", "Away": "Denver Broncos", "Home": "Kansas City Chiefs", "Time (ET)": "8:15 PM", "TV": "ESPN/ABC", "Note": "MNF"},
    ])
    st.dataframe(week1_reg, use_container_width=True, hide_index=True)
    st.info("Full 18-week schedule can be expanded later. Live odds will appear here once the Odds API is connected.")

# =====================================================
# TAB 5: HOF TRENDS
# =====================================================
with tab5:
    st.header("Hall of Fame Game — Betting Trends")
    st.write("""
    - Underdogs roughly **7-4 SU** and **8-2-1 ATS** since 2013
    - Average winning margin ~8.3 points
    - Over has hit in the last 4 HOF Games
    - When totals are 34+, Unders have been strong in recent samples
    - Line moves toward the favorite have often underperformed ATS
    """)
    st.success("Soft analytical lean: **Cardinals +1.5** (research only — preseason games are noisy)")
    st.warning("This is historical trend analysis only. Not a betting recommendation.")

# =====================================================
# TAB 6: HEADLINES
# =====================================================
with tab6:
    st.header("Preseason Headlines")
    st.write("""
    - Carson Beck confirmed as Cardinals starting QB for HOF Game
    - Jonathon Brooks (Panthers) will not play
    - Bijan Robinson signed major extension with Falcons
    - Browns QB competition continues (Sanders / Watson each expected to start a preseason game)
    - Preseason Week 1 begins in full on August 13
    """)

st.markdown("---")
st.caption("FADE MACHINE • Black / White / Grey / Red • Analytical tool only")
