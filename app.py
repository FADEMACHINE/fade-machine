import streamlit as st
import pandas as pd
import requests
from datetime import datetime, date, timedelta
from zoneinfo import ZoneInfo
import bcrypt
import json
import os
import time
from fantasy_models import render_fantasy_tab
# Odds math lives in bet_slips so the My Bets blending and the Betting board
# can't drift apart — one implementation, imported in both places.
from bet_slips import (
    render_my_bets_tab, fmt_odds, fmt_steel, american_to_profit,
    american_to_implied_prob, implied_prob_to_american, devig_two_way,
)
import bet_store
import matchup_trends as mtr
import user_data
import auth_store
import auth_ui
from bet_settlement import (
    fetch_scores, scores_by_game_id, grade_bet,
    steel_result_for, balance_credit_for,
)
from bet_analytics import render_bet_history_section
import content_engine
import post_studio
import cbb_tab

st.set_page_config(
    page_title="FADE MACHINE | NFL Analytics",
    page_icon="🎯",
    layout="wide",
    initial_sidebar_state="expanded"
)

st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Oswald:wght@400;500;600;700&family=Roboto+Mono:wght@400;500;600;700&display=swap');

    /* ===== Design tokens — mirrors .streamlit/config.toml so custom CSS never
       drifts from the native theme's black/silver/red system =====
       Typography: Oswald (display/impact — headers, tabs, buttons, wordmarks),
       Inter (body — set via config.toml's `font`), Roboto Mono (odds/stat
       figures — sportsbook-style tabular precision). */
    :root {
        --bg: #0a0a0a;
        --surface: #161616;
        --surface-raised: #1c1c1c;
        --border: #333336;
        --text: #f5f5f5;
        --muted: #a6a8ad;
        --muted-dim: #7d7f84;
        --accent: #e10600;
        --accent-light: #ff6b60;
        --accent-dark: #8a1c14;
        --accent-bg: #2a0806;
        --silver: #a6a8ad;
        --positive: #4ade80;
        --positive-bg: #14321f;
        --negative: #f87171;
        /* Secondary accent — echoes the molten-gold glow in the FADE MACHINE
           brand mark on X. Used sparingly for premium/highlight moments only
           (VALUE badge, hero glow) so it reads as an accent, not a second
           primary color competing with red. */
        --gold: #f0b429;
        --gold-light: #fbd97a;
        --gold-glow: rgba(240, 180, 41, 0.35);
        /* Position identity colors — pulled from the theme's own chart
           categorical palette so badges stay on-brand instead of introducing
           an unrelated rainbow of hues. */
        --pos-qb: #e10600;
        --pos-rb: #ff6b60;
        --pos-wr: #a6a8ad;
        --pos-te: #8a1c14;
        --font-display: 'Oswald', 'Inter', sans-serif;
        --font-mono: 'Roboto Mono', ui-monospace, monospace;
        --space-1: 4px; --space-2: 8px; --space-3: 12px; --space-4: 16px;
        --space-5: 24px; --space-6: 32px;
        --radius-sm: 6px; --radius-md: 10px; --radius-lg: 14px;
    }
    .stApp, [data-testid="stAppViewContainer"] {
        background-color: var(--bg) !important;
        color: var(--text) !important;
    }
    /* Deliberately excludes span/div: those tags host per-badge/per-value
       custom colors (position badges, VALUE pill, over/under, rank deltas)
       throughout Betting/Props/Fantasy. Forcing them white here with
       !important silently flattened every one of those colors — text and
       label containers still need the override to fight Streamlit's own
       inline styles, but span/div should just inherit like normal CSS. */
    body, p, label, .stMarkdown, .stText,
    [data-testid="stMarkdownContainer"],
    [data-testid="stWidgetLabel"] {
        color: var(--text) !important;
    }
    h1, h2, h3, h4, h5, h6 {
        color: var(--text) !important;
        font-family: var(--font-display) !important;
        letter-spacing: 0.3px;
    }
    [data-testid="stSidebar"] { background-color: var(--surface) !important; }
    [data-testid="stSidebar"] * { color: var(--text) !important; }

    /* ===== Tab bar: 9 tabs need to scroll, not wrap into a 3-row mess.
       flex-wrap:nowrap + overflow-x:auto turns it into one clean swipeable
       row (native scrollbar hidden, edge fade hints more content). Active
       tab is a filled pill instead of a thin underline — much easier to
       spot at a glance with this many items.
       Selectors target [data-testid="stTab"]/[role="tablist"] — this
       Streamlit version (1.61, react-aria based) does NOT use the older
       [data-baseweb="tab"] BaseWeb markup; that selector silently matched
       nothing here. ===== */
    [data-testid="stTabs"] [role="tablist"] {
        background-color: var(--surface);
        gap: 6px; flex-wrap: nowrap; overflow-x: auto; overflow-y: hidden;
        scrollbar-width: none; -ms-overflow-style: none;
        -webkit-overflow-scrolling: touch;
        padding: 4px; border-radius: var(--radius-md);
        mask-image: linear-gradient(to right, black calc(100% - 28px), transparent 100%);
        -webkit-mask-image: linear-gradient(to right, black calc(100% - 28px), transparent 100%);
    }
    [data-testid="stTabs"] [role="tablist"]::-webkit-scrollbar { display: none; }
    [data-testid="stTab"] {
        color: var(--muted) !important; padding: 10px 16px !important; font-size: 0.85rem !important;
        font-family: var(--font-display) !important; font-weight: 600 !important;
        letter-spacing: 0.4px; text-transform: uppercase;
        white-space: nowrap; flex-shrink: 0; min-height: 44px;
        border-radius: var(--radius-sm) !important; border-bottom: none !important;
        transition: background-color 150ms ease, color 150ms ease;
    }
    [data-testid="stTab"] p { font-family: var(--font-display) !important; font-weight: 600 !important; letter-spacing: 0.4px; text-transform: uppercase; }
    [data-testid="stTab"]:hover { background: rgba(255,255,255,0.06); color: var(--text) !important; }
    [data-testid="stTab"][aria-selected="true"] {
        color: #ffffff !important; background: var(--accent) !important;
        box-shadow: 0 2px 10px rgba(225,6,0,0.4);
    }
    [data-testid="stTab"][aria-selected="true"] p { color: #ffffff !important; }
    [data-testid="stTab"][aria-selected="true"]:hover { background: var(--accent) !important; }

    /* ===== Buttons: bigger, bolder, gradient + glow instead of a flat fill ===== */
    .stButton > button {
        background: linear-gradient(180deg, #ff3020 0%, var(--accent) 55%, #b30500 100%) !important;
        color: #ffffff !important;
        border: 1px solid rgba(255,255,255,0.14) !important;
        min-height: 48px !important; padding: 0.7rem 1.6rem !important;
        font-family: var(--font-display) !important; font-size: 0.95rem !important; font-weight: 600 !important;
        letter-spacing: 0.7px !important; text-transform: uppercase !important;
        border-radius: var(--radius-md) !important;
        box-shadow: 0 4px 14px rgba(225,6,0,0.35), inset 0 1px 0 rgba(255,255,255,0.18) !important;
        transition: transform 120ms ease, box-shadow 120ms ease, filter 120ms ease !important;
    }
    .stButton > button:hover {
        filter: brightness(1.08);
        transform: translateY(-1px);
        box-shadow: 0 6px 20px rgba(225,6,0,0.45), inset 0 1px 0 rgba(255,255,255,0.22) !important;
    }
    .stButton > button:active { transform: translateY(0); filter: brightness(0.95); }
    .stButton > button[kind="secondary"] {
        background: var(--surface-raised) !important; color: var(--text) !important;
        border: 1.5px solid var(--border) !important; box-shadow: none !important;
    }
    .stButton > button[kind="secondary"]:hover { border-color: var(--accent) !important; }

    .stCaptionContainer { color: var(--muted) !important; }
    div[data-testid="stExpander"] {
        border: 1px solid var(--border) !important; border-radius: var(--radius-md) !important;
        background-color: var(--surface) !important; margin-top: 8px; margin-bottom: 16px;
        transition: border-color 150ms ease;
    }
    div[data-testid="stExpander"]:hover { border-color: #4a4a4e !important; }
    div[data-testid="stExpander"] summary,
    div[data-testid="stExpander"] summary span,
    div[data-testid="stExpander"] summary p { color: var(--text) !important; font-weight: 600 !important; font-size: 0.95rem !important; }
    div[data-testid="stExpander"] svg { fill: var(--muted) !important; }
    @media (max-width: 768px) {
        [data-testid="stTab"] { font-size: 0.78rem !important; padding: 10px 12px !important; }
        h1 { font-size: 1.6rem !important; }
        h2 { font-size: 1.3rem !important; }
        h3 { font-size: 1.1rem !important; }
        /* Force every multi-column row (hero, filter rows, Props grid, the
           comparison strip) to stack instead of squeezing N columns into a
           phone-width screen. Applied explicitly rather than relying on
           Streamlit's own responsive behavior, which this environment had
           no reliable way to verify empirically. */
        [data-testid="stHorizontalBlock"] { flex-direction: column !important; }
        [data-testid="stHorizontalBlock"] [data-testid="stColumn"] {
            width: 100% !important; flex: 1 1 100% !important;
        }
    }
    [data-testid="stMetricValue"] { color: var(--text) !important; font-size: 1.4rem !important; font-family: var(--font-mono) !important; }
    [data-testid="stMetricLabel"] { color: var(--muted) !important; }

    /* ===== Hero: premium "steel plate" chip instead of a flat outlined box ===== */
    .steel-balance-bar {
        border: 1px solid var(--accent); border-radius: var(--radius-md);
        background: linear-gradient(145deg, rgba(225,6,0,0.24), rgba(225,6,0,0.05) 70%);
        padding: 10px 20px; display: inline-flex; flex-direction: column; align-items: flex-end;
        min-width: 150px; box-shadow: 0 4px 18px rgba(225,6,0,0.18), inset 0 1px 0 rgba(255,255,255,0.06);
    }
    .steel-balance-bar .steel-label {
        font-family: var(--font-display); font-size: 0.68rem; color: var(--muted) !important;
        font-weight: 600; letter-spacing: 1px; text-transform: uppercase;
    }
    .steel-balance-bar .steel-amount {
        font-family: var(--font-mono); font-size: 1.5rem; color: var(--text) !important;
        font-weight: 700; line-height: 1.3;
    }

    /* ===== Fade-bar divider — the app's signature section separator ===== */
    .fade-divider {
        height: 3px; border-radius: 999px; margin: 10px 0 22px 0;
        background: linear-gradient(90deg, var(--gold) 0%, var(--accent) 35%, var(--accent) 70%, transparent 100%);
    }
    .fm-section-title {
        display: flex; align-items: center; gap: 10px; margin-top: 4px;
    }
    .fm-section-title .fm-section-icon {
        display: inline-flex; align-items: center; justify-content: center;
        width: 38px; height: 38px; border-radius: var(--radius-sm);
        background: linear-gradient(145deg, rgba(225,6,0,0.28), rgba(225,6,0,0.06));
        border: 1px solid var(--accent); font-size: 1.15rem; flex-shrink: 0;
    }
    .fm-section-title h2 {
        margin: 0 !important; font-size: 1.6rem !important; text-transform: uppercase; letter-spacing: 0.5px;
    }

    /* ===== Shared card / badge components (Betting, Trends, Props) ===== */
    .fm-badge {
        display: inline-block; padding: 3px 10px; border-radius: 999px;
        font-size: 0.68rem; font-weight: 700; letter-spacing: 0.4px; text-transform: uppercase;
        white-space: nowrap;
    }
    /* !important throughout: a global `span, div { color: var(--text) !important }`
       rule earlier in this block otherwise wins over these more specific
       classes and flattens every badge back to plain white text. */
    .fm-badge-week { background: var(--surface-raised); color: var(--muted) !important; border: 1px solid var(--border); }
    .fm-badge-over { background: var(--positive-bg); color: var(--positive) !important; }
    .fm-badge-under { background: var(--accent-bg); color: var(--accent-light) !important; }
    .fm-badge-pos {
        background: rgba(255,255,255,0.06); font-weight: 800; letter-spacing: 0.6px;
        border: 1px solid currentColor;
    }
    .fm-badge-pos-qb { color: var(--pos-qb) !important; }
    .fm-badge-pos-rb { color: var(--pos-rb) !important; }
    .fm-badge-pos-wr { color: var(--pos-wr) !important; }
    .fm-badge-pos-te { color: var(--pos-te) !important; }
    .fm-nums { font-family: var(--font-mono); font-variant-numeric: tabular-nums; }
    /* Hand-rolled odds tables — replaces st.dataframe on the Betting board,
       which was the single most expensive widget there (two per game, one of
       them a pandas Styler). Same look, a fraction of the render cost. */
    .fm-odds-wrap { overflow-x: auto; margin: 4px 0 2px 0; }
    .fm-odds-table {
        width: 100%; border-collapse: collapse;
        font-family: var(--font-mono); font-variant-numeric: tabular-nums;
        font-size: 0.82rem;
    }
    .fm-odds-table th {
        text-align: left; white-space: nowrap;
        font-family: var(--font-display); font-size: 0.68rem; font-weight: 600;
        letter-spacing: 0.6px; text-transform: uppercase;
        color: var(--muted) !important;
        padding: 6px 10px; border-bottom: 1px solid var(--border);
    }
    .fm-odds-table td {
        padding: 7px 10px; white-space: nowrap;
        border-bottom: 1px solid var(--border); color: var(--text);
    }
    .fm-odds-table tbody tr:last-child td { border-bottom: none; }
    .fm-odds-table tbody tr:hover td { background: var(--surface-raised); }
    .fm-odds-best { color: var(--positive) !important; font-weight: 800; }

    /* ===== Motion =====
       Streamlit reruns the whole script on every interaction, which restarts
       CSS entrance animations — a slow fade would replay each time a week is
       tapped or a bet is placed. So entrances are kept short (under ~300ms)
       and read as a refresh rather than a delay; only the stale-odds dot and
       the loading shimmer loop. */
    @keyframes fm-fade-up {
        from { opacity: 0; transform: translateY(6px); }
        to   { opacity: 1; transform: none; }
    }
    @keyframes fm-grow-x {
        from { transform: scaleX(0); }
        to   { transform: scaleX(1); }
    }
    @keyframes fm-pulse-dot {
        0%, 100% { opacity: 1; transform: scale(1); }
        50%      { opacity: 0.4; transform: scale(0.7); }
    }
    @keyframes fm-shimmer {
        0%   { background-position: -600px 0; }
        100% { background-position: 600px 0; }
    }

    /* Skeleton placeholders — shown while live odds are in flight so the
       board has shape immediately instead of a blank spinner. */
    .fm-skel-card {
        background: var(--surface); border: 1px solid var(--border);
        border-radius: var(--radius-md); padding: 16px 18px; margin-bottom: 10px;
    }
    .fm-skel-row {
        display: grid; grid-template-columns: minmax(120px, 1.6fr) repeat(3, 1fr);
        gap: 10px;
    }
    .fm-skel {
        height: 12px; border-radius: 6px;
        background: linear-gradient(90deg, var(--surface-raised) 25%, #2f2f34 50%, var(--surface-raised) 75%);
        background-size: 600px 100%;
        animation: fm-shimmer 1.25s linear infinite;
    }
    .fm-skel-lg { height: 16px; }
    .fm-skel-bar { height: 6px; border-radius: 999px; margin-top: 16px; }

    @media (prefers-reduced-motion: reduce) {
        *, *::before, *::after {
            animation-duration: 0.001ms !important;
            animation-iteration-count: 1 !important;
            transition-duration: 0.001ms !important;
        }
    }

    /* ===== Betting board: line-age strip, matchup card, win-prob bar ===== */
    .fm-freshness {
        display: flex; align-items: center; gap: 8px; flex-wrap: wrap;
        margin: 2px 0 10px 0; font-size: 0.8rem;
    }
    .fm-fresh-dot {
        width: 8px; height: 8px; border-radius: 50%; flex-shrink: 0;
        display: inline-block;
    }
    .fm-fresh-fresh { background: var(--positive); box-shadow: 0 0 8px rgba(74,222,128,0.6); }
    /* Stale prices are the one thing on a betting board worth nagging about,
       so this dot keeps pulsing until the lines are refreshed. */
    .fm-fresh-stale {
        background: var(--gold); box-shadow: 0 0 8px var(--gold-glow);
        animation: fm-pulse-dot 1.8s ease-in-out infinite;
    }
    .fm-fresh-txt { color: var(--muted) !important; }
    .fm-fresh-txt b { color: var(--text) !important; font-weight: 600; }
    .fm-fresh-sep { color: var(--muted-dim) !important; }

    .fm-gc {
        display: grid; grid-template-columns: minmax(120px, 1.6fr) repeat(3, 1fr);
        gap: 10px; align-items: start;
    }
    .fm-gc-teams { display: flex; flex-direction: column; gap: 2px; min-width: 0; }
    .fm-gc-kick {
        font-family: var(--font-display); font-size: 0.62rem; font-weight: 600;
        letter-spacing: 0.6px; text-transform: uppercase; color: var(--muted) !important;
        margin-bottom: 3px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis;
    }
    .fm-gc-team {
        font-size: 0.95rem; font-weight: 600; color: var(--text); line-height: 1.35;
        white-space: nowrap; overflow: hidden; text-overflow: ellipsis;
    }
    .fm-gc-col { display: flex; flex-direction: column; gap: 2px; text-align: right; }
    .fm-gc-lab {
        font-family: var(--font-display); font-size: 0.58rem; font-weight: 600;
        letter-spacing: 0.7px; color: var(--muted) !important; margin-bottom: 3px;
    }
    .fm-gc-val {
        font-size: 0.95rem; font-weight: 700; color: var(--text); line-height: 1.35;
    }

    .fm-wp { margin: 12px 0 2px 0; }
    .fm-wp-row {
        display: flex; align-items: center; gap: 6px; margin-bottom: 4px;
        font-size: 0.74rem;
    }
    .fm-wp-team { color: var(--muted) !important; }
    .fm-wp-pct { font-weight: 700; color: var(--text); }
    .fm-wp-spacer { flex: 1; }
    .fm-wp-bar {
        display: flex; height: 6px; border-radius: 999px; overflow: hidden;
        background: var(--surface-raised);
    }
    /* Each side grows out from its own edge toward the middle. scaleX rather
       than width so it never triggers layout while animating. */
    .fm-wp-away, .fm-wp-home {
        animation: fm-grow-x 560ms cubic-bezier(0.22, 1, 0.36, 1) both;
    }
    .fm-wp-away {
        background: linear-gradient(90deg, #6b6d72, var(--silver));
        transform-origin: left center;
    }
    .fm-wp-home {
        background: linear-gradient(90deg, var(--accent), #ff3020);
        transform-origin: right center;
    }
    .fm-wp-pct { animation: fm-fade-up 380ms ease-out 200ms both; }

    /* Game cards fade up in sequence. The delay is capped so a 16-game week
       doesn't leave the last card waiting on a long queue. */
    [class*="st-key-fm_game_"] {
        animation: fm-fade-up 280ms cubic-bezier(0.22, 1, 0.36, 1) both;
    }

    @media (max-width: 640px) {
        .fm-gc { grid-template-columns: 1fr 1fr; row-gap: 12px; }
        .fm-gc-teams { grid-column: 1 / -1; }
        .fm-gc-col { text-align: left; }
    }
    .fm-stat-card {
        background: var(--surface); border: 1px solid var(--border); border-radius: var(--radius-md);
        padding: 16px 18px; height: 100%; transition: border-color 150ms ease, transform 150ms ease;
        border-top: 2px solid var(--accent);
    }
    .fm-stat-card:hover { border-color: #4a4a4e; transform: translateY(-1px); }
    .fm-stat-card .fm-stat-label {
        font-family: var(--font-display); font-size: 0.7rem; font-weight: 600; letter-spacing: 0.8px; text-transform: uppercase;
        color: var(--muted) !important; margin-bottom: 8px;
    }
    .fm-stat-card .fm-stat-body { color: var(--text) !important; font-size: 0.92rem; line-height: 1.5; }

    /* ===== Props grid cards — fixed-shape cards laid out via st.columns,
       wrapped with st.container(border=True). CSS only supplies consistent
       min-height + hover lift; Streamlit's own bordered container supplies
       the actual card chrome (border/radius) natively. ===== */
    .st-key-fm_props_grid [data-testid="stVerticalBlockBorderWrapper"] {
        transition: border-color 150ms ease, transform 150ms ease;
    }
    .st-key-fm_props_grid [data-testid="stVerticalBlockBorderWrapper"]:hover {
        border-color: var(--accent) !important; transform: translateY(-2px);
    }
    .fm-prop-card-name {
        font-family: var(--font-display); font-weight: 600; font-size: 1.02rem;
        color: var(--text) !important; white-space: nowrap; overflow: hidden;
        text-overflow: ellipsis; margin: 6px 0 2px 0;
    }
    .fm-prop-card-meta { color: var(--muted) !important; font-size: 0.78rem; margin-bottom: 8px; }
    .fm-prop-card-line {
        font-family: var(--font-mono); font-size: 1.6rem; font-weight: 700;
        color: var(--text) !important; line-height: 1.1; margin-bottom: 8px;
    }
    .fm-headline-row {
        display: flex; align-items: flex-start; gap: 12px;
        padding: 12px 4px; border-bottom: 1px solid var(--border);
    }
    .fm-headline-row:last-child { border-bottom: none; }
    .fm-headline-row .fm-headline-bar {
        width: 4px; align-self: stretch; border-radius: 999px;
        background: linear-gradient(180deg, var(--gold), var(--accent)); flex-shrink: 0;
    }
    .fm-headline-row .fm-headline-text { color: var(--text) !important; font-size: 0.95rem; line-height: 1.5; }

    /* Touch/interaction spacing: keep adjacent radio + tag targets from crowding */
    div[data-baseweb="radio"] { gap: 10px !important; }
    span[data-baseweb="tag"] { margin: 2px 4px 2px 0 !important; }

    /* ===== Dropdown / Select visibility (high contrast) ===== */
    div[data-baseweb="select"] > div,
    div[data-baseweb="select"] > div > div {
        background-color: var(--surface-raised) !important;
        border: 1.5px solid var(--accent) !important;
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
        background-color: var(--surface) !important;
        border: 1.5px solid var(--accent) !important;
        border-radius: 8px !important;
    }
    li[role="option"],
    div[role="option"] {
        color: #ffffff !important;
        background-color: var(--surface) !important;
    }
    li[role="option"]:hover,
    div[role="option"]:hover,
    li[aria-selected="true"] {
        background-color: var(--accent) !important;
        color: #ffffff !important;
    }
    /* Multiselect tags */
    span[data-baseweb="tag"] {
        background-color: var(--accent) !important;
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


def section_title(icon, text):
    """Branded section header: icon chip + Oswald title + the fade-bar
    divider, used in place of st.header() so every tab opens the same way."""
    st.markdown(
        f"""<div class="fm-section-title">
          <div class="fm-section-icon">{icon}</div>
          <h2>{text}</h2>
        </div>
        <div class="fade-divider"></div>""",
        unsafe_allow_html=True,
    )


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
    {"player": 'Kyler Murray', "team": 'ARI', "pos": 'QB', "game": 'ARI vs TBD', "market": 'Pass Yds', "line": 230.5, "over": 105, "under": -125},
    {"player": 'Kyler Murray', "team": 'ARI', "pos": 'QB', "game": 'ARI vs TBD', "market": 'Pass TDs', "line": 1.5, "over": -120, "under": 100},
    {"player": 'Kyler Murray', "team": 'ARI', "pos": 'QB', "game": 'ARI vs TBD', "market": 'Rush Yds', "line": 15.0, "over": -125, "under": 105},
    {"player": 'James Conner', "team": 'ARI', "pos": 'RB', "game": 'ARI vs TBD', "market": 'Rush Yds', "line": 49.0, "over": -110, "under": -110},
    {"player": 'James Conner', "team": 'ARI', "pos": 'RB', "game": 'ARI vs TBD', "market": 'Receptions', "line": 1.5, "over": 105, "under": -125},
    {"player": 'James Conner', "team": 'ARI', "pos": 'RB', "game": 'ARI vs TBD', "market": 'Rec Yds', "line": 13.0, "over": -110, "under": -110},
    {"player": 'Marvin Harrison Jr.', "team": 'ARI', "pos": 'WR', "game": 'ARI vs TBD', "market": 'Receptions', "line": 4.5, "over": -120, "under": 100},
    {"player": 'Marvin Harrison Jr.', "team": 'ARI', "pos": 'WR', "game": 'ARI vs TBD', "market": 'Rec Yds', "line": 68.0, "over": -110, "under": -110},
    {"player": 'Marvin Harrison Jr.', "team": 'ARI', "pos": 'WR', "game": 'ARI vs TBD', "market": 'Rec TDs', "line": 0.5, "over": -110, "under": -110},
    {"player": 'Trey McBride', "team": 'ARI', "pos": 'TE', "game": 'ARI vs TBD', "market": 'Receptions', "line": 5.0, "over": -110, "under": -110},
    {"player": 'Trey McBride', "team": 'ARI', "pos": 'TE', "game": 'ARI vs TBD', "market": 'Rec Yds', "line": 57.0, "over": -125, "under": 105},
    {"player": 'Michael Penix Jr.', "team": 'ATL', "pos": 'QB', "game": 'ATL vs TBD', "market": 'Pass Yds', "line": 229.5, "over": -110, "under": -110},
    {"player": 'Michael Penix Jr.', "team": 'ATL', "pos": 'QB', "game": 'ATL vs TBD', "market": 'Pass TDs', "line": 1.0, "over": -125, "under": 105},
    {"player": 'Michael Penix Jr.', "team": 'ATL', "pos": 'QB', "game": 'ATL vs TBD', "market": 'Rush Yds', "line": 10.0, "over": -120, "under": 100},
    {"player": 'Bijan Robinson', "team": 'ATL', "pos": 'RB', "game": 'ATL vs TBD', "market": 'Rush Yds', "line": 85.5, "over": -110, "under": -110},
    {"player": 'Bijan Robinson', "team": 'ATL', "pos": 'RB', "game": 'ATL vs TBD', "market": 'Receptions', "line": 3.5, "over": -110, "under": -110},
    {"player": 'Bijan Robinson', "team": 'ATL', "pos": 'RB', "game": 'ATL vs TBD', "market": 'Rec Yds', "line": 27.0, "over": -120, "under": 100},
    {"player": 'Drake London', "team": 'ATL', "pos": 'WR', "game": 'ATL vs TBD', "market": 'Receptions', "line": 4.5, "over": 100, "under": -120},
    {"player": 'Drake London', "team": 'ATL', "pos": 'WR', "game": 'ATL vs TBD', "market": 'Rec Yds', "line": 59.0, "over": 105, "under": -125},
    {"player": 'Drake London', "team": 'ATL', "pos": 'WR', "game": 'ATL vs TBD', "market": 'Rec TDs', "line": 0.5, "over": -110, "under": -110},
    {"player": 'Darnell Mooney', "team": 'ATL', "pos": 'WR', "game": 'ATL vs TBD', "market": 'Receptions', "line": 4.0, "over": -110, "under": -110},
    {"player": 'Darnell Mooney', "team": 'ATL', "pos": 'WR', "game": 'ATL vs TBD', "market": 'Rec Yds', "line": 53.5, "over": -110, "under": -110},
    {"player": 'Darnell Mooney', "team": 'ATL', "pos": 'WR', "game": 'ATL vs TBD', "market": 'Rec TDs', "line": 0.5, "over": -110, "under": -110},
    {"player": 'Lamar Jackson', "team": 'BAL', "pos": 'QB', "game": 'BAL vs TBD', "market": 'Pass Yds', "line": 272.5, "over": 100, "under": -120},
    {"player": 'Lamar Jackson', "team": 'BAL', "pos": 'QB', "game": 'BAL vs TBD', "market": 'Pass TDs', "line": 2.0, "over": -120, "under": 100},
    {"player": 'Lamar Jackson', "team": 'BAL', "pos": 'QB', "game": 'BAL vs TBD', "market": 'Rush Yds', "line": 26.0, "over": -120, "under": 100},
    {"player": 'Derrick Henry', "team": 'BAL', "pos": 'RB', "game": 'BAL vs TBD', "market": 'Rush Yds', "line": 79.5, "over": 100, "under": -120},
    {"player": 'Derrick Henry', "team": 'BAL', "pos": 'RB', "game": 'BAL vs TBD', "market": 'Receptions', "line": 3.0, "over": 105, "under": -125},
    {"player": 'Derrick Henry', "team": 'BAL', "pos": 'RB', "game": 'BAL vs TBD', "market": 'Rec Yds', "line": 26.0, "over": 105, "under": -125},
    {"player": 'Zay Flowers', "team": 'BAL', "pos": 'WR', "game": 'BAL vs TBD', "market": 'Receptions', "line": 5.0, "over": -110, "under": -110},
    {"player": 'Zay Flowers', "team": 'BAL', "pos": 'WR', "game": 'BAL vs TBD', "market": 'Rec Yds', "line": 60.0, "over": 105, "under": -125},
    {"player": 'Zay Flowers', "team": 'BAL', "pos": 'WR', "game": 'BAL vs TBD', "market": 'Rec TDs', "line": 0.5, "over": -110, "under": -110},
    {"player": 'Mark Andrews', "team": 'BAL', "pos": 'TE', "game": 'BAL vs TBD', "market": 'Receptions', "line": 3.5, "over": -125, "under": 105},
    {"player": 'Mark Andrews', "team": 'BAL', "pos": 'TE', "game": 'BAL vs TBD', "market": 'Rec Yds', "line": 44.5, "over": -120, "under": 100},
    {"player": 'Josh Allen', "team": 'BUF', "pos": 'QB', "game": 'BUF vs TBD', "market": 'Pass Yds', "line": 268.0, "over": 100, "under": -120},
    {"player": 'Josh Allen', "team": 'BUF', "pos": 'QB', "game": 'BUF vs TBD', "market": 'Pass TDs', "line": 2.0, "over": 100, "under": -120},
    {"player": 'Josh Allen', "team": 'BUF', "pos": 'QB', "game": 'BUF vs TBD', "market": 'Rush Yds', "line": 27.5, "over": -110, "under": -110},
    {"player": 'James Cook', "team": 'BUF', "pos": 'RB', "game": 'BUF vs TBD', "market": 'Rush Yds', "line": 59.5, "over": -120, "under": 100},
    {"player": 'James Cook', "team": 'BUF', "pos": 'RB', "game": 'BUF vs TBD', "market": 'Receptions', "line": 2.5, "over": -110, "under": -110},
    {"player": 'James Cook', "team": 'BUF', "pos": 'RB', "game": 'BUF vs TBD', "market": 'Rec Yds', "line": 18.0, "over": -120, "under": 100},
    {"player": 'Khalil Shakir', "team": 'BUF', "pos": 'WR', "game": 'BUF vs TBD', "market": 'Receptions', "line": 4.0, "over": -110, "under": -110},
    {"player": 'Khalil Shakir', "team": 'BUF', "pos": 'WR', "game": 'BUF vs TBD', "market": 'Rec Yds', "line": 44.5, "over": -125, "under": 105},
    {"player": 'Khalil Shakir', "team": 'BUF', "pos": 'WR', "game": 'BUF vs TBD', "market": 'Rec TDs', "line": 0.5, "over": 100, "under": -120},
    {"player": 'Bryce Young', "team": 'CAR', "pos": 'QB', "game": 'CAR vs TBD', "market": 'Pass Yds', "line": 200.0, "over": -110, "under": -110},
    {"player": 'Bryce Young', "team": 'CAR', "pos": 'QB', "game": 'CAR vs TBD', "market": 'Pass TDs', "line": 1.0, "over": 100, "under": -120},
    {"player": 'Bryce Young', "team": 'CAR', "pos": 'QB', "game": 'CAR vs TBD', "market": 'Rush Yds', "line": 8.5, "over": -110, "under": -110},
    {"player": 'Chuba Hubbard', "team": 'CAR', "pos": 'RB', "game": 'CAR vs TBD', "market": 'Rush Yds', "line": 48.5, "over": -110, "under": -110},
    {"player": 'Chuba Hubbard', "team": 'CAR', "pos": 'RB', "game": 'CAR vs TBD', "market": 'Receptions', "line": 1.5, "over": 100, "under": -120},
    {"player": 'Chuba Hubbard', "team": 'CAR', "pos": 'RB', "game": 'CAR vs TBD', "market": 'Rec Yds', "line": 13.0, "over": -110, "under": -110},
    {"player": 'Tetairoa McMillan', "team": 'CAR', "pos": 'WR', "game": 'CAR vs TBD', "market": 'Receptions', "line": 3.5, "over": -120, "under": 100},
    {"player": 'Tetairoa McMillan', "team": 'CAR', "pos": 'WR', "game": 'CAR vs TBD', "market": 'Rec Yds', "line": 49.5, "over": -110, "under": -110},
    {"player": 'Tetairoa McMillan', "team": 'CAR', "pos": 'WR', "game": 'CAR vs TBD', "market": 'Rec TDs', "line": 0.5, "over": 100, "under": -120},
    {"player": 'Xavier Legette', "team": 'CAR', "pos": 'WR', "game": 'CAR vs TBD', "market": 'Receptions', "line": 2.5, "over": -125, "under": 105},
    {"player": 'Xavier Legette', "team": 'CAR', "pos": 'WR', "game": 'CAR vs TBD', "market": 'Rec Yds', "line": 33.5, "over": -120, "under": 100},
    {"player": 'Caleb Williams', "team": 'CHI', "pos": 'QB', "game": 'CHI vs TBD', "market": 'Pass Yds', "line": 194.0, "over": -125, "under": 105},
    {"player": 'Caleb Williams', "team": 'CHI', "pos": 'QB', "game": 'CHI vs TBD', "market": 'Pass TDs', "line": 1.5, "over": -110, "under": -110},
    {"player": 'Caleb Williams', "team": 'CHI', "pos": 'QB', "game": 'CHI vs TBD', "market": 'Rush Yds', "line": 11.0, "over": 100, "under": -120},
    {"player": "D'Andre Swift", "team": 'CHI', "pos": 'RB', "game": 'CHI vs TBD', "market": 'Rush Yds', "line": 48.5, "over": -110, "under": -110},
    {"player": "D'Andre Swift", "team": 'CHI', "pos": 'RB', "game": 'CHI vs TBD', "market": 'Receptions', "line": 2.0, "over": -110, "under": -110},
    {"player": "D'Andre Swift", "team": 'CHI', "pos": 'RB', "game": 'CHI vs TBD', "market": 'Rec Yds', "line": 12.5, "over": 100, "under": -120},
    {"player": 'DJ Moore', "team": 'CHI', "pos": 'WR', "game": 'CHI vs TBD', "market": 'Receptions', "line": 5.0, "over": 100, "under": -120},
    {"player": 'DJ Moore', "team": 'CHI', "pos": 'WR', "game": 'CHI vs TBD', "market": 'Rec Yds', "line": 69.5, "over": -110, "under": -110},
    {"player": 'DJ Moore', "team": 'CHI', "pos": 'WR', "game": 'CHI vs TBD', "market": 'Rec TDs', "line": 0.5, "over": -110, "under": -110},
    {"player": 'Rome Odunze', "team": 'CHI', "pos": 'WR', "game": 'CHI vs TBD', "market": 'Receptions', "line": 4.0, "over": -110, "under": -110},
    {"player": 'Rome Odunze', "team": 'CHI', "pos": 'WR', "game": 'CHI vs TBD', "market": 'Rec Yds', "line": 52.0, "over": -110, "under": -110},
    {"player": 'Rome Odunze', "team": 'CHI', "pos": 'WR', "game": 'CHI vs TBD', "market": 'Rec TDs', "line": 0.5, "over": 105, "under": -125},
    {"player": 'Joe Burrow', "team": 'CIN', "pos": 'QB', "game": 'CIN vs TBD', "market": 'Pass Yds', "line": 274.0, "over": -110, "under": -110},
    {"player": 'Joe Burrow', "team": 'CIN', "pos": 'QB', "game": 'CIN vs TBD', "market": 'Pass TDs', "line": 2.0, "over": -125, "under": 105},
    {"player": 'Joe Burrow', "team": 'CIN', "pos": 'QB', "game": 'CIN vs TBD', "market": 'Rush Yds', "line": 25.0, "over": 105, "under": -125},
    {"player": 'Chase Brown', "team": 'CIN', "pos": 'RB', "game": 'CIN vs TBD', "market": 'Rush Yds', "line": 64.0, "over": -110, "under": -110},
    {"player": 'Chase Brown', "team": 'CIN', "pos": 'RB', "game": 'CIN vs TBD', "market": 'Receptions', "line": 2.0, "over": 105, "under": -125},
    {"player": 'Chase Brown', "team": 'CIN', "pos": 'RB', "game": 'CIN vs TBD', "market": 'Rec Yds', "line": 20.0, "over": -110, "under": -110},
    {"player": "Ja'Marr Chase", "team": 'CIN', "pos": 'WR', "game": 'CIN vs TBD', "market": 'Receptions', "line": 5.5, "over": -125, "under": 105},
    {"player": "Ja'Marr Chase", "team": 'CIN', "pos": 'WR', "game": 'CIN vs TBD', "market": 'Rec Yds', "line": 71.5, "over": -125, "under": 105},
    {"player": "Ja'Marr Chase", "team": 'CIN', "pos": 'WR', "game": 'CIN vs TBD', "market": 'Rec TDs', "line": 0.5, "over": -110, "under": -110},
    {"player": 'Tee Higgins', "team": 'CIN', "pos": 'WR', "game": 'CIN vs TBD', "market": 'Receptions', "line": 5.0, "over": -110, "under": -110},
    {"player": 'Tee Higgins', "team": 'CIN', "pos": 'WR', "game": 'CIN vs TBD', "market": 'Rec Yds', "line": 63.0, "over": 100, "under": -120},
    {"player": 'Tee Higgins', "team": 'CIN', "pos": 'WR', "game": 'CIN vs TBD', "market": 'Rec TDs', "line": 0.5, "over": 105, "under": -125},
    {"player": 'Dillon Gabriel', "team": 'CLE', "pos": 'QB', "game": 'CLE vs TBD', "market": 'Pass Yds', "line": 206.5, "over": -110, "under": -110},
    {"player": 'Dillon Gabriel', "team": 'CLE', "pos": 'QB', "game": 'CLE vs TBD', "market": 'Pass TDs', "line": 1.0, "over": 105, "under": -125},
    {"player": 'Dillon Gabriel', "team": 'CLE', "pos": 'QB', "game": 'CLE vs TBD', "market": 'Rush Yds', "line": 9.0, "over": -110, "under": -110},
    {"player": 'Quinshon Judkins', "team": 'CLE', "pos": 'RB', "game": 'CLE vs TBD', "market": 'Rush Yds', "line": 41.0, "over": -125, "under": 105},
    {"player": 'Quinshon Judkins', "team": 'CLE', "pos": 'RB', "game": 'CLE vs TBD', "market": 'Receptions', "line": 2.0, "over": -110, "under": -110},
    {"player": 'Quinshon Judkins', "team": 'CLE', "pos": 'RB', "game": 'CLE vs TBD', "market": 'Rec Yds', "line": 13.5, "over": -110, "under": -110},
    {"player": 'Jerry Jeudy', "team": 'CLE', "pos": 'WR', "game": 'CLE vs TBD', "market": 'Receptions', "line": 3.5, "over": 100, "under": -120},
    {"player": 'Jerry Jeudy', "team": 'CLE', "pos": 'WR', "game": 'CLE vs TBD', "market": 'Rec Yds', "line": 45.5, "over": 105, "under": -125},
    {"player": 'Jerry Jeudy', "team": 'CLE', "pos": 'WR', "game": 'CLE vs TBD', "market": 'Rec TDs', "line": 0.5, "over": -125, "under": 105},
    {"player": 'David Njoku', "team": 'CLE', "pos": 'TE', "game": 'CLE vs TBD', "market": 'Receptions', "line": 3.0, "over": -110, "under": -110},
    {"player": 'David Njoku', "team": 'CLE', "pos": 'TE', "game": 'CLE vs TBD', "market": 'Rec Yds', "line": 36.5, "over": -110, "under": -110},
    {"player": 'Dak Prescott', "team": 'DAL', "pos": 'QB', "game": 'DAL vs TBD', "market": 'Pass Yds', "line": 250.0, "over": -110, "under": -110},
    {"player": 'Dak Prescott', "team": 'DAL', "pos": 'QB', "game": 'DAL vs TBD', "market": 'Pass TDs', "line": 1.5, "over": -125, "under": 105},
    {"player": 'Dak Prescott', "team": 'DAL', "pos": 'QB', "game": 'DAL vs TBD', "market": 'Rush Yds', "line": 15.0, "over": -125, "under": 105},
    {"player": 'Javonte Williams', "team": 'DAL', "pos": 'RB', "game": 'DAL vs TBD', "market": 'Rush Yds', "line": 41.5, "over": -125, "under": 105},
    {"player": 'Javonte Williams', "team": 'DAL', "pos": 'RB', "game": 'DAL vs TBD', "market": 'Receptions', "line": 1.5, "over": -120, "under": 100},
    {"player": 'Javonte Williams', "team": 'DAL', "pos": 'RB', "game": 'DAL vs TBD', "market": 'Rec Yds', "line": 12.5, "over": 100, "under": -120},
    {"player": 'CeeDee Lamb', "team": 'DAL', "pos": 'WR', "game": 'DAL vs TBD', "market": 'Receptions', "line": 6.5, "over": -110, "under": -110},
    {"player": 'CeeDee Lamb', "team": 'DAL', "pos": 'WR', "game": 'DAL vs TBD', "market": 'Rec Yds', "line": 72.0, "over": -125, "under": 105},
    {"player": 'CeeDee Lamb', "team": 'DAL', "pos": 'WR', "game": 'DAL vs TBD', "market": 'Rec TDs', "line": 0.5, "over": 100, "under": -120},
    {"player": 'Jake Ferguson', "team": 'DAL', "pos": 'TE', "game": 'DAL vs TBD', "market": 'Receptions', "line": 3.0, "over": 100, "under": -120},
    {"player": 'Jake Ferguson', "team": 'DAL', "pos": 'TE', "game": 'DAL vs TBD', "market": 'Rec Yds', "line": 36.0, "over": -110, "under": -110},
    {"player": 'Bo Nix', "team": 'DEN', "pos": 'QB', "game": 'DEN vs TBD', "market": 'Pass Yds', "line": 269.5, "over": -110, "under": -110},
    {"player": 'Bo Nix', "team": 'DEN', "pos": 'QB', "game": 'DEN vs TBD', "market": 'Pass TDs', "line": 1.5, "over": -110, "under": -110},
    {"player": 'Bo Nix', "team": 'DEN', "pos": 'QB', "game": 'DEN vs TBD', "market": 'Rush Yds', "line": 17.0, "over": -110, "under": -110},
    {"player": 'J.K. Dobbins', "team": 'DEN', "pos": 'RB', "game": 'DEN vs TBD', "market": 'Rush Yds', "line": 44.5, "over": -120, "under": 100},
    {"player": 'J.K. Dobbins', "team": 'DEN', "pos": 'RB', "game": 'DEN vs TBD', "market": 'Receptions', "line": 1.5, "over": 105, "under": -125},
    {"player": 'J.K. Dobbins', "team": 'DEN', "pos": 'RB', "game": 'DEN vs TBD', "market": 'Rec Yds', "line": 11.5, "over": 105, "under": -125},
    {"player": 'Courtland Sutton', "team": 'DEN', "pos": 'WR', "game": 'DEN vs TBD', "market": 'Receptions', "line": 3.5, "over": -120, "under": 100},
    {"player": 'Courtland Sutton', "team": 'DEN', "pos": 'WR', "game": 'DEN vs TBD', "market": 'Rec Yds', "line": 44.5, "over": 105, "under": -125},
    {"player": 'Courtland Sutton', "team": 'DEN', "pos": 'WR', "game": 'DEN vs TBD', "market": 'Rec TDs', "line": 0.5, "over": 100, "under": -120},
    {"player": 'Jaylen Waddle', "team": 'DEN', "pos": 'WR', "game": 'DEN vs TBD', "market": 'Receptions', "line": 4.5, "over": 105, "under": -125},
    {"player": 'Jaylen Waddle', "team": 'DEN', "pos": 'WR', "game": 'DEN vs TBD', "market": 'Rec Yds', "line": 62.5, "over": -120, "under": 100},
    {"player": 'Jaylen Waddle', "team": 'DEN', "pos": 'WR', "game": 'DEN vs TBD', "market": 'Rec TDs', "line": 0.5, "over": 100, "under": -120},
    {"player": 'Jared Goff', "team": 'DET', "pos": 'QB', "game": 'DET vs TBD', "market": 'Pass Yds', "line": 226.0, "over": 105, "under": -125},
    {"player": 'Jared Goff', "team": 'DET', "pos": 'QB', "game": 'DET vs TBD', "market": 'Pass TDs', "line": 1.5, "over": -110, "under": -110},
    {"player": 'Jared Goff', "team": 'DET', "pos": 'QB', "game": 'DET vs TBD', "market": 'Rush Yds', "line": 17.0, "over": 100, "under": -120},
    {"player": 'Jahmyr Gibbs', "team": 'DET', "pos": 'RB', "game": 'DET vs TBD', "market": 'Rush Yds', "line": 81.5, "over": -110, "under": -110},
    {"player": 'Jahmyr Gibbs', "team": 'DET', "pos": 'RB', "game": 'DET vs TBD', "market": 'Receptions', "line": 3.5, "over": -110, "under": -110},
    {"player": 'Jahmyr Gibbs', "team": 'DET', "pos": 'RB', "game": 'DET vs TBD', "market": 'Rec Yds', "line": 26.5, "over": 105, "under": -125},
    {"player": 'Amon-Ra St. Brown', "team": 'DET', "pos": 'WR', "game": 'DET vs TBD', "market": 'Receptions', "line": 6.0, "over": -120, "under": 100},
    {"player": 'Amon-Ra St. Brown', "team": 'DET', "pos": 'WR', "game": 'DET vs TBD', "market": 'Rec Yds', "line": 78.0, "over": -120, "under": 100},
    {"player": 'Amon-Ra St. Brown', "team": 'DET', "pos": 'WR', "game": 'DET vs TBD', "market": 'Rec TDs', "line": 0.5, "over": -110, "under": -110},
    {"player": 'Sam LaPorta', "team": 'DET', "pos": 'TE', "game": 'DET vs TBD', "market": 'Receptions', "line": 4.0, "over": 100, "under": -120},
    {"player": 'Sam LaPorta', "team": 'DET', "pos": 'TE', "game": 'DET vs TBD', "market": 'Rec Yds', "line": 45.5, "over": 100, "under": -120},
    {"player": 'Jordan Love', "team": 'GB', "pos": 'QB', "game": 'GB vs TBD', "market": 'Pass Yds', "line": 234.0, "over": -110, "under": -110},
    {"player": 'Jordan Love', "team": 'GB', "pos": 'QB', "game": 'GB vs TBD', "market": 'Pass TDs', "line": 1.5, "over": -110, "under": -110},
    {"player": 'Jordan Love', "team": 'GB', "pos": 'QB', "game": 'GB vs TBD', "market": 'Rush Yds', "line": 11.0, "over": -110, "under": -110},
    {"player": 'Josh Jacobs', "team": 'GB', "pos": 'RB', "game": 'GB vs TBD', "market": 'Rush Yds', "line": 61.5, "over": 100, "under": -120},
    {"player": 'Josh Jacobs', "team": 'GB', "pos": 'RB', "game": 'GB vs TBD', "market": 'Receptions', "line": 2.5, "over": -110, "under": -110},
    {"player": 'Josh Jacobs', "team": 'GB', "pos": 'RB', "game": 'GB vs TBD', "market": 'Rec Yds', "line": 21.0, "over": -110, "under": -110},
    {"player": 'Jayden Reed', "team": 'GB', "pos": 'WR', "game": 'GB vs TBD', "market": 'Receptions', "line": 4.0, "over": -110, "under": -110},
    {"player": 'Jayden Reed', "team": 'GB', "pos": 'WR', "game": 'GB vs TBD', "market": 'Rec Yds', "line": 47.0, "over": -120, "under": 100},
    {"player": 'Jayden Reed', "team": 'GB', "pos": 'WR', "game": 'GB vs TBD', "market": 'Rec TDs', "line": 0.5, "over": 105, "under": -125},
    {"player": 'Tucker Kraft', "team": 'GB', "pos": 'TE', "game": 'GB vs TBD', "market": 'Receptions', "line": 3.0, "over": -110, "under": -110},
    {"player": 'Tucker Kraft', "team": 'GB', "pos": 'TE', "game": 'GB vs TBD', "market": 'Rec Yds', "line": 36.5, "over": -110, "under": -110},
    {"player": 'C.J. Stroud', "team": 'HOU', "pos": 'QB', "game": 'HOU vs TBD', "market": 'Pass Yds', "line": 234.0, "over": -120, "under": 100},
    {"player": 'C.J. Stroud', "team": 'HOU', "pos": 'QB', "game": 'HOU vs TBD', "market": 'Pass TDs', "line": 1.5, "over": -110, "under": -110},
    {"player": 'C.J. Stroud', "team": 'HOU', "pos": 'QB', "game": 'HOU vs TBD', "market": 'Rush Yds', "line": 17.5, "over": -110, "under": -110},
    {"player": 'Joe Mixon', "team": 'HOU', "pos": 'RB', "game": 'HOU vs TBD', "market": 'Rush Yds', "line": 44.0, "over": 105, "under": -125},
    {"player": 'Joe Mixon', "team": 'HOU', "pos": 'RB', "game": 'HOU vs TBD', "market": 'Receptions', "line": 1.5, "over": -125, "under": 105},
    {"player": 'Joe Mixon', "team": 'HOU', "pos": 'RB', "game": 'HOU vs TBD', "market": 'Rec Yds', "line": 13.0, "over": -110, "under": -110},
    {"player": 'Nico Collins', "team": 'HOU', "pos": 'WR', "game": 'HOU vs TBD', "market": 'Receptions', "line": 4.0, "over": -125, "under": 105},
    {"player": 'Nico Collins', "team": 'HOU', "pos": 'WR', "game": 'HOU vs TBD', "market": 'Rec Yds', "line": 68.0, "over": -110, "under": -110},
    {"player": 'Nico Collins', "team": 'HOU', "pos": 'WR', "game": 'HOU vs TBD', "market": 'Rec TDs', "line": 0.5, "over": 100, "under": -120},
    {"player": 'Tank Dell', "team": 'HOU', "pos": 'WR', "game": 'HOU vs TBD', "market": 'Receptions', "line": 4.0, "over": -110, "under": -110},
    {"player": 'Tank Dell', "team": 'HOU', "pos": 'WR', "game": 'HOU vs TBD', "market": 'Rec Yds', "line": 51.5, "over": -110, "under": -110},
    {"player": 'Tank Dell', "team": 'HOU', "pos": 'WR', "game": 'HOU vs TBD', "market": 'Rec TDs', "line": 0.5, "over": -110, "under": -110},
    {"player": 'Daniel Jones', "team": 'IND', "pos": 'QB', "game": 'IND vs TBD', "market": 'Pass Yds', "line": 223.0, "over": -110, "under": -110},
    {"player": 'Daniel Jones', "team": 'IND', "pos": 'QB', "game": 'IND vs TBD', "market": 'Pass TDs', "line": 1.5, "over": -110, "under": -110},
    {"player": 'Daniel Jones', "team": 'IND', "pos": 'QB', "game": 'IND vs TBD', "market": 'Rush Yds', "line": 11.5, "over": -110, "under": -110},
    {"player": 'Jonathan Taylor', "team": 'IND', "pos": 'RB', "game": 'IND vs TBD', "market": 'Rush Yds', "line": 81.5, "over": -110, "under": -110},
    {"player": 'Jonathan Taylor', "team": 'IND', "pos": 'RB', "game": 'IND vs TBD', "market": 'Receptions', "line": 3.5, "over": -110, "under": -110},
    {"player": 'Jonathan Taylor', "team": 'IND', "pos": 'RB', "game": 'IND vs TBD', "market": 'Rec Yds', "line": 26.5, "over": -120, "under": 100},
    {"player": 'Michael Pittman Jr.', "team": 'IND', "pos": 'WR', "game": 'IND vs TBD', "market": 'Receptions', "line": 4.0, "over": -110, "under": -110},
    {"player": 'Michael Pittman Jr.', "team": 'IND', "pos": 'WR', "game": 'IND vs TBD', "market": 'Rec Yds', "line": 47.0, "over": -120, "under": 100},
    {"player": 'Michael Pittman Jr.', "team": 'IND', "pos": 'WR', "game": 'IND vs TBD', "market": 'Rec TDs', "line": 0.5, "over": 100, "under": -120},
    {"player": 'Josh Downs', "team": 'IND', "pos": 'WR', "game": 'IND vs TBD', "market": 'Receptions', "line": 2.5, "over": -110, "under": -110},
    {"player": 'Josh Downs', "team": 'IND', "pos": 'WR', "game": 'IND vs TBD', "market": 'Rec Yds', "line": 38.0, "over": -110, "under": -110},
    {"player": 'Trevor Lawrence', "team": 'JAX', "pos": 'QB', "game": 'JAX vs TBD', "market": 'Pass Yds', "line": 205.5, "over": 105, "under": -125},
    {"player": 'Trevor Lawrence', "team": 'JAX', "pos": 'QB', "game": 'JAX vs TBD', "market": 'Pass TDs', "line": 1.0, "over": 105, "under": -125},
    {"player": 'Trevor Lawrence', "team": 'JAX', "pos": 'QB', "game": 'JAX vs TBD', "market": 'Rush Yds', "line": 11.5, "over": -110, "under": -110},
    {"player": 'Travis Etienne Jr.', "team": 'JAX', "pos": 'RB', "game": 'JAX vs TBD', "market": 'Rush Yds', "line": 59.0, "over": 105, "under": -125},
    {"player": 'Travis Etienne Jr.', "team": 'JAX', "pos": 'RB', "game": 'JAX vs TBD', "market": 'Receptions', "line": 2.0, "over": 105, "under": -125},
    {"player": 'Travis Etienne Jr.', "team": 'JAX', "pos": 'RB', "game": 'JAX vs TBD', "market": 'Rec Yds', "line": 18.5, "over": -120, "under": 100},
    {"player": 'Brian Thomas Jr.', "team": 'JAX', "pos": 'WR', "game": 'JAX vs TBD', "market": 'Receptions', "line": 4.5, "over": -120, "under": 100},
    {"player": 'Brian Thomas Jr.', "team": 'JAX', "pos": 'WR', "game": 'JAX vs TBD', "market": 'Rec Yds', "line": 60.5, "over": 105, "under": -125},
    {"player": 'Brian Thomas Jr.', "team": 'JAX', "pos": 'WR', "game": 'JAX vs TBD', "market": 'Rec TDs', "line": 0.5, "over": 105, "under": -125},
    {"player": 'Patrick Mahomes', "team": 'KC', "pos": 'QB', "game": 'KC vs TBD', "market": 'Pass Yds', "line": 288.0, "over": -110, "under": -110},
    {"player": 'Patrick Mahomes', "team": 'KC', "pos": 'QB', "game": 'KC vs TBD', "market": 'Pass TDs', "line": 2.0, "over": -110, "under": -110},
    {"player": 'Patrick Mahomes', "team": 'KC', "pos": 'QB', "game": 'KC vs TBD', "market": 'Rush Yds', "line": 28.5, "over": -110, "under": -110},
    {"player": 'Isiah Pacheco', "team": 'KC', "pos": 'RB', "game": 'KC vs TBD', "market": 'Rush Yds', "line": 43.5, "over": 105, "under": -125},
    {"player": 'Isiah Pacheco', "team": 'KC', "pos": 'RB', "game": 'KC vs TBD', "market": 'Receptions', "line": 1.5, "over": -125, "under": 105},
    {"player": 'Isiah Pacheco', "team": 'KC', "pos": 'RB', "game": 'KC vs TBD', "market": 'Rec Yds', "line": 12.0, "over": -120, "under": 100},
    {"player": 'Xavier Worthy', "team": 'KC', "pos": 'WR', "game": 'KC vs TBD', "market": 'Receptions', "line": 3.5, "over": 100, "under": -120},
    {"player": 'Xavier Worthy', "team": 'KC', "pos": 'WR', "game": 'KC vs TBD', "market": 'Rec Yds', "line": 47.5, "over": -120, "under": 100},
    {"player": 'Xavier Worthy', "team": 'KC', "pos": 'WR', "game": 'KC vs TBD', "market": 'Rec TDs', "line": 0.5, "over": -110, "under": -110},
    {"player": 'Travis Kelce', "team": 'KC', "pos": 'TE', "game": 'KC vs TBD', "market": 'Receptions', "line": 4.0, "over": -110, "under": -110},
    {"player": 'Travis Kelce', "team": 'KC', "pos": 'TE', "game": 'KC vs TBD', "market": 'Rec Yds', "line": 41.5, "over": -125, "under": 105},
    {"player": 'Justin Herbert', "team": 'LAC', "pos": 'QB', "game": 'LAC vs TBD', "market": 'Pass Yds', "line": 245.5, "over": 100, "under": -120},
    {"player": 'Justin Herbert', "team": 'LAC', "pos": 'QB', "game": 'LAC vs TBD', "market": 'Pass TDs', "line": 1.5, "over": 100, "under": -120},
    {"player": 'Justin Herbert', "team": 'LAC', "pos": 'QB', "game": 'LAC vs TBD', "market": 'Rush Yds', "line": 16.0, "over": -120, "under": 100},
    {"player": 'Omarion Hampton', "team": 'LAC', "pos": 'RB', "game": 'LAC vs TBD', "market": 'Rush Yds', "line": 56.5, "over": -125, "under": 105},
    {"player": 'Omarion Hampton', "team": 'LAC', "pos": 'RB', "game": 'LAC vs TBD', "market": 'Receptions', "line": 2.5, "over": -120, "under": 100},
    {"player": 'Omarion Hampton', "team": 'LAC', "pos": 'RB', "game": 'LAC vs TBD', "market": 'Rec Yds', "line": 17.5, "over": 105, "under": -125},
    {"player": 'Ladd McConkey', "team": 'LAC', "pos": 'WR', "game": 'LAC vs TBD', "market": 'Receptions', "line": 4.5, "over": -120, "under": 100},
    {"player": 'Ladd McConkey', "team": 'LAC', "pos": 'WR', "game": 'LAC vs TBD', "market": 'Rec Yds', "line": 65.0, "over": -110, "under": -110},
    {"player": 'Ladd McConkey', "team": 'LAC', "pos": 'WR', "game": 'LAC vs TBD', "market": 'Rec TDs', "line": 0.5, "over": -120, "under": 100},
    {"player": 'Matthew Stafford', "team": 'LAR', "pos": 'QB', "game": 'LAR vs TBD', "market": 'Pass Yds', "line": 223.5, "over": -125, "under": 105},
    {"player": 'Matthew Stafford', "team": 'LAR', "pos": 'QB', "game": 'LAR vs TBD', "market": 'Pass TDs', "line": 1.5, "over": -125, "under": 105},
    {"player": 'Matthew Stafford', "team": 'LAR', "pos": 'QB', "game": 'LAR vs TBD', "market": 'Rush Yds', "line": 14.5, "over": -125, "under": 105},
    {"player": 'Kyren Williams', "team": 'LAR', "pos": 'RB', "game": 'LAR vs TBD', "market": 'Rush Yds', "line": 62.5, "over": 100, "under": -120},
    {"player": 'Kyren Williams', "team": 'LAR', "pos": 'RB', "game": 'LAR vs TBD', "market": 'Receptions', "line": 2.5, "over": 100, "under": -120},
    {"player": 'Kyren Williams', "team": 'LAR', "pos": 'RB', "game": 'LAR vs TBD', "market": 'Rec Yds', "line": 19.5, "over": -110, "under": -110},
    {"player": 'Puka Nacua', "team": 'LAR', "pos": 'WR', "game": 'LAR vs TBD', "market": 'Receptions', "line": 6.5, "over": -110, "under": -110},
    {"player": 'Puka Nacua', "team": 'LAR', "pos": 'WR', "game": 'LAR vs TBD', "market": 'Rec Yds', "line": 74.0, "over": 105, "under": -125},
    {"player": 'Puka Nacua', "team": 'LAR', "pos": 'WR', "game": 'LAR vs TBD', "market": 'Rec TDs', "line": 0.5, "over": 100, "under": -120},
    {"player": 'Davante Adams', "team": 'LAR', "pos": 'WR', "game": 'LAR vs TBD', "market": 'Receptions', "line": 4.5, "over": 105, "under": -125},
    {"player": 'Davante Adams', "team": 'LAR', "pos": 'WR', "game": 'LAR vs TBD', "market": 'Rec Yds', "line": 60.5, "over": 105, "under": -125},
    {"player": 'Davante Adams', "team": 'LAR', "pos": 'WR', "game": 'LAR vs TBD', "market": 'Rec TDs', "line": 0.5, "over": -110, "under": -110},
    {"player": 'Geno Smith', "team": 'LV', "pos": 'QB', "game": 'LV vs TBD', "market": 'Pass Yds', "line": 221.0, "over": -110, "under": -110},
    {"player": 'Geno Smith', "team": 'LV', "pos": 'QB', "game": 'LV vs TBD', "market": 'Pass TDs', "line": 1.0, "over": 100, "under": -120},
    {"player": 'Geno Smith', "team": 'LV', "pos": 'QB', "game": 'LV vs TBD', "market": 'Rush Yds', "line": 11.5, "over": -110, "under": -110},
    {"player": 'Ashton Jeanty', "team": 'LV', "pos": 'RB', "game": 'LV vs TBD', "market": 'Rush Yds', "line": 59.5, "over": -120, "under": 100},
    {"player": 'Ashton Jeanty', "team": 'LV', "pos": 'RB', "game": 'LV vs TBD', "market": 'Receptions', "line": 2.5, "over": -110, "under": -110},
    {"player": 'Ashton Jeanty', "team": 'LV', "pos": 'RB', "game": 'LV vs TBD', "market": 'Rec Yds', "line": 17.0, "over": -125, "under": 105},
    {"player": 'Brock Bowers', "team": 'LV', "pos": 'TE', "game": 'LV vs TBD', "market": 'Receptions', "line": 5.5, "over": -110, "under": -110},
    {"player": 'Brock Bowers', "team": 'LV', "pos": 'TE', "game": 'LV vs TBD', "market": 'Rec Yds', "line": 61.0, "over": -120, "under": 100},
    {"player": 'Tua Tagovailoa', "team": 'MIA', "pos": 'QB', "game": 'MIA vs TBD', "market": 'Pass Yds', "line": 209.0, "over": -120, "under": 100},
    {"player": 'Tua Tagovailoa', "team": 'MIA', "pos": 'QB', "game": 'MIA vs TBD', "market": 'Pass TDs', "line": 1.0, "over": 105, "under": -125},
    {"player": 'Tua Tagovailoa', "team": 'MIA', "pos": 'QB', "game": 'MIA vs TBD', "market": 'Rush Yds', "line": 10.5, "over": 100, "under": -120},
    {"player": "De'Von Achane", "team": 'MIA', "pos": 'RB', "game": 'MIA vs TBD', "market": 'Rush Yds', "line": 62.0, "over": 100, "under": -120},
    {"player": "De'Von Achane", "team": 'MIA', "pos": 'RB', "game": 'MIA vs TBD', "market": 'Receptions', "line": 2.5, "over": -110, "under": -110},
    {"player": "De'Von Achane", "team": 'MIA', "pos": 'RB', "game": 'MIA vs TBD', "market": 'Rec Yds', "line": 18.0, "over": 105, "under": -125},
    {"player": 'Tyreek Hill', "team": 'MIA', "pos": 'WR', "game": 'MIA vs TBD', "market": 'Receptions', "line": 4.5, "over": 100, "under": -120},
    {"player": 'Tyreek Hill', "team": 'MIA', "pos": 'WR', "game": 'MIA vs TBD', "market": 'Rec Yds', "line": 59.0, "over": 105, "under": -125},
    {"player": 'Tyreek Hill', "team": 'MIA', "pos": 'WR', "game": 'MIA vs TBD', "market": 'Rec TDs', "line": 0.5, "over": -120, "under": 100},
    {"player": 'Jaylen Waddle', "team": 'MIA', "pos": 'WR', "game": 'MIA vs TBD', "market": 'Receptions', "line": 3.5, "over": 105, "under": -125},
    {"player": 'Jaylen Waddle', "team": 'MIA', "pos": 'WR', "game": 'MIA vs TBD', "market": 'Rec Yds', "line": 47.5, "over": -120, "under": 100},
    {"player": 'Jaylen Waddle', "team": 'MIA', "pos": 'WR', "game": 'MIA vs TBD', "market": 'Rec TDs', "line": 0.5, "over": 100, "under": -120},
    {"player": 'J.J. McCarthy', "team": 'MIN', "pos": 'QB', "game": 'MIN vs TBD', "market": 'Pass Yds', "line": 238.5, "over": -110, "under": -110},
    {"player": 'J.J. McCarthy', "team": 'MIN', "pos": 'QB', "game": 'MIN vs TBD', "market": 'Pass TDs', "line": 1.0, "over": 100, "under": -120},
    {"player": 'J.J. McCarthy', "team": 'MIN', "pos": 'QB', "game": 'MIN vs TBD', "market": 'Rush Yds', "line": 10.5, "over": 100, "under": -120},
    {"player": 'Aaron Jones Sr.', "team": 'MIN', "pos": 'RB', "game": 'MIN vs TBD', "market": 'Rush Yds', "line": 42.0, "over": -125, "under": 105},
    {"player": 'Aaron Jones Sr.', "team": 'MIN', "pos": 'RB', "game": 'MIN vs TBD', "market": 'Receptions', "line": 1.5, "over": -125, "under": 105},
    {"player": 'Aaron Jones Sr.', "team": 'MIN', "pos": 'RB', "game": 'MIN vs TBD', "market": 'Rec Yds', "line": 13.5, "over": -110, "under": -110},
    {"player": 'Justin Jefferson', "team": 'MIN', "pos": 'WR', "game": 'MIN vs TBD', "market": 'Receptions', "line": 6.0, "over": -110, "under": -110},
    {"player": 'Justin Jefferson', "team": 'MIN', "pos": 'WR', "game": 'MIN vs TBD', "market": 'Rec Yds', "line": 87.5, "over": -110, "under": -110},
    {"player": 'Justin Jefferson', "team": 'MIN', "pos": 'WR', "game": 'MIN vs TBD', "market": 'Rec TDs', "line": 0.5, "over": 100, "under": -120},
    {"player": 'Jordan Addison', "team": 'MIN', "pos": 'WR', "game": 'MIN vs TBD', "market": 'Receptions', "line": 3.5, "over": -125, "under": 105},
    {"player": 'Jordan Addison', "team": 'MIN', "pos": 'WR', "game": 'MIN vs TBD', "market": 'Rec Yds', "line": 44.0, "over": -125, "under": 105},
    {"player": 'Jordan Addison', "team": 'MIN', "pos": 'WR', "game": 'MIN vs TBD', "market": 'Rec TDs', "line": 0.5, "over": 105, "under": -125},
    {"player": 'Drake Maye', "team": 'NE', "pos": 'QB', "game": 'NE vs TBD', "market": 'Pass Yds', "line": 258.0, "over": -110, "under": -110},
    {"player": 'Drake Maye', "team": 'NE', "pos": 'QB', "game": 'NE vs TBD', "market": 'Pass TDs', "line": 1.5, "over": -110, "under": -110},
    {"player": 'Drake Maye', "team": 'NE', "pos": 'QB', "game": 'NE vs TBD', "market": 'Rush Yds', "line": 16.0, "over": -120, "under": 100},
    {"player": 'Rhamondre Stevenson', "team": 'NE', "pos": 'RB', "game": 'NE vs TBD', "market": 'Rush Yds', "line": 43.0, "over": 105, "under": -125},
    {"player": 'Rhamondre Stevenson', "team": 'NE', "pos": 'RB', "game": 'NE vs TBD', "market": 'Receptions', "line": 1.5, "over": -125, "under": 105},
    {"player": 'Rhamondre Stevenson', "team": 'NE', "pos": 'RB', "game": 'NE vs TBD', "market": 'Rec Yds', "line": 13.0, "over": -110, "under": -110},
    {"player": 'A.J. Brown', "team": 'NE', "pos": 'WR', "game": 'NE vs TBD', "market": 'Receptions', "line": 6.5, "over": -110, "under": -110},
    {"player": 'A.J. Brown', "team": 'NE', "pos": 'WR', "game": 'NE vs TBD', "market": 'Rec Yds', "line": 81.0, "over": 100, "under": -120},
    {"player": 'A.J. Brown', "team": 'NE', "pos": 'WR', "game": 'NE vs TBD', "market": 'Rec TDs', "line": 0.5, "over": -125, "under": 105},
    {"player": 'Hunter Henry', "team": 'NE', "pos": 'TE', "game": 'NE vs TBD', "market": 'Receptions', "line": 3.5, "over": -110, "under": -110},
    {"player": 'Hunter Henry', "team": 'NE', "pos": 'TE', "game": 'NE vs TBD', "market": 'Rec Yds', "line": 31.0, "over": 105, "under": -125},
    {"player": 'Tyler Shough', "team": 'NO', "pos": 'QB', "game": 'NO vs TBD', "market": 'Pass Yds', "line": 187.0, "over": -120, "under": 100},
    {"player": 'Tyler Shough', "team": 'NO', "pos": 'QB', "game": 'NO vs TBD', "market": 'Pass TDs', "line": 1.0, "over": -110, "under": -110},
    {"player": 'Tyler Shough', "team": 'NO', "pos": 'QB', "game": 'NO vs TBD', "market": 'Rush Yds', "line": 8.5, "over": 100, "under": -120},
    {"player": 'Alvin Kamara', "team": 'NO', "pos": 'RB', "game": 'NO vs TBD', "market": 'Rush Yds', "line": 59.5, "over": -120, "under": 100},
    {"player": 'Alvin Kamara', "team": 'NO', "pos": 'RB', "game": 'NO vs TBD', "market": 'Receptions', "line": 2.5, "over": -110, "under": -110},
    {"player": 'Alvin Kamara', "team": 'NO', "pos": 'RB', "game": 'NO vs TBD', "market": 'Rec Yds', "line": 21.0, "over": -110, "under": -110},
    {"player": 'Chris Olave', "team": 'NO', "pos": 'WR', "game": 'NO vs TBD', "market": 'Receptions', "line": 3.5, "over": 105, "under": -125},
    {"player": 'Chris Olave', "team": 'NO', "pos": 'WR', "game": 'NO vs TBD', "market": 'Rec Yds', "line": 47.5, "over": 100, "under": -120},
    {"player": 'Chris Olave', "team": 'NO', "pos": 'WR', "game": 'NO vs TBD', "market": 'Rec TDs', "line": 0.5, "over": -120, "under": 100},
    {"player": 'Jaxson Dart', "team": 'NYG', "pos": 'QB', "game": 'NYG vs TBD', "market": 'Pass Yds', "line": 226.0, "over": -110, "under": -110},
    {"player": 'Jaxson Dart', "team": 'NYG', "pos": 'QB', "game": 'NYG vs TBD', "market": 'Pass TDs', "line": 1.0, "over": 100, "under": -120},
    {"player": 'Jaxson Dart', "team": 'NYG', "pos": 'QB', "game": 'NYG vs TBD', "market": 'Rush Yds', "line": 10.0, "over": 105, "under": -125},
    {"player": 'Tyrone Tracy Jr.', "team": 'NYG', "pos": 'RB', "game": 'NYG vs TBD', "market": 'Rush Yds', "line": 46.0, "over": 100, "under": -120},
    {"player": 'Tyrone Tracy Jr.', "team": 'NYG', "pos": 'RB', "game": 'NYG vs TBD', "market": 'Receptions', "line": 2.0, "over": -110, "under": -110},
    {"player": 'Tyrone Tracy Jr.', "team": 'NYG', "pos": 'RB', "game": 'NYG vs TBD', "market": 'Rec Yds', "line": 11.5, "over": 105, "under": -125},
    {"player": 'Malik Nabers', "team": 'NYG', "pos": 'WR', "game": 'NYG vs TBD', "market": 'Receptions', "line": 5.5, "over": 105, "under": -125},
    {"player": 'Malik Nabers', "team": 'NYG', "pos": 'WR', "game": 'NYG vs TBD', "market": 'Rec Yds', "line": 81.0, "over": 100, "under": -120},
    {"player": 'Malik Nabers', "team": 'NYG', "pos": 'WR', "game": 'NYG vs TBD', "market": 'Rec TDs', "line": 0.5, "over": -120, "under": 100},
    {"player": 'Justin Fields', "team": 'NYJ', "pos": 'QB', "game": 'NYJ vs TBD', "market": 'Pass Yds', "line": 233.5, "over": -110, "under": -110},
    {"player": 'Justin Fields', "team": 'NYJ', "pos": 'QB', "game": 'NYJ vs TBD', "market": 'Pass TDs', "line": 1.5, "over": -110, "under": -110},
    {"player": 'Justin Fields', "team": 'NYJ', "pos": 'QB', "game": 'NYJ vs TBD', "market": 'Rush Yds', "line": 11.5, "over": -110, "under": -110},
    {"player": 'Breece Hall', "team": 'NYJ', "pos": 'RB', "game": 'NYJ vs TBD', "market": 'Rush Yds', "line": 64.0, "over": -110, "under": -110},
    {"player": 'Breece Hall', "team": 'NYJ', "pos": 'RB', "game": 'NYJ vs TBD', "market": 'Receptions', "line": 2.0, "over": -125, "under": 105},
    {"player": 'Breece Hall', "team": 'NYJ', "pos": 'RB', "game": 'NYJ vs TBD', "market": 'Rec Yds', "line": 19.0, "over": 100, "under": -120},
    {"player": 'Garrett Wilson', "team": 'NYJ', "pos": 'WR', "game": 'NYJ vs TBD', "market": 'Receptions', "line": 5.0, "over": -110, "under": -110},
    {"player": 'Garrett Wilson', "team": 'NYJ', "pos": 'WR', "game": 'NYJ vs TBD', "market": 'Rec Yds', "line": 61.0, "over": -120, "under": 100},
    {"player": 'Garrett Wilson', "team": 'NYJ', "pos": 'WR', "game": 'NYJ vs TBD', "market": 'Rec TDs', "line": 0.5, "over": 100, "under": -120},
    {"player": 'Jalen Hurts', "team": 'PHI', "pos": 'QB', "game": 'PHI vs TBD', "market": 'Pass Yds', "line": 225.5, "over": 105, "under": -125},
    {"player": 'Jalen Hurts', "team": 'PHI', "pos": 'QB', "game": 'PHI vs TBD', "market": 'Pass TDs', "line": 1.5, "over": 105, "under": -125},
    {"player": 'Jalen Hurts', "team": 'PHI', "pos": 'QB', "game": 'PHI vs TBD', "market": 'Rush Yds', "line": 16.0, "over": -120, "under": 100},
    {"player": 'Saquon Barkley', "team": 'PHI', "pos": 'RB', "game": 'PHI vs TBD', "market": 'Rush Yds', "line": 75.0, "over": 105, "under": -125},
    {"player": 'Saquon Barkley', "team": 'PHI', "pos": 'RB', "game": 'PHI vs TBD', "market": 'Receptions', "line": 3.0, "over": 105, "under": -125},
    {"player": 'Saquon Barkley', "team": 'PHI', "pos": 'RB', "game": 'PHI vs TBD', "market": 'Rec Yds', "line": 27.0, "over": -120, "under": 100},
    {"player": 'DeVonta Smith', "team": 'PHI', "pos": 'WR', "game": 'PHI vs TBD', "market": 'Receptions', "line": 4.0, "over": -125, "under": 105},
    {"player": 'DeVonta Smith', "team": 'PHI', "pos": 'WR', "game": 'PHI vs TBD', "market": 'Rec Yds', "line": 62.5, "over": -120, "under": 100},
    {"player": 'DeVonta Smith', "team": 'PHI', "pos": 'WR', "game": 'PHI vs TBD', "market": 'Rec TDs', "line": 0.5, "over": -120, "under": 100},
    {"player": 'Dallas Goedert', "team": 'PHI', "pos": 'TE', "game": 'PHI vs TBD', "market": 'Receptions', "line": 3.0, "over": -110, "under": -110},
    {"player": 'Dallas Goedert', "team": 'PHI', "pos": 'TE', "game": 'PHI vs TBD', "market": 'Rec Yds', "line": 33.0, "over": 100, "under": -120},
    {"player": 'Aaron Rodgers', "team": 'PIT', "pos": 'QB', "game": 'PIT vs TBD', "market": 'Pass Yds', "line": 201.5, "over": 105, "under": -125},
    {"player": 'Aaron Rodgers', "team": 'PIT', "pos": 'QB', "game": 'PIT vs TBD', "market": 'Pass TDs', "line": 1.5, "over": -110, "under": -110},
    {"player": 'Aaron Rodgers', "team": 'PIT', "pos": 'QB', "game": 'PIT vs TBD', "market": 'Rush Yds', "line": 10.5, "over": -120, "under": 100},
    {"player": 'Jaylen Warren', "team": 'PIT', "pos": 'RB', "game": 'PIT vs TBD', "market": 'Rush Yds', "line": 49.5, "over": -110, "under": -110},
    {"player": 'Jaylen Warren', "team": 'PIT', "pos": 'RB', "game": 'PIT vs TBD', "market": 'Receptions', "line": 2.0, "over": -110, "under": -110},
    {"player": 'Jaylen Warren', "team": 'PIT', "pos": 'RB', "game": 'PIT vs TBD', "market": 'Rec Yds', "line": 11.5, "over": 105, "under": -125},
    {"player": 'DK Metcalf', "team": 'PIT', "pos": 'WR', "game": 'PIT vs TBD', "market": 'Receptions', "line": 5.0, "over": -110, "under": -110},
    {"player": 'DK Metcalf', "team": 'PIT', "pos": 'WR', "game": 'PIT vs TBD', "market": 'Rec Yds', "line": 65.5, "over": -110, "under": -110},
    {"player": 'DK Metcalf', "team": 'PIT', "pos": 'WR', "game": 'PIT vs TBD', "market": 'Rec TDs', "line": 0.5, "over": -125, "under": 105},
    {"player": 'Calvin Austin III', "team": 'PIT', "pos": 'WR', "game": 'PIT vs TBD', "market": 'Receptions', "line": 2.5, "over": -110, "under": -110},
    {"player": 'Calvin Austin III', "team": 'PIT', "pos": 'WR', "game": 'PIT vs TBD', "market": 'Rec Yds', "line": 37.5, "over": -110, "under": -110},
    {"player": 'Sam Darnold', "team": 'SEA', "pos": 'QB', "game": 'SEA vs TBD', "market": 'Pass Yds', "line": 220.5, "over": -110, "under": -110},
    {"player": 'Sam Darnold', "team": 'SEA', "pos": 'QB', "game": 'SEA vs TBD', "market": 'Pass TDs', "line": 1.5, "over": -110, "under": -110},
    {"player": 'Sam Darnold', "team": 'SEA', "pos": 'QB', "game": 'SEA vs TBD', "market": 'Rush Yds', "line": 11.5, "over": -110, "under": -110},
    {"player": 'Kenneth Walker III', "team": 'SEA', "pos": 'RB', "game": 'SEA vs TBD', "market": 'Rush Yds', "line": 60.5, "over": -120, "under": 100},
    {"player": 'Kenneth Walker III', "team": 'SEA', "pos": 'RB', "game": 'SEA vs TBD', "market": 'Receptions', "line": 2.0, "over": -125, "under": 105},
    {"player": 'Kenneth Walker III', "team": 'SEA', "pos": 'RB', "game": 'SEA vs TBD', "market": 'Rec Yds', "line": 20.0, "over": -110, "under": -110},
    {"player": 'Jaxon Smith-Njigba', "team": 'SEA', "pos": 'WR', "game": 'SEA vs TBD', "market": 'Receptions', "line": 5.5, "over": 105, "under": -125},
    {"player": 'Jaxon Smith-Njigba', "team": 'SEA', "pos": 'WR', "game": 'SEA vs TBD', "market": 'Rec Yds', "line": 82.5, "over": -110, "under": -110},
    {"player": 'Jaxon Smith-Njigba', "team": 'SEA', "pos": 'WR', "game": 'SEA vs TBD', "market": 'Rec TDs', "line": 0.5, "over": -110, "under": -110},
    {"player": 'Brock Purdy', "team": 'SF', "pos": 'QB', "game": 'SF vs TBD', "market": 'Pass Yds', "line": 266.5, "over": -110, "under": -110},
    {"player": 'Brock Purdy', "team": 'SF', "pos": 'QB', "game": 'SF vs TBD', "market": 'Pass TDs', "line": 2.0, "over": -110, "under": -110},
    {"player": 'Brock Purdy', "team": 'SF', "pos": 'QB', "game": 'SF vs TBD', "market": 'Rush Yds', "line": 17.0, "over": -110, "under": -110},
    {"player": 'Christian McCaffrey', "team": 'SF', "pos": 'RB', "game": 'SF vs TBD', "market": 'Rush Yds', "line": 83.0, "over": -110, "under": -110},
    {"player": 'Christian McCaffrey', "team": 'SF', "pos": 'RB', "game": 'SF vs TBD', "market": 'Receptions', "line": 3.5, "over": -110, "under": -110},
    {"player": 'Christian McCaffrey', "team": 'SF', "pos": 'RB', "game": 'SF vs TBD', "market": 'Rec Yds', "line": 30.5, "over": -110, "under": -110},
    {"player": 'Brandon Aiyuk', "team": 'SF', "pos": 'WR', "game": 'SF vs TBD', "market": 'Receptions', "line": 4.0, "over": -125, "under": 105},
    {"player": 'Brandon Aiyuk', "team": 'SF', "pos": 'WR', "game": 'SF vs TBD', "market": 'Rec Yds', "line": 62.5, "over": -120, "under": 100},
    {"player": 'Brandon Aiyuk', "team": 'SF', "pos": 'WR', "game": 'SF vs TBD', "market": 'Rec TDs', "line": 0.5, "over": -125, "under": 105},
    {"player": 'George Kittle', "team": 'SF', "pos": 'TE', "game": 'SF vs TBD', "market": 'Receptions', "line": 3.5, "over": 105, "under": -125},
    {"player": 'George Kittle', "team": 'SF', "pos": 'TE', "game": 'SF vs TBD', "market": 'Rec Yds', "line": 45.5, "over": -120, "under": 100},
    {"player": 'Baker Mayfield', "team": 'TB', "pos": 'QB', "game": 'TB vs TBD', "market": 'Pass Yds', "line": 221.5, "over": -125, "under": 105},
    {"player": 'Baker Mayfield', "team": 'TB', "pos": 'QB', "game": 'TB vs TBD', "market": 'Pass TDs', "line": 1.5, "over": -110, "under": -110},
    {"player": 'Baker Mayfield', "team": 'TB', "pos": 'QB', "game": 'TB vs TBD', "market": 'Rush Yds', "line": 18.0, "over": -110, "under": -110},
    {"player": 'Bucky Irving', "team": 'TB', "pos": 'RB', "game": 'TB vs TBD', "market": 'Rush Yds', "line": 62.5, "over": 100, "under": -120},
    {"player": 'Bucky Irving', "team": 'TB', "pos": 'RB', "game": 'TB vs TBD', "market": 'Receptions', "line": 2.5, "over": -110, "under": -110},
    {"player": 'Bucky Irving', "team": 'TB', "pos": 'RB', "game": 'TB vs TBD', "market": 'Rec Yds', "line": 18.0, "over": 105, "under": -125},
    {"player": 'Mike Evans', "team": 'TB', "pos": 'WR', "game": 'TB vs TBD', "market": 'Receptions', "line": 5.0, "over": -110, "under": -110},
    {"player": 'Mike Evans', "team": 'TB', "pos": 'WR', "game": 'TB vs TBD', "market": 'Rec Yds', "line": 62.5, "over": -120, "under": 100},
    {"player": 'Mike Evans', "team": 'TB', "pos": 'WR', "game": 'TB vs TBD', "market": 'Rec TDs', "line": 0.5, "over": -125, "under": 105},
    {"player": 'Chris Godwin', "team": 'TB', "pos": 'WR', "game": 'TB vs TBD', "market": 'Receptions', "line": 4.0, "over": -110, "under": -110},
    {"player": 'Chris Godwin', "team": 'TB', "pos": 'WR', "game": 'TB vs TBD', "market": 'Rec Yds', "line": 50.5, "over": -110, "under": -110},
    {"player": 'Chris Godwin', "team": 'TB', "pos": 'WR', "game": 'TB vs TBD', "market": 'Rec TDs', "line": 0.5, "over": 100, "under": -120},
    {"player": 'Cam Ward', "team": 'TEN', "pos": 'QB', "game": 'TEN vs TBD', "market": 'Pass Yds', "line": 232.0, "over": -110, "under": -110},
    {"player": 'Cam Ward', "team": 'TEN', "pos": 'QB', "game": 'TEN vs TBD', "market": 'Pass TDs', "line": 1.0, "over": -120, "under": 100},
    {"player": 'Cam Ward', "team": 'TEN', "pos": 'QB', "game": 'TEN vs TBD', "market": 'Rush Yds', "line": 10.0, "over": -120, "under": 100},
    {"player": 'Tony Pollard', "team": 'TEN', "pos": 'RB', "game": 'TEN vs TBD', "market": 'Rush Yds', "line": 49.5, "over": -110, "under": -110},
    {"player": 'Tony Pollard', "team": 'TEN', "pos": 'RB', "game": 'TEN vs TBD', "market": 'Receptions', "line": 1.5, "over": -120, "under": 100},
    {"player": 'Tony Pollard', "team": 'TEN', "pos": 'RB', "game": 'TEN vs TBD', "market": 'Rec Yds', "line": 11.0, "over": -125, "under": 105},
    {"player": 'Calvin Ridley', "team": 'TEN', "pos": 'WR', "game": 'TEN vs TBD', "market": 'Receptions', "line": 4.0, "over": -110, "under": -110},
    {"player": 'Calvin Ridley', "team": 'TEN', "pos": 'WR', "game": 'TEN vs TBD', "market": 'Rec Yds', "line": 46.0, "over": 105, "under": -125},
    {"player": 'Calvin Ridley', "team": 'TEN', "pos": 'WR', "game": 'TEN vs TBD', "market": 'Rec TDs', "line": 0.5, "over": 100, "under": -120},
    {"player": 'Jayden Daniels', "team": 'WAS', "pos": 'QB', "game": 'WAS vs TBD', "market": 'Pass Yds', "line": 291.0, "over": -110, "under": -110},
    {"player": 'Jayden Daniels', "team": 'WAS', "pos": 'QB', "game": 'WAS vs TBD', "market": 'Pass TDs', "line": 2.0, "over": -125, "under": 105},
    {"player": 'Jayden Daniels', "team": 'WAS', "pos": 'QB', "game": 'WAS vs TBD', "market": 'Rush Yds', "line": 25.0, "over": 105, "under": -125},
    {"player": 'Brian Robinson Jr.', "team": 'WAS', "pos": 'RB', "game": 'WAS vs TBD', "market": 'Rush Yds', "line": 48.5, "over": -110, "under": -110},
    {"player": 'Brian Robinson Jr.', "team": 'WAS', "pos": 'RB', "game": 'WAS vs TBD', "market": 'Receptions', "line": 1.5, "over": -120, "under": 100},
    {"player": 'Brian Robinson Jr.', "team": 'WAS', "pos": 'RB', "game": 'WAS vs TBD', "market": 'Rec Yds', "line": 12.5, "over": -110, "under": -110},
    {"player": 'Terry McLaurin', "team": 'WAS', "pos": 'WR', "game": 'WAS vs TBD', "market": 'Receptions', "line": 5.0, "over": -110, "under": -110},
    {"player": 'Terry McLaurin', "team": 'WAS', "pos": 'WR', "game": 'WAS vs TBD', "market": 'Rec Yds', "line": 68.0, "over": -110, "under": -110},
    {"player": 'Terry McLaurin', "team": 'WAS', "pos": 'WR', "game": 'WAS vs TBD', "market": 'Rec TDs', "line": 0.5, "over": 105, "under": -125},
    {"player": 'Deebo Samuel Sr.', "team": 'WAS', "pos": 'WR', "game": 'WAS vs TBD', "market": 'Receptions', "line": 4.0, "over": -110, "under": -110},
    {"player": 'Deebo Samuel Sr.', "team": 'WAS', "pos": 'WR', "game": 'WAS vs TBD', "market": 'Rec Yds', "line": 50.0, "over": -110, "under": -110},
    {"player": 'Deebo Samuel Sr.', "team": 'WAS', "pos": 'WR', "game": 'WAS vs TBD', "market": 'Rec TDs', "line": 0.5, "over": 100, "under": -120},
]

PROPS_PAGE_SIZES = [12, 24, 48]
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

# ---- Live NFL game odds (The Odds API) ----
ODDS_API_URL = "https://api.the-odds-api.com/v4/sports/americanfootball_nfl/odds"
ODDS_API_TTL_SECONDS = 3 * 60 * 60  # free tier is ~500 credits/month — don't refetch every reload
PREFERRED_BOOKMAKERS = ["draftkings", "fanduel", "betmgm", "caesars", "espnbet"]
BOOKS_PER_GAME = 4

def get_odds_api_key():
    try:
        return st.secrets.get("ODDS_API_KEY")
    except Exception:
        return None

def odds_cache_bucket():
    """Current TTL window, used as a cache-key argument.

    Streamlit silently ignores `ttl` on a `persist="disk"` cache (it logs
    "TTL that will be ignored" at startup), so the odds cache never expired —
    the board was still serving the payload fetched the first time the app
    ran. Passing the time bucket in as an argument gives the persistent cache
    a key that rolls over every TTL, which expires it for real while still
    surviving restarts so we don't burn API credits on every reload.
    """
    return int(time.time() // ODDS_API_TTL_SECONDS)


# show_spinner=False: the Betting tab paints skeleton cards while this runs,
# and a spinner stacked on top of them just reads as two loading states.
@st.cache_data(persist="disk", show_spinner=False)
def fetch_nfl_odds_raw(api_key, bucket):
    resp = requests.get(
        ODDS_API_URL,
        params={
            "apiKey": api_key,
            "regions": "us",
            "markets": "h2h,spreads,totals",
            "oddsFormat": "american",
        },
        timeout=10,
    )
    resp.raise_for_status()
    return {"fetched_at": time.time(), "games": resp.json()}

def parse_odds_games(raw_games):
    games = []
    for g in raw_games or []:
        away, home = g.get("away_team", ""), g.get("home_team", "")
        books = []
        for bm in g.get("bookmakers", []):
            entry = {"key": bm.get("key"), "title": bm.get("title") or bm.get("key") or "Book"}
            for mkt in bm.get("markets", []):
                mkey = mkt.get("key")
                outcomes = mkt.get("outcomes", [])
                if mkey == "h2h":
                    h2h = {}
                    for o in outcomes:
                        if o.get("name") == home:
                            h2h["home"] = o.get("price")
                        elif o.get("name") == away:
                            h2h["away"] = o.get("price")
                    if "home" in h2h and "away" in h2h:
                        entry["h2h"] = h2h
                elif mkey == "spreads":
                    sp = {}
                    for o in outcomes:
                        side = "home" if o.get("name") == home else "away" if o.get("name") == away else None
                        if side:
                            sp[side] = {"price": o.get("price"), "point": o.get("point")}
                    if "home" in sp and "away" in sp:
                        entry["spreads"] = sp
                elif mkey == "totals":
                    tot = {}
                    for o in outcomes:
                        name = (o.get("name") or "").lower()
                        if name in ("over", "under"):
                            tot[name] = {"price": o.get("price"), "point": o.get("point")}
                    if "over" in tot and "under" in tot:
                        entry["totals"] = tot
            if any(k in entry for k in ("h2h", "spreads", "totals")):
                books.append(entry)
        books.sort(key=lambda b: PREFERRED_BOOKMAKERS.index(b["key"]) if b["key"] in PREFERRED_BOOKMAKERS else len(PREFERRED_BOOKMAKERS))
        capped_books = books[:BOOKS_PER_GAME]
        games.append({
            "id": g.get("id"),
            "away": away,
            "home": home,
            "commence_time": g.get("commence_time", ""),
            "books": capped_books,
            "consensus": build_game_consensus(capped_books),
        })
    games.sort(key=lambda g: g["commence_time"])
    return games

def load_nfl_betting_board():
    """Returns (games, error, fetched_at).

    error is None on success, else a short reason code/message. fetched_at is
    the unix time the live payload was actually pulled from The Odds API (not
    when it was read back out of cache), so the board can show line age.
    """
    api_key = get_odds_api_key()
    if not api_key:
        return None, "missing_key", None
    try:
        raw = fetch_nfl_odds_raw(api_key, odds_cache_bucket())
    except requests.exceptions.RequestException as e:
        detail = str(e).replace(api_key, "***")
        return None, f"The Odds API request failed: {detail}", None
    except Exception as e:
        detail = str(e).replace(api_key, "***")
        return None, f"Unexpected error loading odds: {detail}", None
    return parse_odds_games(raw.get("games")), None, raw.get("fetched_at")

def odds_table_html(columns, rows, highlight=None):
    """Render a compact odds table as plain HTML.

    st.dataframe (and especially a pandas Styler) costs far more per call than
    markup does, and the Betting board draws two tables per game — this keeps
    a full week of games cheap to re-render. `highlight` is a set of
    (row_index, column_name) cells to paint as the best available price.
    """
    highlight = highlight or set()
    head = "".join(f"<th>{c}</th>" for c in columns)
    body = ""
    for r_i, row in enumerate(rows):
        cells = ""
        for c in columns:
            val = row.get(c, "—")
            cls = " class='fm-odds-best'" if (r_i, c) in highlight else ""
            cells += f"<td{cls}>{val}</td>"
        body += f"<tr>{cells}</tr>"
    return (
        f"<div class='fm-odds-wrap'><table class='fm-odds-table'>"
        f"<thead><tr>{head}</tr></thead><tbody>{body}</tbody></table></div>"
    )


def odds_skeleton_html(cards=6):
    """Shimmer placeholders shaped like the real game cards.

    Shown while the live odds request is in flight — Streamlit blocks on the
    fetch, so without this the tab is blank apart from a spinner. Matching the
    card's own grid means the board doesn't jump when real data lands.
    """
    col = (
        "<div><div class='fm-skel' style='width:58%;margin-left:auto'></div>"
        "<div class='fm-skel' style='width:42%;margin:8px 0 0 auto'></div></div>"
    )
    card = (
        "<div class='fm-skel-card'><div class='fm-skel-row'>"
        "<div>"
        "<div class='fm-skel' style='width:56%'></div>"
        "<div class='fm-skel fm-skel-lg' style='width:80%;margin-top:9px'></div>"
        "<div class='fm-skel fm-skel-lg' style='width:68%;margin-top:6px'></div>"
        "</div>"
        f"{col}{col}{col}"
        "</div><div class='fm-skel fm-skel-bar'></div></div>"
    )
    return card * cards


def odds_freshness_html(fetched_at, game_count):
    """Line-age strip. Stale odds are worse than no odds on a betting board,
    so the age is stated outright rather than buried in a caption."""
    if not fetched_at:
        age_txt, tone = "unknown", "stale"
    else:
        mins = max(0, int((time.time() - fetched_at) / 60))
        if mins < 60:
            age_txt = f"{mins} min ago"
        elif mins < 60 * 48:
            age_txt = f"{mins // 60}h ago"
        else:
            age_txt = f"{mins // 1440}d ago"
        tone = "fresh" if mins <= ODDS_API_TTL_SECONDS / 60 else "stale"
    return (
        f"<div class='fm-freshness'>"
        f"<span class='fm-fresh-dot fm-fresh-{tone}'></span>"
        f"<span class='fm-fresh-txt'>Lines updated <b>{age_txt}</b></span>"
        f"<span class='fm-fresh-sep'>·</span>"
        f"<span class='fm-fresh-txt'>{game_count} game{'s' if game_count != 1 else ''}</span>"
        f"<span class='fm-fresh-sep'>·</span>"
        f"<span class='fm-fresh-txt'>Source: The Odds API</span>"
        f"</div>"
    )


def win_prob_bar_html(away, home, away_price, home_price):
    """De-vigged moneyline as a two-sided win-probability bar — the fastest
    read on a board of games, and it's already computed for the consensus."""
    if away_price is None or home_price is None:
        return ""
    pa, ph = devig_two_way(away_price, home_price)
    return (
        f"<div class='fm-wp'>"
        f"<div class='fm-wp-row'>"
        f"<span class='fm-wp-team'>{away}</span>"
        f"<span class='fm-wp-pct fm-nums'>{pa * 100:.0f}%</span>"
        f"<span class='fm-wp-spacer'></span>"
        f"<span class='fm-wp-pct fm-nums'>{ph * 100:.0f}%</span>"
        f"<span class='fm-wp-team'>{home}</span>"
        f"</div>"
        f"<div class='fm-wp-bar'>"
        f"<div class='fm-wp-away' style='width:{pa * 100:.1f}%'></div>"
        f"<div class='fm-wp-home' style='width:{ph * 100:.1f}%'></div>"
        f"</div></div>"
    )


def game_card_header_html(g, consensus):
    """At-a-glance matchup card: teams, kickoff, and the consensus spread /
    total / moneyline without needing to expand anything."""
    def cell(label, away_val, home_val):
        return (
            f"<div class='fm-gc-col'>"
            f"<div class='fm-gc-lab'>{label}</div>"
            f"<div class='fm-gc-val fm-nums'>{away_val}</div>"
            f"<div class='fm-gc-val fm-nums'>{home_val}</div>"
            f"</div>"
        )

    sp = consensus.get("spreads")
    tot = consensus.get("totals")
    ml = consensus.get("h2h")
    spread_cell = cell(
        "SPREAD",
        f"{sp['away_point']:+g}" if sp else "—",
        f"{sp['home_point']:+g}" if sp else "—",
    )
    total_cell = cell(
        "TOTAL",
        f"O {tot['point']:g}" if tot else "—",
        f"U {tot['point']:g}" if tot else "—",
    )
    ml_cell = cell(
        "MONEYLINE",
        fmt_odds(ml["away"]) if ml else "—",
        fmt_odds(ml["home"]) if ml else "—",
    )
    return (
        f"<div class='fm-gc'>"
        f"<div class='fm-gc-teams'>"
        f"<div class='fm-gc-kick'>{fmt_kickoff(g['commence_time'])}</div>"
        f"<div class='fm-gc-team'>{g['away']}</div>"
        f"<div class='fm-gc-team'>{g['home']}</div>"
        f"</div>"
        f"{spread_cell}{total_cell}{ml_cell}"
        f"</div>"
    )



def build_game_consensus(books):
    """MACHINE Consensus: de-vig every listed book's price for a side, average
    those fair probabilities across books, then convert back to American
    odds. This is the only price Steel bets settle at — individual books
    are shown for reference only, so nobody can line-shop between them."""
    consensus = {}

    h2h_books = [b for b in books if "h2h" in b]
    if h2h_books:
        fair_away = [devig_two_way(b["h2h"]["away"], b["h2h"]["home"])[0] for b in h2h_books]
        fair_home = [devig_two_way(b["h2h"]["away"], b["h2h"]["home"])[1] for b in h2h_books]
        avg_a, avg_h = sum(fair_away) / len(fair_away), sum(fair_home) / len(fair_home)
        norm = avg_a + avg_h
        consensus["h2h"] = {
            "away": implied_prob_to_american(avg_a / norm),
            "home": implied_prob_to_american(avg_h / norm),
            "book_count": len(h2h_books),
        }

    spread_books = [b for b in books if "spreads" in b]
    if spread_books:
        fair_away = [devig_two_way(b["spreads"]["away"]["price"], b["spreads"]["home"]["price"])[0] for b in spread_books]
        fair_home = [devig_two_way(b["spreads"]["away"]["price"], b["spreads"]["home"]["price"])[1] for b in spread_books]
        avg_a, avg_h = sum(fair_away) / len(fair_away), sum(fair_home) / len(fair_home)
        norm = avg_a + avg_h
        home_points = sorted(b["spreads"]["home"]["point"] for b in spread_books)
        median_home_point = home_points[len(home_points) // 2]
        consensus["spreads"] = {
            "away": implied_prob_to_american(avg_a / norm),
            "home": implied_prob_to_american(avg_h / norm),
            "away_point": -median_home_point,
            "home_point": median_home_point,
            "book_count": len(spread_books),
        }

    total_books = [b for b in books if "totals" in b]
    if total_books:
        fair_over = [devig_two_way(b["totals"]["over"]["price"], b["totals"]["under"]["price"])[0] for b in total_books]
        fair_under = [devig_two_way(b["totals"]["over"]["price"], b["totals"]["under"]["price"])[1] for b in total_books]
        avg_o, avg_u = sum(fair_over) / len(fair_over), sum(fair_under) / len(fair_under)
        norm = avg_o + avg_u
        over_points = sorted(b["totals"]["over"]["point"] for b in total_books)
        median_point = over_points[len(over_points) // 2]
        consensus["totals"] = {
            "over": implied_prob_to_american(avg_o / norm),
            "under": implied_prob_to_american(avg_u / norm),
            "point": median_point,
            "book_count": len(total_books),
        }

    return consensus

def fmt_kickoff(iso_ts):
    try:
        dt = datetime.fromisoformat(iso_ts.replace("Z", "+00:00"))
        et = dt.astimezone(ZoneInfo("America/New_York"))
        return et.strftime(f"%a %b %d, %I:%M %p {et.tzname()}")
    except Exception:
        return iso_ts or "TBD"

def nfl_week_label(iso_ts):
    """Best-effort NFL week label for a game's kickoff time.

    The Odds API doesn't tag games with a week number, so derive one from the
    standard schedule rule: Week 1 kicks off the Thursday after Labor Day, and
    each week resets on Tuesday.
    """
    try:
        dt = datetime.fromisoformat(iso_ts.replace("Z", "+00:00"))
    except Exception:
        return "TBD"
    season_year = dt.year if dt.month >= 3 else dt.year - 1
    sep1 = date(season_year, 9, 1)
    labor_day = sep1 + timedelta(days=(7 - sep1.weekday()) % 7)
    week1_kickoff = labor_day + timedelta(days=3)
    boundary_start = week1_kickoff - timedelta(days=2)  # weeks reset on Tuesday
    delta_days = (dt.date() - boundary_start).days
    if delta_days < 0:
        return "Preseason"
    week_num = delta_days // 7 + 1
    return f"Week {week_num}" if week_num <= 18 else "Playoffs"

def nfl_week_sort_key(label):
    if label == "Preseason":
        return -1
    if label == "Playoffs":
        return 999
    if label.startswith("Week "):
        try:
            return int(label.split(" ")[1])
        except (IndexError, ValueError):
            return 500
    return 1000  # "TBD" and anything unrecognized sorts last

# ---- Historical NFL data (Supabase: teams / games / ats_results) ----
# Reads with the anon key only — this app never writes to Supabase.
# scripts/load_historical_data.py (a separate, offline, one-time job) is
# what populates these tables using its own service_role key.
@st.cache_resource(show_spinner=False)
def get_supabase_client():
    try:
        url = st.secrets.get("SUPABASE_URL")
        key = st.secrets.get("SUPABASE_ANON_KEY")
    except Exception:
        return None
    if not url or not key:
        return None
    # Imported lazily: `supabase` costs ~1s to import and is only needed by
    # the historical-data tabs, so it shouldn't be paid on every cold start.
    from supabase import create_client
    return create_client(url, key)

def _fetch_all_rows(client, table_name, page_size=1000):
    """PostgREST caps a bare select() at ~1000 rows — page through with
    .range() until a short page signals the end, instead of silently
    truncating the table."""
    rows = []
    start = 0
    while True:
        page = client.table(table_name).select("*").range(start, start + page_size - 1).execute().data
        rows.extend(page)
        if len(page) < page_size:
            break
        start += page_size
    return rows

@st.cache_data(ttl=3600, show_spinner="Loading historical NFL data...")
def fetch_supabase_ats_data():
    client = get_supabase_client()
    if not client:
        return None, None, "missing_credentials"
    try:
        teams_rows = _fetch_all_rows(client, "teams")
        ats_rows = _fetch_all_rows(client, "ats_results")
        return teams_rows, ats_rows, None
    except Exception as e:
        return None, None, str(e)

@st.cache_data(ttl=1800, show_spinner=False)
def fetch_completed_games(limit=25):
    client = get_supabase_client()
    if not client:
        return None, "missing_credentials"
    try:
        resp = (
            client.table("games")
            .select("game_id,season,week,game_date,home_team,away_team,home_score,away_score")
            .not_.is_("home_score", "null")
            .order("game_date", desc=True)
            .limit(limit)
            .execute()
        )
        return resp.data, None
    except Exception as e:
        return None, str(e)

def load_trend_data():
    """Returns (data, source). data has the shape {'seasons','divisions','records'}.
    Prefers live Supabase ATS history; falls back to the bundled sample JSON,
    clearly labeled as sample (never presented as if it were live)."""
    teams_rows, ats_rows, err = fetch_supabase_ats_data()
    if not err and teams_rows and ats_rows:
        data = content_engine.build_ats_trends_from_rows(teams_rows, ats_rows)
        if data.get("records"):
            return data, "live"
    return content_engine.load_ats_trends(), "sample"

# Users / Steel system
USERS_DB_PATH = "users_db.json"
STEEL_PRICE_USD = 0.10
# Purchasable Steel packs. Stakes are free-entry (see stake_input), so this
# list only ever sizes purchases.
STEEL_PACKS = [10, 25, 50, 100, 250, 500, 1000]

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

def stake_input(key_prefix, balance):
    """Free-entry Steel stake, to the cent.

    Capped at the current balance so an unaffordable stake can't be typed in
    the first place, rather than being rejected only after Confirm.
    """
    max_stake = max(0.0, round(float(balance or 0), 2))
    if max_stake < 0.01:
        st.caption("No Steel available — buy Steel on the Profile tab to bet.")
        return 0.0
    return st.number_input(
        "Stake (Steel)",
        min_value=0.01,
        max_value=max_stake,
        value=min(25.0, max_stake),
        step=1.0,
        format="%.2f",
        key=f"{key_prefix}_stake",
        help=f"Type any amount to the cent, up to your {fmt_steel(max_stake)} Steel balance.",
    )


def current_steel_balance():
    """Balance from whichever store is active for this user."""
    if auth_store.signed_in():
        profile = auth_store.get_profile()
        return float((profile or {}).get("steel_balance", 0) or 0)
    profile = get_current_profile()
    return float((profile or {}).get("steel_balance", 0) or 0)


def adjust_steel_balance(delta, tx_type, note=""):
    """Apply a Steel change and log it, against the active store.

    Signed in -> the Supabase profile; guest -> users_db.json. Returns the new
    balance so callers don't have to re-read it.
    """
    if auth_store.signed_in():
        new_balance = round(current_steel_balance() + delta, 2)
        auth_store.set_steel_balance(new_balance)
        auth_store.add_transaction(tx_type, delta, note)
        return new_balance
    users = load_users()
    uname = st.session_state.username
    if uname not in users:
        return current_steel_balance()
    user = ensure_user_fields(users[uname])
    user["steel_balance"] = round(user.get("steel_balance", 0) + delta, 2)
    user["transactions"].append({
        "type": tx_type,
        "steel_amount": delta,
        "timestamp": datetime.utcnow().isoformat(),
        "note": note,
    })
    users[uname] = user
    save_users(users)
    return user["steel_balance"]


def purchase_steel(amount):
    if not st.session_state.get("authenticated"):
        return False, "Log in first"
    balance = adjust_steel_balance(amount, "purchase", f"Bought {amount} Steel")
    return True, f"Added {amount} Steel! Balance: {balance:.0f}"


def place_steel_bet(game_id, away, home, market, selection, line, odds, stake, label="", market_type="fixed", player=None):
    if not st.session_state.get("authenticated"):
        return False, "Log in to place bets"
    uname = st.session_state.username
    bal = current_steel_balance()
    if stake > bal:
        return False, f"Insufficient Steel (have {bal:.0f})"
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
    # The ledger in bets.db is the source of truth for bets; users_db.json
    # keeps the account (balance + transactions). The JSON list is still
    # appended so an older copy of the app, or a restore from backup, still
    # sees the bet — the store's migration is keyed on bet id, so importing
    # the same bet twice is a no-op.
    user_data.record_bet(uname, bet)
    new_balance = adjust_steel_balance(
        -stake, "bet", label or f"{selection} {market}"
    )
    return True, (f"Bet placed: {stake} Steel on {selection.upper()} "
                  f"({market}). Balance: {new_balance:.0f}")

def settle_user_bets():
    """Settle open bets whose games have finished, then credit the balance.

    Runs on every rerun, but the scores request is cached (10 min) and skipped
    entirely when the user has no settleable open bets, so it costs nothing on
    a normal page view. Player props are left open on purpose — grading them
    needs a box score this endpoint doesn't carry (see bet_settlement).
    """
    if not st.session_state.get("authenticated"):
        return
    uname = st.session_state.get("username")
    pending = user_data.open_bets_with_games(uname)
    if not pending:
        return
    api_key = get_odds_api_key()
    if not api_key:
        return
    try:
        finals = scores_by_game_id(fetch_scores(api_key))
    except Exception:
        return  # settlement is best-effort; never block the page on it
    if not finals:
        return

    settled_ids = []
    for bet in pending:
        game = finals.get(bet.get("game_id"))
        if not game or not game.get("completed"):
            continue
        status, note = grade_bet(bet, game)
        if status is None:
            continue
        profit = american_to_profit(bet.get("stake", 0), bet.get("odds") or -110)
        result = steel_result_for(status, bet.get("stake", 0), profit)
        credit = balance_credit_for(status, bet.get("stake", 0), profit)
        user_data.mark_settled(
            bet["id"], status, result, datetime.utcnow().isoformat(),
            game.get("away_score"), game.get("home_score"), note,
        )
        settled_ids.append(bet["id"])
        if credit:
            # Credited one bet at a time so a failure part-way through can't
            # leave the balance crediting bets that were never marked settled.
            adjust_steel_balance(
                credit, f"settle_{status}",
                f"{bet.get('label') or bet.get('market')} — {note}",
            )

    if not settled_ids:
        return

    # Keep the legacy JSON open-bets list from drifting for guest accounts.
    if not auth_store.signed_in():
        users = load_users()
        if uname in users:
            user = ensure_user_fields(users[uname])
            done = set(settled_ids)
            user["open_bets"] = [
                b for b in user.get("open_bets", []) if b.get("id") not in done
            ]
            users[uname] = user
            save_users(users)

def render_prop_bet_ui(prop, key_prefix, use_expander=True):
    """Place Steel on a single player prop Over/Under."""
    def _body():
        if not st.session_state.get("authenticated"):
            st.warning("Log in via Profile to place Steel bets on props.")
            return
        bal = current_steel_balance()
        st.caption(f"Available: {fmt_steel(bal)} Steel · Line: {prop.get('line')}")
        side = st.radio(
            "Side",
            ["over", "under"],
            key=f"{key_prefix}_side",
            format_func=lambda x: f"OVER {prop.get('line')} ({prop.get('over', -110)})" if x == "over" else f"UNDER {prop.get('line')} ({prop.get('under', -110)})",
            horizontal=True,
        )
        odds_val = prop.get("over", -110) if side == "over" else prop.get("under", -110)
        stake = stake_input(key_prefix, bal)
        try:
            profit = american_to_profit(stake, odds_val)
            st.write(f"To win: **{fmt_steel(profit)}** Steel  ·  "
                     f"Returns **{fmt_steel(stake + profit)}**")
        except Exception:
            profit = 0
        if st.button("Confirm Prop Bet", key=f"{key_prefix}_btn", type="primary"):
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

def render_game_bet_ui(game, key_prefix, use_expander=True):
    """Place Steel on a game's MACHINE Consensus line — the de-vigged
    average across all listed books (build_game_consensus). Users can't
    pick a specific sportsbook's price here; individual books are shown
    elsewhere for reference only."""
    def _body():
        if not st.session_state.get("authenticated"):
            st.warning("Log in via Profile to place Steel bets on game lines.")
            return
        consensus = game.get("consensus") or {}
        if not consensus:
            st.caption("No MACHINE Consensus available for this game yet.")
            return
        bal = current_steel_balance()
        st.caption(f"Available: {fmt_steel(bal)} Steel · Betting the MACHINE Consensus line")

        market_labels = []
        if "h2h" in consensus:
            market_labels.append("Moneyline")
        if "spreads" in consensus:
            market_labels.append("Spread")
        if "totals" in consensus:
            market_labels.append("Total")

        bet_type = st.radio("Market", market_labels, key=f"{key_prefix}_type", horizontal=True)

        if bet_type == "Moneyline":
            c = consensus["h2h"]
            side = st.radio(
                "Side", ["away", "home"],
                format_func=lambda s: f"{game['away']} ({fmt_odds(c['away'])})" if s == "away" else f"{game['home']} ({fmt_odds(c['home'])})",
                horizontal=True, key=f"{key_prefix}_side",
            )
            odds_val = c[side]
            line_val = None
            selection = game["away"] if side == "away" else game["home"]
        elif bet_type == "Spread":
            c = consensus["spreads"]
            side = st.radio(
                "Side", ["away", "home"],
                format_func=lambda s: f"{game['away']} ({c['away_point']:+g}, {fmt_odds(c['away'])})" if s == "away" else f"{game['home']} ({c['home_point']:+g}, {fmt_odds(c['home'])})",
                horizontal=True, key=f"{key_prefix}_side",
            )
            odds_val = c[side]
            line_val = c["away_point"] if side == "away" else c["home_point"]
            selection = game["away"] if side == "away" else game["home"]
        else:
            c = consensus["totals"]
            side = st.radio(
                "Side", ["over", "under"],
                format_func=lambda s: f"OVER {c['point']} ({fmt_odds(c['over'])})" if s == "over" else f"UNDER {c['point']} ({fmt_odds(c['under'])})",
                horizontal=True, key=f"{key_prefix}_side",
            )
            odds_val = c[side]
            line_val = c["point"]
            selection = side

        stake = stake_input(key_prefix, bal)
        try:
            profit = american_to_profit(stake, odds_val)
            st.write(f"To win: **{fmt_steel(profit)}** Steel  ·  "
                     f"Returns **{fmt_steel(stake + profit)}**")
        except Exception:
            profit = 0

        if st.button("Confirm Bet", key=f"{key_prefix}_btn", type="primary"):
            line_txt = f" {line_val:+g}" if line_val is not None else ""
            label = f"{game['away']} @ {game['home']} — {bet_type} {selection}{line_txt} (MACHINE Consensus)"
            ok, msg = place_steel_bet(
                game_id=game["id"], away=game["away"], home=game["home"],
                market=bet_type, selection=selection, line=line_val,
                odds=odds_val, stake=stake, label=label,
                market_type=bet_type.lower(),
            )
            if ok:
                st.success(msg)
                st.rerun()
            else:
                st.error(msg)

    if use_expander:
        with st.expander(f"⚙️ Bet Steel — {game['away']} @ {game['home']}"):
            _body()
    else:
        _body()

GUEST_USERNAME = "guest"

if "authenticated" not in st.session_state:
    # Login is disabled for now (too much friction re-logging in every
    # session) — auto-sign everyone into a shared guest profile instead of
    # showing a login wall. The Profile tab still supports logging into a
    # separate real account if someone wants to.
    users = load_users()
    if GUEST_USERNAME not in users:
        guest_user = ensure_user_fields({
            "password_hash": bcrypt.hashpw(os.urandom(16), bcrypt.gensalt()).decode(),
            "display_name": "Guest",
            "created": datetime.utcnow().isoformat(),
        })
        users[GUEST_USERNAME] = guest_user
        save_users(users)
    st.session_state.authenticated = True
    st.session_state.username = GUEST_USERNAME
if "username" not in st.session_state:
    st.session_state.username = GUEST_USERNAME

# Re-establish a signed-in session from the browser cookie before anything
# reads bets or balance, so a refresh doesn't silently drop back to guest.
auth_ui.restore_session()

if "bets_migrated" not in st.session_state:
    # Idempotent: only inserts bet ids the ledger hasn't seen, so this is a
    # no-op after the first run.
    bet_store.migrate_from_users_json(USERS_DB_PATH)
    st.session_state.bets_migrated = True

if st.session_state.authenticated:
    settle_user_bets()

# Header identity comes from the active store: the Supabase profile when
# signed in, the local guest profile otherwise.
if auth_store.signed_in():
    sb_profile = auth_store.get_profile() or {}
    display_name = sb_profile.get("display_name") or (
        (auth_store.current_session() or {}).get("email") or "Player"
    )
    steel_balance = sb_profile.get("steel_balance", 0)
else:
    profile = get_current_profile()
    display_name = None
    steel_balance = 0
    if profile:
        display_name = profile.get("display_name", st.session_state.username)
        steel_balance = profile.get("steel_balance", 0)

# Header — title/tagline and the Steel chip share one row on desktop and
# stack (Streamlit's own responsive column behavior) on narrow screens.
hero_left, hero_right = st.columns([3, 1])
with hero_left:
    st.title("🎯 FADE MACHINE")
    st.caption("NFL Trends • Odds • Props • Fantasy Rankings • Steel Bets")
with hero_right:
    if st.session_state.authenticated:
        st.markdown(
            f"""<div style='display:flex;justify-content:flex-end;padding-top:10px'>
            <div class='steel-balance-bar'>
            <div class='steel-label'>Steel Balance</div>
            <div class='steel-amount'>{steel_balance}</div>
            </div></div>""",
            unsafe_allow_html=True,
        )
st.markdown('<div class="fade-divider"></div>', unsafe_allow_html=True)

# Live odds / props helpers (simplified for recovery)
def fetch_live_props():
    return []

live_props = fetch_live_props()
props_source = "live" if live_props else "sample"
ALL_PROPS = live_props if live_props else SAMPLE_PLAYER_PROPS

# Private owner page: ?studio=1 swaps the tabs for the Post Studio. The odds
# board call is the same cached one the Betting tab uses, so no extra credits.
if st.query_params.get("studio") == "1":
    studio_games, studio_err, _ = load_nfl_betting_board()
    post_studio.render_post_studio(studio_games, studio_err)
    st.stop()

# Named rather than tab1..tabN so adding or removing a tab can't silently
# shift every block below it onto the wrong panel.
(tab_betting, tab_results, tab_trends, tab_props, tab_fantasy, tab_cbb,
 tab_headlines, tab_mybets, tab_profile) = st.tabs([
    "🎲 Betting", "📊 Results", "📈 Trends", "🏈 Props",
    "🏆 Fantasy", "🏀 College Hoops", "📰 Headlines", "🧾 My Bets", "👤 Profile"
], on_change="rerun")

if tab_betting.open:
    with tab_betting:
        section_title("🎲", "Betting — NFL Game Lines")
        # Paint skeleton cards first — this markdown reaches the browser
        # before the blocking odds request runs, so the board has shape
        # immediately instead of sitting blank behind a spinner.
        odds_skeleton = st.empty()
        odds_skeleton.markdown(odds_skeleton_html(), unsafe_allow_html=True)
        games, odds_err, fetched_at = load_nfl_betting_board()
        odds_skeleton.empty()
        if odds_err == "missing_key":
            st.info("Live odds are offline: no `ODDS_API_KEY` found in `st.secrets`. Add your The Odds API key to enable moneyline, spread, and total boards.")
        elif odds_err:
            st.error(f"Couldn't load live odds right now. {odds_err}")
        elif not games:
            st.warning("No upcoming NFL games found from The Odds API right now.")
        else:
            for g in games:
                g["week"] = nfl_week_label(g["commence_time"])
            weeks_present = sorted({g["week"] for g in games}, key=nfl_week_sort_key)
            # Default to the soonest week still on the board — The Odds API
            # only returns upcoming games, so that's the current week.
            default_week = weeks_present[0] if weeks_present else None

            head_l, head_r = st.columns([3, 1])
            with head_l:
                # Segmented control instead of a dropdown: every week is one
                # tap, and the active week is visible without opening a menu.
                # "All Weeks" is deliberately absent — the full season is 270+
                # games and rendering them at once is what used to hang the app.
                selected_week = st.segmented_control(
                    "NFL Week", weeks_present,
                    default=default_week, key="betting_week_filter",
                ) or default_week
            with head_r:
                st.markdown("<div style='height:26px'></div>", unsafe_allow_html=True)
                if st.button("↻ Refresh odds", key="betting_refresh",
                             use_container_width=True,
                             help="Pull fresh lines from The Odds API now."):
                    fetch_nfl_odds_raw.clear()
                    st.rerun()

            games = [g for g in games if g["week"] == selected_week]
            st.markdown(odds_freshness_html(fetched_at, len(games)), unsafe_allow_html=True)
            # Historical trend data is loaded once for the whole board and
            # cached, so each card's trends panel is a pandas filter rather
            # than its own query.
            mtr.inject_css()
            trend_games = mtr.games_frame()
            trend_names = mtr.team_name_map()
            if not games:
                st.info("No games found for that week.")
            # Per-card entrance delays. Capped at 320ms so the last card of a
            # 16-game week isn't still waiting after the rest have settled.
            st.markdown(
                "<style>"
                + "".join(
                    f".st-key-fm_game_{i} {{ animation-delay: {min(i * 40, 320)}ms; }}"
                    for i in range(len(games))
                )
                + "</style>",
                unsafe_allow_html=True,
            )
            for i, g in enumerate(games):
                books = g["books"]
                consensus = g.get("consensus") or {}
                with st.container(border=True, key=f"fm_game_{i}"):
                    # Card face: teams, kickoff and the consensus spread /
                    # total / moneyline are readable without expanding
                    # anything, so a full week scans as one board.
                    st.markdown(game_card_header_html(g, consensus),
                                unsafe_allow_html=True)
                    ml = consensus.get("h2h")
                    if ml:
                        st.markdown(
                            win_prob_bar_html(g["away"], g["home"],
                                              ml["away"], ml["home"]),
                            unsafe_allow_html=True,
                        )
                    if not books:
                        st.caption("No sportsbook lines available for this game yet.")
                    elif not consensus:
                        st.caption("No MACHINE Consensus available for this game yet.")
                    else:
                        st.caption(
                            f"🎯 MACHINE Consensus · de-vigged average across "
                            f"{len(books)} book{'s' if len(books) != 1 else ''} · "
                            f"the only price Steel bets settle at"
                        )

                    act_l, act_t, act_r = st.columns([1, 1, 1])
                    with act_l:
                        with st.popover("🎯 Bet Steel", use_container_width=True):
                            render_game_bet_ui(g, f"gamebet_{i}", use_expander=False)
                    with act_t:
                        with st.popover("📈 Trends", use_container_width=True):
                            trends = mtr.matchup_trends(
                                trend_games, g["away"], g["home"], trend_names
                            )
                            if trends is None:
                                st.caption(
                                    "No historical data for this matchup — "
                                    "check the Supabase connection."
                                )
                            else:
                                st.markdown(
                                    mtr.trends_html(trends, g["away"], g["home"]),
                                    unsafe_allow_html=True,
                                )
                                st.caption(
                                    "From completed games 1999–2025. ATS uses the "
                                    "closing line on record; percentages exclude pushes."
                                )
                    with act_r:
                        # Popover, not a toggle: a toggle reruns the whole
                        # script and redraws every game on the board just to
                        # reveal one table. The popover opens client-side.
                        with st.popover(f"📊 Compare {len(books)} books",
                                        use_container_width=True,
                                        disabled=not books):
                            st.caption(
                                "Reference only — you can't bet a specific book's "
                                "price. Green = best price for that side."
                            )
                            rows = []
                            # Track raw numeric prices per column so the best price
                            # for the bettor can be highlighted — a standard
                            # odds-comparison pattern on real sportsbook boards.
                            raw_prices = {"ML Away": {}, "ML Home": {}, "Spread Away": {}, "Spread Home": {}, "Total O": {}, "Total U": {}}
                            for idx, b in enumerate(books):
                                row = {"Sportsbook": b["title"]}
                                if "h2h" in b:
                                    row["ML Away"] = fmt_odds(b["h2h"]["away"])
                                    row["ML Home"] = fmt_odds(b["h2h"]["home"])
                                    raw_prices["ML Away"][idx] = b["h2h"]["away"]
                                    raw_prices["ML Home"][idx] = b["h2h"]["home"]
                                if "spreads" in b:
                                    row["Spread Away"] = f"{b['spreads']['away']['point']:+g} ({fmt_odds(b['spreads']['away']['price'])})"
                                    row["Spread Home"] = f"{b['spreads']['home']['point']:+g} ({fmt_odds(b['spreads']['home']['price'])})"
                                    raw_prices["Spread Away"][idx] = b["spreads"]["away"]["price"]
                                    raw_prices["Spread Home"][idx] = b["spreads"]["home"]["price"]
                                if "totals" in b:
                                    row["Total O"] = f"O {b['totals']['over']['point']} ({fmt_odds(b['totals']['over']['price'])})"
                                    row["Total U"] = f"U {b['totals']['under']['point']} ({fmt_odds(b['totals']['under']['price'])})"
                                    raw_prices["Total O"][idx] = b["totals"]["over"]["price"]
                                    raw_prices["Total U"][idx] = b["totals"]["under"]["price"]
                                rows.append(row)

                            best_cells = set()
                            for col, valmap in raw_prices.items():
                                if not valmap:
                                    continue
                                best = max(valmap.values())
                                best_cells.update((idx, col) for idx, v in valmap.items() if v == best)
                            odds_cols = ["Sportsbook"] + [
                                c for c in ("ML Away", "ML Home", "Spread Away",
                                            "Spread Home", "Total O", "Total U")
                                if any(c in r for r in rows)
                            ]
                            st.markdown(
                                odds_table_html(odds_cols, rows, best_cells),
                                unsafe_allow_html=True,
                            )

if tab_results.open:
    with tab_results:
        section_title("📊", "Results")
        for g in COMPLETED_GAMES:
            with st.container(border=True):
                st.markdown(f"<div class='fm-prop-card-meta' style='margin-bottom:2px'>{g['label']}</div>", unsafe_allow_html=True)
                st.markdown(
                    f"<div class='fm-prop-card-line' style='font-size:1.3rem'>{g['away']} {g['away_score']} — {g['home']} {g['home_score']}</div>",
                    unsafe_allow_html=True,
                )
                if g.get("notes"):
                    st.caption(g["notes"])

        st.markdown("### Recent NFL Results")
        completed, completed_err = fetch_completed_games(limit=25)
        if completed_err == "missing_credentials":
            st.info("Add `SUPABASE_URL` and `SUPABASE_ANON_KEY` to `st.secrets` to show real historical results here.")
        elif completed_err:
            st.error(f"Couldn't load results from Supabase. {completed_err}")
        elif not completed:
            st.caption("No completed games in the database yet.")
        else:
            for g in completed:
                with st.container(border=True):
                    st.markdown(
                        f"<div class='fm-prop-card-meta' style='margin-bottom:2px'>Season {g['season']} · Week {g['week']} · {g.get('game_date', '')}</div>",
                        unsafe_allow_html=True,
                    )
                    st.markdown(
                        f"<div class='fm-prop-card-line'>{g['away_team']} {g['away_score']} — {g['home_team']} {g['home_score']}</div>",
                        unsafe_allow_html=True,
                    )

if tab_trends.open:
    with tab_trends:
        section_title("📈", "Trends")
        st.caption("Season-long and weekly trend snapshots")

        trend_data, trend_source = load_trend_data()
        st.caption(f"Source: {'Supabase (real historical ATS results)' if trend_source == 'live' else 'Sample / illustrative ATS data'}")
        ats_df = content_engine.ats_dataframe(trend_data)
        if ats_df.empty:
            st.warning("No ATS trend data available.")
        else:
            seasons = trend_data.get("seasons", [])
            divisions = trend_data.get("divisions", [])
            tf1, tf2 = st.columns(2)
            with tf1:
                season_filter = st.multiselect("Season", seasons, default=seasons[-3:] if len(seasons) > 3 else seasons, key="trend_season")
            with tf2:
                division_filter = st.multiselect("Division", divisions, default=divisions, key="trend_division")
            agg = content_engine.aggregate_ats(ats_df, seasons=season_filter, divisions=division_filter)
            if agg.empty:
                st.info("No teams match the selected filters.")
            else:
                st.dataframe(
                    agg[["team_name", "division", "record", "cover_pct", "home_ats_wins", "home_ats_losses", "away_ats_wins", "away_ats_losses"]]
                    .rename(columns={
                        "team_name": "Team", "division": "Division", "record": "ATS Record", "cover_pct": "Cover %",
                        "home_ats_wins": "Home W", "home_ats_losses": "Home L", "away_ats_wins": "Away W", "away_ats_losses": "Away L",
                    }),
                    hide_index=True, width="stretch",
                )
                best, worst = content_engine.best_worst_ats(agg, n=5)
                bc1, bc2 = st.columns(2)
                with bc1:
                    st.markdown("**Best ATS**")
                    for b in best:
                        st.write(f"{b['team_name']} — {b['record']} ({b['cover_pct']*100:.0f}%)")
                with bc2:
                    st.markdown("**Toughest Fade**")
                    for w in worst:
                        st.write(f"{w['team_name']} — {w['record']} ({w['cover_pct']*100:.0f}%)")

        tc1, tc2 = st.columns(2)
        with tc1:
            st.markdown(
                "<div class='fm-stat-card'>"
                "<div class='fm-stat-label'>HOF Game Result</div>"
                "<div class='fm-stat-body'>"
                "<span class='fm-nums' style='font-size:1.15rem;font-weight:700'>Panthers 33, Cardinals 30</span><br>"
                "Haynes King walk-off TD"
                "</div></div>",
                unsafe_allow_html=True,
            )
        with tc2:
            st.markdown(
                "<div class='fm-stat-card'>"
                "<div class='fm-stat-label'>Fantasy Rankings</div>"
                "<div class='fm-stat-body'>Update automatically from the season-long "
                "futures dataset — see the Fantasy tab for the live board.</div>"
                "</div>",
                unsafe_allow_html=True,
            )

if tab_props.open:
    with tab_props:
        section_title("🏈", "Player Prop Bets")
        st.caption(f"Source: {'Live Odds API' if props_source == 'live' else 'Sample / illustrative lines (preseason)'} · Place Steel on Over/Under")

        markets = sorted(set(p["market"] for p in ALL_PROPS))
        positions = sorted(set(p.get("pos", "") for p in ALL_PROPS if p.get("pos")))
        f1, f2, f3, f4 = st.columns([2, 2, 2, 1])
        with f1:
            mkt_filter = st.multiselect("Market", markets, default=markets, key="prop_mkt")
        with f2:
            pos_filter = st.multiselect("Position", positions if positions else ["QB", "RB", "WR", "TE"],
                                        default=positions if positions else ["QB", "RB", "WR", "TE"], key="prop_pos")
        with f3:
            search = st.text_input("Search player", "", key="prop_search")
        with f4:
            # Every card carries a bordered container, five markdowns and a
            # popover holding a radio, selectbox and button. Rendering all
            # ~340 props at once cost ~3.9s per rerun and left a DOM the
            # browser couldn't re-apply, so the grid is paged.
            page_size = st.selectbox("Per page", PROPS_PAGE_SIZES, index=1, key="prop_page_size")

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
            total_pages = max(1, (len(filtered) + page_size - 1) // page_size)
            page = 1
            if total_pages > 1:
                page = st.selectbox(
                    "Page", list(range(1, total_pages + 1)), index=0, key="prop_page",
                    format_func=lambda p: f"Page {p} of {total_pages}",
                )
            start = (page - 1) * page_size
            page_props = filtered[start:start + page_size]
            st.markdown(
                f"### Prop Cards <span class='fm-nums' style='font-size:0.9rem;color:var(--muted)'>"
                f"({start + 1}–{start + len(page_props)} of {len(filtered)})</span>",
                unsafe_allow_html=True,
            )
            # True card grid: st.columns per row + st.container(border=True)
            # per card keeps every card the same fixed shape (badge, name,
            # line, O/U) — the variable-height bet form lives in a popover
            # instead of an inline expander, so it never stretches the card.
            cols_per_row = 3
            grid = st.container(key="fm_props_grid")
            with grid:
                for row_start in range(0, len(page_props), cols_per_row):
                    row_props = page_props[row_start:row_start + cols_per_row]
                    cols = st.columns(cols_per_row)
                    for offset, (col, p) in enumerate(zip(cols, row_props)):
                        # Keyed off the position in the full filtered list so
                        # each prop's bet-form widgets stay stable across pages.
                        idx = start + row_start + offset
                        pos = (p.get("pos") or "").upper()
                        pos_class = f"fm-badge-pos-{pos.lower()}" if pos.lower() in ("qb", "rb", "wr", "te") else "fm-badge-pos-wr"
                        with col:
                            with st.container(border=True):
                                st.markdown(
                                    f"<span class='fm-badge fm-badge-pos {pos_class}'>{pos or '—'}</span> "
                                    f"<span class='fm-badge fm-badge-week'>{p['market']}</span>",
                                    unsafe_allow_html=True,
                                )
                                st.markdown(f"<div class='fm-prop-card-name'>{p['player']}</div>", unsafe_allow_html=True)
                                st.markdown(f"<div class='fm-prop-card-meta'>{p.get('team','')} · {p.get('game','')}</div>", unsafe_allow_html=True)
                                st.markdown(f"<div class='fm-prop-card-line'>{p['line']}</div>", unsafe_allow_html=True)
                                st.markdown(
                                    f"<span class='fm-badge fm-badge-over'>O {p.get('over','—')}</span> "
                                    f"<span class='fm-badge fm-badge-under'>U {p.get('under','—')}</span>",
                                    unsafe_allow_html=True,
                                )
                                st.markdown("<div style='margin-top:10px'></div>", unsafe_allow_html=True)
                                with st.popover("🎯 Bet Steel", width="stretch"):
                                    render_prop_bet_ui(p, f"propbet_{idx}", use_expander=False)

if tab_fantasy.open:
    with tab_fantasy:
        # Advanced season-long models + rank-by-prop (see fantasy_models.py)
        render_fantasy_tab(ALL_PROPS)

if tab_cbb.open:
    with tab_cbb:
        section_title("🏀", "College Hoops — MACHINE Ratings & March Madness")
        cbb_tab.render_cbb_tab()

if tab_headlines.open:
    with tab_headlines:
        section_title("📰", "Preseason Headlines")
        headline_trend_data, _ = load_trend_data()
        headline_agg = content_engine.aggregate_ats(content_engine.ats_dataframe(headline_trend_data))
        headlines = content_engine.generate_headlines(headline_agg, [], [])
        headlines += [
            "<b>FINAL:</b> Panthers 33, Cardinals 30 (Haynes King walk-off TD) — HOF Game Aug 6",
            "Fantasy rankings powered by season-long futures lines",
            "Steel betting live on player props",
        ]
        rows_html = "".join(
            f"<div class='fm-headline-row'><div class='fm-headline-bar'></div>"
            f"<div class='fm-headline-text'>{h}</div></div>"
            for h in headlines
        )
        st.markdown(f"<div>{rows_html}</div>", unsafe_allow_html=True)

if tab_mybets.open:
    with tab_mybets:
        section_title("🧾", "My Bets")
        if not st.session_state.authenticated:
            st.warning("Log in on the Profile tab to see open and settled bets.")
        else:
            render_my_bets_tab(
                user_data.bets_for(st.session_state.username, "open"),
                user_data.bets_for(st.session_state.username, "settled"),
            )

if tab_profile.open:
    with tab_profile:
        section_title("👤", "Profile")
        if not st.session_state.authenticated:
            login_tab, register_tab = st.tabs(["Login", "Create Account"])
            with login_tab:
                u = st.text_input("Username", key="login_u")
                p = st.text_input("Password", type="password", key="login_p")
                if st.button("Log in", type="primary"):
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
                if st.button("Create account", type="primary"):
                    ok, msg = register_user(nu, npw, nd)
                    if ok:
                        st.success(msg)
                    else:
                        st.error(msg)
        else:
            current = get_current_profile()
            st.success(f"Logged in as **{display_name}**")
            st.metric("Steel Balance", steel_balance)
            sub_account, sub_bank, sub_buy, sub_history = st.tabs(
                ["Account", "Bet Bank", "Buy Steel", "Transaction History"]
            )
            with sub_bank:
                render_bet_history_section(
                    st.session_state.username,
                    rows=user_data.history_rows(st.session_state.username),
                    storage_note=(
                        "Stored durably in your account — survives redeploys."
                        if user_data.is_durable() else
                        "⚠️ Guest storage: kept on this machine only and wiped "
                        "when the app redeploys. Sign in on the Account tab to "
                        "keep this history permanently."
                    ),
                )
            with sub_account:
                auth_ui.render_account_panel(
                    local_bets_getter=lambda: bet_store.bets_for(GUEST_USERNAME)
                )
            with sub_buy:
                pack_amount = st.selectbox(
                    "Steel pack", STEEL_PACKS,
                    index=STEEL_PACKS.index(100),
                    format_func=lambda x: f"{x:,} Steel — ${x * STEEL_PRICE_USD:,.2f}",
                )
                st.caption(
                    f"All packs price at ${STEEL_PRICE_USD:.2f} per Steel · "
                    f"{pack_amount:,} Steel = ${pack_amount * STEEL_PRICE_USD:,.2f}"
                )
                if st.button(f"Purchase {pack_amount:,} Steel", type="primary"):
                    ok, msg = purchase_steel(pack_amount)
                    st.success(msg) if ok else st.error(msg)
                    if ok:
                        st.rerun()
                st.caption(
                    "⚠️ No payment is taken — this credits Steel straight to your "
                    "balance. Wiring up real checkout would need a payment processor."
                )
            with sub_history:
                # Signed-in transactions live in Supabase; guests keep theirs
                # in the local JSON profile. Timestamps are named differently
                # by the two stores, hence the fallback.
                if auth_store.signed_in():
                    txs = auth_store.transactions()
                else:
                    txs = (current or {}).get("transactions", [])
                if not txs:
                    st.caption("No transactions.")
                else:
                    st.dataframe(pd.DataFrame([{
                        "Date": str(t.get("timestamp") or t.get("created_at") or "")[:16],
                        "Type": str(t.get("type", "")).replace("_", " ").title(),
                        "Steel": t.get("steel_amount"),
                        "Note": t.get("note", "")
                    } for t in txs]), use_container_width=True, hide_index=True)

st.markdown("---")
st.caption("FADE MACHINE • Season-long futures • Rank by prop • Prop Steel bets • Advanced fantasy models")
