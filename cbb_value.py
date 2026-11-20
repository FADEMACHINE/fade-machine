"""CBB Value: the owner's moneyline checklist, scored on every game with a line.

Built from docs/cbb-moneyline-handoff.md. A year of the owner's own betting
history showed the edge was CBB moneylines in two price lanes, so this view
scores both sides of each game against the 10-point checklist and marks a PLAY
only when enough checks agree.

Sources (all free, no Odds API credits):
  - ESPN scoreboard (via cbb_data): schedule, venue, results, DraftKings moneylines
  - CollegeBasketballData.com API (CBBD_API_KEY): adjusted efficiency, pace, four factors
  - Bart Torvik static CSVs: the same stats, used when there's no key or CBBD fails
  - MACHINE ratings (cbb_data.fit_ratings): this season's results only

Every threshold lives in RULES below so it can be tuned without touching the
logic. Real data only: a check with no data is shown as "no data" and isn't
counted either way.
"""
import io
import re
from datetime import datetime, timedelta
from math import erf, sqrt

import pandas as pd
import requests
import streamlit as st

import auth_store
import cbb_board
import cbb_data as cd
from bet_slips import american_to_implied_prob, fmt_odds, implied_prob_to_american

TORVIK = "https://barttorvik.com"

LOOKAHEAD_DAYS = 1   # admins can scope this many days past today (Master Settings)
REQUIRE_CORE = True  # a board PLAY must be in a price lane with model value (Master Settings)

RULES = {
    "fav_lane": (-300, -150),      # favourite lane, inclusive
    "dog_lane": (150, 300),        # underdog lane, inclusive
    "min_value_pts": 3.0,          # model win% minus book implied%, in points
    "play_at": 4,                  # checks that must agree for a PLAY
    "ratings_settle": (12, 15),    # (month, day) ratings stop leaning on priors
    "rest_edge_days": 2,           # extra rest days that count as an edge
    "ft_edge": 3.0,                # FTs made per 100 FGA better than opponent
    "ft_min_pct": 70.0,            # and the team must shoot at least this FT%
    "reb_edge": 3.0,               # expected offensive-rebound % edge
    "to_edge": 2.0,                # expected turnover % edge
    "home_edge": 0.014,            # home court as a share of efficiency
    "margin_sd": cd.MARGIN_SD,     # spread of results around a projection
}

CONSOLATION = re.compile(r"consolation|third place|3rd place|fifth place|5th place|"
                         r"seventh place|7th place", re.I)

# ESPN location -> Torvik name, for D1 schools whose names don't normalise
# to the same thing. Non-D1 opponents are left unmatched on purpose.
ALIASES = {
    "App State": "Appalachian St.", "California Baptist": "Cal Baptist",
    "Grambling": "Grambling St.", "Kansas City": "UMKC",
    "Long Island University": "LIU", "McNeese": "McNeese St.",
    "Miami": "Miami FL", "Miami (OH)": "Miami OH", "Nicholls": "Nicholls St.",
    "SE Louisiana": "Southeastern Louisiana", "Sam Houston": "Sam Houston St.",
    "San José State": "San Jose St.", "Seattle U": "Seattle",
    "South Carolina Upstate": "USC Upstate",
    "Texas A&M-Corpus Christi": "Texas A&M Corpus Chris", "UAlbany": "Albany",
    "UConn": "Connecticut", "UIC": "Illinois Chicago", "UL Monroe": "Louisiana Monroe",
    "UT Martin": "Tennessee Martin", "Ole Miss": "Mississippi",
    "Omaha": "Nebraska Omaha", "Purdue Fort Wayne": "Purdue Fort Wayne",
    "Hawai'i": "Hawaii", "Loyola Maryland": "Loyola MD",
}


# ---- Torvik ----------------------------------------------------------------
def _norm(s):
    s = (s or "").lower().replace("&", "and").replace("saint ", "st ")
    s = s.replace("state", "st").replace("st.", "st")
    return re.sub(r"[^a-z0-9]", "", s)


