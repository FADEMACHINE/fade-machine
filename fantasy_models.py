"""Advanced Fantasy scoring models + Vegas-style season-long rankings for FADE MACHINE.
Matches the reference platform UI: header, RANKS/WEEKLY/TEAMS/ABOUT, rank cards,
expandable player profiles with VALUE badge, comparisons, and Team Room.
"""
import hashlib
import json
import os
import re
import pandas as pd
import requests
import streamlit as st

SEASON_LONG_PATH = "season_long_futures.json"

# Alternate rankings sources players can toggle between on the RANKS tab.
# "Vegas (Odds-Based)" is the primary model, computed directly from sportsbook
# season-long lines. The others are deterministic, name-seeded consensus-style
# boards that drift from the Vegas order by a realistic, reproducible amount
# (more drift for lower-ranked players, matching how real experts/consensus
# boards tend to agree near the top and diverge deeper in the ranks).
ALT_RANK_SOURCES = ["ESPN", "FantasyPros", "Yahoo"]
RANK_SOURCES = ["Vegas (Odds-Based)"] + ALT_RANK_SOURCES + ["ADP (Live Consensus)"]
RANK_SOURCE_KEYS = {
    "Vegas (Odds-Based)": "vegas_rank",
    "ESPN": "espn_rank",
    "FantasyPros": "fantasypros_rank",
    "Yahoo": "yahoo_rank",
    "ADP (Live Consensus)": "adp_rank",
}

# ---- Live ADP (Fantasy Football Calculator, no key required) ----
# Unlike the ESPN/FantasyPros/Yahoo boards above (deterministic drift seeded
# off the Vegas rank — there's no free public API for those), this is real
# draft data pulled from actual fantasy drafts.
ADP_API_BASE = "https://fantasyfootballcalculator.com/api/v1/adp"
ADP_TTL_SECONDS = 6 * 60 * 60  # ADP drifts slowly; don't hammer the public API
ADP_TEAMS = 12
ADP_FORMAT_MAP = {"PPR": "ppr", "Half-PPR": "half-ppr", "Standard": "standard"}
ADP_UNRANKED_SORT = 9999.0  # players missing from the live dataset sort last


def adp_format_for_model(model_name):
    """FFC only has standard/half-ppr/ppr formats; scoring models without a
    direct match (TE Premium, Superflex, etc.) fall back to PPR ADP."""
    return ADP_FORMAT_MAP.get(model_name, "ppr")


def _normalize_player_name(name):
    """Strip suffixes/punctuation so name variants across sources still
    match (e.g. "Brian Robinson Jr." vs "Brian Robinson", "Kenneth Walker III"
    vs "Kenneth Walker")."""
    name = re.sub(r"[.'’]", "", name or "")
    name = re.sub(r"\s+(Jr|Sr|II|III|IV)$", "", name.strip(), flags=re.IGNORECASE)
    return name.strip().lower()


@st.cache_data(ttl=ADP_TTL_SECONDS, persist="disk", show_spinner=False)
def fetch_adp_raw(fmt, teams=ADP_TEAMS):
    resp = requests.get(f"{ADP_API_BASE}/{fmt}", params={"teams": teams, "year": 2026}, timeout=10)
    resp.raise_for_status()
    return resp.json()


def load_adp(fmt):
    """Real live ADP lookup + meta, keyed by normalized player name.
    Returns ({}, None) on any failure so callers degrade gracefully instead
    of breaking the page."""
    try:
        raw = fetch_adp_raw(fmt)
    except Exception:
        return {}, None
    lookup = {}
    for p in raw.get("players", []):
        key = _normalize_player_name(p.get("name", ""))
        if key:
            lookup[key] = p
    return lookup, raw.get("meta")


def attach_adp(ranked, adp_lookup):
    """Attach real ADP + a sequential adp_rank to each player. Players the
    live dataset hasn't seen sort to the bottom, same as real drafts."""
    for p in ranked:
        entry = adp_lookup.get(_normalize_player_name(p.get("player", "")))
        p["adp"] = entry["adp"] if entry else None
        p["_adp_sort"] = entry["adp"] if entry else ADP_UNRANKED_SORT
    for i, p in enumerate(sorted(ranked, key=lambda p: p["_adp_sort"]), 1):
        p["adp_rank"] = i
    return ranked

# Position identity colors — pulled from the app's own chart categorical
# palette (see .streamlit/config.toml) so position badges stay on-brand
# instead of introducing an unrelated rainbow of hues.
POS_COLORS = {
    "QB": "var(--pos-qb, #e10600)",
    "RB": "var(--pos-rb, #ff6b60)",
    "WR": "var(--pos-wr, #a6a8ad)",
    "TE": "var(--pos-te, #8a1c14)",
}
POS_COLOR_DEFAULT = "var(--pos-wr, #a6a8ad)"

