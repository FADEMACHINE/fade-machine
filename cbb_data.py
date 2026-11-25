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
HOME_COURT = 3.0      # points; standard college home-court edge, held fixed (see fit_ratings)


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


def _ml(odds, side):
    """American moneyline for 'home'/'away' from ESPN's odds block: closing
    (current) price first, then opening, then the legacy teamOdds field."""
    ml = (odds.get("moneyline") or {}).get(side) or {}
    for key in ("close", "open"):
        v = _num(str((ml.get(key) or {}).get("odds", "")).replace("+", ""))
        if v is not None:
            return v
    if str((ml.get("close") or {}).get("odds", "")).upper() == "EVEN":
        return 100.0
    return _num((odds.get(f"{side}TeamOdds") or {}).get("moneyLine"))


def _spread_close(odds, side):
    """(line, price) for 'home'/'away' from ESPN's pointSpread block: closing
    (current) line first, then opening. (None, None) if not posted."""
    ps = (odds.get("pointSpread") or {}).get(side) or {}
    for key in ("close", "open"):
        leg = ps.get(key) or {}
        line, price = _num(str(leg.get("line", "")).replace("+", "")), _num(str(leg.get("odds", "")).replace("+", ""))
        if line is not None and price is not None:
            return line, price
    return None, None


def _odds_side_check(odds, home_abbr, away_abbr):
    """True if ESPN's home/away prices are attached to the wrong teams.

    At neutral sites ESPN sometimes swaps which team it calls home during the
    day but leaves the odds block where it was, so the 'home' price belongs to
    the other team. The summary line ("LSU -4.5") names the favourite by
    abbreviation and can't drift, so it's the referee: if it says one team is
    favoured but the moneylines say the other, the prices are flipped."""
    details = (odds.get("details") or "").strip()
    parts = details.rsplit(" ", 1)
    if len(parts) != 2 or _num(parts[1]) is None or _num(parts[1]) == 0:
        return False
    fav = parts[0].strip().upper()
    hml, aml = _ml(odds, "home"), _ml(odds, "away")
    if hml is None or aml is None or hml == aml:
        return False
    ml_fav_home = hml < aml
    if fav == (home_abbr or "").upper():
        return not ml_fav_home
    if fav == (away_abbr or "").upper():
        return ml_fav_home
    return False


def _side_prices(odds, home_abbr, away_abbr):
    if not odds:
        return {k: None for k in ("home_ml", "away_ml", "home_spread_line", "home_spread_odds",
                                  "away_spread_line", "away_spread_odds")}
    flip = _odds_side_check(odds, home_abbr, away_abbr)
    h, a = ("away", "home") if flip else ("home", "away")
    return {
        "home_ml": _ml(odds, h), "away_ml": _ml(odds, a),
        "home_spread_line": _spread_close(odds, h)[0], "home_spread_odds": _spread_close(odds, h)[1],
        "away_spread_line": _spread_close(odds, a)[0], "away_spread_odds": _spread_close(odds, a)[1],
        "odds_flipped": flip,
    }


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
            "home_loc": ht.get("location"), "away_loc": at.get("location"),
            "home_short": ht.get("shortDisplayName"), "away_short": at.get("shortDisplayName"),
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
            # Each side's moneyline, spread line and price (DraftKings via ESPN),
            # swapped back when ESPN has left them on the wrong teams.
            **_side_prices(odds, ht.get("abbreviation"), at.get("abbreviation")),
            "line_source": odds.get("provider", {}).get("name") if odds else None,
            "notes": notes,
            "tournament": "Men's Basketball Championship" in notes,
        })
    df = pd.DataFrame(rows)
    if df.empty:
        return df
    df = df.drop_duplicates("id")
    df["date"] = pd.to_datetime(df["date"], utc=True, errors="coerce")
    df["et_date"] = df["date"].dt.tz_convert(ET).dt.date   # computed once, reused everywhere
    return df.sort_values("date").reset_index(drop=True)


@st.cache_data(ttl=30 * 60, show_spinner=False)
def load_season(season):
    """(games_df, failed_days). Cached as a whole for 30 min on top of the
    per-day caches, so tab switches don't re-parse a whole season."""
    events, failed = fetch_events(season_dates(season))
    return parse_events(events), failed