def _read_torvik_csv(text):
    """Torvik's CSVs repeat rank column names ("Rk") and fffinal.csv rows carry
    4 unlabelled values past the header, which makes pandas shift every column.
    Read positionally instead: the first len(header) values line up with the
    header; anything after is ignored. Repeated names get a _2, _3 suffix."""
    import csv
    rows = list(csv.reader(io.StringIO(text)))
    if len(rows) < 2:
        return pd.DataFrame()
    header, seen = [], {}
    for h in rows[0]:
        seen[h] = seen.get(h, 0) + 1
        header.append(h if seen[h] == 1 else f"{h}_{seen[h]}")
    body = [r[:len(header)] for r in rows[1:] if len(r) >= len(header)]
    df = pd.DataFrame(body, columns=header)
    for c in df.columns:
        conv = pd.to_numeric(df[c], errors="coerce")
        if conv.notna().all():
            df[c] = conv
    return df


def _plausible(df, tolerance=0.0):
    """Guard against a silent format change: every stat must sit in a
    believable range for D1 (allowing `tolerance` share of stray outliers),
    or we refuse to use the data."""
    bounds = {"adjoe": (70, 140), "adjde": (70, 140), "adjt": (55, 85), "efg": (30, 70),
              "ftr": (5, 80), "orb": (5, 60), "orb_allowed": (5, 60), "to": (5, 35),
              "to_forced": (5, 35), "three_rate": (10, 75), "ft_pct": (40, 100)}
    for col, (lo, hi) in bounds.items():
        vals = pd.to_numeric(df[col], errors="coerce")
        bad = vals.isna() | ~vals.between(lo, hi)
        if bad.mean() > tolerance:
            return False
    return True


TORVIK_LAST_ERROR = {"msg": None}   # why the last load failed, for the daily job's log


def _torvik_text(path):
    resp = requests.get(f"{TORVIK}/{path}", timeout=30)
    body = resp.text
    if resp.status_code != 200 or body.lstrip().startswith("<"):
        snippet = " ".join(body[:160].split())
        raise ValueError(f"{path}: HTTP {resp.status_code}, "
                         f"{resp.headers.get('content-type', '?')}: {snippet!r}")
    return body


@st.cache_data(ttl=6 * 3600, show_spinner=False)
def load_torvik(season):
    """One row per D1 team with efficiency + four factors, or empty on failure.

    fffinal.csv's "DR%" is the offensive-rebound rate a team ALLOWS (lower is
    better: Torvik ranks it ascending), and "TO% Def." is the turnover rate it
    FORCES."""
    TORVIK_LAST_ERROR["msg"] = None
    try:
        res = _read_torvik_csv(_torvik_text(f"{season}_team_results.csv"))
        ff = _read_torvik_csv(_torvik_text(f"{season}_fffinal.csv"))
    except Exception as e:
        TORVIK_LAST_ERROR["msg"] = str(e)[:300]
        return pd.DataFrame()
    need_res = ["team", "conf", "record", "adjoe", "adjde", "barthag", "adjt"]
    need_ff = ["TeamName", "eFG%", "FTR", "FTR Def", "OR%", "DR%", "TO%", "TO% Def.", "3P rate", "ft%"]
    if any(c not in res.columns for c in need_res) or any(c not in ff.columns for c in need_ff):
        TORVIK_LAST_ERROR["msg"] = "Torvik CSV columns changed"
        return pd.DataFrame()   # Torvik changed its format: show nothing rather than misread it
    ff = ff[need_ff].rename(columns={
        "TeamName": "team", "eFG%": "efg", "FTR": "ftr", "FTR Def": "ftr_d", "OR%": "orb",
        "DR%": "orb_allowed", "TO%": "to", "TO% Def.": "to_forced", "3P rate": "three_rate", "ft%": "ft_pct"})
    df = res[need_res].merge(ff, on="team", how="inner")
    if len(df) < 300 or not _plausible(df):
        TORVIK_LAST_ERROR["msg"] = f"Torvik data failed sanity checks ({len(df)} teams)"
        return pd.DataFrame()
    df["key"] = df["team"].map(_norm)
    return df.drop_duplicates("key").set_index("key")


