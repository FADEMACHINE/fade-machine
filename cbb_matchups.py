"""Recent-matchup context for CBB picks: shown next to the checklist, not scored.

For a game the model likes:
  - each team's last 3 games: opponent, site, score, and margin against the
    DraftKings closing spread (from ESPN's game summary). Beating the line
    recently means a team is playing better than the market expected.
  - common opponents this season: each team's margin against the same team,
    adjusted for home court, giving a direct strength comparison.

Informational only: it hasn't been backtested, so it doesn't change whether a
game qualifies. Real data only: ESPN scores and saved DraftKings closing lines.
"""
from concurrent.futures import ThreadPoolExecutor

import pandas as pd
import requests
import streamlit as st

import cbb_data as cd

SUMMARY = "https://site.api.espn.com/apis/site/v2/sports/basketball/mens-college-basketball/summary"
RECENT = 3
FORM_EDGE = 3.0   # points vs the line before recent form counts as backing / arguing against


@st.cache_data(ttl=12 * 3600, show_spinner=False, max_entries=2000)
def closing_spreads(event_id):
    """{team_id: DraftKings closing spread} for a finished game, or {}.
    Matched by team id, never by home/away label."""
    try:
        r = requests.get(SUMMARY, params={"event": event_id}, timeout=20)
        r.raise_for_status()
        s = r.json()
    except Exception:
        return {}
    comps = (s.get("header", {}).get("competitions") or [{}])[0].get("competitors") or []
    dk = next((p for p in s.get("pickcenter") or [] if (p.get("provider") or {}).get("name") == "DraftKings"), None)
    if not dk or not comps:
        return {}
    out, abbr = {}, {}
    for c in comps:
        leg = (((dk.get("pointSpread") or {}).get(c.get("homeAway")) or {}).get("close") or {})
        try:
            out[str(c["team"]["id"])] = float(str(leg.get("line")).replace("+", ""))
            abbr[str(c["team"]["id"])] = (c["team"].get("abbreviation") or "").upper()
        except (TypeError, ValueError, KeyError):
            continue
    # Same guard as cbb_data: the "ABBR -x.x" summary names the favourite; if
    # the spreads are on the wrong teams, swap them.
    fav = (dk.get("details") or "").rsplit(" ", 1)[0].strip().upper()
    if len(out) == 2 and fav in abbr.values():
        fav_id = next(t for t, a in abbr.items() if a == fav)
        if out[fav_id] > 0:
            a_, b_ = list(out)
            out = {a_: out[b_], b_: out[a_]}
    return out


def _team_games(season_games, team_id, before_day):
    done = season_games[season_games["completed"] & (season_games["et_date"] < before_day)
                        & ((season_games["home_id"] == team_id) | (season_games["away_id"] == team_id))]
    rows = []
    for r in done.sort_values("date").itertuples():
        home = r.home_id == team_id
        mine, theirs = (r.home_score, r.away_score) if home else (r.away_score, r.home_score)
        site = "N" if r.neutral else ("H" if home else "A")
        hc = cd.HOME_COURT if site == "H" else -cd.HOME_COURT if site == "A" else 0.0
        rows.append({"id": str(r.id), "date": r.et_date, "opp_id": r.away_id if home else r.home_id,
                     "opp": r.away if home else r.home, "site": site, "mine": int(mine), "theirs": int(theirs),
                     "margin": int(mine - theirs), "adj": (mine - theirs) - hc})
    return pd.DataFrame(rows)


def prefetch(games_and_sides, season_games):
    """Fetch the closing spreads the context will need, 8 at a time."""
    ids = set()
    for g in games_and_sides:
        for tid in (g["home_id"], g["away_id"]):
            tg = _team_games(season_games, tid, g["et_date"])
            ids.update(tg.tail(RECENT)["id"]) if not tg.empty else None
    with ThreadPoolExecutor(max_workers=8) as pool:
        list(pool.map(closing_spreads, sorted(ids)))


