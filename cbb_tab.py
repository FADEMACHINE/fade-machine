"""College Hoops tab: today's board, MACHINE Power Ratings, team lookup and the
March Madness cheat sheet. Data and model live in cbb_data.py; the edges the
cheat sheet flags live in cbb_edges.py (that's the file to keep tuning).
"""
from datetime import datetime

import pandas as pd
import streamlit as st

import cbb_data as cd
import cbb_edges


def _rec(w, l, p=0):
    return f"{int(w)}-{int(l)}" + (f"-{int(p)}" if p else "")


def _ranks(r):
    winpct = r["wins"] / r["games"].where(r["games"] > 0, 1)
    rank = lambda s, asc=False: dict(zip(r["team_id"], s.rank(ascending=asc, method="min").astype(int)))
    return {"net": rank(r["net"]), "off": rank(r["off"]), "def": rank(r["def"]),
            "sos": rank(r["sos"]), "winpct": rank(winpct)}


def _with_flags(r):
    ranks = _ranks(r)
    r = r.copy()
    flags = [cbb_edges.team_flags(row, ranks) for row in r.to_dict("records")]
    r["edges"] = [", ".join(("✅ " if t == "edge" else "🚫 ") + n for n, t, _ in f) for f in flags]
    r["off_rank"] = r["team_id"].map(ranks["off"])
    r["def_rank"] = r["team_id"].map(ranks["def"])
    return r


def _ratings_table(r):
    return pd.DataFrame({
        "Rk": r["rank"],
        "Team": r["team"],
        "W-L": [_rec(w, l) for w, l in zip(r["wins"], r["losses"])],
        "Net": r["net"].round(1),
        "Off (rk)": [f"{o:+.1f} ({k})" for o, k in zip(r["off"], r["off_rank"])],
        "Def (rk)": [f"{d:+.1f} ({k})" for d, k in zip(r["def"], r["def_rank"])],
        "SOS": r["sos"],
        "ATS": [_rec(w, l, p) for w, l, p in zip(r["ats_w"], r["ats_l"], r["ats_p"])],
        "O/U": [_rec(o, u) for o, u in zip(r["over"], r["under"])],
        "Last 10": [_rec(w, n - w) for w, n in zip(r["last10_w"], r["last10_n"])],
        "Edges": r["edges"],
    })


# ---- Sections --------------------------------------------------------------
def _board(games, ratings, model):
    day = st.date_input("Games on", value=datetime.now(cd.ET).date(), key="cbb_day")
    day_games = games[games["date"].dt.tz_convert(cd.ET).dt.date == day] if not games.empty else games
    if day_games.empty:
        st.info("No D1 games found for that date.")
        return
    only_edges = st.checkbox("Only games where the model disagrees with the line by 3+", key="cbb_only_edges")
    rows = []
    for g in day_games.to_dict("records"):
        p = cd.project(g, ratings, model)
        line = "" if g["home_spread"] is None or pd.isna(g["home_spread"]) else f"{g['home_abbr']} {g['home_spread']:+g}"
        row = {
            "Tip (ET)": g["date"].tz_convert(cd.ET).strftime("%-I:%M %p"),
            "Matchup": f"{'#' + str(g['away_rank']) + ' ' if g['away_rank'] and g['away_rank'] <= 25 else ''}{g['away']} "
                       f"{'vs' if g['neutral'] else '@'} "
                       f"{'#' + str(g['home_rank']) + ' ' if g['home_rank'] and g['home_rank'] <= 25 else ''}{g['home']}",
            "Status": g["status"],
            "Line": line,
            "Total": g["total_line"],
            "MACHINE": "" if not p else f"{g['home_abbr']} {-p['margin']:+.1f}",
            "Home win %": None if not p else round(100 * p["home_wp"]),
            "Proj total": None if not p else round(p["total"], 1),
            "Spread edge": None if not p or "spread_edge" not in p else round(p["spread_edge"], 1),
            "Total edge": None if not p or "total_edge" not in p else round(p["total_edge"], 1),
            "Small sample": bool(p and p["thin"]),
        }
        if g["completed"]:
            row["Status"] = f"F {int(g['away_score'])}-{int(g['home_score'])}"
        rows.append(row)
    df = pd.DataFrame(rows)
    if only_edges:
        df = df[(df["Spread edge"].abs() >= 3) | (df["Total edge"].abs() >= 3)]
    st.dataframe(df, hide_index=True, width="stretch")
    st.caption("MACHINE is the model's fair line for the home side. Spread edge > 0 means the model likes "
               "the home team more than the market; < 0 the road team. Total edge > 0 leans over. "
               "Lines are ESPN's posted numbers. Small sample = a team has fewer than "
               f"{cd.MIN_GAMES} games, so trust it less.")