# ---- CollegeBasketballData.com (primary when a key is set) -----------------
CBBD = "https://api.collegebasketballdata.com"
CBBD_KEY = None   # the daily job sets this from its environment; the app uses st.secrets
# Free keys allow 1,000 calls a month and a full load is 3 calls, so the app
# caches for 12 hours and the team list for a week. See scripts/daily_model_check.py
# for the job's budget.


def _cbbd_key():
    if CBBD_KEY:
        return CBBD_KEY
    try:
        return st.secrets.get("CBBD_API_KEY")
    except Exception:
        return None


def _cbbd_get(path, key):
    resp = requests.get(f"{CBBD}/{path}", headers={"Authorization": f"Bearer {key}"}, timeout=40)
    if resp.status_code != 200:
        raise ValueError(f"CollegeBasketballData {path}: HTTP {resp.status_code} {resp.text[:120]!r}")
    return resp.json()


@st.cache_data(ttl=7 * 24 * 3600, show_spinner=False)
def _cbbd_teams(season, key):
    """{CBBD team id: ESPN team id} for D1 teams."""
    return {t["id"]: str(t["sourceId"]) for t in _cbbd_get(f"teams?season={season}", key)
            if t.get("sourceId")}


@st.cache_data(ttl=12 * 3600, show_spinner=False)
def _cbbd_frame(season, key):
    espn = _cbbd_teams(season, key)
    ratings = {r["teamId"]: r for r in _cbbd_get(f"ratings/adjusted?season={season}", key)}
    rows = []
    for r in _cbbd_get(f"stats/team/season?season={season}", key):
        tid = r.get("teamId")
        if tid not in espn or tid not in ratings:
            continue   # non-D1 opponents carry no ESPN D1 id or adjusted rating
        t, o = r.get("teamStats") or {}, r.get("opponentStats") or {}
        tf, of_ = t.get("fourFactors") or {}, o.get("fourFactors") or {}
        fga = (t.get("fieldGoals") or {}).get("attempted") or 0
        three_a = (t.get("threePointFieldGoals") or {}).get("attempted") or 0
        rows.append({
            "team": r.get("team"), "espn_id": espn[tid], "conf": r.get("conference"),
            "record": f"{r.get('wins', 0)}-{r.get('losses', 0)}",
            "adjoe": ratings[tid].get("offensiveRating"), "adjde": ratings[tid].get("defensiveRating"),
            "adjt": r.get("pace"),
            "efg": tf.get("effectiveFieldGoalPct"),
            "ftr": tf.get("freeThrowRate"), "ftr_d": of_.get("freeThrowRate"),
            "orb": tf.get("offensiveReboundPct"), "orb_allowed": of_.get("offensiveReboundPct"),
            # turnoverRatio is per possession (0.19); Torvik-style TO% is a percent
            "to": None if tf.get("turnoverRatio") is None else tf["turnoverRatio"] * 100,
            "to_forced": None if of_.get("turnoverRatio") is None else of_["turnoverRatio"] * 100,
            "three_rate": three_a / fga * 100 if fga else None,
            "ft_pct": (t.get("freeThrows") or {}).get("pct"),
        })
    return pd.DataFrame(rows)


STATS_SOURCES = {"cbbd": "CollegeBasketballData.com", "torvik": "Bart Torvik"}


