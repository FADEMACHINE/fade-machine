import streamlit as st
import pandas as pd
import requests
from datetime import datetime, timezone

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
# HELPER: FETCH ODDS FROM THE ODDS API
# -----------------------------
def get_odds_api_key():
    try:
        return st.secrets["ODDS_API_KEY"]
    except Exception:
        return None

def fetch_nfl_odds(api_key):
    """Fetch upcoming NFL odds from The Odds API."""
    if not api_key:
        return None, "No API key found in secrets."
    
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
            return None, f"API error: {response.status_code} – {response.text[:200]}"
        data = response.json()
        return data, None
    except Exception as e:
        return None, str(e)

def format_odds_rows(odds_data):
    """Turn API response into a clean dataframe."""
    rows = []
    for game in odds_data:
        home = game.get("home_team", "")
        away = game.get("away_team", "")
        commence = game.get("commence_time", "")
        try:
            dt = datetime.fromisoformat(commence.replace("Z", "+00:00"))
            time_str = dt.strftime("%a %b %d • %I:%M %p ET")
        except:
            time_str = commence
        
        for book in game.get("bookmakers", []):
            book_name = book.get("title", book.get("key", "Unknown"))
            spread_home = spread_away = ml_home = ml_away = total = over_odds = under_odds = "—"
            
            for market in book.get("markets", []):
                key = market.get("key")
                outcomes = market.get("outcomes", [])
                
                if key == "spreads":
                    for o in outcomes:
                        if o.get("name") == home:
                            spread_home = f"{o.get('point', '')} ({o.get('price', '')})"
                        elif o.get("name") == away:
                            spread_away = f"{o.get('point', '')} ({o.get('price', '')})"
                
                elif key == "h2h":
                    for o in outcomes:
                        if o.get("name") == home:
                            ml_home = o.get("price", "—")
                        elif o.get("name") == away:
                            ml_away = o.get("price", "—")
                
                elif key == "totals":
                    for o in outcomes:
                        if o.get("name") == "Over":
                            total = o.get("point", "—")
                            over_odds = o.get("price", "—")
                        elif o.get("name") == "Under":
                            under_odds = o.get("price", "—")
            
            rows.append({
                "Game": f"{away} @ {home}",
                "Time": time_str,
                "Book": book_name,
                "Away Spread": spread_away,
                "Home Spread": spread_home,
                "Away ML": ml_away,
                "Home ML": ml_home,
                "Total": total,
                "Over": over_odds,
                "Under": under_odds
            })
    return pd.DataFrame(rows)

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
    st.info("Live odds for this game (and others) are on the **Live Odds** tab once the API key is connected.")

# =====================================================
# TAB 2: LIVE ODDS (API)
# =====================================================
with tab2:
    st.header("Live Odds Board")
    st.caption("Powered by The Odds API • DraftKings, FanDuel, BetMGM and more")
    
    api_key = get_odds_api_key()
    
    if not api_key:
        st.warning("⚠️ No ODDS_API_KEY found in Streamlit Secrets.")
        st.markdown("""
        **How to add it:**
        1. Go to share.streamlit.io → your app → ⋮ → Settings → Secrets
        2. Paste:
        ```toml
        ODDS_API_KEY = "your-key-here"
        ```
        3. Save and refresh this page.
        """)
        
        # Show last known manual snapshot as fallback
        st.subheader("Fallback Snapshot (Hall of Fame Game)")
        fallback = pd.DataFrame([
            {"Book": "Consensus", "Spread": "CAR -1.5", "ML": "CAR -120 / ARI +100", "Total": "35.5", "Over": "-110", "Under": "-110"},
            {"Book": "DraftKings", "Spread": "CAR -1.5", "ML": "CAR -118 / ARI -102", "Total": "35.5", "Over": "-110", "Under": "-110"},
            {"Book": "FanDuel", "Spread": "CAR -1.5", "ML": "CAR -116 / ARI -102", "Total": "35.5", "Over": "-106", "Under": "-114"},
            {"Book": "Kalshi", "Spread": "~ -1.5", "ML": "~51% / 49%", "Total": "35.5", "Over": "~51¢", "Under": "~49¢"},
        ])
        st.dataframe(fallback, use_container_width=True, hide_index=True)
    else:
        with st.spinner("Pulling live NFL odds..."):
            data, error = fetch_nfl_odds(api_key)
        
        if error:
            st.error(f"Could not fetch odds: {error}")
            st.caption("Check that your API key is correct and you still have remaining requests.")
        elif not data:
            st.warning("No upcoming NFL games returned by the API right now.")
        else:
            df = format_odds_rows(data)
            if df.empty:
                st.warning("Odds data was empty.")
            else:
                st.success(f"Loaded {len(df)} book lines across {df['Game'].nunique()} games")
                st.dataframe(df, use_container_width=True, hide_index=True)
                st.caption("Odds update when you refresh the page. American odds format.")

# =====================================================
# TAB 3: PRESEASON
# =====================================================
with tab3:
    st.header("2026 Preseason Schedule")
    st.subheader("Hall of Fame Game")
    st.dataframe(pd.DataFrame([
        {"Date": "Thu Aug 6", "Matchup": "Carolina Panthers @ Arizona Cardinals", "Time": "8:00 PM ET", "TV": "NBC / Peacock"}
    ]), use_container_width=True, hide_index=True)
    
    st.subheader("Preseason Week 1 (Aug 13–15)")
    st.dataframe(pd.DataFrame([
        {"Date": "Thu Aug 13", "Away": "Detroit Lions", "Home": "Cincinnati Bengals", "Time": "7:00 PM"},
        {"Date": "Thu Aug 13", "Away": "Green Bay Packers", "Home": "Pittsburgh Steelers", "Time": "7:00 PM"},
        {"Date": "Thu Aug 13", "Away": "Arizona Cardinals", "Home": "Las Vegas Raiders", "Time": "8:00 PM"},
        {"Date": "Sat Aug 15", "Away": "Carolina Panthers", "Home": "Buffalo Bills", "Time": "1:00 PM"},
        {"Date": "Sat Aug 15", "Away": "Dallas Cowboys", "Home": "Seattle Seahawks", "Time": "8:00 PM"},
    ]), use_container_width=True, hide_index=True)

# =====================================================
# TAB 4: REGULAR SEASON
# =====================================================
with tab4:
    st.header("2026 Regular Season — Week 1 Highlights")
    st.dataframe(pd.DataFrame([
        {"Date": "Wed Sep 9", "Matchup": "New England @ Seattle", "Time": "8:20 PM", "Note": "Kickoff Game"},
        {"Date": "Thu Sep 10", "Matchup": "49ers vs Rams (Melbourne)", "Time": "8:35 PM", "Note": "Australia"},
        {"Date": "Mon Sep 14", "Matchup": "Denver @ Kansas City", "Time": "8:15 PM", "Note": "MNF"},
    ]), use_container_width=True, hide_index=True)

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
