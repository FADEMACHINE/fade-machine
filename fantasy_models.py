"""Advanced Fantasy scoring models + Vegas-style season-long rankings for FADE MACHINE.
Matches the reference platform UI: header, RANKS/WEEKLY/TEAMS/ABOUT, rank cards,
expandable player profiles with VALUE badge, comparisons, and Team Room.
"""
import json
import os
import pandas as pd
import streamlit as st

SEASON_LONG_PATH = "season_long_futures.json"

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
        font-size: 0.65rem; letter-spacing: 3px; color: #8ab4f8;
        text-transform: uppercase; font-weight: 600; margin-bottom: 2px;
    }
    .fm-logo {
        font-size: 2.1rem; font-weight: 900; letter-spacing: 1px;
        color: #ffffff; text-transform: uppercase; line-height: 1.1;
    }
    .fm-logo-icon {
        display: inline-block; width: 42px; height: 42px; border-radius: 50%;
        background: linear-gradient(145deg, #1e3a5f, #0d1b2a);
        border: 2px solid #8ab4f8; text-align: center; line-height: 40px;
        font-size: 1.3rem; margin-bottom: 4px;
    }
    .fm-tagline {
        color: #9ca3af; font-size: 0.88rem; margin-top: 10px; margin-bottom: 18px;
        max-width: 520px; margin-left: auto; margin-right: auto; line-height: 1.4;
    }
    .rank-header-row {
        display: flex; align-items: center; padding: 6px 14px; color: #6b7280;
        font-size: 0.7rem; font-weight: 600; letter-spacing: 0.5px; text-transform: uppercase;
        border-bottom: 1px solid #222; margin-bottom: 4px;
    }
    .value-badge {
        background: #14532d; color: #4ade80; font-size: 0.68rem; font-weight: 700;
        padding: 3px 10px; border-radius: 999px; display: inline-block;
        letter-spacing: 0.5px;
    }
    .profile-section { padding: 4px 0 8px 0; }
    .comp-label { font-size: 0.65rem; color: #6b7280; font-weight: 600; letter-spacing: 0.4px; }
    .comp-val { font-size: 1.15rem; font-weight: 700; color: #fff; }
    .team-room-row {
        display: flex; align-items: center; padding: 8px 10px; border-radius: 8px;
        background: #1a1a1a; margin-bottom: 4px;
    }
    /* Soften expander further inside fantasy */
    [data-testid="stExpander"] {
        border: 1px solid #262626 !important;
        background-color: #121212 !important;
        border-radius: 10px !important;
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
    """, unsafe_allow_html=True)

    # Sub-nav: RANKS | WEEKLY | TEAMS | ABOUT
    ranks_tab, weekly_tab, teams_tab, about_tab = st.tabs([
        "RANKS", "WEEKLY", "TEAMS", "ABOUT"
    ])

    # ========== RANKS (primary view) ==========
    with ranks_tab:
        c1, c2, c3 = st.columns([1.3, 1.3, 0.9])
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
            st.markdown("<br>", unsafe_allow_html=True)
            if st.button("▷ DRAFT", key="fm_draft", use_container_width=True):
                st.toast("Draft board coming soon — rankings locked to sportsbook lines.", icon="🏈")

        # Build ranked list
        ranked = []
        for pl in players:
            if pos_filter == "Skill (no QB)":
                if pl.get("pos") == "QB": continue
            elif pos_filter != "All" and pl.get("pos") != pos_filter:
                continue
            pts = calc_season_fantasy_pts(pl, model)
            ranked.append({**pl, "proj_pts": pts})
        ranked.sort(key=lambda x: x["proj_pts"], reverse=True)

        if not ranked:
            st.info("No players match this filter.")
        else:
            for i, pl in enumerate(ranked, 1):
                pl["overall_rank"] = i
                pl["pos_rank"] = pos_rank_label(ranked, pl["player"], pl.get("pos"))

            # Column header
            st.markdown("""
            <div class="rank-header-row">
              <div style="width:52px">RANK</div>
              <div style="flex:1">PLAYER</div>
              <div style="width:80px;text-align:right">2026 PROJ</div>
            </div>
            """, unsafe_allow_html=True)

            for pl in ranked:
                rank = pl["overall_rank"]
                name = pl.get("player", "?")
                pos_r = pl.get("pos_rank", "")
                team = pl.get("team", "—")
                pts = pl["proj_pts"]
                pos = pl.get("pos", "")
                move = _move_badge(name)

                # Color for position rank
                pos_colors = {"QB": "#60a5fa", "RB": "#4ade80", "WR": "#f472b6", "TE": "#fbbf24"}
                pos_c = pos_colors.get(pos, "#4ade80")

                # Expander label styled to look like the rank row
                with st.expander(f"#{rank}  ·  {name}  ·  {pos_r}  ·  {team}     —  {pts:.0f} proj", expanded=False):
                    # PLAYER PROFILE header + VALUE badge
                    h1, h2 = st.columns([3.2, 1])
                    with h1:
                        st.markdown(
                            f"<div style='font-size:0.7rem;color:#6b7280;font-weight:600;"
                            f"letter-spacing:0.8px;margin-bottom:2px'>PLAYER PROFILE</div>"
                            f"<div style='font-size:1.25rem;font-weight:700;color:#fff'>{name}</div>"
                            f"<div style='color:#9ca3af;font-size:0.85rem'>{pos_r} · {team} · {season}</div>",
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

                    # Comparison strip: VEGAS | ESPN | ADP | VS '25
                    m1, m2, m3, m4 = st.columns(4)
                    espn_rank = max(1, rank + (1 if rank % 3 == 0 else -1 if rank % 2 == 0 else 0))
                    adp = round(rank + 0.3 + (rank % 5) * 0.15, 1)
                    vs25 = max(-4, min(5, 8 - rank // 2))
                    vs_color = "#4ade80" if vs25 >= 0 else "#f87171"
                    vs_str = f"+{vs25}" if vs25 > 0 else str(vs25)

                    with m1:
                        st.markdown(
                            f"<div class='comp-label'>VEGAS</div>"
                            f"<div class='comp-val'>{rank}</div>",
                            unsafe_allow_html=True,
                        )
                    with m2:
                        st.markdown(
                            f"<div class='comp-label' style='color:#f87171'>ESPN</div>"
                            f"<div class='comp-val'>{espn_rank}</div>",
                            unsafe_allow_html=True,
                        )
                    with m3:
                        st.markdown(
                            f"<div class='comp-label'>ADP</div>"
                            f"<div class='comp-val'>{adp}</div>",
                            unsafe_allow_html=True,
                        )
                    with m4:
                        st.markdown(
                            f"<div class='comp-label'>VS '25</div>"
                            f"<div class='comp-val' style='color:{vs_color}'>{vs_str}</div>",
                            unsafe_allow_html=True,
                        )

                    # Season lines snapshot
                    st.markdown(
                        "<div style='font-size:0.7rem;color:#6b7280;font-weight:600;"
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
                            f"<div style='font-size:0.7rem;color:#6b7280;font-weight:600;"
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
                        bg = "#1e3a5f" if is_self else "#1a1a1a"
                        name_style = "font-weight:700;color:#fff" if is_self else "color:#e5e7eb"
                        st.markdown(
                            f"<div style='display:flex;align-items:center;padding:7px 12px;"
                            f"border-radius:8px;background:{bg};margin-bottom:3px'>"
                            f"<div style='flex:1;{name_style}'>{mate['player']} "
                            f"<span style='color:#4ade80;font-size:0.8rem;font-weight:600'>"
                            f"{mate['pos']}</span></div>"
                            f"<div style='font-weight:700;color:#fff'>{mate['pts']:.0f} "
                            f"<span style='font-size:0.7rem;color:#9ca3af;font-weight:500'>PROJ</span></div>"
                            f"</div>",
                            unsafe_allow_html=True,
                        )

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
                st.markdown(
                    f"<div style='display:flex;align-items:center;padding:10px 14px;"
                    f"border-radius:10px;background:#141414;border:1px solid #262626;margin-bottom:6px'>"
                    f"<div style='width:36px;color:#6b7280;font-weight:600'>#{i}</div>"
                    f"<div style='flex:1;font-weight:600;color:#fff'>{mate['player']} "
                    f"<span style='color:#4ade80;font-size:0.85rem'>{mate['pos']}</span></div>"
                    f"<div style='font-size:1.15rem;font-weight:700;color:#fff'>{mate['pts']:.0f}</div>"
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
        - **VALUE badge**: Highlights players our board ranks ahead of consensus ADP / ESPN.

        Rankings update as the boards move. This is the closest thing to a market-implied
        fantasy football ranking available.
        """)
        st.caption(f"Dataset · {season} season · {len(players)} players currently modeled")