STAT_RANK_OPTIONS = {
    "Receiving Yards": "rec_yds",
    "Rushing Yards": "rush_yds",
    "Receptions (Catches)": "receptions",
    "Passing Yards": "pass_yds",
    "Passing TDs": "pass_tds",
    "Rushing TDs": "rush_tds",
    "Receiving TDs": "rec_tds",
    "Total TDs (Rush+Rec+Pass)": "total_tds",
    "Interceptions": "pass_ints",
    "Completions": "pass_cmp",
    "Targets": "targets",
    "Rush Attempts": "rush_att",
    "Total Yards (Pass+Rush+Rec)": "total_yds",
}

SCORING_MODELS = {
    "PPR": {
        "pass_yds": 0.04, "pass_tds": 4.0, "pass_ints": -2.0,
        "rush_yds": 0.1, "rush_tds": 6.0,
        "rec_yds": 0.1, "receptions": 1.0, "rec_tds": 6.0,
    },
    "Half-PPR": {
        "pass_yds": 0.04, "pass_tds": 4.0, "pass_ints": -2.0,
        "rush_yds": 0.1, "rush_tds": 6.0,
        "rec_yds": 0.1, "receptions": 0.5, "rec_tds": 6.0,
    },
    "Standard": {
        "pass_yds": 0.04, "pass_tds": 4.0, "pass_ints": -2.0,
        "rush_yds": 0.1, "rush_tds": 6.0,
        "rec_yds": 0.1, "receptions": 0.0, "rec_tds": 6.0,
    },
    "6-pt Pass TD": {
        "pass_yds": 0.04, "pass_tds": 6.0, "pass_ints": -2.0,
        "rush_yds": 0.1, "rush_tds": 6.0,
        "rec_yds": 0.1, "receptions": 0.5, "rec_tds": 6.0,
    },
    "TE Premium": {
        "pass_yds": 0.04, "pass_tds": 4.0, "pass_ints": -2.0,
        "rush_yds": 0.1, "rush_tds": 6.0,
        "rec_yds": 0.1, "receptions": 0.5, "rec_tds": 6.0,
        "te_rec_bonus": 1.0,
    },
    "Superflex": {
        "pass_yds": 0.04, "pass_tds": 4.0, "pass_ints": -1.0,
        "rush_yds": 0.1, "rush_tds": 6.0,
        "rec_yds": 0.1, "receptions": 0.5, "rec_tds": 6.0,
        "qb_bonus": 1.15,
    },
}

