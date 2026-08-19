"""Sleeper-style mock draft hub for FADE MACHINE.

Flow: a settings screen (teams / format / roster spots / your slot) hands off
to a live draft room — a rounds x teams square board, the pick that's on the
clock, and an available-player queue sortable by any of the app's ranking
sources. Teams other than yours auto-draft off that same source, so the only
picks you make are your own.
"""
import random
import time

import streamlit as st

import fantasy_models as fm

STATE_KEY = "fm_mock_draft"

TEAM_COUNT_OPTIONS = [8, 10, 12, 14, 16]
DRAFT_FORMATS = ["Snake", "Linear"]
ROSTER_SPOT_OPTIONS = list(range(4, 21))

# ---- Advanced settings ----
# Starting-lineup slots. Only QB/RB/WR/TE (+FLEX) are offered because the
# season-long dataset carries no kickers or defenses — a K or DST slot would
# be permanently unfillable.
LINEUP_SLOTS = ["QB", "RB", "WR", "TE", "FLEX"]
FLEX_ELIGIBLE = ("RB", "WR", "TE")
DEFAULT_LINEUP = {"QB": 1, "RB": 2, "WR": 2, "TE": 1, "FLEX": 1}
DEFAULT_BENCH = 2
PICK_CLOCK_OPTIONS = {
    "No limit": None, "30 seconds": 30, "60 seconds": 60,
    "90 seconds": 90, "2 minutes": 120,
}
AI_STYLES = ["Best available", "Strict ADP", "Positional need"]

# Soft positional caps so auto-drafting teams build believable rosters instead
# of taking six quarterbacks straight off the top of the board.
AI_POS_CAPS = {"QB": 3, "RB": 7, "WR": 8, "TE": 3}
# The AI takes best-available, but samples across the top few so two mocks
# from identical settings don't play out pick-for-pick the same.
AI_PICK_WEIGHTS = [0.45, 0.25, 0.15, 0.10, 0.05]

QUEUE_PAGE_SIZE = 30

# Per-pick grading. `value` is the overall pick you spent minus the pick the
# consensus board expected him to go at: positive means he lasted longer than
# the market says he should have, i.e. you got a bargain; negative means you
# reached. Expected pick comes from the player's ADP *rank inside this board*
# rather than his raw ADP — raw ADP is measured across a much deeper player
# universe than the ~119 ranked players drafted here, so comparing it to a
# pick number in this draft drifts further apart every round.
GRADE_BANDS = [
    (18, "A+", "#4ade80"), (10, "A", "#4ade80"), (5, "B+", "#86efac"),
    (1, "B", "#86efac"), (-4, "C", "#facc15"), (-10, "D", "#fb923c"),
    (-10 ** 9, "F", "#f87171"),
]
GRADE_POINTS = {"A+": 4.3, "A": 4.0, "B+": 3.3, "B": 3.0, "C": 2.0, "D": 1.0, "F": 0.0}

# ---------------------------------------------------------------- draft state
def _blank_state():
    return {"started": False}


def _get_state():
    if STATE_KEY not in st.session_state:
        st.session_state[STATE_KEY] = _blank_state()
    return st.session_state[STATE_KEY]


def build_draft_order(num_teams, rounds, fmt, third_round_reversal=False):
    """Team slot on the clock for each overall pick, index 0 = pick 1.

    Snake reverses every even round; linear restarts at slot 1 each round.
    Third-round reversal runs round 3 in the same direction as round 2 (so
    the 1.01 seat waits longest), then alternates normally from round 4.
    """
    order = []
    for rnd in range(1, rounds + 1):
        seq = list(range(1, num_teams + 1))
        if fmt == "Snake":
            if third_round_reversal:
                reverse = rnd in (2, 3) or (rnd >= 4 and rnd % 2 == 1)
            else:
                reverse = rnd % 2 == 0
            if reverse:
                seq.reverse()
        order.extend(seq)
    return order


def pick_label(overall, num_teams):
    """Draft-room style '3.07' label for an overall pick number."""
    rnd = (overall - 1) // num_teams + 1
    slot = (overall - 1) % num_teams + 1
    return f"{rnd}.{slot:02d}", rnd, slot


def player_key(player):
    """Stable identity for a player row.

    Names alone aren't unique — the season-long dataset currently carries two
    "Jaylen Waddle" rows on different teams — and keying drafted players or
    widgets by name alone makes one pick remove both and collides Streamlit
    widget keys. Team and position disambiguate without needing clean data.
    """
    return "|".join([
        (player.get("player") or "?"),
        (player.get("team") or "—"),
        (player.get("pos") or ""),
    ])


def _widget_key(prefix, player):
    safe = "".join(c if c.isalnum() else "_" for c in player_key(player))
    return f"{prefix}_{safe}"


def _roster_counts(state, team_slot):
    counts = {}
    for p in state["picks"]:
        if p["team_slot"] == team_slot:
            counts[p["pos"]] = counts.get(p["pos"], 0) + 1
    return counts


