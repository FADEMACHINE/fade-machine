import streamlit as st
import pandas as pd
import requests
from datetime import datetime
import bcrypt
import json
import os

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
        border: 1.5px solid #e10600 !important; border-radius: 10px !important;
        background-color: rgba(225, 6, 0, 0.12) !important; margin-top: 8px; margin-bottom: 16px;
    }
    div[data-testid="stExpander"] summary,
    div[data-testid="stExpander"] summary span,
    div[data-testid="stExpander"] summary p { color: #ff4d4d !important; font-weight: 600 !important; font-size: 0.95rem !important; }
    div[data-testid="stExpander"] svg { fill: #e10600 !important; }
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

TEAM_HISTORY = {
    "Arizona Cardinals": {"ats": "44-42-0", "cover_pct": 51.2, "home_ats": "20-23", "away_ats": "24-19", "fav_ats": "12-18", "dog_ats": "32-24", "ou": "~51% Over", "note": "Better as underdog"},
    "Atlanta Falcons": {"ats": "34-48-3", "cover_pct": 41.5, "home_ats": "16-24", "away_ats": "18-24", "fav_ats": "10-20", "dog_ats": "24-28", "ou": "Slight Under lean", "note": "Weak ATS overall"},
    "Baltimore Ravens": {"ats": "45-43-2", "cover_pct": 51.1, "home_ats": "24-20", "away_ats": "21-23", "fav_ats": "28-30", "dog_ats": "17-13", "ou": "Over-lean recent years", "note": "Solid as underdog"},
    "Buffalo Bills": {"ats": "47-45-3", "cover_pct": 51.1, "home_ats": "26-20", "away_ats": "21-25", "fav_ats": "32-35", "dog_ats": "15-10", "ou": "Slight Over lean", "note": "Strong home favorite"},
    "Carolina Panthers": {"ats": "37-47-2", "cover_pct": 44.1, "home_ats": "18-24", "away_ats": "19-23", "fav_ats": "8-16", "dog_ats": "29-31", "ou": "Slight Over lean", "note": "Better as underdog"},
    "Chicago Bears": {"ats": "39-43-5", "cover_pct": 47.6, "home_ats": "20-21", "away_ats": "19-22", "fav_ats": "12-18", "dog_ats": "27-25", "ou": "Slight Under lean", "note": "Middle of the pack"},
    "Cincinnati Bengals": {"ats": "52-37-2", "cover_pct": 58.4, "home_ats": "28-17", "away_ats": "24-20", "fav_ats": "30-25", "dog_ats": "22-12", "ou": "Over lean", "note": "Strong ATS team"},
    "Cleveland Browns": {"ats": "37-48-1", "cover_pct": 43.5, "home_ats": "20-22", "away_ats": "17-26", "fav_ats": "10-18", "dog_ats": "27-30", "ou": "Near even", "note": "Struggled ATS"},
    "Dallas Cowboys": {"ats": "48-41-0", "cover_pct": 53.9, "home_ats": "26-18", "away_ats": "22-23", "fav_ats": "30-28", "dog_ats": "18-13", "ou": "Strong Over lean recently", "note": "Above average"},
    "Denver Broncos": {"ats": "42-44-2", "cover_pct": 48.8, "home_ats": "23-20", "away_ats": "19-24", "fav_ats": "18-22", "dog_ats": "24-22", "ou": "Near even", "note": "Average ATS"},
    "Detroit Lions": {"ats": "57-32-0", "cover_pct": 64.0, "home_ats": "30-14", "away_ats": "27-18", "fav_ats": "35-22", "dog_ats": "22-10", "ou": "Over lean", "note": "Best ATS team since 2021"},
    "Green Bay Packers": {"ats": "47-43-0", "cover_pct": 52.2, "home_ats": "25-20", "away_ats": "22-23", "fav_ats": "28-26", "dog_ats": "19-17", "ou": "Near even", "note": "Slightly above average"},
    "Houston Texans": {"ats": "45-43-3", "cover_pct": 51.1, "home_ats": "24-20", "away_ats": "21-23", "fav_ats": "18-20", "dog_ats": "27-23", "ou": "Under lean recently", "note": "Average cover rate"},
    "Indianapolis Colts": {"ats": "42-41-2", "cover_pct": 50.6, "home_ats": "22-20", "away_ats": "20-21", "fav_ats": "18-20", "dog_ats": "24-21", "ou": "Slight Over lean", "note": "Right at league average"},
    "Jacksonville Jaguars": {"ats": "45-42-1", "cover_pct": 51.7, "home_ats": "24-20", "away_ats": "21-22", "fav_ats": "16-18", "dog_ats": "29-24", "ou": "Slight Over lean", "note": "Slightly above average"},
    "Kansas City Chiefs": {"ats": "46-49-3", "cover_pct": 48.4, "home_ats": "25-22", "away_ats": "21-27", "fav_ats": "38-42", "dog_ats": "8-7", "ou": "Strong Under lean", "note": "Often heavy favorites"},
    "Las Vegas Raiders": {"ats": "40-44-2", "cover_pct": 47.6, "home_ats": "20-22", "away_ats": "20-22", "fav_ats": "12-16", "dog_ats": "28-28", "ou": "Near even", "note": "Slightly below average"},
    "Los Angeles Chargers": {"ats": "45-41-2", "cover_pct": 52.3, "home_ats": "23-20", "away_ats": "22-21", "fav_ats": "22-22", "dog_ats": "23-19", "ou": "Under lean recently", "note": "Slightly above average"},
    "Los Angeles Rams": {"ats": "50-42-3", "cover_pct": 54.4, "home_ats": "26-20", "away_ats": "24-22", "fav_ats": "28-26", "dog_ats": "22-16", "ou": "Near even", "note": "Consistently solid ATS"},
    "Miami Dolphins": {"ats": "44-42-1", "cover_pct": 51.2, "home_ats": "24-19", "away_ats": "20-23", "fav_ats": "22-24", "dog_ats": "22-18", "ou": "Near even", "note": "Average cover rate"},
    "Minnesota Vikings": {"ats": "42-40-5", "cover_pct": 51.2, "home_ats": "20-22", "away_ats": "22-18", "fav_ats": "20-22", "dog_ats": "22-18", "ou": "Under lean recently", "note": "Near average"},
    "New England Patriots": {"ats": "42-44-4", "cover_pct": 48.8, "home_ats": "22-22", "away_ats": "20-22", "fav_ats": "16-20", "dog_ats": "26-24", "ou": "Slight Over lean", "note": "Average since 2021"},
    "New Orleans Saints": {"ats": "38-46-1", "cover_pct": 45.2, "home_ats": "20-22", "away_ats": "18-24", "fav_ats": "16-24", "dog_ats": "22-22", "ou": "Strong Under lean", "note": "Below-average ATS"},
    "New York Giants": {"ats": "42-44-1", "cover_pct": 48.8, "home_ats": "22-21", "away_ats": "20-23", "fav_ats": "10-14", "dog_ats": "32-30", "ou": "Under lean", "note": "Average to slightly below"},
    "New York Jets": {"ats": "33-50-2", "cover_pct": 39.8, "home_ats": "16-26", "away_ats": "17-24", "fav_ats": "8-16", "dog_ats": "25-34", "ou": "Over lean recently", "note": "One of the weakest ATS teams"},
    "Philadelphia Eagles": {"ats": "49-43-3", "cover_pct": 53.3, "home_ats": "26-20", "away_ats": "23-23", "fav_ats": "32-30", "dog_ats": "17-13", "ou": "Slight Under lean", "note": "Consistently above average"},
    "Pittsburgh Steelers": {"ats": "48-40-1", "cover_pct": 54.6, "home_ats": "26-18", "away_ats": "22-22", "fav_ats": "22-22", "dog_ats": "26-18", "ou": "Slight Under lean", "note": "Strong ATS track record"},
    "San Francisco 49ers": {"ats": "50-45-1", "cover_pct": 52.6, "home_ats": "27-20", "away_ats": "23-25", "fav_ats": "32-32", "dog_ats": "18-13", "ou": "Slight Over lean", "note": "Solid cover rate"},
    "Seattle Seahawks": {"ats": "45-41-3", "cover_pct": 52.3, "home_ats": "24-20", "away_ats": "21-21", "fav_ats": "22-22", "dog_ats": "23-19", "ou": "Near even", "note": "Slightly above average"},
    "Tampa Bay Buccaneers": {"ats": "41-49-1", "cover_pct": 45.6, "home_ats": "22-23", "away_ats": "19-26", "fav_ats": "20-28", "dog_ats": "21-21", "ou": "Slight Over lean", "note": "Below-average ATS"},
    "Tennessee Titans": {"ats": "35-48-3", "cover_pct": 42.2, "home_ats": "18-24", "away_ats": "17-24", "fav_ats": "10-18", "dog_ats": "25-30", "ou": "Over lean recently", "note": "Weak ATS since 2021"},
    "Washington Commanders": {"ats": "40-44-4", "cover_pct": 47.6, "home_ats": "20-22", "away_ats": "20-22", "fav_ats": "14-18", "dog_ats": "26-26", "ou": "Over lean recently", "note": "Slightly below average"},
}

# =====================================================
# PLAYER PROPS + FANTASY (sample fallback for preseason)
# Lines used as projected values for fantasy scoring
# =====================================================
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

# Half-PPR fantasy scoring
FANTASY_SCORING = {
    "Pass Yds": 0.04,      # 1 pt / 25 yds
    "Pass TDs": 4.0,
    "Rush Yds": 0.1,       # 1 pt / 10 yds
    "Rush TDs": 6.0,
    "Rec Yds": 0.1,
    "Receptions": 0.5,     # half-PPR
    "Rec TDs": 6.0,
}

STEEL_PRICE_USD = 1.00
STEEL_PACK_OPTIONS = [1, 5, 10, 25, 50, 100, 500, 1000]
STEEL_STAKE_OPTIONS = [1, 5, 10, 25, 50]
USERS_DB_PATH = "users_db.json"

def load_users_db():
    try:
        if os.path.exists(USERS_DB_PATH):
            with open(USERS_DB_PATH, "r") as f:
                return json.load(f)
    except Exception:
        pass
    return {}

def save_users_db(users):
    try:
        with open(USERS_DB_PATH, "w") as f:
            json.dump(users, f, indent=2)
        return True
    except Exception:
        return False

if "users_db" not in st.session_state:
    st.session_state.users_db = load_users_db()
if "authenticated" not in st.session_state:
    st.session_state.authenticated = False
if "current_user" not in st.session_state:
    st.session_state.current_user = None

def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()

def check_password(password: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(password.encode(), hashed.encode())
    except Exception:
        return False

def ensure_user_fields(user):
    if "steel_balance" not in user:
        user["steel_balance"] = 0
    if "transactions" not in user:
        user["transactions"] = []
    if "open_bets" not in user:
        user["open_bets"] = []
    if "settled_bets" not in user:
        user["settled_bets"] = []
    return user

def register_user(username, password, display_name):
    username = username.strip().lower()
    if not username or not password:
        return False, "Username and password are required."
    if username in st.session_state.users_db:
        return False, "Username already exists."
    if len(password) < 4:
        return False, "Password must be at least 4 characters."
    st.session_state.users_db[username] = {
        "password_hash": hash_password(password),
        "display_name": display_name.strip() or username,
        "favorite_teams": [],
        "preferred_book": "DraftKings",
        "steel_balance": 0,
        "transactions": [],
        "open_bets": [],
        "settled_bets": [],
        "created_at": datetime.now().isoformat()
    }
    save_users_db(st.session_state.users_db)
    return True, "Account created! Log in from Profile to buy Steel and place bets."

def login_user(username, password):
    username = username.strip().lower()
    st.session_state.users_db = load_users_db()
    user = st.session_state.users_db.get(username)
    if not user:
        return False, "User not found. Create an account first."
    if not check_password(password, user["password_hash"]):
        return False, "Incorrect password."
    st.session_state.users_db[username] = ensure_user_fields(user)
    save_users_db(st.session_state.users_db)
    st.session_state.authenticated = True
    st.session_state.current_user = username
    return True, "Login successful."

def logout_user():
    st.session_state.authenticated = False
    st.session_state.current_user = None

def get_current_profile():
    if not st.session_state.current_user:
        return None
    user = st.session_state.users_db.get(st.session_state.current_user)
    if user:
        user = ensure_user_fields(user)
        st.session_state.users_db[st.session_state.current_user] = user
    return user

def update_profile(display_name, favorite_teams, preferred_book):
    username = st.session_state.current_user
    if username and username in st.session_state.users_db:
        st.session_state.users_db[username]["display_name"] = display_name
        st.session_state.users_db[username]["favorite_teams"] = favorite_teams
        st.session_state.users_db[username]["preferred_book"] = preferred_book
        save_users_db(st.session_state.users_db)
        return True
    return False

def purchase_steel(amount):
    username = st.session_state.current_user
    if not username or username not in st.session_state.users_db:
        return False, "You must be logged in to buy Steel."
    if amount not in STEEL_PACK_OPTIONS:
        return False, "Invalid pack size."
    user = ensure_user_fields(st.session_state.users_db[username])
    cost = round(amount * STEEL_PRICE_USD, 2)
    user["steel_balance"] = user.get("steel_balance", 0) + amount
    tx = {
        "id": f"tx_{datetime.now().strftime('%Y%m%d%H%M%S')}_{amount}",
        "type": "purchase",
        "steel_amount": amount,
        "usd_cost": cost,
        "status": "completed",
        "note": f"Purchased {amount} Steel pack",
        "timestamp": datetime.now().isoformat()
    }
    user["transactions"] = user.get("transactions", [])
    user["transactions"].insert(0, tx)
    st.session_state.users_db[username] = user
    save_users_db(st.session_state.users_db)
    return True, f"Added {amount} Steel! Balance: {user['steel_balance']}"

def american_to_profit(stake, odds):
    try:
        odds = float(odds)
    except (TypeError, ValueError):
        odds = -110
    if odds >= 0:
        return round(stake * (odds / 100.0), 2)
    return round(stake * (100.0 / abs(odds)), 2)

def place_steel_bet(game_id, away, home, market, selection, line, odds, stake, label=""):
    username = st.session_state.current_user
    if not username or username not in st.session_state.users_db:
        return False, "Log in to place bets."
    try:
        stake = int(stake)
    except (TypeError, ValueError):
        return False, "Invalid stake."
    if stake not in STEEL_STAKE_OPTIONS:
        return False, "Stake must be 1, 5, 10, 25, or 50 Steel."
    user = ensure_user_fields(st.session_state.users_db[username])
    bal = user.get("steel_balance", 0)
    if stake > bal:
        return False, f"Insufficient Steel. Balance: {bal}"
    profit = american_to_profit(stake, odds)
    bet = {
        "id": f"bet_{datetime.now().strftime('%Y%m%d%H%M%S')}_{stake}",
        "game_id": game_id,
        "label": label or f"{short_name(away)} @ {short_name(home)}",
        "away": away,
        "home": home,
        "market": market,
        "selection": selection,
        "line": line,
        "odds": odds,
        "stake": stake,
        "to_win": profit,
        "status": "open",
        "steel_result": 0,
        "placed_at": datetime.now().isoformat(),
        "settled_at": None,
        "market_type": "fixed",
    }
    user["steel_balance"] = bal - stake
    user["open_bets"].insert(0, bet)
    user["transactions"].insert(0, {
        "id": f"tx_bet_{bet['id']}",
        "type": "bet_stake",
        "steel_amount": -stake,
        "usd_cost": 0,
        "status": "completed",
        "note": f"Bet {stake} Steel on {bet['label']} ({market}/{selection})",
        "timestamp": datetime.now().isoformat()
    })
    st.session_state.users_db[username] = user
    save_users_db(st.session_state.users_db)
    return True, f"Bet placed: {stake} Steel on {selection.upper()} ({market}). Balance: {user['steel_balance']}"

def _match_completed_game(bet):
    for g in COMPLETED_GAMES:
        if bet.get("game_id") == g["id"]:
            return g
        if bet.get("away") == g["away"] and bet.get("home") == g["home"]:
            return g
    return None

def _resolve_bet_result(bet, game):
    away_score = game["away_score"]
    home_score = game["home_score"]
    margin = away_score - home_score
    total_pts = away_score + home_score
    market = bet["market"]
    selection = bet["selection"]
    try:
        line = float(bet.get("line") if bet.get("line") not in (None, "", "—") else 0)
    except (TypeError, ValueError):
        line = 0.0
    if market == "spread":
        diff = (margin + line) if selection == "away" else ((-margin) + line)
        if abs(diff) < 1e-9:
            return "push"
        return "won" if diff > 0 else "lost"
    if market == "total":
        if selection == "over":
            if total_pts > line: return "won"
            if total_pts < line: return "lost"
            return "push"
        if total_pts < line: return "won"
        if total_pts > line: return "lost"
        return "push"
    if market == "ml":
        if away_score == home_score: return "push"
        if selection == "away":
            return "won" if away_score > home_score else "lost"
        return "won" if home_score > away_score else "lost"
    return "lost"

def settle_user_bets():
    username = st.session_state.current_user
    if not username or username not in st.session_state.users_db:
        return 0
    user = ensure_user_fields(st.session_state.users_db[username])
    still_open = []
    settled_count = 0
    for bet in user.get("open_bets", []):
        game = _match_completed_game(bet)
        if not game:
            still_open.append(bet)
            continue
        result = _resolve_bet_result(bet, game)
        stake = bet.get("stake", 0)
        to_win = bet.get("to_win", 0)
        if result == "won":
            user["steel_balance"] = user.get("steel_balance", 0) + stake + to_win
            bet["status"] = "won"
            bet["steel_result"] = to_win
            note = f"WON +{to_win} Steel on {bet.get('label')}"
        elif result == "push":
            user["steel_balance"] = user.get("steel_balance", 0) + stake
            bet["status"] = "push"
            bet["steel_result"] = 0
            note = f"PUSH — stake returned on {bet.get('label')}"
        else:
            bet["status"] = "lost"
            bet["steel_result"] = -stake
            note = f"LOST -{stake} Steel on {bet.get('label')}"
        bet["settled_at"] = datetime.now().isoformat()
        user["settled_bets"].insert(0, bet)
        user["transactions"].insert(0, {
            "id": f"tx_settle_{bet['id']}",
            "type": f"bet_{bet['status']}",
            "steel_amount": bet["steel_result"] if result != "push" else 0,
            "usd_cost": 0,
            "status": "completed",
            "note": note,
            "timestamp": datetime.now().isoformat()
        })
        settled_count += 1
    user["open_bets"] = still_open
    st.session_state.users_db[username] = user
    save_users_db(st.session_state.users_db)
    return settled_count

def get_bankroll_stats(user):
    settled = user.get("settled_bets", [])
    open_bets = user.get("open_bets", [])
    settled_staked = sum(b.get("stake", 0) for b in settled)
    net_pnl = sum(b.get("steel_result", 0) for b in settled)
    wins = sum(1 for b in settled if b.get("status") == "won")
    losses = sum(1 for b in settled if b.get("status") == "lost")
    pushes = sum(1 for b in settled if b.get("status") == "push")
    decided = wins + losses
    win_rate = round((wins / decided) * 100, 1) if decided else 0.0
    roi = round((net_pnl / settled_staked) * 100, 1) if settled_staked else 0.0
    return {
        "balance": user.get("steel_balance", 0),
        "open_exposure": sum(b.get("stake", 0) for b in open_bets),
        "net_pnl": net_pnl,
        "wins": wins, "losses": losses, "pushes": pushes,
        "win_rate": win_rate, "roi": roi,
        "open_count": len(open_bets), "settled_count": len(settled),
    }

def get_team_history(team_name):
    if team_name in TEAM_HISTORY:
        return TEAM_HISTORY[team_name]
    for key, val in TEAM_HISTORY.items():
        if team_name.lower() in key.lower() or key.lower() in team_name.lower():
            return val
    return None

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
    return mapping.get(full, full[:3].upper() if full else "???")

def evaluate_bets(game):
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

def calc_fantasy_points(player_props_group, scoring=None):
    """Sum projected fantasy pts from prop lines (line = projection). Half-PPR default."""
    scoring = scoring or FANTASY_SCORING
    pts = 0.0
    breakdown = {}
    for p in player_props_group:
        mkt = p.get("market", "")
        line = p.get("line")
        if mkt not in scoring or line is None:
            continue
        try:
            val = float(line)
        except (TypeError, ValueError):
            continue
        contrib = round(val * scoring[mkt], 2)
        breakdown[mkt] = breakdown.get(mkt, 0) + contrib
        pts += contrib
    return round(pts, 2), breakdown

def build_fantasy_rankings(props_list):
    """Group props by player and rank by projected fantasy points."""
    by_player = {}
    for p in props_list:
        key = p.get("player", "Unknown")
        if key not in by_player:
            by_player[key] = {
                "player": key,
                "team": p.get("team", ""),
                "pos": p.get("pos", ""),
                "game": p.get("game", ""),
                "props": [],
            }
        by_player[key]["props"].append(p)
        if not by_player[key]["pos"] and p.get("pos"):
            by_player[key]["pos"] = p["pos"]
        if not by_player[key]["team"] and p.get("team"):
            by_player[key]["team"] = p["team"]

    rows = []
    for name, data in by_player.items():
        pts, breakdown = calc_fantasy_points(data["props"])
        rows.append({
            "Player": name,
            "Team": data["team"],
            "Pos": data["pos"] or "—",
            "Proj Pts": pts,
            "Pass Yds": next((p["line"] for p in data["props"] if p["market"] == "Pass Yds"), None),
            "Pass TDs": next((p["line"] for p in data["props"] if p["market"] == "Pass TDs"), None),
            "Rush Yds": next((p["line"] for p in data["props"] if p["market"] == "Rush Yds"), None),
            "Rush TDs": next((p["line"] for p in data["props"] if p["market"] == "Rush TDs"), None),
            "Rec": next((p["line"] for p in data["props"] if p["market"] == "Receptions"), None),
            "Rec Yds": next((p["line"] for p in data["props"] if p["market"] == "Rec Yds"), None),
            "Rec TDs": next((p["line"] for p in data["props"] if p["market"] == "Rec TDs"), None),
            "Game": data["game"],
        })
    df = pd.DataFrame(rows)
    if not df.empty:
        df = df.sort_values("Proj Pts", ascending=False).reset_index(drop=True)
        df.insert(0, "Rank", range(1, len(df) + 1))
    return df

def render_odds_card(odds, show_trends_button=True):
    if not odds:
        st.caption("No odds available.")
        return
    away_abbr = short_name(odds["away"])
    home_abbr = short_name(odds["home"])
    away_name, home_name = odds["away"], odds["home"]
    card_html = f'''
<div style="border:1.5px solid #ffffff; border-radius:12px; padding:14px; margin-bottom:10px; background-color:#141414;">
  <div style="display:flex; margin-bottom:10px; color:#888; font-size:0.68rem;">
    <div style="flex:3;">TEAM</div><div style="flex:2; text-align:center;">SPREAD</div>
    <div style="flex:2; text-align:center;">TOTAL</div><div style="flex:2; text-align:center;">ML</div>
  </div>
  <div style="display:flex; align-items:center; margin-bottom:12px;">
    <div style="flex:3;"><div style="font-weight:700; color:#fff;">{away_abbr}</div><div style="font-size:0.72rem; color:#aaa;">{away_name}</div></div>
    <div style="flex:2; text-align:center;"><div style="font-weight:700; color:#fff;">{odds["away_spread"]}</div><div style="font-size:0.72rem; color:#aaa;">{odds["away_spread_odds"]}</div></div>
    <div style="flex:2; text-align:center;"><div style="font-weight:700; color:#fff;">O {odds["total"]}</div><div style="font-size:0.72rem; color:#aaa;">{odds["over_odds"]}</div></div>
    <div style="flex:2; text-align:center;"><div style="font-weight:700; color:#fff;">{odds["away_ml"]}</div></div>
  </div>
  <div style="display:flex; align-items:center;">
    <div style="flex:3;"><div style="font-weight:700; color:#fff;">{home_abbr}</div><div style="font-size:0.72rem; color:#aaa;">{home_name}</div></div>
    <div style="flex:2; text-align:center;"><div style="font-weight:700; color:#fff;">{odds["home_spread"]}</div><div style="font-size:0.72rem; color:#aaa;">{odds["home_spread_odds"]}</div></div>
    <div style="flex:2; text-align:center;"><div style="font-weight:700; color:#fff;">U {odds["total"]}</div><div style="font-size:0.72rem; color:#aaa;">{odds["under_odds"]}</div></div>
    <div style="flex:2; text-align:center;"><div style="font-weight:700; color:#fff;">{odds["home_ml"]}</div></div>
  </div>
</div>'''
    st.markdown(card_html, unsafe_allow_html=True)
    if show_trends_button:
        with st.expander("🔍 Dive deeper — Analytical trends"):
            away_hist = get_team_history(away_name)
            home_hist = get_team_history(home_name)
            col_a, col_b = st.columns(2)
            with col_a:
                st.markdown(f"**{away_abbr}**")
                if away_hist:
                    st.write(f"Overall: **{away_hist['ats']}** ({away_hist['cover_pct']}%)")
                    st.write(f"Away: {away_hist.get('away_ats', '—')} · Dog: {away_hist.get('dog_ats', '—')}")
            with col_b:
                st.markdown(f"**{home_abbr}**")
                if home_hist:
                    st.write(f"Overall: **{home_hist['ats']}** ({home_hist['cover_pct']}%)")
                    st.write(f"Home: {home_hist.get('home_ats', '—')} · Fav: {home_hist.get('fav_ats', '—')}")

def render_place_bet_ui(odds, game_id, key_prefix):
    if not odds:
        return
    with st.expander("⚙️ Place Steel Bet"):
        if not st.session_state.authenticated:
            st.warning("Log in via Profile to place Steel bets.")
            return
        bal = get_current_profile().get("steel_balance", 0) if get_current_profile() else 0
        st.caption(f"Available: {bal} Steel")
        market = st.selectbox("Market", ["spread", "total", "ml"], key=f"{key_prefix}_mkt",
                              format_func=lambda x: {"spread": "Spread", "total": "Total", "ml": "Moneyline"}[x])
        if market == "spread":
            sel = st.radio("Side", ["away", "home"], key=f"{key_prefix}_sel",
                           format_func=lambda x: f"{short_name(odds['away'])} {odds['away_spread']}" if x == "away" else f"{short_name(odds['home'])} {odds['home_spread']}")
            line = odds["away_spread"] if sel == "away" else odds["home_spread"]
            odds_val = odds["away_spread_odds"] if sel == "away" else odds["home_spread_odds"]
        elif market == "total":
            sel = st.radio("Side", ["over", "under"], key=f"{key_prefix}_sel",
                           format_func=lambda x: f"Over {odds['total']}" if x == "over" else f"Under {odds['total']}")
            line = odds["total"]
            odds_val = odds["over_odds"] if sel == "over" else odds["under_odds"]
        else:
            sel = st.radio("Side", ["away", "home"], key=f"{key_prefix}_sel",
                           format_func=lambda x: f"{short_name(odds['away'])} ML" if x == "away" else f"{short_name(odds['home'])} ML")
            line = 0
            odds_val = odds["away_ml"] if sel == "away" else odds["home_ml"]
        stake = st.selectbox("Stake (Steel)", STEEL_STAKE_OPTIONS, index=1, key=f"{key_prefix}_stake")
        try:
            profit = american_to_profit(stake, odds_val)
            st.write(f"To win: **{profit}** Steel")
        except Exception:
            pass
        if st.button("Confirm Bet", key=f"{key_prefix}_btn"):
            ok, msg = place_steel_bet(game_id, odds["away"], odds["home"], market, sel, line, odds_val, stake,
                                      label=f"{short_name(odds['away'])} @ {short_name(odds['home'])}")
            if ok:
                st.success(msg)
                st.rerun()
            else:
                st.error(msg)

if st.session_state.authenticated:
    settle_user_bets()

profile = get_current_profile()
display_name = None
steel_balance = 0
if profile:
    display_name = profile.get("display_name", st.session_state.current_user)
    steel_balance = profile.get("steel_balance", 0)
elif st.session_state.current_user:
    display_name = st.session_state.current_user

st.sidebar.markdown("# 🎯 FADE MACHINE")
if display_name:
    st.sidebar.markdown(f"**Welcome, {display_name}**")
    st.sidebar.markdown(f"⚙️ **Steel: {steel_balance}**")
    if st.sidebar.button("Logout"):
        logout_user()
        st.rerun()
else:
    st.sidebar.caption("Optional login available in Profile tab")

st.sidebar.markdown("---")
st.sidebar.info("Analytical / virtual Steel tool — research & education.")
st.sidebar.caption("Brand: Black • White • Grey • Red")

st.sidebar.markdown("### 🔍 Game Filter")
all_game_labels = [g["label"] for g in COMPLETED_GAMES] + ["Upcoming / Live Games"]
selected_games = st.sidebar.multiselect("Select games to view", options=all_game_labels, default=all_game_labels)

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
        "apiKey": api_key, "regions": "us", "markets": "h2h,spreads,totals",
        "oddsFormat": "american", "bookmakers": "draftkings,fanduel,betmgm,williamhill_us,bovada"
    }
    try:
        r = requests.get(url, params=params, timeout=12)
        if r.status_code != 200:
            return None, f"API error: {r.status_code}"
        return r.json(), None
    except Exception as e:
        return None, str(e)

@st.cache_data(ttl=300)
def fetch_nfl_events(api_key):
    if not api_key:
        return [], "No API key"
    try:
        r = requests.get(
            "https://api.the-odds-api.com/v4/sports/americanfootball_nfl/events",
            params={"apiKey": api_key}, timeout=12
        )
        if r.status_code != 200:
            return [], f"Events API error: {r.status_code}"
        return r.json(), None
    except Exception as e:
        return [], str(e)

@st.cache_data(ttl=180)
def fetch_event_player_props(api_key, event_id):
    """Fetch player props for one event (quota cost applies)."""
    if not api_key or not event_id:
        return None, "Missing key or event"
    url = f"https://api.the-odds-api.com/v4/sports/americanfootball_nfl/events/{event_id}/odds"
    params = {
        "apiKey": api_key,
        "regions": "us",
        "markets": PROP_MARKET_KEYS,
        "oddsFormat": "american",
        "bookmakers": "draftkings,fanduel",
    }
    try:
        r = requests.get(url, params=params, timeout=15)
        if r.status_code != 200:
            return None, f"Props API {r.status_code}"
        return r.json(), None
    except Exception as e:
        return None, str(e)

def parse_props_from_event(event_data):
    """Flatten Odds API event props into list of prop dicts."""
    rows = []
    if not event_data:
        return rows
    away = event_data.get("away_team", "")
    home = event_data.get("home_team", "")
    game_label = f"{short_name(away)} @ {short_name(home)}"
    books = event_data.get("bookmakers", [])
    if not books:
        return rows
    book = books[0]
    for market in book.get("markets", []):
        mkey = market.get("key", "")
        label = MARKET_LABEL.get(mkey)
        if not label:
            continue
        # Group Over/Under by player description
        by_player = {}
        for o in market.get("outcomes", []):
            player = o.get("description") or o.get("name", "")
            if o.get("name") in ("Over", "Under"):
                side = o.get("name")
            else:
                continue
            if player not in by_player:
                by_player[player] = {"line": o.get("point"), "over": None, "under": None}
            by_player[player][side.lower()] = o.get("price")
            if o.get("point") is not None:
                by_player[player]["line"] = o.get("point")
        for player, vals in by_player.items():
            rows.append({
                "player": player,
                "team": "",
                "pos": "",
                "game": game_label,
                "market": label,
                "line": vals.get("line"),
                "over": vals.get("over"),
                "under": vals.get("under"),
                "book": book.get("title", ""),
            })
    return rows

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
        "away": away, "home": home,
        "away_spread": "—", "away_spread_odds": "",
        "home_spread": "—", "home_spread_odds": "",
        "away_ml": "—", "home_ml": "—",
        "total": "—", "over_odds": "", "under_odds": ""
    }
    for market in selected.get("markets", []):
        key = market.get("key")
        for o in market.get("outcomes", []):
            name, price, point = o.get("name", ""), o.get("price", ""), o.get("point", "")
            if key == "spreads":
                if name == away:
                    result["away_spread"], result["away_spread_odds"] = point, price
                elif name == home:
                    result["home_spread"], result["home_spread_odds"] = point, price
            elif key == "h2h":
                if name == away:
                    result["away_ml"] = price
                elif name == home:
                    result["home_ml"] = price
            elif key == "totals":
                if name == "Over":
                    result["total"], result["over_odds"] = point, price
                elif name == "Under":
                    result["under_odds"] = price
    return result

api_key = get_odds_api_key()
odds_data, odds_error = (None, None)
if api_key:
    odds_data, odds_error = fetch_nfl_odds(api_key)

# Player props: try live API (max 2 events to save quota), else sample
live_props = []
props_source = "sample"
if api_key:
    events, ev_err = fetch_nfl_events(api_key)
    if events:
        for ev in events[:2]:
            edata, perr = fetch_event_player_props(api_key, ev.get("id"))
            if edata:
                live_props.extend(parse_props_from_event(edata))
        if live_props:
            props_source = "live"

ALL_PROPS = live_props if live_props else SAMPLE_PLAYER_PROPS

BOOK_OPTIONS = {
    "DraftKings": "draftkings", "FanDuel": "fanduel", "BetMGM": "betmgm",
    "Caesars": "williamhill_us", "Bovada": "bovada"
}
ALL_TEAMS = sorted(list(TEAM_HISTORY.keys()))

header_left, header_right = st.columns([3, 1])
with header_left:
    st.title("🎯 FADE MACHINE")
    st.caption("NFL Trends • Odds • Props • Fantasy Rankings • Steel Bets")
with header_right:
    bal_display = steel_balance if profile else 0
    st.markdown(f"""
    <div style="display:flex; justify-content:flex-end; margin-top:12px;">
      <div class="steel-balance-bar">
        <div class="steel-label">⚙️ Steel Balance</div>
        <div class="steel-amount">{bal_display}</div>
      </div>
    </div>
    """, unsafe_allow_html=True)

tab1, tab2, tab3, tab4, tab5, tab6, tab7, tab8, tab9, tab10 = st.tabs([
    "🔴 HOF", "📈 Live Odds", "✅ Results", "📅 Preseason",
    "📊 Trends", "🏈 Props", "🏆 Fantasy", "📰 Headlines",
    "💰 My Bets", "👤 Profile"
])

with tab1:
    if "HOF Game — CAR @ ARI (Aug 6)" in selected_games:
        st.header("Hall of Fame Game — FINAL")
        st.success("### FINAL: Carolina Panthers 33 – Arizona Cardinals 30")
        st.caption("Haynes King walk-off rushing TD")
        game = COMPLETED_GAMES[0]
        results = evaluate_bets(game)
        r1, r2, r3 = st.columns(3)
        r1.metric("Spread (CAR -1.5)", results["spread"]["result"])
        r2.metric("Total (35.5)", results["total"]["result"])
        r3.metric("Moneyline (CAR)", results["ml"]["result"])
    else:
        st.info("HOF Game filtered out.")

with tab2:
    if "Upcoming / Live Games" in selected_games:
        st.header("Live Odds + Place Steel Bets")
        book_choice2 = st.selectbox("Sportsbook", list(BOOK_OPTIONS.keys()), key="live_book")
        if not api_key:
            st.warning("No ODDS_API_KEY found.")
        elif odds_error:
            st.error(odds_error)
        elif not odds_data:
            st.warning("No upcoming games returned.")
        else:
            st.success(f"{len(odds_data)} game(s) available")
            for i, g in enumerate(odds_data):
                away, home = g.get("away_team", ""), g.get("home_team", "")
                if "panther" in (away + home).lower() and "cardinal" in (away + home).lower():
                    continue
                commence = g.get("commence_time", "")
                try:
                    dt = datetime.fromisoformat(commence.replace("Z", "+00:00"))
                    time_str = dt.strftime("%a %b %d • %I:%M %p ET")
                except Exception:
                    time_str = commence
                st.markdown(f"#### {short_name(away)} @ {short_name(home)}")
                st.caption(time_str)
                odds = extract_book_odds(g, BOOK_OPTIONS.get(book_choice2))
                render_odds_card(odds)
                render_place_bet_ui(odds, f"{away}_{home}_{commence}", f"live_{i}")
    else:
        st.info("Upcoming games filtered out.")

with tab3:
    st.header("Completed Games")
    for game in COMPLETED_GAMES:
        if game["label"] in selected_games:
            st.subheader(game["label"])
            st.markdown(f"**{game['final']}**")
            results = evaluate_bets(game)
            col1, col2, col3 = st.columns(3)
            col1.markdown(f"{'🟢' if 'HIT' in results['spread']['result'] else '🔴'} **Spread** — {results['spread']['result']}")
            col2.markdown(f"{'🟢' if 'HIT' in results['total']['result'] else '🔴'} **Total** — {results['total']['result']}")
            col3.markdown(f"{'🟢' if 'HIT' in results['ml']['result'] else '🔴'} **ML** — {results['ml']['result']}")

with tab4:
    st.header("Preseason Schedule")
    st.write("HOF complete. Week 1 preseason ~ Aug 13.")
    st.caption("Props & fantasy tabs use sample lines until books post full boards.")

with tab5:
    st.header("Historical ATS Trends")
    rows = [{"Team": t, "Overall": d["ats"], "Cover %": d["cover_pct"],
             "Home": d.get("home_ats", "—"), "Away": d.get("away_ats", "—"),
             "As Fav": d.get("fav_ats", "—"), "As Dog": d.get("dog_ats", "—")} for t, d in TEAM_HISTORY.items()]
    st.dataframe(pd.DataFrame(rows).sort_values("Cover %", ascending=False), use_container_width=True, hide_index=True)

# =====================================================
# PLAYER PROPS TAB
# =====================================================
with tab6:
    st.header("🏈 Player Prop Bets")
    st.caption(f"Source: {'Live Odds API' if props_source == 'live' else 'Sample / illustrative lines (preseason)'} · O/U lines used as projections")

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
        prop_rows = []
        for p in filtered:
            prop_rows.append({
                "Player": p["player"],
                "Pos": p.get("pos", "—"),
                "Team": p.get("team", "—"),
                "Market": p["market"],
                "Line": p["line"],
                "Over": p.get("over", "—"),
                "Under": p.get("under", "—"),
                "Game": p.get("game", "—"),
            })
        st.dataframe(pd.DataFrame(prop_rows), use_container_width=True, hide_index=True)
        st.caption("Tip: Use these Over/Under lines as inputs for Fantasy rankings (next tab).")

# =====================================================
# FANTASY RANKINGS TAB
# =====================================================
with tab7:
    st.header("🏆 Fantasy Player Rankings")
    st.caption("Projected fantasy points from prop O/U lines · **Half-PPR** scoring")

    with st.expander("Scoring rules"):
        st.markdown("""
        - **Pass Yds:** 0.04 pts (1 / 25 yds)  
        - **Pass TDs:** 4 pts  
        - **Rush Yds:** 0.1 pts (1 / 10 yds)  
        - **Rush TDs:** 6 pts  
        - **Rec Yds:** 0.1 pts  
        - **Receptions:** 0.5 pts (half-PPR)  
        - **Rec TDs:** 6 pts  
        Projection = prop line value (midpoint assumption).
        """)

    scoring_mode = st.radio("Scoring", ["Half-PPR", "Full-PPR", "Standard"], horizontal=True, key="ff_scoring")
    scoring = dict(FANTASY_SCORING)
    if scoring_mode == "Full-PPR":
        scoring["Receptions"] = 1.0
    elif scoring_mode == "Standard":
        scoring["Receptions"] = 0.0

    # Rebuild rankings with selected scoring
    by_player = {}
    for p in ALL_PROPS:
        key = p.get("player", "Unknown")
        if key not in by_player:
            by_player[key] = {"player": key, "team": p.get("team", ""), "pos": p.get("pos", ""),
                              "game": p.get("game", ""), "props": []}
        by_player[key]["props"].append(p)

    rank_rows = []
    for name, data in by_player.items():
        pts = 0.0
        for pr in data["props"]:
            mkt, line = pr.get("market"), pr.get("line")
            if mkt in scoring and line is not None:
                try:
                    pts += float(line) * scoring[mkt]
                except (TypeError, ValueError):
                    pass
        rank_rows.append({
            "Player": name,
            "Team": data["team"] or "—",
            "Pos": data["pos"] or "—",
            "Proj Pts": round(pts, 2),
            "Pass Yds": next((pr["line"] for pr in data["props"] if pr["market"] == "Pass Yds"), None),
            "Pass TD": next((pr["line"] for pr in data["props"] if pr["market"] == "Pass TDs"), None),
            "Rush Yds": next((pr["line"] for pr in data["props"] if pr["market"] == "Rush Yds"), None),
            "Rush TD": next((pr["line"] for pr in data["props"] if pr["market"] == "Rush TDs"), None),
            "Rec": next((pr["line"] for pr in data["props"] if pr["market"] == "Receptions"), None),
            "Rec Yds": next((pr["line"] for pr in data["props"] if pr["market"] == "Rec Yds"), None),
            "Rec TD": next((pr["line"] for pr in data["props"] if pr["market"] == "Rec TDs"), None),
        })

    ff_df = pd.DataFrame(rank_rows)
    if ff_df.empty:
        st.warning("No player data available for rankings.")
    else:
        pos_opts = ["All"] + sorted([p for p in ff_df["Pos"].unique() if p and p != "—"])
        pos_sel = st.selectbox("Filter by position", pos_opts, key="ff_pos")
        if pos_sel != "All":
            ff_df = ff_df[ff_df["Pos"] == pos_sel]
        ff_df = ff_df.sort_values("Proj Pts", ascending=False).reset_index(drop=True)
        ff_df.insert(0, "Rank", range(1, len(ff_df) + 1))
        st.dataframe(ff_df, use_container_width=True, hide_index=True)
        st.caption(f"Ranked {len(ff_df)} players · {scoring_mode} · Lines from {props_source} props")

with tab8:
    st.header("Preseason Headlines")
    st.write("""
    - **FINAL:** Panthers 33, Cardinals 30 (Haynes King walk-off TD)
    - Preseason Week 1 ~ August 13
    - Player props & fantasy rankings use sample lines until full boards post
    """)

with tab9:
    st.header("💰 My Bets & Bankroll")
    if not (st.session_state.authenticated and get_current_profile()):
        st.warning("Log in via Profile to place bets and track bankroll.")
    else:
        user = get_current_profile()
        stats = get_bankroll_stats(user)
        m1, m2, m3, m4 = st.columns(4)
        m1.metric("Steel Balance", stats["balance"])
        m2.metric("Net P&L", f"{stats['net_pnl']:+.1f}")
        m3.metric("Win Rate", f"{stats['win_rate']}%")
        m4.metric("ROI", f"{stats['roi']}%")
        open_sub, settled_sub = st.tabs(["Open Bets", "Settled History"])
        with open_sub:
            open_bets = user.get("open_bets", [])
            if not open_bets:
                st.caption("No open bets.")
            else:
                st.dataframe(pd.DataFrame([{
                    "Game": b.get("label"), "Market": b.get("market", "").upper(),
                    "Pick": str(b.get("selection", "")).upper(), "Stake": b.get("stake"),
                    "To Win": b.get("to_win")
                } for b in open_bets]), use_container_width=True, hide_index=True)
        with settled_sub:
            settled = user.get("settled_bets", [])
            if not settled:
                st.caption("No settled bets yet.")
            else:
                st.dataframe(pd.DataFrame([{
                    "Game": b.get("label"), "Result": b.get("status", "").upper(),
                    "Steel P&L": b.get("steel_result"), "Stake": b.get("stake")
                } for b in settled]), use_container_width=True, hide_index=True)

with tab10:
    st.header("👤 Profile & Steel")
    if not (st.session_state.authenticated and get_current_profile()):
        login_tab, register_tab = st.tabs(["Login", "Create Account"])
        with login_tab:
            with st.form("login_form"):
                username = st.text_input("Username")
                password = st.text_input("Password", type="password")
                if st.form_submit_button("Login"):
                    success, msg = login_user(username, password)
                    if success:
                        st.success(msg)
                        st.rerun()
                    else:
                        st.error(msg)
        with register_tab:
            with st.form("register_form"):
                new_username = st.text_input("Choose a username")
                new_display = st.text_input("Display name (optional)")
                new_password = st.text_input("Password", type="password")
                confirm_password = st.text_input("Confirm password", type="password")
                if st.form_submit_button("Create Account"):
                    if new_password != confirm_password:
                        st.error("Passwords do not match.")
                    else:
                        success, msg = register_user(new_username, new_password, new_display)
                        st.success(msg) if success else st.error(msg)
    else:
        current = get_current_profile()
        steel_bal = current.get("steel_balance", 0)
        st.markdown(f"**⚙️ {steel_bal} Steel** · {current.get('display_name')}")
        sub_account, sub_buy, sub_history = st.tabs(["Account", "Buy Steel", "Transaction History"])
        with sub_account:
            with st.form("profile_form"):
                new_display = st.text_input("Display Name", value=current.get("display_name", ""))
                new_teams = st.multiselect("Favorite Teams", options=ALL_TEAMS, default=current.get("favorite_teams", []))
                new_book = st.selectbox("Preferred Book", list(BOOK_OPTIONS.keys()))
                if st.form_submit_button("Save"):
                    update_profile(new_display, new_teams, new_book)
                    st.success("Saved")
                    st.rerun()
            if st.button("Logout", key="profile_logout"):
                logout_user()
                st.rerun()
        with sub_buy:
            pack_amount = st.selectbox("Pack", STEEL_PACK_OPTIONS, index=1,
                                       format_func=lambda x: f"{x} Steel — ${x * STEEL_PRICE_USD:.2f}")
            if st.button(f"Purchase {pack_amount} Steel", type="primary"):
                ok, msg = purchase_steel(pack_amount)
                st.success(msg) if ok else st.error(msg)
                if ok:
                    st.rerun()
        with sub_history:
            txs = current.get("transactions", [])
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
st.caption("FADE MACHINE • Props • Fantasy (Half-PPR) • Steel bets • Bankroll tracker")
