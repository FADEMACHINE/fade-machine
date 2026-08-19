"""Sleeper-style mock draft hub for FADE MACHINE.

Flow: a settings screen (teams / format / roster spots / your slot) hands off
to a live draft room — a rounds x teams square board, the pick that's on the
clock, and an available-player queue sortable by any of the app's ranking
sources. Teams other than yours auto-draft off that same source, so the only
picks you make are your own.
"""
import random

import streamlit as st

import fantasy_models as fm

STATE_KEY = "fm_mock_draft"

TEAM_COUNT_OPTIONS = [8, 10, 12, 14, 16]
DRAFT_FORMATS = ["Snake", "Linear"]
ROSTER_SPOT_OPTIONS = list(range(4, 21))

# Soft positional caps so auto-drafting teams build believable rosters instead
# of taking six quarterbacks straight off the top of the board.
AI_POS_CAPS = {"QB": 3, "RB": 7, "WR": 8, "TE": 3}
# The AI takes best-available, but samples across the top few so two mocks
# from identical settings don't play out pick-for-pick the same.
AI_PICK_WEIGHTS = [0.45, 0.25, 0.15, 0.10, 0.05]

QUEUE_PAGE_SIZE = 30


# ---------------------------------------------------------------- draft state
def _blank_state():
    return {"started": False}


def _get_state():
    if STATE_KEY not in st.session_state:
        st.session_state[STATE_KEY] = _blank_state()
    return st.session_state[STATE_KEY]


def build_draft_order(num_teams, rounds, fmt):
    """Team slot on the clock for each overall pick, index 0 = pick 1.

    Snake reverses every odd-indexed round; linear restarts at slot 1 each
    round.
    """
    order = []
    for rnd in range(rounds):
        seq = list(range(1, num_teams + 1))
        if fmt == "Snake" and rnd % 2 == 1:
            seq.reverse()
        order.extend(seq)
    return order


def pick_label(overall, num_teams):
    """Draft-room style '3.07' label for an overall pick number."""
    rnd = (overall - 1) // num_teams + 1
    slot = (overall - 1) % num_teams + 1
    return f"{rnd}.{slot:02d}", rnd, slot


def _roster_counts(state, team_slot):
    counts = {}
    for p in state["picks"]:
        if p["team_slot"] == team_slot:
            counts[p["pos"]] = counts.get(p["pos"], 0) + 1
    return counts


def _ai_choice(queue, roster_counts):
    """Best-available off the current board, filtered by positional caps."""
    pool = []
    for p in queue:
        pos = p.get("pos") or ""
        if roster_counts.get(pos, 0) >= AI_POS_CAPS.get(pos, 99):
            continue
        pool.append(p)
        if len(pool) >= len(AI_PICK_WEIGHTS):
            break
    if not pool:  # every remaining player is at a capped position
        pool = queue[:len(AI_PICK_WEIGHTS)]
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
    })
    state["drafted"].add(player.get("player"))
    state["current"] += 1


def _available(state, ranked, source_key):
    return sorted(
        (p for p in ranked if p.get("player") not in state["drafted"]),
        key=lambda p: p.get(source_key, 9999),
    )


def advance_to_user(state, ranked, source_key):
    """Run every AI pick between now and the user's next turn."""
    order = state["order"]
    while state["current"] <= len(order):
        team_slot = order[state["current"] - 1]
        if team_slot == state["settings"]["my_slot"]:
            return
        queue = _available(state, ranked, source_key)
        if not queue:
            state["current"] = len(order) + 1
            return
        _record_pick(state, _ai_choice(queue, _roster_counts(state, team_slot)), team_slot)


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
        # Every pick needs a real player behind it, so cap roster spots at
        # what the ranked pool can actually fill for this many teams.
        max_rounds = max(1, pool_size // teams)
        round_options = [r for r in ROSTER_SPOT_OPTIONS if r <= max_rounds] or [1]
        rounds = st.selectbox(
            "Roster spots per team", round_options, index=len(round_options) - 1,
            key="md_rounds",
            help="Also the number of rounds — one roster spot is filled per round. "
                 "Capped so the draft never runs out of players.",
        )
        scoring = st.selectbox(
            "Scoring", list(fm.SCORING_MODELS.keys()), index=0, key="md_scoring",
        )
    with c3:
        my_slot = st.selectbox(
            "Your draft position", list(range(1, teams + 1)), index=0, key="md_slot",
            help="Which seat you're drafting from in round 1.",
        )
        source = st.selectbox(
            "Board / queue source", fm.RANK_SOURCES,
            index=fm.RANK_SOURCES.index("ADP (Live Consensus)"), key="md_source_init",
            help="Orders your available-player queue and drives how the other teams draft.",
        )

    st.caption(
        f"{teams} teams · {rounds} rounds · {teams * rounds} total picks · "
        f"{fmt.lower()} order · you pick at 1.{my_slot:02d} · "
        f"{pool_size}-player board"
    )
    if rounds * teams > pool_size:
        st.warning(
            f"Only {pool_size} ranked players are loaded — a {teams}-team, "
            f"{rounds}-round draft needs {teams * rounds}. The board will fill "
            f"until the pool runs out."
        )
    if st.button("▷ START DRAFT", type="primary", key="md_start"):
        state.update({
            "started": True,
            "settings": {
                "teams": teams, "rounds": rounds, "format": fmt,
                "my_slot": my_slot, "scoring": scoring,
            },
            "order": build_draft_order(teams, rounds, fmt),
            "picks": [],
            "drafted": set(),
            "current": 1,
            "source": source,
        })
        st.rerun()


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
                    "DRAFT", key=f"md_pick_{name}", disabled=not my_turn,
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
                state["drafted"].discard(last["player"])
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
    else:
        label, rnd, _ = pick_label(state["current"], settings["teams"])
        on_clock = state["order"][state["current"] - 1]
        mine = on_clock == settings["my_slot"]
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

    if source == "ADP (Live Consensus)" and adp_meta:
        st.caption(
            f"Queue ordered by live {adp_meta.get('teams', fm.ADP_TEAMS)}-team "
            f"{adp_meta.get('type', 'PPR')} ADP from "
            f"{adp_meta.get('total_drafts', 0):,} drafts · Fantasy Football Calculator"
        )
    else:
        st.caption(f"Queue ordered by {source} · Scoring: {settings['scoring']}")

    st.markdown(_board_html(state), unsafe_allow_html=True)
    st.markdown(
        _roster_html(state, settings["my_slot"], f"Your roster · Team {settings['my_slot']}"),
        unsafe_allow_html=True,
    )

    if not complete:
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
