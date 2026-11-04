"""College basketball data and the MACHINE ratings model.

Source: ESPN's public scoreboard JSON (no key, no Odds API credits). One request
per day of the season; finished days are cached for a week, today/yesterday for
30 minutes. The lines shown are the ones ESPN publishes with each game.

Model: MACHINE Power Ratings are a ridge-regularised least-squares fit of every
game's score to team offence + defence + home court. Early in the season the
ridge pulls everyone toward average, so ratings start flat and sharpen as games
come in. That's on purpose: no preseason guesses, only this season's results.

Nothing here is invented. If ESPN can't be reached, functions return empty
frames and the tab says so.
"""
from concurrent.futures import ThreadPoolExecutor
from datetime import date, datetime, timedelta
from math import erf, sqrt
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd
import requests
import streamlit as st

ET = ZoneInfo("America/New_York")
SCOREBOARD = ("https://site.api.espn.com/apis/site/v2/sports/basketball/"
              "mens-college-basketball/scoreboard")
MARGIN_SD = 11.0      # spread of real CBB results around a projection, in points
RIDGE = 4.0           # shrinkage toward average; worth ~4 games of evidence
MIN_GAMES = 5         # below this a team's numbers are flagged as thin


# ---- Season calendar -------------------------------------------------------
def season_for(day=None):
    """The season named by the year it ends in: Nov 2026 - Apr 2027 is 2027."""
    day = day or datetime.now(ET).date()
    return day.year + 1 if day.month >= 8 else day.year


def season_dates(season, today=None):
    today = today or datetime.now(ET).date()
    start = date(season - 1, 11, 1)
    end = min(today, date(season, 4, 10))
    return [start + timedelta(days=i) for i in range((end - start).days + 1)]


# ---- Fetch -----------------------------------------------------------------
def _get_day(day_str):
    resp = requests.get(SCOREBOARD, timeout=20, params={
        "dates": day_str, "groups": "50", "limit": "500"})
    resp.raise_for_status()
    return resp.json().get("events", [])


@st.cache_data(ttl=7 * 24 * 3600, show_spinner=False)
def _day_final(day_str):
    return _get_day(day_str)


@st.cache_data(ttl=30 * 60, show_spinner=False)
def _day_live(day_str):
    return _get_day(day_str)


def fetch_events(days):
    """All events for the given dates. Returns (events, failed_day_count)."""
    today = datetime.now(ET).date()

    def one(d):
        s = d.strftime("%Y%m%d")
        try:
            return (_day_live(s) if d >= today - timedelta(days=1) else _day_final(s)), False
        except Exception:
            return [], True

    with ThreadPoolExecutor(max_workers=8) as pool:
        results = list(pool.map(one, days))
    events = [e for evs, _ in results for e in evs]
    return events, sum(1 for _, failed in results if failed)


# ---- Parse -----------------------------------------------------------------
def _num(v):
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def _home_spread(odds, home_abbr, away_abbr):
    """Home team's spread (negative = home favoured), from ESPN's odds block."""
    details = (odds.get("details") or "").strip()
    if details.upper() in ("EVEN", "PK", "PICK"):
        return 0.0
    parts = details.rsplit(" ", 1)
    if len(parts) == 2 and _num(parts[1]) is not None:
        abbr, pts = parts[0].strip().upper(), _num(parts[1])
        if abbr == (home_abbr or "").upper():
            return pts
        if abbr == (away_abbr or "").upper():
            return -pts
    home_fav = (odds.get("homeTeamOdds") or {}).get("favorite")
    away_fav = (odds.get("awayTeamOdds") or {}).get("favorite")
    sp = _num(odds.get("spread"))
    if sp is None:
        return None
    if home_fav:
        return -abs(sp)
    if away_fav:
        return abs(sp)
    return None