def context(g, side, season_games):
    """Recent form and common opponents for the pick side of game g."""
    other = "away" if side == "home" else "home"
    me, them = g[f"{side}_id"], g[f"{other}_id"]
    out = {"teams": [], "common": [], "form_edge": None, "common_edge": None}
    form = {}
    for tid, name in ((me, g[side]), (them, g[other])):
        tg = _team_games(season_games, tid, g["et_date"])
        games = []
        ats = []
        for r in tg.tail(RECENT).itertuples() if not tg.empty else []:
            sp = closing_spreads(r.id).get(str(tid))
            beat = None if sp is None else r.margin + sp
            if beat is not None:
                ats.append(beat)
            games.append({"date": r.date, "opp": r.opp, "site": r.site, "score": f"{r.mine}-{r.theirs}",
                          "won": r.margin > 0, "spread": sp, "vs_line": beat})
        form[tid] = sum(ats) / len(ats) if ats else None
        out["teams"].append({"name": name, "games": games, "vs_line": form[tid],
                             "ats": (sum(a > 0 for a in ats), sum(a < 0 for a in ats))})
    if form.get(me) is not None and form.get(them) is not None:
        out["form_edge"] = form[me] - form[them]
    a, b = _team_games(season_games, me, g["et_date"]), _team_games(season_games, them, g["et_date"])
    if not a.empty and not b.empty:
        diffs = []
        for oid in sorted(set(a.opp_id) & set(b.opp_id) - {me, them}):
            ga, gb = a[a.opp_id == oid], b[b.opp_id == oid]
            diffs.append(ga.adj.mean() - gb.adj.mean())
            out["common"].append({"opp": ga.opp.iloc[0],
                                  "pick": ", ".join(f"{m:+d} ({s})" for m, s in zip(ga.margin, ga.site)),
                                  "other": ", ".join(f"{m:+d} ({s})" for m, s in zip(gb.margin, gb.site))})
        if diffs:
            site = 0.0 if g["neutral"] else (cd.HOME_COURT if side == "home" else -cd.HOME_COURT)
            out["common_edge"] = sum(diffs) / len(diffs) + site
    return out


def verdict(ctx, pick_spread, ml):
    """One line on whether recent matchups back the pick."""
    bits = []
    fe = ctx["form_edge"]
    if fe is not None:
        word = "backs" if fe > FORM_EDGE else "argues against" if fe < -FORM_EDGE else "is neutral on"
        bits.append(f"recent form {word} the pick ({fe:+.1f} pts vs the line)")
    ce = ctx["common_edge"]
    if ce is not None:
        need = 0.0 if ml < 0 or pick_spread is None else -pick_spread
        word = "backs" if ce > need else "argues against"
        n = len(ctx["common"])
        bits.append(f"{n} common opponent{'s' if n > 1 else ''} {word} it (pick by {ce:+.1f})")
    return "; ".join(bits).capitalize() + "." if bits else "Not enough recent data yet."


def render(g, side, season_games, pick_spread, ml):
    ctx = context(g, side, season_games)
    st.markdown(f"**Recent matchups:** {verdict(ctx, pick_spread, ml)}")
    for t in ctx["teams"]:
        if not t["games"]:
            continue
        parts = [f"{x['date']:%-m/%-d} {'@' if x['site'] == 'A' else 'vs'} {x['opp']} "
                 f"{'W' if x['won'] else 'L'} {x['score']}"
                 + ("" if x["vs_line"] is None else f" ({x['vs_line']:+.1f} vs line)") for x in t["games"]]
        summary = "" if t["vs_line"] is None else f" — {t['ats'][0]}-{t['ats'][1]} ATS, {t['vs_line']:+.1f} avg"
        st.caption(f"{t['name']}: " + " · ".join(parts) + summary)
    for c in ctx["common"]:
        st.caption(f"Common opponent {c['opp']}: pick {c['pick']} · other side {c['other']}")