def unfilled_starter_slots(lineup, roster_counts):
    """Starting-lineup positions this roster still needs, FLEX resolved last."""
    needs = set()
    flex_used = 0
    for pos in ("QB", "RB", "WR", "TE"):
        have = roster_counts.get(pos, 0)
        want = lineup.get(pos, 0)
        if have < want:
            needs.add(pos)
        elif pos in FLEX_ELIGIBLE:
            flex_used += have - want
    if flex_used < lineup.get("FLEX", 0):
        needs.update(FLEX_ELIGIBLE)
    return needs


def _ai_choice(queue, roster_counts, style="Best available", lineup=None):
    """Pick for an auto-drafting team off the current board.

    Every style respects the soft positional caps; they differ in how much
    they deviate from straight best-available.
    """
    eligible = [
        p for p in queue
        if roster_counts.get(p.get("pos") or "", 0) < AI_POS_CAPS.get(p.get("pos") or "", 99)
    ]
    if not eligible:  # every remaining player is at a capped position
        eligible = list(queue)

    if style == "Strict ADP":
        return eligible[0]

    if style == "Positional need" and lineup:
        needs = unfilled_starter_slots(lineup, roster_counts)
        if needs:
            needed = [p for p in eligible if (p.get("pos") or "") in needs]
            if needed:
                eligible = needed

    pool = eligible[:len(AI_PICK_WEIGHTS)]
    return random.choices(pool, weights=AI_PICK_WEIGHTS[:len(pool)], k=1)[0]


def _record_pick(state, player, team_slot):
    label, rnd, slot = pick_label(state["current"], state["settings"]["teams"])
    state["picks"].append({
        "overall": state["current"],
        "label": label,
        "round": rnd,
        "team_slot": team_slot,
        "player": player.get("player"),
        "pos": player.get("pos") or "",
        "nfl_team": player.get("team") or "—",
        "adp": player.get("adp"),
        "adp_rank": player.get("adp_rank"),
        "key": player_key(player),
    })
    state["drafted"].add(player_key(player))
    state["current"] += 1


def _available(state, ranked, source_key):
    return sorted(
        (p for p in ranked if player_key(p) not in state["drafted"]),
        key=lambda p: p.get(source_key, 9999),
    )


def advance_to_user(state, ranked, source_key):
    """Run every AI pick between now and the user's next turn."""
    order = state["order"]
    adv = state["settings"].get("advanced", {})
    style = adv.get("ai_style", "Best available")
    lineup = adv.get("lineup")
    while state["current"] <= len(order):
        team_slot = order[state["current"] - 1]
        if team_slot == state["settings"]["my_slot"]:
            return
        queue = _available(state, ranked, source_key)
        if not queue:
            state["current"] = len(order) + 1
            return
        _record_pick(
            state,
            _ai_choice(queue, _roster_counts(state, team_slot), style, lineup),
            team_slot,
        )


# -------------------------------------------------------------------- grading
def grade_for_value(value):
    """Letter grade + color for a pick's value over consensus ADP."""
    for threshold, letter, color in GRADE_BANDS:
        if value >= threshold:
            return letter, color
    return "F", "#f87171"


def letter_for_points(points):
    """Map an averaged grade-point back onto the nearest letter."""
    best = min(GRADE_POINTS.items(), key=lambda kv: abs(kv[1] - points))
    return best[0]


def grade_draft(state):
    """Score every pick the user made against MACHINE ADP Consensus.

    Returns (rows, summary). Players the consensus board has never seen carry
    no ADP, so they're listed but excluded from the average rather than being
    scored against a number that doesn't exist.
    """
    my_slot = state["settings"]["my_slot"]
    rows = []
    for p in state["picks"]:
        if p["team_slot"] != my_slot:
            continue
        expected = p.get("adp_rank") if p.get("adp") is not None else None
        value = p["overall"] - expected if expected is not None else None
        letter, color = grade_for_value(value) if value is not None else (None, None)
        rows.append({**p, "expected": expected, "value": value,
                     "grade": letter, "color": color})

    graded = [r for r in rows if r["grade"]]
    if graded:
        avg_points = sum(GRADE_POINTS[r["grade"]] for r in graded) / len(graded)
        total_value = sum(r["value"] for r in graded)
        steals = sum(1 for r in graded if r["value"] >= 10)
        reaches = sum(1 for r in graded if r["value"] <= -10)
    else:
        avg_points, total_value, steals, reaches = 0.0, 0.0, 0, 0

    summary = {
        "letter": letter_for_points(avg_points) if graded else "—",
        "points": round(avg_points, 2),
        "total_value": total_value,
        "steals": steals,
        "reaches": reaches,
        "graded": len(graded),
        "ungraded": len(rows) - len(graded),
        "picks": len(rows),
    }
    return rows, summary


# --------------------------------------------------------------------- render
def _pos_color(pos):
    return fm.POS_COLORS.get(pos, fm.POS_COLOR_DEFAULT)