def load_team_stats(season):
    """(stats_df, source_key). CollegeBasketballData.com when a key is set,
    otherwise (or if it fails) Bart Torvik. Empty frame if neither loads;
    STATS_LAST_ERROR says why."""
    errors = []
    key = _cbbd_key()
    if key:
        try:
            df = _cbbd_frame(season, key)
            if len(df) >= 300 and _plausible(df, tolerance=0.05):
                df["key"] = df["team"].map(_norm)
                STATS_LAST_ERROR["msg"] = None
                return df.drop_duplicates("espn_id").set_index("key"), "cbbd"
            errors.append(f"CollegeBasketballData failed sanity checks ({len(df)} teams)")
        except Exception as e:
            errors.append(str(e)[:200])
    else:
        errors.append("no CBBD_API_KEY set")
    tv = load_torvik(season)
    if not tv.empty:
        STATS_LAST_ERROR["msg"] = None
        return tv, "torvik"
    errors.append(f"Torvik: {TORVIK_LAST_ERROR['msg']}")
    STATS_LAST_ERROR["msg"] = "; ".join(errors)
    return pd.DataFrame(), None


STATS_LAST_ERROR = {"msg": None}


def team_row(tv, g, side):
    """A team's stats row: exact ESPN id when the source has it, else by name."""
    if tv.empty:
        return None
    if "espn_id" in tv.columns:
        hit = tv[tv["espn_id"] == str(g[f"{side}_id"])]
        if not hit.empty:
            return hit.iloc[0]
    return torvik_row(tv, g[f"{side}_loc"], g[f"{side}_short"])


def torvik_row(tv, location, short):
    if tv.empty:
        return None
    for name in (ALIASES.get(location), location, short):
        if name and _norm(name) in tv.index:
            return tv.loc[_norm(name)]
    return None


def torvik_projection(home, away, neutral, tv):
    """Points, margin and home win% from adjusted efficiency and tempo."""
    avg_eff, avg_t = tv["adjoe"].mean(), tv["adjt"].mean()
    tempo = home["adjt"] * away["adjt"] / avg_t
    hca = 0.0 if neutral else RULES["home_edge"]
    home_ppp = home["adjoe"] * away["adjde"] / avg_eff * (1 + hca)
    away_ppp = away["adjoe"] * home["adjde"] / avg_eff * (1 - hca)
    hp, ap = home_ppp * tempo / 100, away_ppp * tempo / 100
    margin = hp - ap
    return {"home_pts": hp, "away_pts": ap, "margin": margin,
            "home_wp": 0.5 * (1 + erf(margin / (RULES["margin_sd"] * sqrt(2))))}


# ---- Schedule context from this season's ESPN results ----------------------
def _et_date(ts):
    return ts.tz_convert(cd.ET).date()


def schedule_context(season_games, team_id, game_day):
    """Rest days, back-to-back / 3-in-4, and letdown spot for one team.
    Uses the et_date column parse_events computes once, instead of converting
    every game's timestamp again for each team."""
    if season_games is None or season_games.empty:
        return None
    sg = season_games
    if "et_date" not in sg.columns:
        sg = sg.assign(et_date=sg["date"].dt.tz_convert(cd.ET).dt.date)
    mine = sg[((sg["home_id"] == team_id) | (sg["away_id"] == team_id))
              & sg["completed"] & (sg["et_date"] < game_day)]
    if mine.empty:
        return {"rest": None, "b2b": False, "three_in_four": False, "letdown": False, "last": None}
    days = mine["et_date"]
    rest = (game_day - days.max()).days
    recent = int((days >= game_day - timedelta(days=3)).sum())
    last = mine.iloc[-1]
    home = last["home_id"] == team_id
    won = (last["home_score"] > last["away_score"]) == home
    opp_rank = last["away_rank"] if home else last["home_rank"]
    beat_ranked = bool(won and opp_rank and opp_rank <= 25)
    opp_name = last["away"] if home else last["home"]
    return {"rest": rest, "b2b": rest == 1, "three_in_four": recent >= 2,
            "letdown": beat_ranked, "last": f"{'beat' if won else 'lost to'} {opp_name}"}


# ---- Checklist -------------------------------------------------------------
def _check(name, passed, detail):
    """passed: True / False, or None when there's no data to judge."""
    return {"name": name, "passed": passed, "detail": detail}