def _ratings(r):
    q = st.text_input("Find a team", key="cbb_find")
    view = r[r["team"].str.contains(q, case=False, na=False)] if q else r
    st.dataframe(_ratings_table(view), hide_index=True, width="stretch", height=600)
    st.caption("Net = points better than an average D1 team on a neutral floor (Off + Def). "
               "SOS = opponents' average Net. Built only from this season's scores.")


def _team(games, r):
    team = st.selectbox("Team", r["team"].tolist(), key="cbb_team")
    t = r[r["team"] == team].iloc[0]
    c = st.columns(4)
    c[0].metric("MACHINE rank", f"#{t['rank']}", f"Net {t['net']:+.1f}")
    c[1].metric("Record", _rec(t["wins"], t["losses"]), f"Last 10: {_rec(t['last10_w'], t['last10_n'] - t['last10_w'])}")
    c[2].metric("ATS", _rec(t["ats_w"], t["ats_l"], t["ats_p"]),
                f"Fav {_rec(t['fav_ats_w'], t['fav_ats_l'])} · Dog {_rec(t['dog_ats_w'], t['dog_ats_l'])}")
    c[3].metric("O/U", _rec(t["over"], t["under"]), f"Close games {_rec(t['close_w'], t['close_n'] - t['close_w'])}")
    if t["edges"]:
        st.markdown(f"**Edges:** {t['edges']}")
    tid = t["team_id"]
    mine = games[((games["home_id"] == tid) | (games["away_id"] == tid)) & games["completed"]]
    log = []
    for g in mine.iloc[::-1].to_dict("records"):
        home = g["home_id"] == tid
        pts, opp = (g["home_score"], g["away_score"]) if home else (g["away_score"], g["home_score"])
        spread = None if g["home_spread"] is None or pd.isna(g["home_spread"]) else (g["home_spread"] if home else -g["home_spread"])
        ats = "" if spread is None else ("W" if pts - opp + spread > 0 else "L" if pts - opp + spread < 0 else "P")
        log.append({
            "Date": g["date"].tz_convert(cd.ET).strftime("%b %-d"),
            "Opponent": ("vs " if home or g["neutral"] else "@ ") + (g["away"] if home else g["home"]),
            "Result": f"{'W' if pts > opp else 'L'} {int(pts)}-{int(opp)}",
            "Line": "" if spread is None else f"{spread:+g}",
            "ATS": ats,
            "Total": g["total_line"],
        })
    st.dataframe(pd.DataFrame(log), hide_index=True, width="stretch")


def _matchup(r, model, key):
    names = r["team"].tolist()
    c = st.columns(2)
    a = c[0].selectbox("Team A", names, index=0, key=f"{key}_a")
    b = c[1].selectbox("Team B", names, index=min(1, len(names) - 1), key=f"{key}_b")
    if a == b:
        return
    ta, tb = r[r["team"] == a].iloc[0], r[r["team"] == b].iloc[0]
    p = cd.project({"home_id": ta["team_id"], "away_id": tb["team_id"], "neutral": True,
                    "home_spread": None, "total_line": None}, r, model)
    if not p:
        return
    fav, dog = (a, b) if p["margin"] >= 0 else (b, a)
    st.markdown(f"**Neutral floor:** {fav} by {abs(p['margin']):.1f} · "
                f"{a} win {100 * p['home_wp']:.0f}% · projected {p['home_pts']:.0f}-{p['away_pts']:.0f} "
                f"(total {p['total']:.1f})")


