import streamlit as st
import pandas as pd
import requests
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
        padding: 8px;
        border-radius: 6px;
        border-left: 3px solid #e10600;
    }
    [data-testid="stMetricLabel"] { font-size: 0.75rem !important; color: #aaaaaa !important; }
    [data-testid="stMetricValue"] { font-size: 1.0rem !important; color: #ffffff !important; }
    
    .stDataFrame, [data-testid="stDataFrame"] { font-size: 0.80rem !important; }
    
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
        font-size: 0.85rem;
    }
    .stCaptionContainer { color: #aaaaaa !important; }
    
    /* Odds card styling */
    .odds-card {
        background-color: #1a1a1a;
        border: 1px solid #333;
        border-radius: 10px;
        padding: 14px 18px;
        margin-bottom: 16px;
    }
    .odds-header {
        font-size: 0.75rem;
        color: #888;
        letter-spacing: 0.5px;
        margin-bottom: 8px;
    }
</style>
""", unsafe_allow_html=True)

# ------------------------------
# SIDEBAR
# -----------------------------
st.sidebar.markdown("# 🎯 FADE MACHINE")
st.sidebar.markdown("**NFL Analytics | Live Odds**")
st.sidebar.markdown("---")
st.sidebar.info("Analytical tool only — research & education.")
st.sidebar.caption("Brand: Black • White • Grey • Red")

# ------------------------------
# ODDS HELPERS
# -----------------------------
def get_odds_api_key():
    try:
        return st.secrets["ODDS_API_KEY"]
    except Exception:
        return None

@st.cache_data(ttl=120)
def fetch_nfl_odds(api_key):
    if not api_key:
        return None, "No API key found."
    url = "https://api.the-odds-api.com/v4/sports/americanfootball_nfl/odds"
    params = {
        "apiKey": api_key,
        "regions": "us",
        "markets": "h2h,spreads,totals",
        "oddsFormat": "american",
        "bookmakers": "draftkings,fanduel,betmgm,williamhill_us,bovada"
    }
    try:
        r = requests.get(url, params=params, timeout=12)
        if r.status_code != 200:
            return None, f"API error: {r.status_code}"
        return r.json(), None
    except Exception as e:
        return None, str(e)

def extract_book_odds(game, book_key=None):
    """
    Extract clean Away-on-top / Home-on-bottom odds for one book.
    Returns dict with spread, total, ml for away & home.
    """
    home = game.get("home_team", "")
    away = game.get("away_team", "")
    books = game.get("bookmakers", [])
    
    # Prefer requested book, else first available
    selected = None
    if book_key:
        for b in books:
            if b.get("key") == book_key or book_key.lower() in b.get("title", "").lower():
                selected = b
                break
    if not selected and books:
        selected = books[0]
    if not selected:
        return None
    
    result = {
        "book": selected.get("title", selected.get("key", "Unknown")),
        "away": away,
        "home": home,
        "away_spread": "—", "away_spread_odds": "",
        "home_spread": "—", "home_spread_odds": "",
        "away_ml": "—",
        "home_ml": "—",
        "total": "—",
        "over_odds": "", "under_odds": ""
    }
    
    for market in selected.get("markets", []):
        key = market.get("key")
        for o in market.get("outcomes", []):
            name = o.get("name", "")
            price = o.get("price", "")
            point = o.get("point", "")
            
            if key == "spreads":
                if name == away:
                    result["away_spread"] = point
                    result["away_spread_odds"] = price
                elif name == home:
                    result["home_spread"] = point
                    result["home_spread_odds"] = price
            elif key == "h2h":
                if name == away:
                    result["away_ml"] = price
                elif name == home:
                    result["home_ml"] = price
            elif key == "totals":
                if name == "Over":
                    result["total"] = point
                    result["over_odds"] = price
                elif name == "Under":
                    result["under_odds"] = price
    return result

def short_name(full):
    """Simple abbreviation helper."""
    mapping = {
        "Arizona Cardinals": "ARI", "Atlanta Falcons": "ATL", "Baltimore Ravens": "BAL",
        "Buffalo Bills": "BUF", "Carolina Panthers": "CAR", "Chicago Bears": "CHI",
        "Cincinnati Bengals": "CIN", "Cleveland Browns": "CLE", "Dallas Cowboys": "DAL",
        "Denver Broncos": "DEN", "Detroit Lions": "DET", "Green Bay Packers": "GB",
        "Houston Texans": "HOU", "Indianapolis Colts": "IND", "Jacksonville Jaguars": "JAX",
        "Kansas City Chiefs": "KC", "Las Vegas Raiders": "LV", "Los Angeles Chargers": "LAC",
        "Los Angeles Rams": "LAR", "Miami Dolphins": "MIA", "Minnesota Vikings": "MIN",
        "New England Patriots": "NE", "New Orleans Saints": "NO", "New York Giants": "NYG",
        "New York Jets": "NYJ", "Philadelphia Eagles": "PHI", "Pittsburgh Steelers": "PIT",
        "San Francisco 49ers": "SF", "Seattle Seahawks": "SEA", "Tampa Bay Buccaneers": "TB",
        "Tennessee Titans": "TEN", "Washington Commanders": "WAS"
    }
    return mapping.get(full, full[:3].upper())

def render_odds_card(odds, show_trends_button=True):
    """Render a clean Away-top / Home-bottom odds card."""
    if not odds:
        st.caption("No odds available.")
        return
    
    away_abbr = short_name(odds["away"])
    home_abbr = short_name(odds["home"])
    
    # Header row
    h1, h2, h3, h4 = st.columns([3, 2, 2, 2])
    h1.caption("")
    h2.caption("SPREAD")
    h3.caption("TOTAL")
    h4.caption("WINNER")
    
    # Away row (always top)
    a1, a2, a3, a4 = st.columns([3, 2, 2, 2])
    a1.markdown(f"**{away_abbr}**  \n{odds['away']}")
    a2.markdown(f"**{odds['away_spread']}**  \n{odds['away_spread_odds']}")
    a3.markdown(f"**O {odds['total']}**  \n{odds['over_odds']}")
    a4.markdown(f"**{odds['away_ml']}**")
    
    # Home row (always bottom)
    b1, b2, b3, b4 = st.columns([3, 2, 2, 2])
    b1.markdown(f"**{home_abbr}**  \n{odds['home']}")
    b2.markdown(f"**{odds['home_spread']}**  \n{odds['home_spread_odds']}")
    b3.markdown(f"**U {odds['total']}**  \n{odds['under_odds']}")
    b4.markdown(f"**{odds['home_ml']}**")
    
    if show_trends_button:
        with st.expander("Dive deeper — Analytical trends for this matchup"):
            st.markdown(f"### {odds['away']} @ {odds['home']}")
            st.write("""
            **Quick analytical angles (research only):**
            - Compare recent ATS records of both teams
            - Check home/away splits and rest situations
            - Review historical results in similar spots (favorites/underdogs, totals range)
            - Preseason games have high variance — starters often play limited snaps
            - Always cross-check injury reports and depth chart notes
            """)
            st.caption("Full historical ATS database and deeper models will be expanded in future updates.")

# ------------------------------
# FETCH ODDS
# -----------------------------
api_key = get_odds_api_key()
odds_data, odds_error = (None, None)
if api_key:
    odds_data, odds_error = fetch_nfl_odds(api_key)

# Available books for dropdown
BOOK_OPTIONS = {
    "DraftKings": "draftkings",
    "FanDuel": "fanduel",
    "BetMGM": "betmgm",
    "Caesars": "williamhill_us",
    "Bovada": "bovada"
}

# ------------------------------
# TITLE
# -----------------------------
st.title("🎯 FADE MACHINE")
st.caption("NFL Historical Trends • Live Odds • Schedule")

# =====================================================
# TABS
# =====================================================
tab1, tab2, tab3, tab4, tab5, tab6 = st.tabs([
    "🔴 HOF Game",
    "📈 Live Odds",
    "📅 Preseason",
    "📆 Regular Season",
    "📊 Trends",
    "📰 Headlines"
])

# =====================================================
# TAB 1: HOF GAME
# =====================================================
with tab1:
    st.header("Hall of Fame Game")
    st.markdown("**Thu Aug 6, 2026 • 8:00 PM ET • NBC / Peacock • Canton, OH**")
    
    c1, c2, c3 = st.columns([2, 1, 2])
    with c1:
        st.subheader("Carolina Panthers")
        st.caption("Away • Kenny Pickett expected")
    with c2:
        st.markdown("### VS")
    with c3:
        st.subheader("Arizona Cardinals")
        st.caption("Home • Carson Beck (R) expected")
    
    st.markdown("---")
    st.subheader("Live Odds")
    
    book_choice = st.selectbox("Select Sportsbook", list(BOOK_OPTIONS.keys()), key="hof_book")
    
    if not api_key:
        st.warning("Add ODDS_API_KEY in Secrets to load live odds.")
    elif odds_error:
        st.error(odds_error)
    else:
        # Find HOF game
        target = None
        if odds_data:
            for g in odds_data:
                teams = (g.get("home_team", "") + g.get("away_team", "")).lower()
                if "panther" in teams and "cardinal" in teams:
                    target = g
                    break
        if target:
            odds = extract_book_odds(target, BOOK_OPTIONS.get(book_choice))
            render_odds_card(odds)
        else:
            st.info("HOF Game odds not currently returned by the API. Check the Live Odds tab.")

# =====================================================
# TAB 2: LIVE ODDS (ALL GAMES)
# =====================================================
with tab2:
    st.header("Live Odds — All Upcoming Games")
    
    book_choice2 = st.selectbox("Select Sportsbook", list(BOOK_OPTIONS.keys()), key="live_book")
    
    if not api_key:
        st.warning("⚠️ No ODDS_API_KEY found.")
    elif odds_error:
        st.error(odds_error)
    elif not odds_data:
        st.warning("No upcoming games returned.")
    else:
        st.success(f"{len(odds_data)} game(s) available")
        for g in odds_data:
            away = g.get("away_team", "")
            home = g.get("home_team", "")
            commence = g.get("commence_time", "")
            try:
                dt = datetime.fromisoformat(commence.replace("Z", "+00:00"))
                time_str = dt.strftime("%a %b %d • %I:%M %p ET")
            except:
                time_str = commence
            
            st.markdown(f"#### {short_name(away)} @ {short_name(home)}")
            st.caption(time_str)
            odds = extract_book_odds(g, BOOK_OPTIONS.get(book_choice2))
            render_odds_card(odds)
            st.markdown("---")

# =====================================================
# TAB 3: PRESEASON
# =====================================================
with tab3:
    st.header("Preseason + Odds")
    book_choice3 = st.selectbox("Select Sportsbook", list(BOOK_OPTIONS.keys()), key="pre_book")
    
    st.subheader("Hall of Fame Game")
    st.caption("Carolina Panthers @ Arizona Cardinals • Thu Aug 6")
    if odds_data:
        for g in odds_data:
            teams = (g.get("home_team", "") + g.get("away_team", "")).lower()
            if "panther" in teams and "cardinal" in teams:
                odds = extract_book_odds(g, BOOK_OPTIONS.get(book_choice3))
                render_odds_card(odds)
                break
    
    st.markdown("---")
    st.subheader("Other Upcoming Preseason Games")
    if odds_data:
        for g in odds_data:
            teams = (g.get("home_team", "") + g.get("away_team", "")).lower()
            if "panther" in teams and "cardinal" in teams:
                continue
            away = g.get("away_team", "")
            home = g.get("home_team", "")
            st.markdown(f"**{short_name(away)} @ {short_name(home)}**")
            odds = extract_book_odds(g, BOOK_OPTIONS.get(book_choice3))
            render_odds_card(odds)
    else:
        st.caption("Live odds will appear here when available.")

# =====================================================
# TAB 4: REGULAR SEASON
# =====================================================
with tab4:
    st.header("Regular Season — Week 1 Highlights + Odds")
    book_choice4 = st.selectbox("Select Sportsbook", list(BOOK_OPTIONS.keys()), key="reg_book")
    
    if odds_data:
        for g in odds_data:
            away = g.get("away_team", "")
            home = g.get("home_team", "")
            st.markdown(f"**{short_name(away)} @ {short_name(home)}**")
            odds = extract_book_odds(g, BOOK_OPTIONS.get(book_choice4))
            render_odds_card(odds)
    else:
        st.info("Regular season lines usually appear closer to September. Current API results will show here automatically.")

# =====================================================
# TAB 5: TRENDS
# =====================================================
with tab5:
    st.header("HOF Game Trends & Deeper Analysis")
    st.write("""
    - Underdogs roughly **7-4 SU** and **8-2-1 ATS** in Hall of Fame Games since 2013
    - Average winning margin ~8.3 points
    - Over has hit in the last 4 HOF Games
    - When totals sit at 34+, Unders have been strong in recent samples
    - Preseason games = high variance (limited starter snaps)
    """)
    st.success("Research lean: **Cardinals +1.5** (historical underdog trend)")
    st.caption("For analysis only. Not a betting recommendation.")
    
    st.markdown("---")
    st.subheader("Current Odds Snapshot")
    if odds_data:
        for g in odds_data:
            teams = (g.get("home_team", "") + g.get("away_team", "")).lower()
            if "panther" in teams and "cardinal" in teams:
                odds = extract_book_odds(g, "draftkings")
                render_odds_card(odds, show_trends_button=False)
                break

# =====================================================
# TAB 6: HEADLINES
# =====================================================
with tab6:
    st.header("Preseason Headlines")
    st.write("""
    - Carson Beck starts for Cardinals in HOF Game
    - Jonathon Brooks (Panthers) out
    - Bijan Robinson extension completed
    - Preseason Week 1 starts Aug 13
    """)

st.markdown("---")
st.caption("FADE MACHINE • Away always on top • Home on bottom • Dive deeper for trends")