def score_side(side, g, tv_rows, tv_proj, machine_wp, ctx, tv, game_day):
    """All ten checks for betting `side` ('home'/'away') on its moneyline."""
    other = "away" if side == "home" else "home"
    ml = int(g[f"{side}_ml"])
    me, opp = tv_rows[side], tv_rows[other]
    checks = []

    # 1. Price lane
    lo, hi = RULES["fav_lane"]; dlo, dhi = RULES["dog_lane"]
    in_lane = lo <= ml <= hi or dlo <= ml <= dhi
    checks.append(_check("Price lane", in_lane,
                         f"{fmt_odds(ml)} is {'in' if in_lane else 'outside'} the "
                         f"{fmt_odds(lo)}..{fmt_odds(hi)} / {fmt_odds(dlo)}..{fmt_odds(dhi)} lanes"))

    # 2. Model value
    implied = american_to_implied_prob(ml)
    wp = None if tv_proj is None else (tv_proj["home_wp"] if side == "home" else 1 - tv_proj["home_wp"])
    if wp is None:
        checks.append(_check("Model value", None, "No efficiency rating for one of the teams"))
        value = None
    else:
        value = 100 * (wp - implied)
        checks.append(_check("Model value", value >= RULES["min_value_pts"],
                             f"Model {100 * wp:.1f}% (fair {fmt_odds(implied_prob_to_american(wp))}) vs "
                             f"book {100 * implied:.1f}% ({fmt_odds(ml)}): {value:+.1f} pts"))

    # 3. Roster continuity
    checks.append(_check("Roster continuity", None,
                         "Returning-minutes data isn't wired in yet, so this isn't scored"))

    # 4. Schedule / fatigue
    mc, oc = ctx[side], ctx[other]
    if mc is None or oc is None or mc["rest"] is None or oc["rest"] is None:
        checks.append(_check("Schedule / fatigue", None, "Not enough games played to judge rest"))
    else:
        tired = lambda c: c["b2b"] or c["three_in_four"]
        passed = (tired(oc) and not tired(mc)) or (
            not tired(mc) and mc["rest"] - oc["rest"] >= RULES["rest_edge_days"])
        tag = lambda c: f"{c['rest']}d rest" + (" (back-to-back)" if c["b2b"] else "") + (
            " (3rd game in 4 days)" if c["three_in_four"] else "")
        checks.append(_check("Schedule / fatigue", passed,
                             f"Pick {tag(mc)} vs opponent {tag(oc)}. Travel and time zones not modelled."))

    # 5. Motivation
    if CONSOLATION.search(g.get("notes") or ""):
        checks.append(_check("Motivation", False, f"Consolation game ({g['notes']})"))
    elif mc is None or oc is None or mc["last"] is None or oc["last"] is None:
        checks.append(_check("Motivation", None, "Not enough games played to judge"))
    else:
        passed = oc["letdown"] and not mc["letdown"]
        why = ("Opponent is in a letdown spot after a ranked win" if passed else
               "Pick is in a letdown spot after a ranked win" if mc["letdown"] else "No letdown or consolation angle")
        checks.append(_check("Motivation", passed, f"{why}. Pick last: {mc['last']}; opponent last: {oc['last']}"))

    if me is None or opp is None:
        for n in ("Free throws", "Rebounding", "Guards / turnovers", "Shooting profile"):
            checks.append(_check(n, None, "No team stats for one of the teams"))
    else:
        # 6. Free throws: FTs made per 100 FGA = FT rate x FT%
        my_ft, op_ft = me["ftr"] * me["ft_pct"] / 100, opp["ftr"] * opp["ft_pct"] / 100
        checks.append(_check("Free throws",
                             my_ft - op_ft >= RULES["ft_edge"] and me["ft_pct"] >= RULES["ft_min_pct"],
                             f"FTM per 100 FGA {my_ft:.1f} vs {op_ft:.1f}; FT% {me['ft_pct']:.1f} vs {opp['ft_pct']:.1f}"))
        # 7. Rebounding: expected OR% = avg of own OR% and opponent's OR% allowed
        my_or = (me["orb"] + opp["orb_allowed"]) / 2
        op_or = (opp["orb"] + me["orb_allowed"]) / 2
        checks.append(_check("Rebounding", my_or - op_or >= RULES["reb_edge"],
                             f"Expected offensive rebound % {my_or:.1f} vs {op_or:.1f}"))
        # 8. Turnovers: expected TO% = avg of own TO% and what the opponent forces
        my_to = (me["to"] + opp["to_forced"]) / 2
        op_to = (opp["to"] + me["to_forced"]) / 2
        checks.append(_check("Guards / turnovers", op_to - my_to >= RULES["to_edge"],
                             f"Expected turnover % {my_to:.1f} vs opponent {op_to:.1f}"))
        # 9. Shooting profile: favourites want steady interior scoring, dogs want 3PT variance
        median, upper = tv["three_rate"].median(), tv["three_rate"].quantile(2 / 3)
        if ml < 0:
            passed = me["three_rate"] <= median
            why = f"Favourite takes {me['three_rate']:.1f}% of shots from 3 (D1 median {median:.1f}%): " + (
                "steadier inside scoring" if passed else "relies on the 3, more variance")
        else:
            passed = me["three_rate"] >= upper
            why = f"Underdog takes {me['three_rate']:.1f}% of shots from 3 (top third starts at {upper:.1f}%): " + (
                "enough variance to pull the upset" if passed else "not enough 3PT variance")
        checks.append(_check("Shooting profile", passed, why))

    # 10. Ratings lag: efficiency ratings are noisy / prior-driven until mid-December
    m, d = RULES["ratings_settle"]
    settled = game_day.month < 8 or (game_day.month, game_day.day) >= (m, d)
    if settled:
        checks.append(_check("Ratings lag", True, "Past mid-December: ratings are driven by this season"))
    elif machine_wp is None:
        checks.append(_check("Ratings lag", False, "Before mid-December and no season-only rating to confirm"))
    else:
        mwp = machine_wp if side == "home" else 1 - machine_wp
        passed = mwp > implied
        checks.append(_check("Ratings lag", passed,
                             f"Before mid-December: season-only MACHINE rating gives {100 * mwp:.1f}% vs book "
                             f"{100 * implied:.1f}%, {'confirming' if passed else 'not confirming'} the value"))

    passed = sum(1 for c in checks if c["passed"] is True)
    scored = sum(1 for c in checks if c["passed"] is not None)
    return {"side": side, "ml": ml, "wp": wp, "value": value, "checks": checks,
            "passed": passed, "scored": scored, "in_lane": in_lane}