def _board_html(state):
    """Rounds x teams square grid, one cell per pick — the draft board."""
    settings = state["settings"]
    teams, rounds, my_slot = settings["teams"], settings["rounds"], settings["my_slot"]
    by_cell = {(p["round"], p["team_slot"]): p for p in state["picks"]}
    on_clock = (
        state["order"][state["current"] - 1]
        if state["current"] <= len(state["order"]) else None
    )
    current_round = (state["current"] - 1) // teams + 1

    head = "".join(
        f"<div class='md-th{' md-th-you' if t == my_slot else ''}'>"
        f"{'YOU' if t == my_slot else f'TM {t}'}</div>"
        for t in range(1, teams + 1)
    )
    cells = ""
    for rnd in range(1, rounds + 1):
        cells += f"<div class='md-rnd'>R{rnd}</div>"
        for t in range(1, teams + 1):
            pick = by_cell.get((rnd, t))
            is_now = on_clock == t and rnd == current_round and not pick
            if pick:
                mine = " md-cell-you" if t == my_slot else ""
                cells += (
                    f"<div class='md-cell md-cell-filled{mine}' "
                    f"style='border-left:3px solid {_pos_color(pick['pos'])}'>"
                    f"<div class='md-cell-pick'>{pick['label']}</div>"
                    f"<div class='md-cell-name'>{pick['player']}</div>"
                    f"<div class='md-cell-meta'>"
                    f"<span style='color:{_pos_color(pick['pos'])};font-weight:700'>"
                    f"{pick['pos']}</span> · {pick['nfl_team']}</div>"
                    f"</div>"
                )
            else:
                label, _, _ = pick_label((rnd - 1) * teams + t, teams)
                # Board columns are fixed to teams, so a snake round's cell
                # label comes from that team's actual pick number, not the
                # left-to-right position.
                slot_overall = next(
                    (i + 1 for i, s in enumerate(state["order"])
                     if s == t and (i // teams) + 1 == rnd),
                    None,
                )
                if slot_overall:
                    label, _, _ = pick_label(slot_overall, teams)
                cells += (
                    f"<div class='md-cell{' md-cell-now' if is_now else ''}'>"
                    f"<div class='md-cell-pick'>{label}</div>"
                    f"{'<div class=md-cell-clock>ON THE CLOCK</div>' if is_now else ''}"
                    f"</div>"
                )
    return (
        f"<div class='md-board-scroll'><div class='md-board' "
        f"style='grid-template-columns:44px repeat({teams}, minmax(104px,1fr))'>"
        f"<div class='md-th md-th-corner'></div>{head}{cells}</div></div>"
    )


def _roster_html(state, team_slot, title):
    picks = [p for p in state["picks"] if p["team_slot"] == team_slot]
    if not picks:
        return (
            f"<div class='md-roster-title'>{title}</div>"
            f"<div class='md-roster-empty'>No picks yet.</div>"
        )
    tiles = "".join(
        f"<div class='md-tile' style='border-top:3px solid {_pos_color(p['pos'])}'>"
        f"<div class='md-tile-pos' style='color:{_pos_color(p['pos'])}'>{p['pos']}</div>"
        f"<div class='md-tile-name'>{p['player']}</div>"
        f"<div class='md-tile-meta'>{p['nfl_team']} · {p['label']}</div>"
        f"</div>"
        for p in picks
    )
    return f"<div class='md-roster-title'>{title}</div><div class='md-roster'>{tiles}</div>"


def _inject_css():
    st.markdown("""
    <style>
    .md-board-scroll { overflow-x: auto; padding-bottom: 6px; }
    .md-board { display: grid; gap: 4px; min-width: min-content; }
    .md-th {
        font-family: var(--font-display, 'Oswald', sans-serif);
        font-size: 0.68rem; font-weight: 600; letter-spacing: 0.6px;
        text-transform: uppercase; color: var(--muted, #a6a8ad);
        text-align: center; padding: 6px 2px;
        border-bottom: 1px solid var(--border, #333336);
    }
    .md-th-you { color: var(--accent-light, #ff6b60); }
    .md-th-corner { border-bottom: none; }
    .md-rnd {
        font-family: var(--font-display, 'Oswald', sans-serif);
        font-size: 0.68rem; font-weight: 600; color: var(--muted-dim, #7d7f84);
        display: flex; align-items: center; justify-content: center;
    }
    .md-cell {
        background: var(--surface, #161616);
        border: 1px solid var(--border, #333336);
        border-radius: var(--radius-sm, 6px);
        min-height: 54px; padding: 5px 7px; overflow: hidden;
    }
    .md-cell-filled { background: var(--surface-raised, #1c1c1c); }
    .md-cell-you { background: rgba(225, 6, 0, 0.14); }
    .md-cell-now {
        border: 1.5px solid var(--accent, #e10600);
        box-shadow: 0 0 14px rgba(225, 6, 0, 0.35);
    }
    .md-cell-pick {
        font-family: var(--font-mono, monospace); font-size: 0.62rem;
        color: var(--muted-dim, #7d7f84);
    }
    .md-cell-name {
        font-size: 0.76rem; font-weight: 600; color: #fff; line-height: 1.2;
        margin-top: 1px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis;
    }
    .md-cell-meta { font-size: 0.64rem; color: var(--muted, #a6a8ad); }
    .md-cell-clock {
        font-family: var(--font-display, 'Oswald', sans-serif); font-size: 0.6rem;
        font-weight: 700; letter-spacing: 0.5px; color: var(--accent-light, #ff6b60);
        margin-top: 4px;
    }
    .md-onclock {
        display: flex; align-items: center; gap: 14px; flex-wrap: wrap;
        background: var(--surface, #161616); border: 1px solid var(--border, #333336);
        border-left: 4px solid var(--accent, #e10600);
        border-radius: var(--radius-md, 10px); padding: 12px 16px; margin: 4px 0 12px 0;
    }
    .md-onclock-label {
        font-family: var(--font-display, 'Oswald', sans-serif); font-size: 0.66rem;
        font-weight: 600; letter-spacing: 1px; color: var(--muted, #a6a8ad);
        text-transform: uppercase;
    }
    .md-onclock-val {
        font-family: var(--font-display, 'Oswald', sans-serif);
        font-size: 1.5rem; font-weight: 700; color: #fff; line-height: 1.1;
    }
    .md-roster-title {
        font-family: var(--font-display, 'Oswald', sans-serif); font-size: 0.7rem;
        font-weight: 600; letter-spacing: 0.8px; text-transform: uppercase;
        color: var(--muted, #a6a8ad); margin: 10px 0 6px 0;
    }
    .md-roster {
        display: grid; gap: 6px;
        grid-template-columns: repeat(auto-fill, minmax(122px, 1fr));
    }
    .md-tile {
        background: var(--surface, #161616); border: 1px solid var(--border, #333336);
        border-radius: var(--radius-sm, 6px); padding: 7px 9px; min-height: 58px;
    }
    .md-tile-pos {
        font-family: var(--font-display, 'Oswald', sans-serif);
        font-size: 0.65rem; font-weight: 700; letter-spacing: 0.5px;
    }
    .md-tile-name {
        font-size: 0.8rem; font-weight: 600; color: #fff; line-height: 1.25;
    }
    .md-tile-meta { font-size: 0.66rem; color: var(--muted, #a6a8ad); margin-top: 2px; }
    .md-roster-empty { color: var(--muted-dim, #7d7f84); font-size: 0.85rem; }
    .md-qrow {
        display: flex; align-items: center; gap: 10px;
        border-bottom: 1px solid var(--border, #333336); padding: 2px 0;
    }
    .md-qrank {
        font-family: var(--font-mono, monospace); font-size: 0.8rem;
        color: var(--muted, #a6a8ad); width: 30px;
    }
    .md-qname { font-size: 0.9rem; font-weight: 600; color: #fff; }
    /* ---- advanced settings ---- */
    .md-adv-note { color: var(--muted, #a6a8ad); font-size: 0.85rem; margin-bottom: 10px; }
    .md-adv-head {
        font-family: var(--font-display, 'Oswald', sans-serif); font-size: 0.7rem;
        font-weight: 600; letter-spacing: 0.8px; text-transform: uppercase;
        color: var(--muted, #a6a8ad); margin: 4px 0 2px 0;
    }
    /* ---- pick clock ---- */
    .md-clock {
        background: var(--surface, #161616); border: 1px solid var(--border, #333336);
        border-radius: var(--radius-md, 10px); padding: 10px 14px; margin-bottom: 12px;
    }
    .md-clock-label {
        font-family: var(--font-display, 'Oswald', sans-serif); font-size: 0.64rem;
        font-weight: 600; letter-spacing: 1px; text-transform: uppercase;
        color: var(--muted, #a6a8ad);
    }
    .md-clock-val {
        font-family: var(--font-mono, monospace); font-size: 1.5rem; font-weight: 700;
        line-height: 1.15;
    }
    .md-clock-bar {
        height: 5px; border-radius: 999px; background: var(--surface-raised, #1c1c1c);
        overflow: hidden; margin-top: 6px;
    }
    .md-clock-fill { height: 100%; border-radius: 999px; transition: width 0.9s linear; }
    /* ---- grade page ---- */
    .md-grade-head {
        font-family: var(--font-display, 'Oswald', sans-serif); font-size: 0.7rem;
        font-weight: 600; letter-spacing: 1.2px; text-transform: uppercase;
        color: var(--muted, #a6a8ad); margin-bottom: 6px;
    }
    .md-grade-hero {
        display: flex; align-items: center; gap: 26px; flex-wrap: wrap;
        background: var(--surface, #161616); border: 1px solid var(--border, #333336);
        border-left: 4px solid var(--accent, #e10600);
        border-radius: var(--radius-md, 10px); padding: 16px 20px; margin-bottom: 8px;
    }
    .md-grade-letter {
        font-family: var(--font-display, 'Oswald', sans-serif);
        font-size: 3.6rem; font-weight: 700; line-height: 1;
    }
    .md-grade-meta { display: flex; gap: 26px; flex-wrap: wrap; }
    .md-grade-meta > div { display: flex; flex-direction: column; }
    .md-grade-k {
        font-family: var(--font-display, 'Oswald', sans-serif); font-size: 0.62rem;
        font-weight: 600; letter-spacing: 0.8px; text-transform: uppercase;
        color: var(--muted, #a6a8ad);
    }
    .md-grade-v {
        font-family: var(--font-mono, monospace); font-size: 1.15rem;
        font-weight: 700; color: #fff;
    }
    .md-gr-table {
        border: 1px solid var(--border, #333336); border-radius: var(--radius-md, 10px);
        overflow: hidden; margin-top: 10px;
    }
    .md-gr {
        display: grid; grid-template-columns: 62px 1fr 70px 74px 66px;
        align-items: center; gap: 8px; padding: 9px 14px;
        border-bottom: 1px solid var(--border, #333336);
    }
    .md-gr:last-child { border-bottom: none; }
    .md-gr:hover { background: var(--surface-raised, #1c1c1c); }
    .md-gr-head {
        background: var(--surface, #161616);
        font-family: var(--font-display, 'Oswald', sans-serif); font-size: 0.64rem;
        font-weight: 600; letter-spacing: 0.7px; color: var(--muted, #a6a8ad);
    }
    .md-gr-head div { color: var(--muted, #a6a8ad) !important; }
    .md-gr-pick { font-family: var(--font-mono, monospace); font-size: 0.8rem; color: var(--muted, #a6a8ad); }
    .md-gr-name { font-size: 0.9rem; font-weight: 600; color: #fff; }
    .md-gr-sub { font-size: 0.74rem; color: var(--muted, #a6a8ad); font-weight: 400; }
    .md-gr-num {
        font-family: var(--font-mono, monospace); font-size: 0.85rem;
        text-align: right; color: var(--text, #f5f5f5);
    }
    .md-gr-grade { text-align: right; }
    .md-gr-badge {
        display: inline-block; min-width: 34px; text-align: center;
        font-family: var(--font-display, 'Oswald', sans-serif); font-weight: 700;
        font-size: 0.85rem; padding: 2px 8px; border-radius: 999px;
        border: 1.5px solid currentColor;
    }
    .md-gr-badge-none { color: var(--muted-dim, #7d7f84); }
    .md-qmeta { font-size: 0.74rem; color: var(--muted, #a6a8ad); }
    /* Keep the queue's per-row draft buttons compact so 30 rows stay scannable */
    .st-key-md_queue .stButton > button {
        padding: 2px 10px !important; min-height: 0 !important; font-size: 0.75rem !important;
    }
    .st-key-md_queue [data-testid="stVerticalBlock"] { gap: 0.25rem !important; }
    </style>
    """, unsafe_allow_html=True)


def _render_settings(state, pool_size):
    st.markdown(
        "<div style='font-size:0.7rem;color:var(--muted,#a6a8ad);font-weight:600;"
        "letter-spacing:0.8px;margin-bottom:2px'>DRAFT SETUP</div>"
        "<div style='font-size:1.35rem;font-weight:700;color:#fff;margin-bottom:10px'>"
        "Configure your mock draft</div>",
        unsafe_allow_html=True,
    )
    c1, c2, c3 = st.columns(3)
    with c1:
        teams = st.selectbox("Number of teams", TEAM_COUNT_OPTIONS, index=2, key="md_teams")
        fmt = st.selectbox("Draft format", DRAFT_FORMATS, index=0, key="md_format")
    with c2:
        scoring = st.selectbox(
            "Scoring", list(fm.SCORING_MODELS.keys()), index=0, key="md_scoring",
        )
        source = st.selectbox(
            "Board / queue source", fm.RANK_SOURCES,
            index=fm.RANK_SOURCES.index("ADP (Live Consensus)"), key="md_source_init",
            help="Orders your available-player queue and drives how the other teams draft.",
        )
    with c3:
        my_slot = st.selectbox(
            "Your draft position", list(range(1, teams + 1)), index=0, key="md_slot",
            help="Which seat you're drafting from in round 1.",
        )

    # Every pick needs a real player behind it, so roster size is capped at
    # what the ranked pool can actually fill for this many teams.
    max_rounds = max(1, pool_size // teams)

    with st.expander("⚙️ Advanced settings", expanded=False):
        st.markdown(
            "<div class='md-adv-note'>Starting lineup, bench depth, pick clock "
            "and how the other teams draft.</div>",
            unsafe_allow_html=True,
        )
        st.markdown("<div class='md-adv-head'>Starting lineup</div>", unsafe_allow_html=True)
        slot_cols = st.columns(len(LINEUP_SLOTS))
        lineup = {}
        for col, slot in zip(slot_cols, LINEUP_SLOTS):
            with col:
                lineup[slot] = st.number_input(
                    slot, min_value=0, max_value=6,
                    value=DEFAULT_LINEUP.get(slot, 0), step=1, key=f"md_slot_{slot}",
                    help="FLEX takes RB/WR/TE." if slot == "FLEX" else None,
                )
        st.caption(
            "Kicker and defense slots aren't offered — the season-long dataset "
            "carries only QB, RB, WR and TE."
        )

        a1, a2, a3 = st.columns(3)
        with a1:
            bench = st.number_input(
                "Bench spots", min_value=0, max_value=12, value=DEFAULT_BENCH,
                step=1, key="md_bench",
            )
        with a2:
            clock_label = st.selectbox(
                "Time per pick", list(PICK_CLOCK_OPTIONS.keys()), index=0, key="md_clock",
                help="Your picks only. Run out of time and the board takes the "
                     "top available player for you.",
            )
        with a3:
            ai_style = st.selectbox(
                "Opponent draft style", AI_STYLES, index=0, key="md_ai_style",
                help="Best available samples the top of the board; Strict ADP "
                     "always takes the top player; Positional need fills "
                     "starting slots first.",
            )
        third_round_reversal = st.checkbox(
            "Third-round reversal (3RR)", value=False, key="md_3rr",
            disabled=(fmt != "Snake"),
            help="Round 3 runs the same direction as round 2, evening out the "
                 "advantage of an early first-round pick. Snake drafts only.",
        )

    starters = sum(lineup.values())
    rounds = starters + bench
    over_pool = rounds > max_rounds
    if over_pool:
        rounds = max_rounds

    m1, m2, m3 = st.columns(3)
    m1.metric("Starters", starters)
    m2.metric("Bench", bench)
    m3.metric("Rounds", rounds)

    st.caption(
        f"{teams} teams · {rounds} rounds · {teams * rounds} total picks · "
        f"{fmt.lower()}{' + 3RR' if third_round_reversal and fmt == 'Snake' else ''} order · "
        f"you pick at 1.{my_slot:02d} · {pool_size}-player board"
    )
    if over_pool:
        st.warning(
            f"A {starters}-starter + {bench}-bench roster is {starters + bench} rounds, "
            f"but only {pool_size} ranked players are loaded — {teams} teams can fill "
            f"{max_rounds}. The draft will run {max_rounds} rounds."
        )
    if rounds < 1:
        st.error("Add at least one starting or bench spot to draft.")
        return

    if st.button("▷ START DRAFT", type="primary", key="md_start"):
        state.update({
            "started": True,
            "settings": {
                "teams": teams, "rounds": rounds, "format": fmt,
                "my_slot": my_slot, "scoring": scoring,
                "advanced": {
                    "lineup": lineup,
                    "bench": bench,
                    "starters": starters,
                    "pick_seconds": PICK_CLOCK_OPTIONS[clock_label],
                    "ai_style": ai_style,
                    "third_round_reversal": bool(third_round_reversal and fmt == "Snake"),
                },
            },
            "order": build_draft_order(
                teams, rounds, fmt, bool(third_round_reversal and fmt == "Snake")
            ),
            "picks": [],
            "drafted": set(),
            "current": 1,
            "source": source,
            "deadline": None,
        })
        st.rerun()


@st.fragment(run_every=1)
def _pick_clock():
    """Live countdown for the user's pick.

    Runs as a fragment so the tick re-renders only this strip, not the whole
    draft room. On expiry it auto-drafts the top available player and asks
    for a full rerun so the board and queue catch up.
    """
    state = _get_state()
    deadline = state.get("deadline")
    if not state.get("started") or deadline is None:
        return
    remaining = deadline - time.time()

    if remaining <= 0:
        settings = state["settings"]
        data = fm.load_season_long()
        ranked, _ = fm.build_ranked_players(
            fm.enrich_players(data.get("players", [])), settings["scoring"], "All"
        )
        source_key = fm.RANK_SOURCE_KEYS[state.get("source", fm.RANK_SOURCES[0])]
        queue = _available(state, ranked, source_key)
        if queue:
            _record_pick(state, queue[0], settings["my_slot"])
            state["autopicked"] = queue[0].get("player")
            advance_to_user(state, ranked, source_key)
        state["deadline"] = None
        st.rerun(scope="app")
        return

    total = state["settings"]["advanced"].get("pick_seconds") or 1
    pct = max(0.0, min(1.0, remaining / total))
    urgent = remaining <= 10
    color = "var(--accent, #e10600)" if urgent else "var(--positive, #4ade80)"
    st.markdown(
        f"<div class='md-clock'>"
        f"<div class='md-clock-label'>Time remaining</div>"
        f"<div class='md-clock-val' style='color:{color}'>{int(remaining)}s</div>"
        f"<div class='md-clock-bar'><div class='md-clock-fill' "
        f"style='width:{pct * 100:.0f}%;background:{color}'></div></div>"
        f"</div>",
        unsafe_allow_html=True,
    )


def _render_grade_page(state):
    """Post-draft report card: your picks vs MACHINE ADP Consensus."""
    rows, s = grade_draft(state)
    if not rows:
        st.info("You didn't make any picks in this draft.")
        return

    st.markdown(
        "<div class='md-grade-head'>MACHINE ADP CONSENSUS · DRAFT GRADE</div>",
        unsafe_allow_html=True,
    )
    _, color = grade_for_value(0)
    letter_color = next(
        (c for th, l, c in GRADE_BANDS if l == s["letter"]), "var(--muted,#a6a8ad)"
    )
    st.markdown(
        f"<div class='md-grade-hero'>"
        f"<div class='md-grade-letter' style='color:{letter_color}'>{s['letter']}</div>"
        f"<div class='md-grade-meta'>"
        f"<div><span class='md-grade-k'>Grade points</span>"
        f"<span class='md-grade-v'>{s['points']:.2f}</span></div>"
        f"<div><span class='md-grade-k'>Total value vs ADP</span>"
        f"<span class='md-grade-v' style='color:"
        f"{'var(--positive,#4ade80)' if s['total_value'] >= 0 else 'var(--negative,#f87171)'}'>"
        f"{s['total_value']:+d}</span></div>"
        f"<div><span class='md-grade-k'>Steals / Reaches</span>"
        f"<span class='md-grade-v'>{s['steals']} / {s['reaches']}</span></div>"
        f"<div><span class='md-grade-k'>Picks graded</span>"
        f"<span class='md-grade-v'>{s['graded']} of {s['picks']}</span></div>"
        f"</div></div>",
        unsafe_allow_html=True,
    )
    st.caption(
        "**Expected** is where MACHINE ADP Consensus says the player should have "
        "gone on this board. **Value** is your pick number minus that — positive "
        "means he lasted longer than the market says and you got a bargain; "
        "negative means you reached."
    )

    head = (
        "<div class='md-gr md-gr-head'>"
        "<div class='md-gr-pick'>YOUR PICK</div><div class='md-gr-name'>PLAYER</div>"
        "<div class='md-gr-num'>ADP</div><div class='md-gr-num'>EXPECTED</div>"
        "<div class='md-gr-num'>VALUE</div><div class='md-gr-grade'>GRADE</div></div>"
    )
    body = ""
    for r in rows:
        if r["grade"]:
            val_color = "var(--positive,#4ade80)" if r["value"] >= 0 else "var(--negative,#f87171)"
            val_txt = f"{r['value']:+d}"
            adp_txt = f"{r['adp']:.1f}"
            exp_txt = f"#{r['expected']}"
            grade_html = (
                f"<span class='md-gr-badge' style='color:{r['color']};"
                f"border-color:{r['color']}'>{r['grade']}</span>"
            )
        else:
            val_color = "var(--muted-dim,#7d7f84)"
            val_txt = adp_txt = exp_txt = "—"
            grade_html = "<span class='md-gr-badge md-gr-badge-none'>NR</span>"
        body += (
            f"<div class='md-gr'>"
            f"<div class='md-gr-pick'>{r['label']}"
            f"<span class='md-gr-sub'> #{r['overall']}</span></div>"
            f"<div class='md-gr-name'>{r['player']}"
            f"<span class='md-gr-sub'> <span style='color:{_pos_color(r['pos'])};"
            f"font-weight:700'>{r['pos']}</span> · {r['nfl_team']}</span></div>"
            f"<div class='md-gr-num'>{adp_txt}</div>"
            f"<div class='md-gr-num'>{exp_txt}</div>"
            f"<div class='md-gr-num' style='color:{val_color}'>{val_txt}</div>"
            f"<div class='md-gr-grade'>{grade_html}</div>"
            f"</div>"
        )
    st.markdown(f"<div class='md-gr-table'>{head}{body}</div>", unsafe_allow_html=True)

    if s["ungraded"]:
        st.caption(
            f"{s['ungraded']} pick(s) marked NR — the consensus board has no ADP "
            f"for them, so they're left out of the average."
        )


def _render_queue(state, ranked, source_key):
    """Available (undrafted) players, ordered by the selected ranking source."""
    settings = state["settings"]
    queue = _available(state, ranked, source_key)
    my_turn = (
        state["current"] <= len(state["order"])
        and state["order"][state["current"] - 1] == settings["my_slot"]
    )

    f1, f2 = st.columns([1, 2])
    with f1:
        pos_filter = st.selectbox(
            "Position", ["All", "QB", "RB", "WR", "TE"], key="md_qpos",
        )
    with f2:
        search = st.text_input("Search player", key="md_qsearch", placeholder="Name…")

    shown = [
        p for p in queue
        if (pos_filter == "All" or p.get("pos") == pos_filter)
        and (not search or search.lower() in (p.get("player") or "").lower())
    ]
    st.caption(f"{len(queue)} players available · showing {min(len(shown), QUEUE_PAGE_SIZE)}")

    box = st.container(key="md_queue")
    with box:
        for p in shown[:QUEUE_PAGE_SIZE]:
            name = p.get("player", "?")
            pos = p.get("pos") or ""
            adp = p.get("adp")
            adp_txt = f"ADP {adp:.1f}" if adp is not None else "ADP —"
            col_a, col_b = st.columns([6, 1])
            with col_a:
                st.markdown(
                    f"<div class='md-qrow'>"
                    f"<div class='md-qrank'>{p.get(source_key, '—')}</div>"
                    f"<div style='flex:1'>"
                    f"<div class='md-qname'>{name}</div>"
                    f"<div class='md-qmeta'>"
                    f"<span style='color:{_pos_color(pos)};font-weight:700'>{pos}</span>"
                    f" · {p.get('team', '—')} · {adp_txt} · {p['proj_pts']:.0f} proj</div>"
                    f"</div></div>",
                    unsafe_allow_html=True,
                )
            with col_b:
                if st.button(
                    "DRAFT", key=_widget_key("md_pick", p), disabled=not my_turn,
                    use_container_width=True,
                ):
                    _record_pick(state, p, settings["my_slot"])
                    advance_to_user(state, ranked, source_key)
                    st.rerun()

    if not shown:
        st.info("No available players match that filter.")


def _render_draft_room(state):
    settings = state["settings"]
    data = fm.load_season_long()
    players = fm.enrich_players(data.get("players", []))
    ranked, adp_meta = fm.build_ranked_players(players, settings["scoring"], "All")

    top = st.columns([1.6, 1, 1])
    with top[0]:
        source = st.selectbox(
            "Board / queue source", fm.RANK_SOURCES,
            index=fm.RANK_SOURCES.index(state.get("source", fm.RANK_SOURCES[0])),
            key="md_source_live",
        )
        state["source"] = source
    source_key = fm.RANK_SOURCE_KEYS[source]
    with top[1]:
        st.markdown("<br>", unsafe_allow_html=True)
        # Only enabled once the user owns a pick — otherwise "undo" would just
        # re-roll the AI picks ahead of their first turn.
        has_own_pick = any(p["team_slot"] == settings["my_slot"] for p in state["picks"])
        if st.button("↩ Undo last pick", key="md_undo", use_container_width=True,
                     disabled=not has_own_pick):
            # Roll back to the user's own previous pick so undo doesn't just
            # get instantly re-made by the AI teams ahead of them.
            my_slot = settings["my_slot"]
            while state["picks"]:
                last = state["picks"].pop()
                state["drafted"].discard(last.get("key", last["player"]))
                state["current"] = last["overall"]
                if last["team_slot"] == my_slot:
                    break
            st.rerun()
    with top[2]:
        st.markdown("<br>", unsafe_allow_html=True)
        if st.button("✕ Exit draft", key="md_reset", use_container_width=True):
            st.session_state[STATE_KEY] = _blank_state()
            st.rerun()

    total_picks = len(state["order"])
    complete = state["current"] > total_picks

    # Other teams pick automatically — catch up to the user's turn on load.
    if not complete:
        advance_to_user(state, ranked, source_key)
        complete = state["current"] > total_picks

    if complete:
        st.success(f"Draft complete — {len(state['picks'])} picks made.")
        state["deadline"] = None
    else:
        label, rnd, _ = pick_label(state["current"], settings["teams"])
        on_clock = state["order"][state["current"] - 1]
        mine = on_clock == settings["my_slot"]
        # Start (or clear) the pick clock as the turn changes.
        pick_seconds = settings.get("advanced", {}).get("pick_seconds")
        if mine and pick_seconds:
            if state.get("deadline") is None:
                state["deadline"] = time.time() + pick_seconds
        else:
            state["deadline"] = None
        st.markdown(
            f"<div class='md-onclock'>"
            f"<div><div class='md-onclock-label'>Pick</div>"
            f"<div class='md-onclock-val'>{label}</div></div>"
            f"<div><div class='md-onclock-label'>Round</div>"
            f"<div class='md-onclock-val'>{rnd} <span style='font-size:0.9rem;"
            f"color:var(--muted,#a6a8ad)'>of {settings['rounds']}</span></div></div>"
            f"<div><div class='md-onclock-label'>On the clock</div>"
            f"<div class='md-onclock-val' style='color:"
            f"{'var(--accent-light,#ff6b60)' if mine else '#fff'}'>"
            f"{'YOUR PICK' if mine else f'Team {on_clock}'}</div></div>"
            f"</div>",
            unsafe_allow_html=True,
        )
        if state.get("deadline") is not None:
            _pick_clock()

    autopicked = state.pop("autopicked", None)
    if autopicked:
        st.toast(f"Clock expired — auto-drafted {autopicked}.", icon="⏱️")

    if source == "ADP (Live Consensus)" and adp_meta:
        st.caption(
            f"Queue ordered by live {adp_meta.get('teams', fm.ADP_TEAMS)}-team "
            f"{adp_meta.get('type', 'PPR')} ADP from "
            f"{adp_meta.get('total_drafts', 0):,} drafts · Fantasy Football Calculator"
        )
    else:
        st.caption(f"Queue ordered by {source} · Scoring: {settings['scoring']}")

    if complete:
        grade_view, board_view = st.tabs(["📊 DRAFT GRADE", "🗒️ FINAL BOARD"])
        with grade_view:
            _render_grade_page(state)
        with board_view:
            st.markdown(_board_html(state), unsafe_allow_html=True)
            st.markdown(
                _roster_html(state, settings["my_slot"],
                             f"Your roster · Team {settings['my_slot']}"),
                unsafe_allow_html=True,
            )
        return

    st.markdown(_board_html(state), unsafe_allow_html=True)
    st.markdown(
        _roster_html(state, settings["my_slot"], f"Your roster · Team {settings['my_slot']}"),
        unsafe_allow_html=True,
    )
    st.markdown("---")
    _render_queue(state, ranked, source_key)


def render_mock_draft_tab():
    """Entry point — settings screen until a draft is started, then the room."""
    _inject_css()
    state = _get_state()
    if not state.get("started"):
        data = fm.load_season_long()
        pool_size = len(data.get("players", []))
        if not pool_size:
            st.warning("No ranked players loaded — can't start a draft.")
            return
        _render_settings(state, pool_size)
    else:
        _render_draft_room(state)