def parse_events(events):
    rows = []
    for ev in events or []:
        comp = (ev.get("competitions") or [{}])[0]
        teams = {c.get("homeAway"): c for c in comp.get("competitors", [])}
        home, away = teams.get("home"), teams.get("away")
        if not home or not away:
            continue
        ht, at = home.get("team", {}), away.get("team", {})
        status = (ev.get("status") or comp.get("status") or {}).get("type", {})
        odds = (comp.get("odds") or [{}])[0] or {}
        notes = " ".join(n.get("headline", "") for n in comp.get("notes", []) if n.get("headline"))
        rows.append({
            "id": ev.get("id"),
            "date": ev.get("date"),
            "home_id": ht.get("id"), "away_id": at.get("id"),
            "home": ht.get("displayName") or ht.get("location"),
            "away": at.get("displayName") or at.get("location"),
            "home_abbr": ht.get("abbreviation"), "away_abbr": at.get("abbreviation"),
            "home_rank": (home.get("curatedRank") or {}).get("current"),
            "away_rank": (away.get("curatedRank") or {}).get("current"),
            "home_score": _num(home.get("score")), "away_score": _num(away.get("score")),
            "completed": bool(status.get("completed")),
            "state": status.get("state"),
            "status": status.get("shortDetail") or status.get("description"),
            "neutral": bool(comp.get("neutralSite")),
            "conf_game": bool(comp.get("conferenceCompetition")),
            "home_spread": _home_spread(odds, ht.get("abbreviation"), at.get("abbreviation")) if odds else None,
            "total_line": _num(odds.get("overUnder")),
            "line_source": odds.get("provider", {}).get("name") if odds else None,
            "notes": notes,
            "tournament": "Men's Basketball Championship" in notes,
        })
    df = pd.DataFrame(rows)
    if df.empty:
        return df
    df = df.drop_duplicates("id")
    df["date"] = pd.to_datetime(df["date"], utc=True, errors="coerce")
    return df.sort_values("date").reset_index(drop=True)


@st.cache_data(ttl=30 * 60, show_spinner=False)
def load_season(season):
    """(games_df, failed_days). Cached as a whole for 30 min on top of the
    per-day caches, so tab switches don't re-parse a whole season."""
    events, failed = fetch_events(season_dates(season))
    return parse_events(events), failed


# ---- Model -----------------------------------------------------------------
def fit_ratings(games):
    """Ridge fit of points scored: pts = avg + off[team] - def[opp] ± hca/2.

    Returns (ratings_df, model) where model has avg points and home edge.
    A team's net rating is off + def = points better than an average D1 team
    on a neutral floor.
    """
    done = games[games["completed"] & games["home_score"].notna()] if not games.empty else games
    if done is None or done.empty:
        return pd.DataFrame(), None

    ids = pd.unique(pd.concat([done["home_id"], done["away_id"]]))
    idx = {t: i for i, t in enumerate(ids)}
    n = len(ids)
    # params: off[0..n), def[n..2n), hca
    rows, y = [], []
    for g in done.itertuples():
        h, a = idx[g.home_id], idx[g.away_id]
        site = 0.0 if g.neutral else 0.5
        r = np.zeros(2 * n + 1); r[h] = 1; r[n + a] = -1; r[-1] = site
        rows.append(r); y.append(g.home_score)
        r = np.zeros(2 * n + 1); r[a] = 1; r[n + h] = -1; r[-1] = -site
        rows.append(r); y.append(g.away_score)
    X, y = np.array(rows), np.array(y)
    avg = y.mean()
    reg = np.full(2 * n + 1, RIDGE); reg[-1] = 0.01
    beta = np.linalg.solve(X.T @ X + np.diag(reg), X.T @ (y - avg))
    off, dfn, hca = beta[:n], beta[n:2 * n], beta[-1]

    names = {}
    for g in done.itertuples():
        names[g.home_id] = g.home
        names[g.away_id] = g.away
    rat = pd.DataFrame({"team_id": ids, "team": [names[t] for t in ids],
                        "off": off, "def": dfn})
    rat["net"] = rat["off"] + rat["def"]
    rat = rat.merge(team_records(done, rat), on="team_id", how="left")
    rat["rank"] = rat["net"].rank(ascending=False, method="min").astype(int)
    return rat.sort_values("net", ascending=False).reset_index(drop=True), {"avg": avg, "hca": hca}


