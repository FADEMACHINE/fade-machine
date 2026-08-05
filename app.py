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
        padding: 10px;
        border-radius: 8px;
        border-left: 4px solid #e10600;
    }
    [data-testid="stMetricLabel"] { font-size: 0.78rem !important; color: #ffffff !important; }
    [data-testid="stMetricValue"] { font-size: 1.05rem !important; color: #ffffff !important; }
    
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
    }
    .stCaptionContainer { color: #cccccc !important; }
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

@st.cache_data(ttl=120)  # cache for 2 minutes
def fetch_nfl_odds(api_key):
    if not api_key:
        return None, "No API key found."
    
    url = "https://api.the-odds-api.com/v4/sports/americanfootball_nfl/odds"
    params = {
        "apiKey": api_key,
        "regions": "us",
        "markets": "h2h,spreads,totals",
        "oddsFormat": "american",
        "bookmakers": "draftkings,fanduel,betmgm,williamhill_us"
    }
    
    try:
        response = requests.get(url, params=params, timeout=12)
        if response.status_code != 200:
            return None, f"API error: {response.status_code}"
        return response.json(), None
    except Exception as e:
        return None, str(e)

def parse_game_odds(game):
    home = game.get("home_team", "")
    away = game.get("away_team", "")
    commence = game.get("commence_time", "")
    try:
        dt = datetime.fromisoformat(commence.replace("Z", "+00:00"))
        time_str = dt.strftime("%a %b %d • %I:%M %p ET")
    except:
        time_str = commence
    
    rows = []
    for book in game.get("bookmakers", []):
        book_name = book.get("title", book.get("key", "Unknown"))
        spread_away = spread_home = ml_away = ml_home = total = over_odds = under_odds = "—"
        
        for market in book.get("markets", []):
            key = market.get("key")
            outcomes = market.get("outcomes", [])
            
            if key == "spreads":
                for o in outcomes:
                    point = o.get("point", "")
                    price = o.get("price", "")
                    if o.get("name") == away:
                        spread_away = f"{point} ({price})"
                    elif o.get("name") == home:
                        spread_home = f"{point} ({price})"
            elif key == "h2h":
                for o in outcomes:
                    if o.get("name") == away:
                        ml_away = o.get("price", "—")
                    elif o.get("name") == home:
                        ml_home = o.get("price", "—")
            elif key == "totals":
                for o in outcomes:
                    if o.get("name") == "Over":
                        total = o.get("point", "—")
                        over_odds = o.get("price", "—")
                    elif o.get("name") == "Under":
                        under_odds = o.get("price", "—")
        
        rows.append({
            "Book": book_name,
            "Away Spread": spread_away,
            "Home Spread": spread_home,
            "Away ML": ml_away,
            "Home ML": ml_home,
            "Total": total,
            "Over": over_odds,
            "Under": under_odds
        })
    
    return {
        "away": away,
        "home": home,
        "time": time_str,
        "odds_df": pd.DataFrame(rows),
        "raw": game
    }

def find_game(odds_data, team1, team2):
    """Find a game that matches two team names (partial match)."""
    if not odds_data:
        return None
    t1 = team1.lower()
    t2 = team2.lower()
    for g in odds_data:
        home = g.get("home_team", "").lower()
        away = g.get("away_team", "").lower()
        if (t1 in home or t1 in away) and (t2 in home or t2 in away):
            return parse_game_odds(g)
    return None

def show_odds_for_game(parsed, compact=False):
    """Display odds table for one parsed game."""
    if parsed is None or parsed["odds_df"].empty:
        st.caption("No live odds available for this game yet.")
        return
    st.dataframe(parsed["odds_df"], use_container_width=True, hide_index=True)

# ------------------------------
# FETCH ODDS ONCE (shared across tabs)
# -----------------------------
api_key = get_odds_api_key()
odds_data, odds_error = (None, None)
if api_key:
    odds_data, odds_error = fetch_nfl_odds(api_key)

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
# TAB 1: HOF GAME + LIVE ODDS
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
    st.subheader("Live Odds for this game")
    
    if not api_key:
        st.warning("Add your ODDS_API_KEY in Streamlit Secrets to see live odds here.")
    elif odds_error:
        st.error(f"Odds fetch error: {odds_error}")
    else:
        hof = find_game(odds_data, "Panthers", "Cardinals")
        if hof:
            st.caption(hof["time"])
            show_odds_for_game(hof)
        else:
            st.info("Hall of Fame Game odds not returned by the API yet (or already started). Check the Live Odds tab for all available games.")

# =====================================================
# TAB 2: FULL LIVE ODDS BOARD
# =====================================================
with tab2:
    st.header("Live Odds — All Upcoming Games")
    st.caption("Grouped by game • Data from The Odds API")
    
    if not api_key:
        st.warning("⚠️ No ODDS_API_KEY found in secrets.")
    elif odds_error:
        st.error(f"Could not fetch odds: {odds_error}")
    elif not odds_data:
        st.warning("No upcoming NFL games returned right now.")
    else:
        st.success(f"Found {len(odds_data)} upcoming game(s)")
        for game in odds_data:
            parsed = parse_game_odds(game)
            st.markdown(f"### {parsed['away']}  @  {parsed['home']}")
            st.caption(parsed["time"])
            show_odds_for_game(parsed)
            st.markdown("---")
        st.caption("Odds refresh roughly every 2 minutes when you reload the page.")

# =====================================================
# TAB 3: PRESEASON + ODDS WHERE AVAILABLE
# =====================================================
with tab3:
    st.header("2026 Preseason Schedule + Odds")
    
    st.subheader("Hall of Fame Game")
    st.write("**Carolina Panthers @ Arizona Cardinals** — Thu Aug 6 • 8:00 PM ET")
    hof = find_game(odds_data, "Panthers", "Cardinals") if odds_data else None
    show_odds_for_game(hof)
    
    st.markdown("---")
    st.subheader("Preseason Week 1 (Aug 13–15)")
    
    preseason_games = [
        ("Lions", "Bengals", "Detroit Lions @ Cincinnati Bengals", "Thu Aug 13 • 7:00 PM"),
        ("Packers", "Steelers", "Green Bay Packers @ Pittsburgh Steelers", "Thu Aug 13 • 7:00 PM"),
        ("Cardinals", "Raiders", "Arizona Cardinals @ Las Vegas Raiders", "Thu Aug 13 • 8:00 PM"),
        ("Panthers", "Bills", "Carolina Panthers @ Buffalo Bills", "Sat Aug 15 • 1:00 PM"),
        ("Cowboys", "Seahawks", "Dallas Cowboys @ Seattle Seahawks", "Sat Aug 15 • 8:00 PM"),
    ]
    
    for t1, t2, label, time_label in preseason_games:
        st.markdown(f"**{label}**")
        st.caption(time_label)
        match = find_game(odds_data, t1, t2) if odds_data else None
        show_odds_for_game(match)
        st.markdown("")

# =====================================================
# TAB 4: REGULAR SEASON + ODDS WHERE AVAILABLE
# =====================================================
with tab4:
    st.header("2026 Regular Season — Week 1 + Odds")
    
    reg_games = [
        ("Patriots", "Seahawks", "New England Patriots @ Seattle Seahawks", "Wed Sep 9 • 8:20 PM • Kickoff Game"),
        ("49ers", "Rams", "San Francisco 49ers vs Los Angeles Rams (Melbourne)", "Thu Sep 10 • 8:35 PM"),
        ("Broncos", "Chiefs", "Denver Broncos @ Kansas City Chiefs", "Mon Sep 14 • 8:15 PM • MNF"),
    ]
    
    for t1, t2, label, time_label in reg_games:
        st.markdown(f"**{label}**")
        st.caption(time_label)
        match = find_game(odds_data, t1, t2) if odds_data else None
        show_odds_for_game(match)
        st.markdown("")
    
    st.info("More regular-season games will appear here automatically once books post lines and the API returns them.")

# =====================================================
# TAB 5: TRENDS
# =====================================================
with tab5:
    st.header("HOF Game Trends")
    st.write("""
    - Underdogs ~7-4 SU and 8-2-1 ATS since 2013
    - Over has hit in the last 4 HOF Games
    - Soft lean historically toward the underdog side in this spot
    """)
    st.success("Research lean: Cardinals +1.5 (preseason = high variance)")
    st.caption("For analysis only. Not a betting recommendation.")
    
    st.markdown("---")
    st.subheader("Current HOF Odds (quick view)")
    hof = find_game(odds_data, "Panthers", "Cardinals") if odds_data else None
    show_odds_for_game(hof)

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
st.caption("FADE MACHINE • Live odds via The Odds API • Analytical tool only")