# ---- Model -----------------------------------------------------------------
@st.cache_data(ttl=30 * 60, show_spinner=False, max_entries=4)
def fit_ratings(games):
    """Ridge fit of points scored: pts = avg + off[team] - def[opp] ± hca/2.

    Returns (ratings_df, model) where model has avg points and home edge.
    A team's net rating is off + def = points better than an average D1 team
    on a neutral floor.

    Each team-game is one observation touching three parameters (scorer's
    offence, opponent's defence, home court), so the normal equations are
    summed straight into a (2n+1)^2 matrix instead of materialising the full
    design matrix, which would reach ~130 MB by March. Cached for 30 minutes
    alongside the season data it's fitted to.
    """
    done = games[games["completed"] & games["home_score"].notna()] if not games.empty else games
    if done is None or done.empty:
        return pd.DataFrame(), None

    ids = pd.unique(pd.concat([done["home_id"], done["away_id"]]))
    idx = {t: i for i, t in enumerate(ids)}
    n, p = len(ids), 2 * len(ids) + 1
    h = done["home_id"].map(idx).to_numpy()
    a = done["away_id"].map(idx).to_numpy()
    site = np.where(done["neutral"].to_numpy(dtype=bool), 0.0, 0.5)
    # Two observations per game: home scoring vs away defence, and vice versa.
    off_i = np.concatenate([h, a])                 # scorer's offence column
    def_i = np.concatenate([a, h]) + n             # opponent's defence column
    s = np.concatenate([site, -site])              # home-court column
    y = np.concatenate([done["home_score"].to_numpy(float), done["away_score"].to_numpy(float)])
    avg = y.mean()
    yc = y - avg

    xtx = np.zeros((p, p))
    np.add.at(xtx, (off_i, off_i), 1.0)
    np.add.at(xtx, (def_i, def_i), 1.0)
    np.add.at(xtx, (off_i, def_i), -1.0)
    np.add.at(xtx, (def_i, off_i), -1.0)
    np.add.at(xtx, (off_i, p - 1), s)
    np.add.at(xtx, (p - 1, off_i), s)
    np.add.at(xtx, (def_i, p - 1), -s)
    np.add.at(xtx, (p - 1, def_i), -s)
    xtx[p - 1, p - 1] += float((s * s).sum())
    xty = np.zeros(p)
    np.add.at(xty, off_i, yc)
    np.add.at(xty, def_i, -yc)
    xty[p - 1] = float((s * yc).sum())

    # Home court is pinned at HOME_COURT points. Fitted freely it came out near
    # 17-18 points early in the season: good teams mostly host very weak ones
    # (often non-D1), and the fit credited "beat a bad team at home" to home
    # court. A very stiff prior holds it at the standard value instead.
    reg = np.full(p, RIDGE); reg[-1] = 1e6
    prior = np.zeros(p); prior[-1] = HOME_COURT
    beta = np.linalg.solve(xtx + np.diag(reg), xty + reg * prior)
    off, dfn, hca = beta[:n], beta[n:2 * n], beta[-1]

    names = dict(zip(done["home_id"], done["home"])) | dict(zip(done["away_id"], done["away"]))
    rat = pd.DataFrame({"team_id": ids, "team": [names[t] for t in ids],
                        "off": off, "def": dfn})
    rat["net"] = rat["off"] + rat["def"]
    rat = rat.merge(team_records(done, rat), on="team_id", how="left")
    rat["rank"] = rat["net"].rank(ascending=False, method="min").astype(int)
    rat = rat.sort_values("net", ascending=False).reset_index(drop=True)
    # Plain lookup for project(), so it doesn't re-index the frame per game.
    by_id = {t: (float(o), float(d), int(gm)) for t, o, d, gm
             in zip(rat["team_id"], rat["off"], rat["def"], rat["games"])}
    return rat, {"avg": float(avg), "hca": float(hca), "by_id": by_id}