def team_records(done, rat):
    """W-L, ATS, O/U, close games, last 10 and strength of schedule per team."""
    net = dict(zip(rat["team_id"], rat["off"] + rat["def"]))
    long = []
    for g in done.itertuples():
        for side in ("home", "away"):
            other = "away" if side == "home" else "home"
            pts, opp = getattr(g, f"{side}_score"), getattr(g, f"{other}_score")
            spread = None
            if g.home_spread is not None and not pd.isna(g.home_spread):
                spread = g.home_spread if side == "home" else -g.home_spread
            ats = None
            if spread is not None:
                m = pts - opp + spread
                ats = "W" if m > 0 else "L" if m < 0 else "P"
            ou = None
            if g.total_line is not None and not pd.isna(g.total_line):
                t = pts + opp
                ou = "O" if t > g.total_line else "U" if t < g.total_line else "P"
            long.append({"team_id": getattr(g, f"{side}_id"), "date": g.date,
                         "win": pts > opp, "margin": pts - opp, "ats": ats, "ou": ou,
                         "fav": spread is not None and spread < 0,
                         "opp_net": net.get(getattr(g, f"{other}_id"), 0.0)})
    L = pd.DataFrame(long).sort_values("date")

    def summarise(grp):
        last10 = grp.tail(10)
        close = grp[grp["margin"].abs() <= 5]
        ats = grp[grp["ats"].notna()]
        fav = ats[ats["fav"]]
        dog = ats[~ats["fav"]]
        ou = grp[grp["ou"].notna()]
        return pd.Series({
            "games": len(grp), "wins": int(grp["win"].sum()), "losses": int((~grp["win"]).sum()),
            "last10_w": int(last10["win"].sum()), "last10_n": len(last10),
            "close_w": int(close["win"].sum()), "close_n": len(close),
            "ats_w": int((ats["ats"] == "W").sum()), "ats_l": int((ats["ats"] == "L").sum()),
            "ats_p": int((ats["ats"] == "P").sum()),
            "fav_ats_w": int((fav["ats"] == "W").sum()), "fav_ats_l": int((fav["ats"] == "L").sum()),
            "dog_ats_w": int((dog["ats"] == "W").sum()), "dog_ats_l": int((dog["ats"] == "L").sum()),
            "over": int((ou["ou"] == "O").sum()), "under": int((ou["ou"] == "U").sum()),
            "avg_margin": round(grp["margin"].mean(), 1),
            "sos": round(grp["opp_net"].mean(), 1),
        })

    return L.groupby("team_id").apply(summarise, include_groups=False).reset_index()


def win_prob(margin):
    return 0.5 * (1 + erf(margin / (MARGIN_SD * sqrt(2))))


def project(game, ratings, model):
    """Projected home margin and total for one game row, or None if either
    team has no rating yet."""
    if ratings is None or ratings.empty or model is None:
        return None
    r = ratings.set_index("team_id")
    if game["home_id"] not in r.index or game["away_id"] not in r.index:
        return None
    h, a = r.loc[game["home_id"]], r.loc[game["away_id"]]
    site = 0.0 if game["neutral"] else 0.5
    home_pts = model["avg"] + h["off"] - a["def"] + site * model["hca"]
    away_pts = model["avg"] + a["off"] - h["def"] - site * model["hca"]
    margin = home_pts - away_pts
    out = {"home_pts": home_pts, "away_pts": away_pts, "margin": margin,
           "total": home_pts + away_pts, "home_wp": win_prob(margin),
           "thin": min(h["games"], a["games"]) < MIN_GAMES}
    if game.get("home_spread") is not None and not pd.isna(game.get("home_spread")):
        # Positive = model likes the home side more than the line does.
        out["spread_edge"] = margin + game["home_spread"]
    if game.get("total_line") is not None and not pd.isna(game.get("total_line")):
        out["total_edge"] = out["total"] - game["total_line"]
    return out