def evaluate_day(day_games, season_games, tv, ratings, model):
    """One result per game that has both moneylines: the better-scoring side."""
    out = []
    for g in day_games.to_dict("records"):
        if g["home_ml"] is None or g["away_ml"] is None or pd.isna(g["home_ml"]) or pd.isna(g["away_ml"]):
            continue
        if g["completed"] or g["state"] != "pre":
            continue   # only games that haven't tipped: in-game prices aren't pregame lines
        game_day = _et_date(g["date"])
        rows = {"home": team_row(tv, g, "home"), "away": team_row(tv, g, "away")}
        proj = (torvik_projection(rows["home"], rows["away"], g["neutral"], tv)
                if rows["home"] is not None and rows["away"] is not None else None)
        mp = cd.project(g, ratings, model) if ratings is not None and not ratings.empty else None
        ctx = {s: schedule_context(season_games, g[f"{s}_id"], game_day) for s in ("home", "away")}
        sides = [score_side(s, g, rows, proj, mp["home_wp"] if mp else None, ctx, tv, game_day)
                 for s in ("home", "away")]
        best = max(sides, key=lambda r: (r["passed"], r["value"] if r["value"] is not None else -99))
        out.append({"game": g, "pick": best, "proj": proj, "matched": all(v is not None for v in rows.values())})
    return out