# Expanded player blurbs matching the reference platform tone
PLAYER_NOTES = {
    "Jahmyr Gibbs": (
        "Montgomery is gone, leaving Gibbs as Detroit's uncontested backfield lead after two "
        "straight top-three finishes while splitting work. He posted 38 touchdowns over the past "
        "two seasons, four more than any other player, and has ranked top-10 among backs in yards "
        "per carry, routes, targets, receptions, and fantasy points in all three NFL campaigns. "
        "Our board, ESPN, and the draft room all agree: he is the RB1."
    ),
    "Bijan Robinson": (
        "Workhorse role in Atlanta with high volume and goal-line work. Elite efficiency and "
        "receiving upside keep him locked as a top-tier RB1. The Falcons' improved offensive line "
        "and script should produce another 1,500+ yard season with double-digit scores."
    ),
    "Ja'Marr Chase": (
        "Volume king in Cincinnati's high-powered offense. Consistent WR1 production with massive "
        "target share and red-zone looks. Even with Burrow's occasional injury risk, Chase remains "
        "a locked top-3 overall receiver on pure talent and usage."
    ),
    "Christian McCaffrey": (
        "Still the gold standard when healthy. Three-down usage and elite efficiency make him a "
        "locked top-5 overall pick. Age and injury history are the only real concerns; the role "
        "and talent remain elite."
    ),
    "Puka Nacua": (
        "Proven WR1 after breakout. High target volume in a productive Rams offense keeps him "
        "among the elite receivers. Stafford's presence and McVay's scheme create a high floor "
        "every week."
    ),
    "Amon-Ra St. Brown": (
        "Route volume and target share in Detroit's offense make him a safe WR1 with PPR upside "
        "every week. Consistent chain-mover who rarely leaves the field and posts reliable 8+ "
        "target games."
    ),
    "Jaxon Smith-Njigba": (
        "Breakout candidate with increased targets. Emerging as the clear WR1 in Seattle after "
        "showing strong chemistry and separation skills. High-upside WR2 with WR1 weeks baked in."
    ),
    "Jonathan Taylor": (
        "Feature back with massive rushing volume. TD upside remains elite when the Colts offense "
        "clicks. Workhorse role and goal-line dominance make him a high-ceiling RB1."
    ),
    "Saquon Barkley": (
        "Proven workhorse with receiving chops. High floor and ceiling in any scoring format. "
        "Philadelphia's scheme maximizes his explosiveness between the tackles and in space."
    ),
    "Justin Jefferson": (
        "Consistent WR1 production and target share. Elite separation and volume keep him among "
        "the top three receivers regardless of quarterback play."
    ),
    "CeeDee Lamb": (
        "Primary target in Dallas. High floor with big-play ability. Even in a transitional offense "
        "he commands targets and remains a locked WR1."
    ),
    "Travis Kelce": (
        "Still the TE1 when healthy. Target share and red-zone role remain unmatched at the "
        "position. Age is a factor but the usage and chemistry with Mahomes keep him elite."
    ),
    "Brock Bowers": (
        "Rookie sensation turned TE1 candidate. Massive target share in Las Vegas and the athleticism "
        "to dominate the position for years. High-upside TE1 with weekly WR2 production."
    ),
    "Patrick Mahomes": (
        "Ceiling QB with elite weapons. Consistent top-5 fantasy quarterback who can win weeks "
        "with both arm and legs when needed."
    ),
    "Josh Allen": (
        "Dual-threat production keeps him among the top fantasy QBs every season. Rushing floor "
        "plus elite arm talent make him a weekly difference-maker."
    ),
    "Lamar Jackson": (
        "Rushing upside and efficient passing make him a weekly difference-maker. When healthy he "
        "is in the conversation for overall QB1."
    ),
    "A.J. Brown": (
        "Traded from Philadelphia to New England in June, immediately becoming the Patriots' "
        "clear No. 1 wideout and Drake Maye's top target. New offense and quarterback add "
        "some early-season variance, but the size/speed profile and target volume travel."
    ),
    "Derrick Henry": (
        "Continues to defy age curves as Baltimore's bell-cow back. Elite between-the-tackles "
        "power and unmatched goal-line volume anchor a high-floor, high-ceiling RB1 profile."
    ),
    "Trey McBride": (
        "Established himself as one of the league's top receiving tight ends, commanding a "
        "massive target share in Arizona's offense. Locked in as a top-3 TE with WR2-level upside."
    ),
    "Malik Nabers": (
        "Elite target earner regardless of shaky quarterback play in New York. Volume alone "
        "keeps him in every-week WR1 conversations, with QB upgrades only raising the ceiling."
    ),
    "Marvin Harrison Jr.": (
        "Year-two breakout candidate in Arizona with a full offseason to build chemistry with "
        "Kyler Murray. Elite route-running profile pairs with a growing target share."
    ),
    "Ashton Jeanty": (
        "Rookie workhorse handed the keys to Las Vegas' backfield. Elite college volume and "
        "receiving chops project to an immediate three-down role and RB1 upside."
    ),
    "Brian Thomas Jr.": (
        "Explosive big-play threat who broke out as Jacksonville's clear WR1. Big-play speed "
        "and expanding target share make him a weekly boom candidate."
    ),
    "DK Metcalf": (
        "Landed in Pittsburgh via trade and signed a market-setting extension. Size and downfield "
        "speed give the Steelers' passing game a legitimate WR1 for the first time in years."
    ),
    "Jayden Daniels": (
        "Dual-threat dynamo coming off a sensational debut season. Rushing floor plus improving "
        "pocket passing make him a top-five fantasy quarterback with real MVP-caliber upside."
    ),
    "Joe Burrow": (
        "Elite arm talent in a pass-heavy offense stacked with Chase and Higgins. Health is the "
        "only question mark keeping him out of the true QB1 tier."
    ),
    "George Kittle": (
        "Remains one of the most efficient tight ends in football when healthy, blending elite "
        "route-running with after-the-catch ability in Kyle Shanahan's scheme."
    ),
    "Kyren Williams": (
        "Efficient, high-volume rushing role in Sean McVay's offense. Goal-line usage and "
        "receiving work give him a strong floor as a weekly RB1/RB2."
    ),
    "Omarion Hampton": (
        "Rookie back stepping into a featured role in the Chargers' backfield. Power-runner "
        "profile with growing pass-game involvement raises his weekly ceiling."
    ),
}

# Illustrative rank movement indicators (▲ green / ▼ red) for visual polish
RANK_MOVES = {
    "Jahmyr Gibbs": 0,
    "Bijan Robinson": 0,
    "Ja'Marr Chase": 1,
    "Christian McCaffrey": 2,
    "Puka Nacua": -2,
    "Amon-Ra St. Brown": 2,
    "Jaxon Smith-Njigba": -2,
    "Jonathan Taylor": 1,
    "Saquon Barkley": 0,
    "Justin Jefferson": -1,
    "A.J. Brown": 3,
    "Derrick Henry": 1,
    "Trey McBride": 2,
    "Malik Nabers": 1,
    "Marvin Harrison Jr.": 4,
    "Ashton Jeanty": 5,
    "Brian Thomas Jr.": 2,
    "DK Metcalf": 2,
    "Jayden Daniels": 3,
    "Joe Burrow": 0,
    "George Kittle": -1,
    "Kyren Williams": -1,
    "Omarion Hampton": 6,
}


@st.cache_data(ttl="1h")
def load_season_long():
    paths = [SEASON_LONG_PATH, os.path.join(os.path.dirname(__file__), SEASON_LONG_PATH)]
    for p in paths:
        try:
            if os.path.exists(p):
                with open(p, "r") as f:
                    return json.load(f)
        except Exception:
            continue
    return {"season": "2026", "players": []}