def _march(games, r, model):
    tourney = games[games["tournament"]] if not games.empty else games
    if not tourney.empty:
        st.markdown("#### NCAA Tournament games")
        rows = []
        for g in tourney.to_dict("records"):
            p = cd.project(g, r, model)
            fav = g["home"] if p and p["margin"] >= 0 else g["away"]
            rows.append({
                "Round": g["notes"].split(" - ")[-1] if g["notes"] else "",
                "Matchup": f"{g['away']} vs {g['home']}",
                "MACHINE pick": fav if p else "",
                "Win %": None if not p else round(100 * max(p["home_wp"], 1 - p["home_wp"])),
                "Line": "" if g["home_spread"] is None or pd.isna(g["home_spread"]) else f"{g['home_abbr']} {g['home_spread']:+g}",
                "Spread edge": None if not p or "spread_edge" not in p else round(p["spread_edge"], 1),
                "Result": f"{int(g['away_score'])}-{int(g['home_score'])}" if g["completed"] else g["status"],
            })
        st.dataframe(pd.DataFrame(rows), hide_index=True, width="stretch")
    else:
        st.info("The bracket lands on Selection Sunday. Until then this is Bracket Watch: the top 68 "
                "by MACHINE rating with every edge flagged, so the cheat sheet is ready the moment "
                "seeds drop.")

    st.markdown("#### Cheat sheet: top 68")
    top = r.head(68)
    sheet = _ratings_table(top)
    st.dataframe(sheet, hide_index=True, width="stretch", height=500)
    st.download_button("Download cheat sheet (CSV)", sheet.to_csv(index=False),
                       file_name=f"fade_machine_cheat_sheet_{datetime.now(cd.ET):%Y%m%d}.csv",
                       mime="text/csv", key="cbb_csv")

    st.markdown("#### Edge legend")
    for e in cbb_edges.EDGES:
        st.markdown(f"{'✅' if e['tone'] == 'edge' else '🚫'} **{e['name']}**: {e['why']}")

    st.markdown("#### Head-to-head")
    _matchup(r, model, "cbb_h2h")


# ---- Entry -----------------------------------------------------------------
def render_cbb_tab():
    season = cd.season_for()
    with st.spinner("Loading the college basketball season…"):
        games, failed = cd.load_season(season)
    if games.empty:
        st.info("College basketball data isn't reachable right now (ESPN scoreboard). Nothing is shown "
                "rather than sample numbers. Try again shortly.")
        return
    if failed:
        st.caption(f"{failed} day(s) of the schedule didn't load and will retry on the next refresh.")

    ratings, model = cd.fit_ratings(games)
    done = int(games["completed"].sum())
    st.caption(f"{season - 1}-{str(season)[-2:]} season · {done:,} completed D1 games · "
               f"{len(ratings)} rated teams · refreshes every 30 min")
    if ratings.empty:
        st.info("No completed games yet this season, so there are no ratings. The board still shows lines.")
        _board(games, ratings, model)
        return
    if done < 600:
        st.warning("Early season: ratings are built from only a few games per team and pulled toward "
                   "average on purpose. Treat edges as a watchlist until teams have 8-10 games.")
    ratings = _with_flags(ratings)

    board, power, team, march = st.tabs(["📅 Board", "📊 Power Ratings", "🔎 Team", "🏆 March Madness"])
    with board:
        _board(games, ratings, model)
    with power:
        _ratings(ratings)
    with team:
        _team(games, ratings)
    with march:
        _march(games, ratings, model)