def is_play(pick, require_core, need=None):
    need = RULES["play_at"] if need is None else need
    core_ok = pick["in_lane"] and pick["value"] is not None and pick["value"] >= RULES["min_value_pts"]
    return pick["passed"] >= need and (core_ok or not require_core)


# ---- View ------------------------------------------------------------------
def render_value(season_games, ratings, model):
    tv, source = load_team_stats(cd.season_for())
    if tv.empty:
        st.info("Team stats aren't reachable right now (CollegeBasketballData.com or Bart Torvik), "
                "so games can't be scored. Nothing is shown rather than guessed numbers.")
        return
    st.caption("Scores both sides of every game on your 10-point moneyline checklist. "
               f"Lines: DraftKings via ESPN. Stats: {STATS_SOURCES[source]}. Read-only analytics.")

    c = st.columns(3)
    today = datetime.now(cd.ET).date()
    # Looking ahead at tomorrow's lines is an admin-only tool (Machine Model page).
    max_day = today + timedelta(days=LOOKAHEAD_DAYS) if auth_store.is_admin() else today
    day = c[0].date_input("Games on", value=today, max_value=max_day, key="cbbv_day")
    need = c[1].slider("Checks needed to play", 3, 8, RULES["play_at"], key="cbbv_need")
    require_core = c[2].checkbox("Require price lane + model value", value=REQUIRE_CORE, key="cbbv_core",
                                 help="Your history says the edge is the price lane. Keep this on to only "
                                      "play games in a lane with real model value.")

    events, failed = cd.fetch_events([day])
    day_games = cd.parse_events(events)
    if day_games.empty:
        st.info("No D1 games found for that date." if not failed else "ESPN didn't load. Try again shortly.")
        return
    results = evaluate_day(day_games, season_games, tv, ratings, model)
    if not results:
        st.info("No upcoming games with moneylines posted for that date yet.")
        return

    plays = [r for r in results if is_play(r["pick"], require_core, need)]
    # The Model Board logs with the default rules only, so a viewer moving the
    # slider can't add or hide plays from the public record.
    board_plays = [r for r in results if is_play(r["pick"], REQUIRE_CORE, RULES["play_at"])]
    if board_plays and day == today:   # the public record only ever logs today's games
        _, board_err = cbb_board.log_plays(board_plays)
        if board_err:
            st.caption(f"⚠️ {board_err}")
    # Backup for the daily job: lock today's Top 3 if it hasn't been yet.
    _, top_err = cbb_board.select_top3(results, day) if day == today else (0, None)
    if top_err:
        st.caption(f"⚠️ {top_err}")
    st.markdown(f"**{len(plays)} PLAY** of {len(results)} games with lines")
    only = st.checkbox("Show plays only", value=bool(plays), key="cbbv_only")

    rows = []
    for r in results:
        g, p = r["game"], r["pick"]
        team = g[p["side"]]
        rows.append({
            "Verdict": "✅ PLAY" if is_play(p, require_core, need) else "PASS",
            "Tip (ET)": g["date"].tz_convert(cd.ET).strftime("%-I:%M %p"),
            "Matchup": f"{g['away']} {'vs' if g['neutral'] else '@'} {g['home']}",
            "Side": team,
            "ML": fmt_odds(p["ml"]),
            "Model win %": None if p["wp"] is None else round(100 * p["wp"], 1),
            "Fair": "" if p["wp"] is None else fmt_odds(implied_prob_to_american(p["wp"])),
            "Value (pts)": None if p["value"] is None else round(p["value"], 1),
            "Checks": f"{p['passed']}/{p['scored']}",
            "Flags": "Neutral site" if g["neutral"] else "",
        })
    df = pd.DataFrame(rows)
    if only:
        df = df[df["Verdict"] == "✅ PLAY"]
    st.dataframe(df, hide_index=True, width="stretch")

    st.markdown("#### Checklist by game")
    for r in results:
        g, p = r["game"], r["pick"]
        if only and not is_play(p, require_core, need):
            continue
        label = (f"{'✅' if is_play(p, require_core, need) else '·'} {g[p['side']]} {fmt_odds(p['ml'])} "
                 f"— {p['passed']}/{p['scored']} checks")
        with st.expander(label):
            if g["neutral"]:
                st.caption("⚠️ Neutral site. Check it isn't near one team's campus.")
            if not r["matched"]:
                st.caption("One team isn't in the D1 stats list, so stat checks are skipped.")
            for ch in p["checks"]:
                icon = "✅" if ch["passed"] is True else "❌" if ch["passed"] is False else "➖"
                st.markdown(f"{icon} **{ch['name']}**: {ch['detail']}")

    with st.expander("The MACHINE MODEL checklist"):
        render_checklist(need)


