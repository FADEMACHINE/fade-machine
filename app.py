import streamlit as st
import pandas as pd
import requests
from datetime import datetime

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
    .stCaptionContainer { color: #aaaaaa !important; }
    
    div[data-testid="stExpander"] {
        border: 1.5px solid #e10600 !important;
        border-radius: 10px !important;
        background-color: rgba(225, 6, 0, 0.12) !important;
        margin-top: 6px;
        margin-bottom: 18px;
    }
    div[data-testid="stExpander"] summary,
    div[data-testid="stExpander"] summary span,
    div[data-testid="stExpander"] summary p {
        color: #ff4d4d !important;
        font-weight: 600 !important;
    }
    div[data-testid="stExpander"] svg {
        fill: #e10600 !important;
    }
</style>
""", unsafe_allow_html=True)

st.sidebar.markdown("# 🎯 FADE MACHINE")
st.sidebar.markdown("**NFL Analytics | Live Odds + Results**")
st.sidebar.markdown("---")
st.sidebar.info("Analytical tool only — research & education.")
st.sidebar.caption("Brand: Black • White • Grey • Red")

# =====================================================
# COMPLETED GAMES (Final scores + bet results)
# =====================================================
COMPLETED_GAMES = [
    {
        "id": "hof_2026",
        "label": "HOF Game — CAR @ ARI (Aug 6)",
        "away": "Carolina Panthers",
        "home": "Arizona Cardinals",
        "away_score": 33,
        "home_score": 30,
        "final": "CAR 33 – ARI 30",
        "status": "FINAL",
        "date": "Thu Aug 6, 2026",
        "note": "Haynes King walk-off rushing TD as time expired",
        "spread_line": -1.5,
        "spread_favorite": "Carolina Panthers",
        "total_line": 35.5,
        "ml_favorite": "Carolina Panthers",
    }
]

def evaluate_bets(game):
    """Return hit/miss for Spread, Total, Moneyline."""
    away_score = game["away_score"]
    home_score = game["home_score"]
    margin = away_score - home_score
    total_pts = away_score + home_score

    spread_result = "HIT" if margin > 1.5 else "MISS"
    spread_detail = f"CAR -1.5 → actual margin {margin:+d} → {'Cover' if margin > 1.5 else 'No cover'}"

    total_result = "HIT (Over)" if total_pts > game["total_line"] else ("HIT (Under)" if total_pts < game["total_line"] else "PUSH")
    total_detail = f"Total {game['total_line']} → actual {total_pts} → {total_result}"

    ml_result = "HIT" if away_score > home_score else "MISS"
    ml_detail = f"CAR ML → CAR won {away_score}-{home_score}"

    return {
        "spread": {"result": spread_result, "detail": spread_detail},
        "total": {"result": total_result, "detail": total_detail},
        "ml": {"result": ml_result, "detail": ml_detail},
    }

# =====================================================
# HISTORICAL ATS + O/U DATA (All 32 Teams)
# =====================================================
TEAM_HISTORY = {
    "Arizona Cardinals": {"ats": "44-42-0", "cover_pct": 51.2, "ou": "~51% Over", "note": "Near league average ATS"},
    "Atlanta Falcons": {"ats": "34-48-3", "cover_pct": 41.5, "ou": "Slight Under lean", "note": "One of the weaker ATS teams since 2021"},
    "Baltimore Ravens": {"ats": "45-43-2", "cover_pct": 51.1, "ou": "Over-lean recent years", "note": "Solid but not elite cover rate"},
    "Buffalo Bills": {"ats": "47-45-3", "cover_pct": 51.1, "ou": "Slight Over lean", "note": "High scoring, close to average ATS"},
    "Carolina Panthers": {"ats": "37-47-2", "cover_pct": 44.1, "ou": "Slight Over lean", "note": "Below-average ATS since 2021; better as underdog in spots"},
    "Chicago Bears": {"ats": "39-43-5", "cover_pct": 47.6, "ou": "Slight Under lean", "note": "Middle of the pack"},
    "Cincinnati Bengals": {"ats": "52-37-2", "cover_pct": 58.4, "ou": "Over lean", "note": "Strong ATS performer since 2021"},
    "Cleveland Browns": {"ats": "37-48-1", "cover_pct": 43.5, "ou": "Near even", "note": "Struggled ATS overall"},
    "Dallas Cowboys": {"ats": "48-41-0", "cover_pct": 53.9, "ou": "Strong Over lean recently", "note": "Above-average cover rate"},
    "Denver Broncos": {"ats": "42-44-2", "cover_pct": 48.8, "ou": "Near even", "note": "Average ATS"},
    "Detroit Lions": {"ats": "57-32-0", "cover_pct": 64.0, "ou": "Over lean", "note": "Best ATS team in the league since 2021"},
    "Green Bay Packers": {"ats": "47-43-0", "cover_pct": 52.2, "ou": "Near even", "note": "Slightly above average"},
    "Houston Texans": {"ats": "45-43-3", "cover_pct": 51.1, "ou": "Under lean recently", "note": "Average cover rate"},
    "Indianapolis Colts": {"ats": "42-41-2", "cover_pct": 50.6, "ou": "Slight Over lean", "note": "Right at league average"},
    "Jacksonville Jaguars": {"ats": "45-42-1", "cover_pct": 51.7, "ou": "Slight Over lean", "note": "Slightly above average"},
    "Kansas City Chiefs": {"ats": "46-49-3", "cover_pct": 48.4, "ou": "Strong Under lean", "note": "Often priced as heavy favorites; ATS has lagged"},
    "Las Vegas Raiders": {"ats": "40-44-2", "cover_pct": 47.6, "ou": "Near even", "note": "Slightly below average"},
    "Los Angeles Chargers": {"ats": "45-41-2", "cover_pct": 52.3, "ou": "Under lean recently", "note": "Slightly above average ATS"},
    "Los Angeles Rams": {"ats": "50-42-3", "cover_pct": 54.4, "ou": "Near even", "note": "Consistently solid ATS"},
    "Miami Dolphins": {"ats": "44-42-1", "cover_pct": 51.2, "ou": "Near even", "note": "Average cover rate"},
    "Minnesota Vikings": {"ats": "42-40-5", "cover_pct": 51.2, "ou": "Under lean recently", "note": "Near average"},
    "New England Patriots": {"ats": "42-44-4", "cover_pct": 48.8, "ou": "Slight Over lean", "note": "Average since 2021"},
    "New Orleans Saints": {"ats": "38-46-1", "cover_pct": 45.2, "ou": "Strong Under lean", "note": "Below-average ATS"},
    "New York Giants": {"ats": "42-44-1", "cover_pct": 48.8, "ou": "Under lean", "note": "Average to slightly below"},
    "New York Jets": {"ats": "33-50-2", "cover_pct": 39.8, "ou": "Over lean recently", "note": "One of the weakest ATS teams since 2021"},
    "Philadelphia Eagles": {"ats": "49-43-3", "cover_pct": 53.3, "ou": "Slight Under lean", "note": "Consistently above average"},
    "Pittsburgh Steelers": {"ats": "48-40-1", "cover_pct": 54.6, "ou": "Slight Under lean", "note": "Strong ATS track record"},
    "San Francisco 49ers": {"ats": "50-45-1", "cover_pct": 52.6, "ou": "Slight Over lean", "note": "Solid cover rate"},
    "Seattle Seahawks": {"ats": "45-41-3", "cover_pct": 52.3, "ou": "Near even", "note": "Slightly above average"},
    "Tampa Bay Buccaneers": {"ats": "41-49-1", "cover_pct": 45.6, "ou": "Slight Over lean", "note": "Below-average ATS"},
    "Tennessee Titans": {"ats": "35-48-3", "cover_pct": 42.2, "ou": "Over lean recently", "note": "Weak ATS since 2021"},
    "Washington Commanders": {"ats": "40-44-4", "cover_pct": 47.6, "ou": "Over lean recently", "note": "Slightly below average"},
}

def get_team_history(team_name):
    if team_name in TEAM_HISTORY:
        return TEAM_HISTORY[team_name]
    for key, val in TEAM_HISTORY.items():
        if team_name.lower() in key.lower() or key.lower() in team_name.lower():
            return val
    return None

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
    home = game.get("home_team", "")
    away = game.get("away_team", "")
    books = game.get("bookmakers", [])
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
    if not odds:
        st.caption("No odds available.")
        return
    
    away_abbr = short_name(odds["away"])
    home_abbr = short_name(odds["home"])
    away_name = odds["away"]
    home_name = odds["home"]
    
    card_html = f'''
<div style="border:1.5px solid #ffffff; border-radius:12px; padding:16px 18px; margin-bottom:8px; background-color:#141414;">
  <div style="display:flex; margin-bottom:12px; color:#888; font-size:0.72rem; letter-spacing:0.4px;">
    <div style="flex:3;">TEAM</div>
    <div style="flex:2; text-align:center;">SPREAD</div>
    <div style="flex:2; text-align:center;">TOTAL</div>
    <div style="flex:2; text-align:center;">WINNER</div>
  </div>
  <div style="display:flex; align-items:center; margin-bottom:14px;">
    <div style="flex:3;">
      <div style="font-weight:700; font-size:1.05rem; color:#ffffff;">{away_abbr}</div>
      <div style="font-size:0.78rem; color:#aaaaaa;">{away_name}</div>
    </div>
    <div style="flex:2; text-align:center;">
      <div style="font-weight:700; font-size:1.05rem; color:#ffffff;">{odds["away_spread"]}</div>
      <div style="font-size:0.78rem; color:#aaaaaa;">{odds["away_spread_odds"]}</div>
    </div>
    <div style="flex:2; text-align:center;">
      <div style="font-weight:700; font-size:1.05rem; color:#ffffff;">O {odds["total"]}</div>
      <div style="font-size:0.78rem; color:#aaaaaa;">{odds["over_odds"]}</div>
    </div>
    <div style="flex:2; text-align:center;">
      <div style="font-weight:700; font-size:1.05rem; color:#ffffff;">{odds["away_ml"]}</div>
    </div>
  </div>
  <div style="display:flex; align-items:center;">
    <div style="flex:3;">
      <div style="font-weight:700; font-size:1.05rem; color:#ffffff;">{home_abbr}</div>
      <div style="font-size:0.78rem; color:#aaaaaa;">{home_name}</div>
    </div>
    <div style="flex:2; text-align:center;">
      <div style="font-weight:700; font-size:1.05rem; color:#ffffff;">{odds["home_spread"]}</div>
      <div style="font-size:0.78rem; color:#aaaaaa;">{odds["home_spread_odds"]}</div>
    </div>
    <div style="flex:2; text-align:center;">
      <div style="font-weight:700; font-size:1.05rem; color:#ffffff;">U {odds["total"]}</div>
      <div style="font-size:0.78rem; color:#aaaaaa;">{odds["under_odds"]}</div>
    </div>
    <div style="flex:2; text-align:center;">
      <div style="font-weight:700; font-size:1.05rem; color:#ffffff;">{odds["home_ml"]}</div>
    </div>
  </div>
</div>
'''
    st.markdown(card_html, unsafe_allow_html=True)
    
    if show_trends_button:
        with st.expander("🔍 Dive deeper — Analytical trends for this matchup"):
            st.markdown(f"### {away_name} @ {home_name}")
            away_hist = get_team_history(away_name)
            home_hist = get_team_history(home_name)
            col_a, col_b = st.columns(2)
            with col_a:
                st.markdown(f"**{away_abbr} — {away_name}**")
                if away_hist:
                    st.write(f"ATS (2021–2025): **{away_hist['ats']}** ({away_hist['cover_pct']}% cover)")
                    st.write(f"O/U lean: {away_hist['ou']}")
                    st.caption(away_hist['note'])
            with col_b:
                st.markdown(f"**{home_abbr} — {home_name}**")
                if home_hist:
                    st.write(f"ATS (2021–2025): **{home_hist['ats']}** ({home_hist['cover_pct']}% cover)")
                    st.write(f"O/U lean: {home_hist['ou']}")
                    st.caption(home_hist['note'])
            st.caption("Data primarily covers 2021–2025 regular seasons. Not a betting recommendation.")

api_key = get_odds_api_key()
odds_data, odds_error = (None, None)
if api_key:
    odds_data, odds_error = fetch_nfl_odds(api_key)

BOOK_OPTIONS = {
    "DraftKings": "draftkings",
    "FanDuel": "fanduel",
    "BetMGM": "betmgm",
    "Caesars": "williamhill_us",
    "Bovada": "bovada"
}

st.title("🎯 FADE MACHINE")
st.caption("NFL Historical Trends • Live Odds • Final Scores & Bet Results")

# =====================================================
# GLOBAL GAME FILTER
# =====================================================
st.sidebar.markdown("### 🔍 Game Filter")
all_game_labels = [g["label"] for g in COMPLETED_GAMES] + ["Upcoming / Live Games"]
selected_games = st.sidebar.multiselect(
    "Select games to view",
    options=all_game_labels,
    default=all_game_labels,
    help="Choose which completed or upcoming games to display"
)

tab1, tab2, tab3, tab4, tab5, tab6 = st.tabs([
    "🔴 HOF Game",
    "📈 Live Odds",
    "✅ Results & Bets",
    "📅 Preseason",
    "📊 Trends",
    "📰 Headlines"
])

# =====================================================
# TAB 1: HOF GAME (now FINAL)
# =====================================================
with tab1:
    if "HOF Game — CAR @ ARI (Aug 6)" in selected_games:
        st.header("Hall of Fame Game — FINAL")
        st.markdown("**Thu Aug 6, 2026 • Canton, OH**")
        
        st.success("### FINAL: Carolina Panthers 33 – Arizona Cardinals 30")
        st.caption("Haynes King walk-off rushing touchdown as time expired")
        
        c1, c2, c3 = st.columns([2, 1, 2])
        with c1:
            st.subheader("Carolina Panthers")
            st.markdown("### 33")
            st.caption("Winner")
        with c2:
            st.markdown("### FINAL")
        with c3:
            st.subheader("Arizona Cardinals")
            st.markdown("### 30")
        
        st.markdown("---")
        st.subheader("Bet Results (based on tracked lines)")
        
        game = COMPLETED_GAMES[0]
        results = evaluate_bets(game)
        
        r1, r2, r3 = st.columns(3)
        with r1:
            st.metric("Spread (CAR -1.5)", results["spread"]["result"])
            st.caption(results["spread"]["detail"])
        with r2:
            st.metric("Total (35.5)", results["total"]["result"])
            st.caption(results["total"]["detail"])
        with r3:
            st.metric("Moneyline (CAR)", results["ml"]["result"])
            st.caption(results["ml"]["detail"])
        
        st.markdown("---")
        st.info("**Summary:** Spread HIT • Over HIT • Moneyline HIT")
    else:
        st.info("HOF Game is currently filtered out. Use the sidebar filter to show it.")

# =====================================================
# TAB 2: LIVE ODDS
# =====================================================
with tab2:
    if "Upcoming / Live Games" in selected_games:
        st.header("Live Odds — Upcoming Games")
        book_choice2 = st.selectbox("Select Sportsbook", list(BOOK_OPTIONS.keys()), key="live_book")
        
        if not api_key:
            st.warning("⚠️ No ODDS_API_KEY found.")
        elif odds_error:
            st.error(odds_error)
        elif not odds_data:
            st.warning("No upcoming games returned by the API right now.")
        else:
            st.success(f"{len(odds_data)} game(s) available")
            for g in odds_data:
                away = g.get("away_team", "")
                home = g.get("home_team", "")
                teams = (away + home).lower()
                if "panther" in teams and "cardinal" in teams:
                    continue
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
    else:
        st.info("Upcoming games are currently filtered out.")

# =====================================================
# TAB 3: RESULTS & BETS
# =====================================================
with tab3:
    st.header("Completed Games — Scores & Bet Results")
    st.caption("Shows which bets would have HIT or MISS based on the lines we tracked")
    
    shown = False
    for game in COMPLETED_GAMES:
        if game["label"] in selected_games:
            shown = True
            st.subheader(game["label"])
            st.markdown(f"**{game['final']}**")
            st.caption(game["note"])
            
            results = evaluate_bets(game)
            
            col1, col2, col3 = st.columns(3)
            with col1:
                color = "🟢" if "HIT" in results["spread"]["result"] else "🔴"
                st.markdown(f"{color} **Spread**  \n{results['spread']['result']}  \n{results['spread']['detail']}")
            with col2:
                color = "🟢" if "HIT" in results["total"]["result"] else "🔴"
                st.markdown(f"{color} **Total**  \n{results['total']['result']}  \n{results['total']['detail']}")
            with col3:
                color = "🟢" if "HIT" in results["ml"]["result"] else "🔴"
                st.markdown(f"{color} **Moneyline**  \n{results['ml']['result']}  \n{results['ml']['detail']}")
            
            st.markdown("---")
    
    if not shown:
        st.info("No completed games selected in the filter.")

# =====================================================
# TAB 4: PRESEASON
# =====================================================
with tab4:
    st.header("Preseason Schedule")
    st.write("HOF Game is complete. Next preseason games begin around Aug 13.")
    st.caption("Use the Live Odds tab once books post new lines.")

# =====================================================
# TAB 5: TRENDS
# =====================================================
with tab5:
    st.header("Historical ATS & O/U Trends (All 32 Teams)")
    st.caption("Primary window: 2021–2025 regular seasons")
    
    rows = []
    for team, data in TEAM_HISTORY.items():
        rows.append({
            "Team": team,
            "ATS Record": data["ats"],
            "Cover %": data["cover_pct"],
            "O/U Lean": data["ou"],
            "Note": data["note"]
        })
    df = pd.DataFrame(rows).sort_values("Cover %", ascending=False)
    st.dataframe(df, use_container_width=True, hide_index=True)

# =====================================================
# TAB 6: HEADLINES
# =====================================================
with tab6:
    st.header("Preseason Headlines")
    st.write("""
    - **FINAL:** Panthers 33, Cardinals 30 (Haynes King walk-off TD)
    - Carson Beck started for the Cardinals and performed well in limited action
    - Preseason Week 1 games begin around August 13
    """)

st.markdown("---")
st.caption("FADE MACHINE • Final scores + bet results • Game filter in sidebar • Analytical tool only")
