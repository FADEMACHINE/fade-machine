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

# Strong white text on black/dark background
st.markdown("""
<style>
    /* Core background */
    .stApp, [data-testid="stAppViewContainer"] {
        background-color: #0d0d0d !important;
        color: #ffffff !important;
    }
    
    /* All text white */
    body, p, span, div, label, .stMarkdown, .stText, 
    [data-testid="stMarkdownContainer"], 
    [data-testid="stWidgetLabel"],
    .stSelectbox label, .stMultiSelect label {
        color: #ffffff !important;
    }
    
    /* Headers */
    h1, h2, h3, h4, h5, h6 {
        color: #ffffff !important;
    }
    
    /* Sidebar */
    [data-testid="stSidebar"] {
        background-color: #1a1a1a !important;
    }
    [data-testid="stSidebar"] * {
        color: #ffffff !important;
    }
    
    /* Metrics */
    [data-testid="stMetric"] {
        background-color: #1f1f1f !important;
        padding: 15px;
        border-radius: 8px;
        border-left: 4px solid #e10600;
    }
    [data-testid="stMetricLabel"], [data-testid="stMetricValue"], [data-testid="stMetricDelta"] {
        color: #ffffff !important;
    }
    
    /* Dataframes and tables */
    .stDataFrame, [data-testid="stDataFrame"] {
        background-color: #1a1a1a !important;
        color: #ffffff !important;
    }
    
    /* Tabs */
    .stTabs [data-baseweb="tab-list"] {
        background-color: #1a1a1a;
        gap: 8px;
    }
    .stTabs [data-baseweb="tab"] {
        color: #cccccc !important;
        background-color: #1a1a1a;
    }
    .stTabs [aria-selected="true"] {
        color: #e10600 !important;
        border-bottom: 2px solid #e10600;
    }
    
    /* Buttons */
    .stButton > button {
        background-color: #e10600 !important;
        color: #ffffff !important;
        border: none;
    }
    
    /* Info / Success / Warning boxes */
    .stAlert, [data-testid="stAlert"] {
        color: #ffffff !important;
    }
    
    /* Captions */
    .stCaptionContainer, [data-testid="stCaptionContainer"] {
        color: #cccccc !important;
    }
</style>
""", unsafe_allow_html=True)

# ------------------------------
# SIDEBAR
# -----------------------------
st.sidebar.markdown("# 🎯 FADE MACHINE")
st.sidebar.markdown("**NFL Analytics | Historical Trends**")
st.sidebar.markdown("---")
st.sidebar.info("Pure analytical tool — research only.")
st.sidebar.caption("Brand: Black • White • Grey • Red")
st.sidebar.caption("Next: Hall of Fame Game — Thu Aug 6, 8 PM ET")

# ------------------------------
# TITLE
# -----------------------------
st.title("🎯 FADE MACHINE")
st.caption("NFL Historical Trends • Preseason Analysis • Schedule")