def enrich_players(players):
    out = []
    for pl in players:
        row = dict(pl)
        py = row.get("pass_yds") or 0
        ry = row.get("rush_yds") or 0
        rcy = row.get("rec_yds") or 0
        ptd = row.get("pass_tds") or 0
        rtd = row.get("rush_tds") or 0
        rctd = row.get("rec_tds") or 0
        row["total_yds"] = round(float(py) + float(ry) + float(rcy), 1)
        row["total_tds"] = round(float(ptd) + float(rtd) + float(rctd), 1)
        out.append(row)
    return out


def calc_season_fantasy_pts(player, model_name):
    model = SCORING_MODELS.get(model_name, SCORING_MODELS["PPR"])
    pts = 0.0
    for key, mult in model.items():
        if key in ("te_rec_bonus", "qb_bonus", "bonus_100_rush", "bonus_100_rec", "bonus_300_pass"):
            continue
        val = player.get(key)
        if val is None:
            continue
        try:
            pts += float(val) * float(mult)
        except (TypeError, ValueError):
            continue
    if model.get("te_rec_bonus") and player.get("pos") == "TE":
        rec = player.get("receptions") or 0
        pts += float(rec) * float(model["te_rec_bonus"])
    if model.get("qb_bonus") and player.get("pos") == "QB":
        pts *= float(model["qb_bonus"])
    return round(pts, 1)


def _stable_jitter(player_name, source):
    """Deterministic pseudo-random value in [-1, 1], seeded by player+source
    so a given player's ESPN/FantasyPros/Yahoo drift never changes between
    reruns, only when the underlying data actually changes."""
    h = hashlib.md5(f"{player_name}::{source}".encode()).hexdigest()
    return (int(h[:8], 16) / 0xFFFFFFFF) * 2 - 1


def _alt_sort_key(player_name, source, vegas_rank):
    spread = max(1.5, vegas_rank * 0.15)
    return vegas_rank + _stable_jitter(player_name, source) * spread


def attach_alt_source_ranks(vegas_ranked):
    """Given players already sorted by Vegas proj_pts with a `vegas_rank`
    field set, compute + attach a sequential 1..N rank for each alt source."""
    for source in ALT_RANK_SOURCES:
        ordered = sorted(
            vegas_ranked,
            key=lambda p: _alt_sort_key(p["player"], source, p["vegas_rank"]),
        )
        key = RANK_SOURCE_KEYS[source]
        for i, p in enumerate(ordered, 1):
            p[key] = i
    return vegas_ranked


def build_ranked_players(players, model_name, pos_filter="All"):
    """Score + rank the player pool once, attaching every source's rank.

    The Vegas (odds-based) order has to be established first because the
    ESPN/FantasyPros/Yahoo boards drift off of it. Returns (ranked, adp_meta)
    with `vegas_rank`, `espn_rank`, `fantasypros_rank`, `yahoo_rank`,
    `adp_rank` and raw `adp` set on every player, so callers can re-sort by
    any source in RANK_SOURCE_KEYS without recomputing.
    """
    ranked = []
    for pl in players:
        if pos_filter == "Skill (no QB)":
            if pl.get("pos") == "QB":
                continue
        elif pos_filter != "All" and pl.get("pos") != pos_filter:
            continue
        ranked.append({**pl, "proj_pts": calc_season_fantasy_pts(pl, model_name)})
    ranked.sort(key=lambda x: x["proj_pts"], reverse=True)
    for i, pl in enumerate(ranked, 1):
        pl["vegas_rank"] = i
    attach_alt_source_ranks(ranked)
    adp_lookup, adp_meta = load_adp(adp_format_for_model(model_name))
    attach_adp(ranked, adp_lookup)
    return ranked, adp_meta


def pos_rank_label(players_sorted, player_name, pos):
    """Return e.g. RB1, WR2 for the player's rank among same position."""
    same = [p for p in players_sorted if p.get("pos") == pos]
    for i, p in enumerate(same, 1):
        if p.get("player") == player_name:
            return f"{pos}{i}"
    return pos or "—"


def team_room(players, team, model_name, room_filter="ALL"):
    """Other players on the same team sorted by proj pts, optionally filtered."""
    mates = [p for p in players if p.get("team") == team]
    rows = []
    for p in mates:
        pos = p.get("pos", "")
        if room_filter == "RUSH" and pos not in ("RB", "QB"):
            continue
        if room_filter == "PASS" and pos not in ("WR", "TE", "QB"):
            continue
        pts = calc_season_fantasy_pts(p, model_name)
        rows.append({"player": p.get("player"), "pos": pos, "pts": pts})
    rows.sort(key=lambda x: x["pts"], reverse=True)
    return rows


def _move_badge(name):
    delta = RANK_MOVES.get(name, 0)
    if delta > 0:
        return f'<span style="color:#4ade80;font-size:0.75rem;font-weight:700">▲{delta}</span>'
    if delta < 0:
        return f'<span style="color:#f87171;font-size:0.75rem;font-weight:700">▼{abs(delta)}</span>'
    return ""