def team_records(done, rat):
    """W-L, ATS, O/U, close games, last 10 and strength of schedule per team.

    Built in one vectorised pass (one row per team-game, then a single
    groupby) rather than a Python function per team.
    """
    net = dict(zip(rat["team_id"], rat["off"] + rat["def"]))
    hs, as_ = done["home_score"].to_numpy(float), done["away_score"].to_numpy(float)
    spread_h = pd.to_numeric(done["home_spread"], errors="coerce").to_numpy(float)
    total = pd.to_numeric(done["total_line"], errors="coerce").to_numpy(float)
    L = pd.DataFrame({
        "team_id": np.concatenate([done["home_id"].to_numpy(), done["away_id"].to_numpy()]),
        "opp_id": np.concatenate([done["away_id"].to_numpy(), done["home_id"].to_numpy()]),
        "date": np.concatenate([done["date"].to_numpy(), done["date"].to_numpy()]),
        "pts": np.concatenate([hs, as_]), "opp": np.concatenate([as_, hs]),
        "spread": np.concatenate([spread_h, -spread_h]),
        "total_line": np.concatenate([total, total]),
    })
    L["margin"] = L["pts"] - L["opp"]
    L["win"] = L["pts"] > L["opp"]
    ats_m = L["margin"] + L["spread"]                  # NaN when there's no line
    L["ats_w"] = ats_m > 0
    L["ats_l"] = ats_m < 0
    L["ats_p"] = ats_m == 0
    L["fav"] = L["spread"] < 0
    tot = L["pts"] + L["opp"]
    L["over"] = tot > L["total_line"]
    L["under"] = tot < L["total_line"]
    L["close"] = L["margin"].abs() <= 5
    L["close_w"] = L["close"] & L["win"]
    L["fav_ats_w"] = L["fav"] & L["ats_w"]
    L["fav_ats_l"] = L["fav"] & L["ats_l"]
    L["dog_ats_w"] = ~L["fav"] & L["ats_w"]
    L["dog_ats_l"] = ~L["fav"] & L["ats_l"] & L["spread"].notna()
    L["opp_net"] = L["opp_id"].map(net).fillna(0.0)
    L = L.sort_values("date", kind="stable")

    g = L.groupby("team_id")
    out = g.agg(games=("win", "size"), wins=("win", "sum"), close_n=("close", "sum"),
                close_w=("close_w", "sum"), ats_w=("ats_w", "sum"), ats_l=("ats_l", "sum"),
                ats_p=("ats_p", "sum"), fav_ats_w=("fav_ats_w", "sum"), fav_ats_l=("fav_ats_l", "sum"),
                dog_ats_w=("dog_ats_w", "sum"), dog_ats_l=("dog_ats_l", "sum"),
                over=("over", "sum"), under=("under", "sum"),
                avg_margin=("margin", "mean"), sos=("opp_net", "mean"))
    last10 = L.groupby("team_id").tail(10).groupby("team_id").agg(
        last10_w=("win", "sum"), last10_n=("win", "size"))
    out = out.join(last10)
    out["losses"] = out["games"] - out["wins"]
    ints = ["games", "wins", "losses", "last10_w", "last10_n", "close_w", "close_n", "ats_w",
            "ats_l", "ats_p", "fav_ats_w", "fav_ats_l", "dog_ats_w", "dog_ats_l", "over", "under"]
    out[ints] = out[ints].astype(int)
    out["avg_margin"] = out["avg_margin"].round(1)
    out["sos"] = out["sos"].round(1)
    return out[ints[:5] + ints[5:] + ["avg_margin", "sos"]].reset_index()


def win_prob(margin):
    return 0.5 * (1 + erf(margin / (MARGIN_SD * sqrt(2))))


def project(game, ratings, model):
    """Projected home margin and total for one game row, or None if either
    team has no rating yet."""
    if ratings is None or ratings.empty or model is None:
        return None
    by_id = model.get("by_id")
    if by_id is None:
        r = ratings.set_index("team_id")
        by_id = {t: (row["off"], row["def"], row["games"]) for t, row in r.iterrows()}
    if game["home_id"] not in by_id or game["away_id"] not in by_id:
        return None
    (h_off, h_def, h_n), (a_off, a_def, a_n) = by_id[game["home_id"]], by_id[game["away_id"]]
    h = {"off": h_off, "def": h_def, "games": h_n}
    a = {"off": a_off, "def": a_def, "games": a_n}
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