# =====================================================
# TABS
# =====================================================
tab1, tab2, tab3, tab4, tab5 = st.tabs([
    "🔴 HOF Game",
    "📅 Preseason Schedule",
    "📆 Regular Season",
    "📊 HOF Trends & Analysis",
    "📰 Preseason Headlines"
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
    st.markdown("#### Approximate Market Odds")
    o1, o2, o3 = st.columns(3)
    o1.metric("Spread", "Panthers -1.5")
    o2.metric("Moneyline", "CAR -125 / ARI +105")
    o3.metric("Total", "35.5 – 36.5")
    
    st.markdown("---")
    st.markdown("#### Context")
    st.write("""
    This game officially opens the **2026 NFL preseason**.  
    Cardinals are the designated home team under first-year head coach **Mike LaFleur**.  
    Hall of Fame Class of 2026 inductees include **Larry Fitzgerald** (Cardinals) and **Luke Kuechly** (Panthers),  
    plus Drew Brees, Adam Vinatieri, and Roger Craig.
    """)

# =====================================================
# TAB 2: PRESEASON SCHEDULE
# =====================================================
with tab2:
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
    
    st.info("Panthers and Cardinals play four preseason games because of the Hall of Fame Game. Most other teams play three.")

# =====================================================
# TAB 3: REGULAR SEASON BY WEEKS
# =====================================================
with tab3:
    st.header("2026 NFL Regular Season — Key Weeks")
    
    st.subheader("Week 1 (Sep 9–14)")
    week1_reg = pd.DataFrame([
        {"Date": "Wed, Sep 9", "Away": "New England Patriots", "Home": "Seattle Seahawks", "Time (ET)": "8:20 PM", "TV": "NBC / Peacock", "Note": "Kickoff Game – Super Bowl LX rematch"},
        {"Date": "Thu, Sep 10", "Away": "San Francisco 49ers", "Home": "Los Angeles Rams", "Time (ET)": "8:35 PM", "TV": "Netflix", "Note": "Melbourne, Australia"},
        {"Date": "Sun, Sep 13", "Away": "Chicago Bears", "Home": "Carolina Panthers", "Time (ET)": "1:00 PM", "TV": "FOX", "Note": ""},
        {"Date": "Sun, Sep 13", "Away": "Buffalo Bills", "Home": "Houston Texans", "Time (ET)": "1:00 PM", "TV": "CBS", "Note": ""},
        {"Date": "Sun, Sep 13", "Away": "Baltimore Ravens", "Home": "Indianapolis Colts", "Time (ET)": "1:00 PM", "TV": "CBS", "Note": ""},
        {"Date": "Mon, Sep 14", "Away": "Denver Broncos", "Home": "Kansas City Chiefs", "Time (ET)": "8:15 PM", "TV": "ESPN / ABC", "Note": "Monday Night Football"},
    ])
    st.dataframe(week1_reg, use_container_width=True, hide_index=True)
    
    st.subheader("Later Key Notes")
    st.write("""
    - **Record 9 international games** in 2026 (including first games in Melbourne, Paris, and Rio).
    - Regular season runs 18 weeks (272 games total).
    - Full week-by-week schedule is available on NFL.com.  
      We can expand every week into the app in a future update.
    """)
    
    st.info("This tab currently focuses on the nearest and most important weeks. Full 18-week grid can be added next.")

# =====================================================
# TAB 4: HOF TRENDS & ANALYSIS
# =====================================================
with tab4:
    st.header("Hall of Fame Game — Betting Trends & Analysis")
    
    st.subheader("Historical Trends (since ~2013)")
    st.write("""
    - **Underdogs** are **7-4 straight up** and approximately **8-2-1 ATS** in Hall of Fame Games since 2013, including several consecutive underdog wins.
    - Average winning margin in that span is roughly **8.3 points**.
    - The **Over** has hit in the last **four** consecutive Hall of Fame Games.
    - When the total is posted at **34 or higher**, the **Under** has a strong recent record (roughly 6-1 in a recent sample).
    - Line movement toward the favorite has been common; teams that receive that movement have performed poorly ATS in recent years.
    - This is an evaluation game. Starters often play only 1–2 series (or not at all). Depth, coaching staff preparation, and who is more invested matter more than regular-season form.
    """)
    
    st.subheader("Team-Specific Notes")
    st.write("""
    - **Arizona Cardinals**: Played in the Hall of Fame Game in 2012 and 2017 (went 0-1-1 ATS in those appearances). New head coach Mike LaFleur. Rookie QB Carson Beck is expected to start. Won the most recent regular-season meeting vs Carolina (27-22 in 2025).
    - **Carolina Panthers**: First Hall of Fame Game appearance since 1995. Recent preseason ATS results under current staff have been weak, especially as favorites. Expected to start Kenny Pickett.
    """)
    
    st.subheader("Analytical Lean (Research Only)")
    c1, c2 = st.columns(2)
    with c1:
        st.success("""
        **Soft lean: Cardinals +1.5**  
        - Strong underdog trend in recent HOF Games  
        - New coaching staff may be more motivated early  
        - Panthers have struggled ATS as preseason favorites  
        - Recent H2H win for Arizona  
        - Still a noisy, low-information game
        """)
    with c2:
        st.warning("""
        **Important caveats**  
        - Preseason results have almost no predictive value for the regular season  
        - Heavy rotation of backups expected  
        - Low total environment  
        - Any edge is small and historical only  
        - This is analysis, not a bet recommendation
        """)
    
    st.caption("Sources: Public betting trend summaries and historical HOF Game data. FADE MACHINE is an analytical tool only.")

# =====================================================
# TAB 5: PRESEASON HEADLINES
# =====================================================
with tab5:
    st.header("Other NFL Preseason Headlines (Early August 2026)")
    
    st.markdown("#### Hall of Fame Game Notes")
    st.write("""
    - Rookie **Carson Beck** (Cardinals, 3rd-round pick) confirmed as the starting quarterback for Thursday’s game.
    - **Kenny Pickett** expected to start for the Panthers.
    - Panthers RB **Jonathon Brooks** will not play (still recovering from knee injury).
    - Both teams will play four preseason games because of the Canton trip.
    """)
    
    st.markdown("#### League-Wide Headlines")
    st.write("""
    - **Bijan Robinson** (Falcons) agreed to a major multi-year extension.
    - Browns coach indicated **Shedeur Sanders** and **Deshaun Watson** will each start a preseason game as the QB competition continues.
    - Multiple teams dealing with early training-camp injuries (examples include reports around Lions RB Sione Vaki and others).
    - Preseason Week 1 begins in full on **Thursday, August 13** with six games.
    - Nationally televised preseason games are limited; most Week 1 contests are local or on NFL Network.
    """)
    
    st.markdown("#### Quick Context")
    st.write("""
    Preseason is primarily about roster evaluation, depth chart battles, and getting young players live reps.  
    Starters are often limited. Betting markets for these games are thinner and more volatile than regular-season markets.
    """)
    
    st.info("Headlines are summarized from public NFL reports as of early August 2026. Always verify with primary sources.")

st.markdown("---")
st.caption("FADE MACHINE • Black / White / Grey / Red • Analytical tool only • No real-money features")