def checklist_rows():
    """The checklist as (check, what it takes to pass), built from RULES so the
    page always matches what the model actually does."""
    lo, hi = RULES["fav_lane"]; dlo, dhi = RULES["dog_lane"]
    m, d = RULES["ratings_settle"]
    return [
        ("Price lane", f"Moneyline between {fmt_odds(lo)} and {fmt_odds(hi)}, or {fmt_odds(dlo)} and {fmt_odds(dhi)}"),
        ("Model value", f"Model win % beats the book's implied win % by {RULES['min_value_pts']:g}+ points "
                        "(adjusted offensive/defensive efficiency and pace)"),
        ("Roster continuity", "Returning minutes. Not scored yet: no free data source"),
        ("Schedule / fatigue", f"Opponent on a back-to-back or 3rd game in 4 days while we're not, or "
                               f"{RULES['rest_edge_days']}+ more days of rest"),
        ("Motivation", "Opponent in a letdown spot after beating a ranked team. Consolation games never pass"),
        ("Free throws", f"{RULES['ft_edge']:g}+ more free throws made per 100 shots, shooting {RULES['ft_min_pct']:g}%+ at the line"),
        ("Rebounding", f"{RULES['reb_edge']:g}+ point edge in expected offensive rebound %"),
        ("Guards / turnovers", f"{RULES['to_edge']:g}+ point edge in expected turnover %"),
        ("Shooting profile", "Favourites: take fewer 3s than the D1 median (steadier). "
                             "Underdogs: top third in 3-point rate (upset variance)"),
        ("Ratings lag", f"After {datetime(2000, m, d):%B %-d} passes automatically. Before that, the "
                        "season-only MACHINE rating must also show value"),
    ]


def render_checklist(need=None):
    need = RULES["play_at"] if need is None else need
    rows = checklist_rows()
    st.markdown("| # | Check | To pass |\n|---|---|---|\n" + "\n".join(
        f"| {i} | **{name}** | {rule} |" for i, (name, rule) in enumerate(rows, 1)))
    st.markdown(f"**A game qualifies for the MACHINE MODEL when {need}+ checks pass, including "
                "the price lane and model value.** Neutral sites are flagged for a closer look but "
                "not scored. Stats: CollegeBasketballData.com (Bart Torvik as backup). "
                "Lines: DraftKings via ESPN.")


def lookahead(season_games, ratings, model, days=None):
    """Score the next `days` days' games that already have moneylines.
    Read-only: nothing is logged to the public board. Returns
    ([(date, results, plays, top3_candidates, games_on_date)], stats_source)."""
    days = LOOKAHEAD_DAYS if days is None else days
    tv, source = load_team_stats(cd.season_for())
    if tv.empty or days < 1:
        return [], source
    out = []
    today = datetime.now(cd.ET).date()
    for i in range(1, days + 1):
        d = today + timedelta(days=i)
        events, _ = cd.fetch_events([d])
        day_games = cd.parse_events(events)
        results = evaluate_day(day_games, season_games, tv, ratings, model) if not day_games.empty else []
        plays = [r for r in results if is_play(r["pick"], REQUIRE_CORE, RULES["play_at"])]
        out.append((d, results, plays, cbb_board.top3_candidates(results), len(day_games)))
    return out, source
