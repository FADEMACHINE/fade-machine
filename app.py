import streamlit as st
import pandas as pd
import requests
from datetime import datetime
import bcrypt
import json
import os
from fantasy_models import render_fantasy_tab

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
    .stTabs [data-baseweb="tab-list"] { background-color: #1a1a1a; gap: 4px; flex-wrap: wrap; }
    .stTabs [data-baseweb="tab"] { color: #cccccc !important; padding: 10px 12px !important; font-size: 0.85rem !important; }
    .stTabs [aria-selected="true"] { color: #e10600 !important; border-bottom: 2px solid #e10600; }
    .stButton > button {
        background-color: #e10600 !important; color: #ffffff !important; border: none;
        min-height: 44px !important; padding: 0.6rem 1.2rem !important; font-size: 1rem !important; border-radius: 8px !important;
    }
    .stCaptionContainer { color: #aaaaaa !important; }
    div[data-testid="stExpander"] {
        border: 1px solid #2a2a2a !important; border-radius: 10px !important;
        background-color: #141414 !important; margin-top: 8px; margin-bottom: 16px;
    }
    div[data-testid="stExpander"] summary,
    div[data-testid="stExpander"] summary span,
    div[data-testid="stExpander"] summary p { color: #ffffff !important; font-weight: 600 !important; font-size: 0.95rem !important; }
    div[data-testid="stExpander"] svg { fill: #cccccc !important; }
    @media (max-width: 768px) {
        .stTabs [data-baseweb="tab"] { font-size: 0.75rem !important; padding: 8px 6px !important; }
        h1 { font-size: 1.6rem !important; }
        h2 { font-size: 1.3rem !important; }
        h3 { font-size: 1.1rem !important; }
    }
    [data-testid="stMetricValue"] { color: #ffffff !important; font-size: 1.4rem !important; }
    [data-testid="stMetricLabel"] { color: #cccccc !important; }
    .steel-balance-bar {
        border: 2px solid #e10600; border-radius: 10px; background-color: rgba(225, 6, 0, 0.18);
        padding: 10px 18px; display: inline-block; text-align: right; min-width: 140px;
    }
    .steel-balance-bar .steel-label { font-size: 0.7rem; color: #ffffff !important; font-weight: 600; letter-spacing: 0.5px; text-transform: uppercase; }
    .steel-balance-bar .steel-amount { font-size: 1.25rem; color: #ffffff !important; font-weight: 700; line-height: 1.3; }

    /* ===== Dropdown / Select visibility (high contrast) ===== */
    div[data-baseweb="select"] > div,
    div[data-baseweb="select"] > div > div {
        background-color: #1f1f1f !important;
        border: 1.5px solid #e10600 !important;
        border-radius: 8px !important;
        color: #ffffff !important;
        min-height: 42px !important;
    }
    div[data-baseweb="select"] span,
    div[data-baseweb="select"] div {
        color: #ffffff !important;
    }
    /* Dropdown popup menu */
    ul[role="listbox"],
    div[data-baseweb="popover"] div[data-baseweb="menu"],
    div[role="listbox"] {
        background-color: #1a1a1a !important;
        border: 1.5px solid #e10600 !important;
        border-radius: 8px !important;
    }
    li[role="option"],
    div[role="option"] {
        color: #ffffff !important;
        background-color: #1a1a1a !important;
    }
    li[role="option"]:hover,
    div[role="option"]:hover,
    li[aria-selected="true"] {
        background-color: #e10600 !important;
        color: #ffffff !important;
    }
    /* Multiselect tags */
    span[data-baseweb="tag"] {
        background-color: #e10600 !important;
        color: #ffffff !important;
        border: none !important;
    }
    /* Radio / checkbox labels already white; ensure select labels */
    [data-testid="stSelectbox"] label,
    [data-testid="stMultiSelect"] label {
        color: #ffffff !important;
        font-weight: 600 !important;
    }
</style>
""", unsafe_allow_html=True)

COMPLETED_GAMES = [
    {
        "id": "hof_2026",
        "label": "HOF Game — CAR @ ARI (Aug 6)",
        "away": "Carolina Panthers",
        "home": "Arizona Cardinals",
        "away_score": 33,
        "home_score": 30,
        "date": "2026-08-06",
        "notes": "Haynes King walk-off TD",
    }
]

SAMPLE_PLAYER_PROPS = [
    {"player": "Josh Allen", "team": "BUF", "pos": "QB", "game": "BUF vs TBD", "market": "Pass Yds", "line": 265.5, "over": -110, "under": -110},
    {"player": "Josh Allen", "team": "BUF", "pos": "QB", "game": "BUF vs TBD", "market": "Pass TDs", "line": 1.5, "over": -125, "under": 105},
    {"player": "Josh Allen", "team": "BUF", "pos": "QB", "game": "BUF vs TBD", "market": "Rush Yds", "line": 32.5, "over": -110, "under": -110},
    {"player": "Lamar Jackson", "team": "BAL", "pos": "QB", "game": "BAL vs TBD", "market": "Pass Yds", "line": 230.5, "over": -110, "under": -110},
    {"player": "Lamar Jackson", "team": "BAL", "pos": "QB", "game": "BAL vs TBD", "market": "Pass TDs", "line": 1.5, "over": 105, "under": -125},
    {"player": "Lamar Jackson", "team": "BAL", "pos": "QB", "game": "BAL vs TBD", "market": "Rush Yds", "line": 55.5, "over": -115, "under": -105},
    {"player": "Patrick Mahomes", "team": "KC", "pos": "QB", "game": "KC vs TBD", "market": "Pass Yds", "line": 275.5, "over": -110, "under": -110},
    {"player": "Patrick Mahomes", "team": "KC", "pos": "QB", "game": "KC vs TBD", "market": "Pass TDs", "line": 2.5, "over": 120, "under": -145},
    {"player": "Christian McCaffrey", "team": "SF", "pos": "RB", "game": "SF vs TBD", "market": "Rush Yds", "line": 75.5, "over": -110, "under": -110},
    {"player": "Christian McCaffrey", "team": "SF", "pos": "RB", "game": "SF vs TBD", "market": "Receptions", "line": 4.5, "over": -120, "under": 100},
    {"player": "Christian McCaffrey", "team": "SF", "pos": "RB", "game": "SF vs TBD", "market": "Rec Yds", "line": 35.5, "over": -110, "under": -110},
    {"player": "Christian McCaffrey", "team": "SF", "pos": "RB", "game": "SF vs TBD", "market": "Rush TDs", "line": 0.5, "over": -105, "under": -115},
    {"player": "Saquon Barkley", "team": "PHI", "pos": "RB", "game": "PHI vs TBD", "market": "Rush Yds", "line": 85.5, "over": -110, "under": -110},
    {"player": "Saquon Barkley", "team": "PHI", "pos": "RB", "game": "PHI vs TBD", "market": "Receptions", "line": 3.5, "over": -115, "under": -105},
    {"player": "Saquon Barkley", "team": "PHI", "pos": "RB", "game": "PHI vs TBD", "market": "Rec Yds", "line": 28.5, "over": -110, "under": -110},
    {"player": "Jahmyr Gibbs", "team": "DET", "pos": "RB", "game": "DET vs TBD", "market": "Rush Yds", "line": 68.5, "over": -110, "under": -110},
    {"player": "Jahmyr Gibbs", "team": "DET", "pos": "RB", "game": "DET vs TBD", "market": "Receptions", "line": 4.5, "over": -110, "under": -110},
    {"player": "CeeDee Lamb", "team": "DAL", "pos": "WR", "game": "DAL vs TBD", "market": "Receptions", "line": 6.5, "over": -115, "under": -105},
    {"player": "CeeDee Lamb", "team": "DAL", "pos": "WR", "game": "DAL vs TBD", "market": "Rec Yds", "line": 82.5, "over": -110, "under": -110},
    {"player": "CeeDee Lamb", "team": "DAL", "pos": "WR", "game": "DAL vs TBD", "market": "Rec TDs", "line": 0.5, "over": 115, "under": -140},
    {"player": "Ja'Marr Chase", "team": "CIN", "pos": "WR", "game": "CIN vs TBD", "market": "Receptions", "line": 6.5, "over": -120, "under": 100},
    {"player": "Ja'Marr Chase", "team": "CIN", "pos": "WR", "game": "CIN vs TBD", "market": "Rec Yds", "line": 88.5, "over": -110, "under": -110},
    {"player": "Amon-Ra St. Brown", "team": "DET", "pos": "WR", "game": "DET vs TBD", "market": "Receptions", "line": 7.5, "over": -110, "under": -110},
    {"player": "Amon-Ra St. Brown", "team": "DET", "pos": "WR", "game": "DET vs TBD", "market": "Rec Yds", "line": 78.5, "over": -110, "under": -110},
    {"player": "Tyreek Hill", "team": "MIA", "pos": "WR", "game": "MIA vs TBD", "market": "Receptions", "line": 5.5, "over": -110, "under": -110},
    {"player": "Tyreek Hill", "team": "MIA", "pos": "WR", "game": "MIA vs TBD", "market": "Rec Yds", "line": 72.5, "over": -110, "under": -110},
    {"player": "Travis Kelce", "team": "KC", "pos": "TE", "game": "KC vs TBD", "market": "Receptions", "line": 5.5, "over": -115, "under": -105},
    {"player": "Travis Kelce", "team": "KC", "pos": "TE", "game": "KC vs TBD", "market": "Rec Yds", "line": 62.5, "over": -110, "under": -110},
    {"player": "Travis Kelce", "team": "KC", "pos": "TE", "game": "KC vs TBD", "market": "Rec TDs", "line": 0.5, "over": 105, "under": -125},
    {"player": "Brock Bowers", "team": "LV", "pos": "TE", "game": "LV vs TBD", "market": "Receptions", "line": 5.5, "over": -110, "under": -110},
    {"player": "Brock Bowers", "team": "LV", "pos": "TE", "game": "LV vs TBD", "market": "Rec Yds", "line": 58.5, "over": -110, "under": -110},
]

PROP_MARKET_KEYS = "player_pass_yds,player_rush_yds,player_reception_yds,player_receptions,player_pass_tds,player_rush_tds,player_reception_tds"
MARKET_LABEL = {
    "player_pass_yds": "Pass Yds",
    "player_rush_yds": "Rush Yds",
    "player_reception_yds": "Rec Yds",
    "player_receptions": "Receptions",
    "player_pass_tds": "Pass TDs",
    "player_rush_tds": "Rush TDs",
    "player_reception_tds": "Rec TDs",
}

# Users / Steel system
USERS_DB_PATH = "users_db.json"
STEEL_STAKE_OPTIONS = [10, 25, 50, 100, 250, 500]
STEEL_PRICE_USD = 0.10

def load_users():
    if os.path.exists(USERS_DB_PATH):
        try:
            with open(USERS_DB_PATH, "r") as f:
                return json.load(f)
        except Exception:
            return {}
    return {}

def save_users(users):
    with open(USERS_DB_PATH, "w") as f:
        json.dump(users, f, indent=2)

def get_current_profile():
    if not st.session_state.get("authenticated"):
        return None
    users = load_users()
    uname = st.session_state.get("username")
    return users.get(uname)

def ensure_user_fields(user):
    if "steel_balance" not in user:
        user["steel_balance"] = 0
    if "open_bets" not in user:
        user["open_bets"] = []
    if "settled_bets" not in user:
        user["settled_bets"] = []
    if "transactions" not in user:
        user["transactions"] = []
    return user

def register_user(username, password, display_name=""):
    users = load_users()
    if username in users:
        return False, "Username already taken"
    hashed = bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()
    users[username] = {
        "password_hash": hashed,
        "display_name": display_name or username,
        "steel_balance": 0,
        "open_bets": [],
        "settled_bets": [],
        "transactions": [],
        "created": datetime.utcnow().isoformat(),
    }
    save_users(users)
    return True, "Account created"

def login_user(username, password):
    users = load_users()
    user = users.get(username)
    if not user:
        return False, "User not found"
    if bcrypt.checkpw(password.encode(), user["password_hash"].encode()):
        st.session_state.authenticated = True
        st.session_state.username = username
        return True, "Logged in"
    return False, "Wrong password"

def purchase_steel(amount):
    if not st.session_state.get("authenticated"):
        return False, "Log in first"
    users = load_users()
    uname = st.session_state.username
    user = ensure_user_fields(users[uname])
    user["steel_balance"] = user.get("steel_balance", 0) + amount
    user["transactions"].append({
        "type": "purchase",
        "steel_amount": amount,
        "timestamp": datetime.utcnow().isoformat(),
        "note": f"Bought {amount} Steel",
    })
    users[uname] = user
    save_users(users)
    return True, f"Added {amount} Steel! Balance: {user['steel_balance']}"

def american_to_profit(stake, odds):
    odds = float(odds)
    if odds > 0:
        return round(stake * (odds / 100), 2)
    else:
        return round(stake * (100 / abs(odds)), 2)

def place_steel_bet(game_id, away, home, market, selection, line, odds, stake, label="", market_type="fixed", player=None):
    if not st.session_state.get("authenticated"):
        return False, "Log in to place bets"
    users = load_users()
    uname = st.session_state.username
    user = ensure_user_fields(users[uname])
    bal = user.get("steel_balance", 0)
    if stake > bal:
        return False, f"Insufficient Steel (have {bal})"
    bet = {
        "id": f"bet_{datetime.utcnow().timestamp()}",
        "game_id": game_id,
        "away": away,
        "home": home,
        "market": market,
        "selection": selection,
        "line": line,
        "odds": odds,
        "stake": stake,
        "label": label,
        "market_type": market_type,
        "player": player,
        "placed_at": datetime.utcnow().isoformat(),
        "status": "open",
        "steel_result": 0,
    }
    user["open_bets"].append(bet)
    user["steel_balance"] = bal - stake
    user["transactions"].append({
        "type": "bet",
        "steel_amount": -stake,
        "timestamp": datetime.utcnow().isoformat(),
        "note": label or f"{selection} {market}",
    })
    users[uname] = user
    save_users(users)
    return True, f"Bet placed: {stake} Steel on {selection.upper()} ({market}). Balance: {user['steel_balance']}"

def settle_user_bets():
    # Placeholder — real settlement would use final scores
    pass

def render_prop_bet_ui(prop, key_prefix, use_expander=True):
    """Place Steel on a single player prop Over/Under."""
    def _body():
        if not st.session_state.get("authenticated"):
            st.warning("Log in via Profile to place Steel bets on props.")
            return
        bal = get_current_profile().get("steel_balance", 0) if get_current_profile() else 0
        st.caption(f"Available: {bal} Steel · Line: {prop.get('line')}")
        side = st.radio(
            "Side",
            ["over", "under"],
            key=f"{key_prefix}_side",
            format_func=lambda x: f"OVER {prop.get('line')} ({prop.get('over', -110)})" if x == "over" else f"UNDER {prop.get('line')} ({prop.get('under', -110)})",
            horizontal=True,
        )
        odds_val = prop.get("over", -110) if side == "over" else prop.get("under", -110)
        stake = st.selectbox("Stake (Steel)", STEEL_STAKE_OPTIONS, index=1, key=f"{key_prefix}_stake")
        try:
            profit = american_to_profit(stake, odds_val)
            st.write(f"To win: **{profit}** Steel")
        except Exception:
            profit = 0
        if st.button("Confirm Prop Bet", key=f"{key_prefix}_btn"):
            label = f"{prop.get('player')} {prop.get('market')} {side.upper()} {prop.get('line')}"
            ok, msg = place_steel_bet(
                game_id=prop.get("game", "prop"),
                away="",
                home="",
                market=prop.get("market", "prop"),
                selection=side,
                line=prop.get("line"),
                odds=odds_val,
                stake=stake,
                label=label,
                market_type="prop",
                player=prop.get("player"),
            )
            if ok:
                st.success(msg)
                st.rerun()
            else:
                st.error(msg)
    if use_expander:
        with st.expander(f"⚙️ Bet Steel — {prop.get('player')} {prop.get('market')}"):
            _body()
    else:
        _body()

if "authenticated" not in st.session_state:
    st.session_state.authenticated = False
if "username" not in st.session_state:
    st.session_state.username = None

if st.session_state.authenticated:
    settle_user_bets()

profile = get_current_profile()
display_name = None
steel_balance = 0
if profile:
    display_name = profile.get("display_name", st.session_state.username)
    steel_balance = profile.get("steel_balance", 0)

# Header
st.title("🎯 FADE MACHINE")
st.caption("NFL Trends • Odds • Props • Fantasy Rankings • Steel Bets")

if st.session_state.authenticated:
    st.markdown(
        f"""<div class='steel-balance-bar'>
        <div class='steel-label'>Steel Balance</div>
        <div class='steel-amount'>{steel_balance}</div>
        </div>""",
        unsafe_allow_html=True,
    )

# Live odds / props helpers (simplified for recovery)
def fetch_live_props():
    return []

live_props = fetch_live_props()
props_source = "live" if live_props else "sample"
ALL_PROPS = live_props if live_props else SAMPLE_PLAYER_PROPS

tab1, tab2, tab3, tab4, tab5, tab6, tab7, tab8, tab9 = st.tabs([
    "📡 Live Odds", "📊 Results", "🏈 Preseason", "📈 Trends",
    "🏈 Props", "🏆 Fantasy", "📰 Headlines", "🧾 My Bets", "👤 Profile"
])

with tab1:
    st.header("📡 Live Odds")
    st.caption("Odds boards load when books open. Sample data shown in preseason.")
    st.info("Connect The Odds API key in secrets for live moneyline / spread / total boards.")

with tab2:
    st.header("📊 Results")
    for g in COMPLETED_GAMES:
        st.subheader(g["label"])
        st.metric("Final", f"{g['away']} {g['away_score']} — {g['home']} {g['home_score']}")
        st.caption(g.get("notes", ""))

with tab3:
    st.header("🏈 Preseason")
    st.caption("Props & fantasy tabs use sample lines until books post full boards.")
    st.write("HOF Game data is archived under Results.")

with tab4:
    st.header("📈 Trends")
    st.caption("Season-long and weekly trend snapshots")
    st.write("• HOF Game: Panthers 33, Cardinals 30 (Haynes King walk-off)")
    st.write("• Fantasy rankings update from season-long futures JSON")

with tab5:
    st.header("🏈 Player Prop Bets")
    st.caption(f"Source: {'Live Odds API' if props_source == 'live' else 'Sample / illustrative lines (preseason)'} · Place Steel on Over/Under")

    markets = sorted(set(p["market"] for p in ALL_PROPS))
    positions = sorted(set(p.get("pos", "") for p in ALL_PROPS if p.get("pos")))
    f1, f2, f3 = st.columns(3)
    with f1:
        mkt_filter = st.multiselect("Market", markets, default=markets, key="prop_mkt")
    with f2:
        pos_filter = st.multiselect("Position", positions if positions else ["QB", "RB", "WR", "TE"],
                                    default=positions if positions else ["QB", "RB", "WR", "TE"], key="prop_pos")
    with f3:
        search = st.text_input("Search player", "", key="prop_search")

    filtered = []
    for p in ALL_PROPS:
        if mkt_filter and p["market"] not in mkt_filter:
            continue
        if pos_filter and p.get("pos") and p["pos"] not in pos_filter:
            continue
        if search and search.lower() not in p["player"].lower():
            continue
        filtered.append(p)

    if not filtered:
        st.warning("No props match filters. Live props may be limited in preseason.")
    else:
        st.markdown("### Prop cards")
        for i, p in enumerate(filtered):
            summary = f"**{p['player']}** · {p.get('pos','')} · {p['market']} · **{p['line']}**  |  O {p.get('over','—')} / U {p.get('under','—')}"
            with st.expander(summary, expanded=False):
                st.caption(f"{p.get('team','')} · {p.get('game','')}")
                render_prop_bet_ui(p, f"propbet_{i}", use_expander=False)

with tab6:
    # Advanced season-long models + rank-by-prop (see fantasy_models.py)
    render_fantasy_tab(ALL_PROPS)

with tab7:
    st.header("📰 Preseason Headlines")
    st.write("""
    - **FINAL:** Panthers 33, Cardinals 30 (Haynes King walk-off TD) — HOF Game Aug 6
    - Fantasy rankings powered by season-long futures lines
    - Steel betting live on player props
    """)

with tab8:
    st.header("🧾 My Bets")
    if not st.session_state.authenticated:
        st.warning("Log in on the Profile tab to see open and settled bets.")
    else:
        current = get_current_profile()
        open_sub, settled_sub = st.tabs(["Open Bets", "Settled History"])
        with open_sub:
            opens = current.get("open_bets", []) if current else []
            if not opens:
                st.caption("No open bets.")
            else:
                st.dataframe(pd.DataFrame(opens), use_container_width=True, hide_index=True)
        with settled_sub:
            settled = current.get("settled_bets", []) if current else []
            if not settled:
                st.caption("No settled bets yet.")
            else:
                st.dataframe(pd.DataFrame(settled), use_container_width=True, hide_index=True)

with tab9:
    st.header("👤 Profile")
    if not st.session_state.authenticated:
        login_tab, register_tab = st.tabs(["Login", "Create Account"])
        with login_tab:
            u = st.text_input("Username", key="login_u")
            p = st.text_input("Password", type="password", key="login_p")
            if st.button("Log in"):
                ok, msg = login_user(u, p)
                if ok:
                    st.success(msg)
                    st.rerun()
                else:
                    st.error(msg)
        with register_tab:
            nu = st.text_input("New username", key="reg_u")
            npw = st.text_input("New password", type="password", key="reg_p")
            nd = st.text_input("Display name (optional)", key="reg_d")
            if st.button("Create account"):
                ok, msg = register_user(nu, npw, nd)
                if ok:
                    st.success(msg)
                else:
                    st.error(msg)
    else:
        current = get_current_profile()
        st.success(f"Logged in as **{display_name}**")
        st.metric("Steel Balance", steel_balance)
        sub_account, sub_buy, sub_history = st.tabs(["Account", "Buy Steel", "Transaction History"])
        with sub_account:
            st.write(f"Username: `{st.session_state.username}`")
            if st.button("Log out"):
                st.session_state.authenticated = False
                st.session_state.username = None
                st.rerun()
        with sub_buy:
            pack_amount = st.selectbox("Steel pack",
                                       STEEL_STAKE_OPTIONS,
                                       format_func=lambda x: f"{x} Steel — ${x * STEEL_PRICE_USD:.2f}")
            if st.button(f"Purchase {pack_amount} Steel", type="primary"):
                ok, msg = purchase_steel(pack_amount)
                st.success(msg) if ok else st.error(msg)
                if ok:
                    st.rerun()
        with sub_history:
            txs = current.get("transactions", []) if current else []
            if not txs:
                st.caption("No transactions.")
            else:
                st.dataframe(pd.DataFrame([{
                    "Date": str(t.get("timestamp", ""))[:16],
                    "Type": str(t.get("type", "")).replace("_", " ").title(),
                    "Steel": t.get("steel_amount"),
                    "Note": t.get("note", "")
                } for t in txs]), use_container_width=True, hide_index=True)

st.markdown("---")
st.caption("FADE MACHINE • Season-long futures • Rank by prop • Prop Steel bets • Advanced fantasy models")