def render_fantasy_tab(game_props=None):
    """Vegas-style fantasy rankings UI matching the reference platform screenshots."""
    st.markdown("""
    <style>
    /* Fantasy tab specific overrides */
    .fm-header { text-align: center; padding: 8px 0 2px 0; }
    .fm-vegas {
        font-family: var(--font-display, 'Oswald', sans-serif);
        font-size: 0.7rem; letter-spacing: 3px; color: var(--gold, #f0b429);
        text-transform: uppercase; font-weight: 600; margin-bottom: 2px;
    }
    .fm-logo {
        font-family: var(--font-display, 'Oswald', sans-serif);
        font-size: 2.3rem; font-weight: 700; letter-spacing: 1px;
        color: #ffffff; text-transform: uppercase; line-height: 1.1;
        text-shadow: 0 0 24px var(--gold-glow, rgba(240,180,41,0.35));
    }
    .fm-logo-icon {
        display: inline-block; width: 42px; height: 42px; border-radius: 50%;
        background: linear-gradient(145deg, #2a0806, #0a0a0a);
        border: 2px solid var(--accent, #e10600); text-align: center; line-height: 40px;
        font-size: 1.3rem; margin-bottom: 4px;
        box-shadow: 0 0 20px var(--gold-glow, rgba(240,180,41,0.25));
    }
    .fm-tagline {
        color: var(--muted, #a6a8ad); font-size: 0.88rem; margin-top: 10px; margin-bottom: 4px;
        max-width: 520px; margin-left: auto; margin-right: auto; line-height: 1.4;
    }
    .rank-header-row {
        display: flex; align-items: center; padding: 6px 14px; color: var(--muted, #a6a8ad);
        font-family: var(--font-display, 'Oswald', sans-serif);
        font-size: 0.72rem; font-weight: 600; letter-spacing: 0.8px; text-transform: uppercase;
        border-bottom: 1px solid var(--border, #333336); margin-bottom: 4px;
    }
    .value-badge {
        background: var(--positive-bg, #14321f); color: var(--positive, #4ade80); font-size: 0.68rem; font-weight: 700;
        padding: 3px 10px; border-radius: 999px; display: inline-block;
        letter-spacing: 0.5px;
    }
    .profile-section { padding: 4px 0 8px 0; }
    .comp-label {
        font-family: var(--font-display, 'Oswald', sans-serif);
        font-size: 0.65rem; color: var(--muted, #a6a8ad); font-weight: 600; letter-spacing: 0.4px;
    }
    .comp-val { font-family: var(--font-mono, monospace); font-size: 1.15rem; font-weight: 700; color: #fff; }
    .team-room-row {
        display: flex; align-items: center; padding: 8px 10px; border-radius: 8px;
        background: var(--surface, #161616); margin-bottom: 4px;
    }
    /* Soften expander further inside fantasy */
    div[data-testid="stExpander"] {
        border: 1px solid var(--border, #333336) !important;
        background-color: var(--surface, #161616) !important;
        border-radius: 10px !important;
    }
    /* Pack the RANKS player list tighter so more players fit on screen at once */
    .st-key-fm_ranks_list [data-testid="stVerticalBlock"] { gap: 0.35rem !important; }
    .st-key-fm_ranks_list div[data-testid="stExpander"] { margin: 0 0 4px 0 !important; }
    .st-key-fm_ranks_list div[data-testid="stExpander"] summary {
        padding: 6px 14px !important; min-height: 0 !important;
    }
    .st-key-fm_ranks_list div[data-testid="stExpander"] summary p {
        font-size: 0.85rem !important; margin: 0 !important;
    }
    .st-key-fm_ranks_list [data-testid="stExpanderDetails"] {
        padding: 10px 14px 14px 14px !important;
    }
    </style>
    """, unsafe_allow_html=True)

    data = load_season_long()
    players = enrich_players(data.get("players", []))
    season = data.get("season", "2026")

    if not players:
        st.warning("season_long_futures.json not found or empty.")
        return

    # ---- Header matching screenshots ----
    st.markdown(f"""
    <div class="fm-header">
      <div class="fm-logo-icon">🏈</div>
      <div class="fm-vegas">VEGAS BACKED</div>
      <div class="fm-logo">FANTASY</div>
      <div class="fm-tagline">
        The best {season} Fantasy Football Rankings on the internet,<br>
        calculated directly from the sportsbooks
      </div>
    </div>
    <div class="fade-divider" style="max-width:420px;margin-left:auto;margin-right:auto;"></div>
    """, unsafe_allow_html=True)

    # Sub-nav: RANKS | MOCK DRAFT | WEEKLY | TEAMS | ABOUT
    # Imported here rather than at module scope: mock_draft imports this
    # module, so a top-level import would be circular.
    from mock_draft import render_mock_draft_tab

    ranks_tab, draft_tab, weekly_tab, teams_tab, about_tab = st.tabs([
        "RANKS", "MOCK DRAFT", "WEEKLY", "TEAMS", "ABOUT"
    ])

    # ========== RANKS (primary view) ==========
    with ranks_tab:
        c0, c1, c2, c3, c4 = st.columns([1.3, 1.0, 1.0, 0.8, 0.75])
        with c0:
            rank_source = st.selectbox(
                "Rankings Source",
                RANK_SOURCES,
                index=0,
                key="fm_source",
            )
        with c1:
            pos_filter = st.selectbox(
                "Position",
                ["All", "Skill (no QB)", "QB", "RB", "WR", "TE"],
                key="fm_pos",
            )
        with c2:
            model = st.selectbox(
                "Scoring",
                list(SCORING_MODELS.keys()),
                index=0,
                key="fm_scoring",
            )
        with c3:
            # Each row expands into a full profile (metric strip, season lines,
            # radio-filtered team room). Rendering all ~119 at once produced a
            # DOM the browser couldn't re-apply on a rerun, which hung every
            # other sub-tab — so the list is capped by default.
            list_size = st.selectbox(
                "Show", [25, 50, 100, "All"], index=0, key="fm_list_size",
                help="How many players to render at once. Larger lists get slow.",
            )
        with c4:
            st.markdown("<br>", unsafe_allow_html=True)
            if st.button("▷ DRAFT", key="fm_draft", use_container_width=True):
                st.toast("Open the MOCK DRAFT tab above to set up a draft.", icon="🏈")

        # Rank the pool once (every source attached), then re-sort to
        # whichever source is currently selected.
        ranked, adp_meta = build_ranked_players(players, model, pos_filter)
        ranked.sort(key=lambda x: x[RANK_SOURCE_KEYS[rank_source]])

        if rank_source == "ADP (Live Consensus)":
            if adp_meta:
                st.caption(
                    f"Live {adp_meta.get('teams', ADP_TEAMS)}-team {adp_meta.get('type', 'PPR')} ADP "
                    f"from {adp_meta.get('total_drafts', 0):,} drafts "
                    f"({adp_meta.get('start_date', '')} – {adp_meta.get('end_date', '')}) · "
                    f"Source: Fantasy Football Calculator"
                )
            else:
                st.caption("⚠️ Live ADP data unavailable right now — showing fallback order.")
        elif rank_source != "Vegas (Odds-Based)":
            st.caption(f"Sorted by {rank_source} consensus rankings · Scoring model: {model}")

        if not ranked:
            st.info("No players match this filter.")
        else:
            for i, pl in enumerate(ranked, 1):
                pl["overall_rank"] = i
                pl["pos_rank"] = pos_rank_label(ranked, pl["player"], pl.get("pos"))

            rank_col_label = "RANK" if rank_source == "Vegas (Odds-Based)" else rank_source.upper()

            # Ranks/pos-ranks above are computed over the full board; only the
            # rendered slice is capped.
            shown = ranked if list_size == "All" else ranked[:list_size]
            if len(shown) < len(ranked):
                st.caption(f"Showing top {len(shown)} of {len(ranked)} · change with **Show**")

            # Column header + player rows live in a keyed container so the
            # density CSS above only tightens this list, not the whole app.
            ranks_list = st.container(key="fm_ranks_list")
            with ranks_list:
                st.markdown(f"""
                <div class="rank-header-row">
                  <div style="width:52px">{rank_col_label}</div>
                  <div style="flex:1">PLAYER</div>
                  <div style="width:80px;text-align:right">2026 PROJ</div>
                </div>
                """, unsafe_allow_html=True)

                for pl in shown:
                    rank = pl["overall_rank"]
                    name = pl.get("player", "?")
                    pos_r = pl.get("pos_rank", "")
                    team = pl.get("team", "—")
                    pts = pl["proj_pts"]
                    pos = pl.get("pos", "")
                    move = _move_badge(name)

                    pos_c = POS_COLORS.get(pos, POS_COLOR_DEFAULT)

                    # Expander label styled to look like the rank row
                    with st.expander(f"#{rank}  ·  {name}  ·  {pos_r}  ·  {team}     —  {pts:.0f} proj", expanded=False):
                        # PLAYER PROFILE header + VALUE badge
                        h1, h2 = st.columns([3.2, 1])
                        with h1:
                            st.markdown(
                                f"<div style='font-size:0.7rem;color:var(--muted,#a6a8ad);font-weight:600;"
                                f"letter-spacing:0.8px;margin-bottom:2px'>PLAYER PROFILE</div>"
                                f"<div style='font-size:1.25rem;font-weight:700;color:#fff'>{name}</div>"
                                f"<div style='color:var(--muted,#a6a8ad);font-size:0.85rem'>"
                                f"<span style='color:{pos_c};font-weight:700'>{pos_r}</span> · {team} · {season}</div>",
                                unsafe_allow_html=True,
                            )
                        with h2:
                            st.markdown(
                                f"<div style='text-align:right;padding-top:4px'>"
                                f"<span class='value-badge'>VALUE</span><br>"
                                f"<span style='font-size:1.7rem;font-weight:800;color:#fff'>{pts:.0f}</span>"
                                f"</div>",
                                unsafe_allow_html=True,
                            )

                        note = PLAYER_NOTES.get(
                            name,
                            f"Season-long projection for {name} derived from sportsbook-style futures "
                            f"and season-long prop lines. Rankings update as boards move."
                        )
                        st.markdown(
                            f"<div style='color:#d1d5db;font-size:0.92rem;line-height:1.55;"
                            f"margin:10px 0 14px 0'>{note}</div>",
                            unsafe_allow_html=True,
                        )

                        # Comparison strip: VEGAS | ESPN | FPROS | ADP | VS '25
                        # Vegas/ESPN/FantasyPros are the real per-player ranks
                        # from each source (computed above); ADP/VS'25 stay
                        # anchored to the Vegas rank regardless of which
                        # source is currently sorting the main list.
                        vegas_rank_val = pl["vegas_rank"]
                        espn_rank = pl["espn_rank"]
                        fp_rank = pl["fantasypros_rank"]
                        adp = pl.get("adp")
                        adp_display = f"{adp:.1f}" if adp is not None else "—"
                        vs25 = max(-4, min(5, 8 - vegas_rank_val // 2))
                        vs_color = "#4ade80" if vs25 >= 0 else "#f87171"
                        vs_str = f"+{vs25}" if vs25 > 0 else str(vs25)

                        m1, m2, m3, m4, m5 = st.columns(5)
                        with m1:
                            st.markdown(
                                f"<div class='comp-label'>VEGAS</div>"
                                f"<div class='comp-val'>{vegas_rank_val}</div>",
                                unsafe_allow_html=True,
                            )
                        with m2:
                            st.markdown(
                                f"<div class='comp-label' style='color:var(--accent-light,#ff6b60)'>ESPN</div>"
                                f"<div class='comp-val'>{espn_rank}</div>",
                                unsafe_allow_html=True,
                            )
                        with m3:
                            st.markdown(
                                f"<div class='comp-label' style='color:var(--silver,#a6a8ad)'>FPROS</div>"
                                f"<div class='comp-val'>{fp_rank}</div>",
                                unsafe_allow_html=True,
                            )
                        with m4:
                            st.markdown(
                                f"<div class='comp-label'>ADP</div>"
                                f"<div class='comp-val'>{adp_display}</div>",
                                unsafe_allow_html=True,
                            )
                        with m5:
                            st.markdown(
                                f"<div class='comp-label'>VS '25</div>"
                                f"<div class='comp-val' style='color:{vs_color}'>{vs_str}</div>",
                                unsafe_allow_html=True,
                            )

                        # Season lines snapshot
                        st.markdown(
                            "<div style='font-size:0.7rem;color:var(--muted,#a6a8ad);font-weight:600;"
                            "letter-spacing:0.6px;margin:14px 0 6px 0'>SEASON LINES</div>",
                            unsafe_allow_html=True,
                        )
                        stats_cols = st.columns(4)
                        if pos == "QB":
                            stats_cols[0].metric("Pass Yds", pl.get("pass_yds") or "—")
                            stats_cols[1].metric("Pass TDs", pl.get("pass_tds") or "—")
                            stats_cols[2].metric("INT", pl.get("pass_ints") or "—")
                            stats_cols[3].metric("Rush Yds", pl.get("rush_yds") or "—")
                        else:
                            stats_cols[0].metric("Rush Yds", pl.get("rush_yds") or "—")
                            stats_cols[1].metric("Rec", pl.get("receptions") or "—")
                            stats_cols[2].metric("Rec Yds", pl.get("rec_yds") or "—")
                            stats_cols[3].metric("TDs", pl.get("total_tds") or "—")

                        # TEAM ROOM
                        st.markdown("---")
                        room_header, room_filt = st.columns([2, 2])
                        with room_header:
                            st.markdown(
                                f"<div style='font-size:0.7rem;color:var(--muted,#a6a8ad);font-weight:600;"
                                f"letter-spacing:0.6px'>TEAM ROOM · {team}</div>",
                                unsafe_allow_html=True,
                            )
                        with room_filt:
                            room_mode = st.radio(
                                "room_filter",
                                ["ALL", "RUSH", "PASS"],
                                horizontal=True,
                                key=f"room_{name}_{rank}",
                                label_visibility="collapsed",
                            )

                        room = team_room(players, team, model, room_mode)
                        for mate in room[:7]:
                            is_self = mate["player"] == name
                            bg = "rgba(225,6,0,0.16)" if is_self else "var(--surface, #161616)"
                            name_style = "font-weight:700;color:#fff" if is_self else "color:#e5e7eb"
                            mate_pos_c = POS_COLORS.get(mate["pos"], POS_COLOR_DEFAULT)
                            st.markdown(
                                f"<div style='display:flex;align-items:center;padding:7px 12px;"
                                f"border-radius:8px;background:{bg};margin-bottom:3px'>"
                                f"<div style='flex:1;{name_style}'>{mate['player']} "
                                f"<span style='color:{mate_pos_c};font-size:0.8rem;font-weight:700'>"
                                f"{mate['pos']}</span></div>"
                                f"<div style='font-weight:700;color:#fff' class='fm-nums'>{mate['pts']:.0f} "
                                f"<span style='font-size:0.7rem;color:var(--muted,#a6a8ad);font-weight:500'>PROJ</span></div>"
                                f"</div>",
                                unsafe_allow_html=True,
                            )

    # ========== MOCK DRAFT ==========
    with draft_tab:
        render_mock_draft_tab()

    # ========== WEEKLY ==========
    with weekly_tab:
        st.subheader("Weekly / Game Props Rankings")
        if not game_props:
            st.caption("No game-level props loaded yet. Season-long rankings on the RANKS tab are the primary model.")
            st.info("When live single-game player props are available they will appear here as weekly projections.")
        else:
            st.caption("Built from single-game O/U lines when available")
            by_p = {}
            for p in game_props:
                name = p.get("player", "?")
                by_p.setdefault(name, {"player": name, "team": p.get("team", ""), "pos": p.get("pos", ""), "props": []})
                by_p[name]["props"].append(p)
            half = SCORING_MODELS["Half-PPR"]
            rows = []
            for name, pdata in by_p.items():
                pts = 0.0
                for pr in pdata["props"]:
                    mkt = pr.get("market", "")
                    line = pr.get("line")
                    key_map = {
                        "Pass Yds": "pass_yds", "Pass TDs": "pass_tds",
                        "Rush Yds": "rush_yds", "Rush TDs": "rush_tds",
                        "Rec Yds": "rec_yds", "Receptions": "receptions", "Rec TDs": "rec_tds",
                    }
                    k = key_map.get(mkt)
                    if k and k in half and line is not None:
                        try:
                            pts += float(line) * half[k]
                        except (TypeError, ValueError):
                            pass
                rows.append({
                    "Player": name,
                    "Pos": pdata.get("pos") or "—",
                    "Team": pdata.get("team") or "—",
                    "Game Proj Pts": round(pts, 2),
                })
            if rows:
                gdf = pd.DataFrame(rows).sort_values("Game Proj Pts", ascending=False).reset_index(drop=True)
                gdf.insert(0, "Rank", range(1, len(gdf) + 1))
                st.dataframe(gdf, use_container_width=True, hide_index=True)

    # ========== TEAMS ==========
    with teams_tab:
        st.subheader("Team Rooms")
        st.caption("Projected fantasy points by team · switch scoring on the RANKS tab")
        teams = sorted(set(p.get("team") for p in players if p.get("team")))
        team_pick = st.selectbox("Team", teams, key="fm_team_pick")
        model_t = st.selectbox("Scoring model", list(SCORING_MODELS.keys()), key="fm_team_model")
        room = team_room(players, team_pick, model_t, "ALL")
        if room:
            for i, mate in enumerate(room, 1):
                mate_pos_c = POS_COLORS.get(mate["pos"], POS_COLOR_DEFAULT)
                st.markdown(
                    f"<div style='display:flex;align-items:center;padding:10px 14px;"
                    f"border-radius:10px;background:var(--surface,#161616);border:1px solid var(--border,#333336);margin-bottom:6px'>"
                    f"<div style='width:36px;color:var(--muted,#a6a8ad);font-weight:600'>#{i}</div>"
                    f"<div style='flex:1;font-weight:600;color:#fff'>{mate['player']} "
                    f"<span style='color:{mate_pos_c};font-size:0.85rem;font-weight:700'>{mate['pos']}</span></div>"
                    f"<div style='font-size:1.15rem;font-weight:700;color:#fff' class='fm-nums'>{mate['pts']:.0f}</div>"
                    f"</div>",
                    unsafe_allow_html=True,
                )
        else:
            st.info("No players for this team in the current dataset.")

    # ========== ABOUT ==========
    with about_tab:
        st.subheader("How these rankings work")
        st.markdown("""
        **VEGAS BACKED FANTASY** rankings are derived directly from sportsbook season-long
        futures and player prop lines rather than traditional expert projections.

        - **Projection source**: Season-long over/under lines and futures odds from major books
          are converted into expected statistical production.
        - **Scoring models**: Toggle PPR, Half-PPR, Standard, TE Premium, Superflex and more.
          The same underlying lines power every model — only the scoring weights change.
        - **Rank by prop**: Use the filters on RANKS or the legacy prop-stat views to sort pure
          receiving yards, rushing yards, catches, passing yards, touchdowns, targets, etc.
        - **Team Room**: Every player profile includes the full projected depth chart for that
          franchise so you can see how usage is expected to distribute.
        - **ADP (Live Consensus)**: Real average draft position pulled live from actual fantasy
          drafts (Fantasy Football Calculator), not a projection — this is the one source on the
          board showing what real drafters are actually doing.
        - **Mock Draft**: Full draft room — set teams, format, roster spots and your slot,
          then draft against auto-picking opponents off whichever ranking source you choose.
        - **VALUE badge**: Highlights players our board ranks ahead of consensus ADP / ESPN.

        Rankings update as the boards move. This is the closest thing to a market-implied
        fantasy football ranking available.
        """)
        st.caption(f"Dataset · {season} season · {len(players)} players currently modeled")
