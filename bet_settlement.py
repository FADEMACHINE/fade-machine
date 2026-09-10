"""Settle open Steel bets against real final scores.

Scores come from The Odds API's /scores endpoint, keyed by the same game id
the odds board stores on each bet, so a bet matches its game exactly rather
than by fuzzy team-name matching.

What can and cannot settle here:
  * Moneyline, Spread and Total settle from the final score alone.
  * Player props cannot. Grading "CeeDee Lamb Over 68.5 receiving yards" needs
    a box score, which this endpoint does not return, and prop bets are stored
    with a descriptive game string ("DAL vs TBD") rather than a real game id,
    so they can't even be matched to a game. They are deliberately left open
    and reported as needing a stats feed, rather than being quietly dropped or
    guessed at.
"""
from datetime import datetime, timezone

import requests
import streamlit as st

SCORES_URL = "https://api.the-odds-api.com/v4/sports/americanfootball_nfl/scores"
SCORES_TTL_SECONDS = 10 * 60   # games finish in real time; 10 min is responsive
SCORES_DAYS_FROM = 3           # how far back the endpoint reports finals

# Bets on markets outside this set need a player box score, not a game score.
SETTLEABLE_MARKETS = {"moneyline", "spread", "total"}


def _now_iso():
    return datetime.now(timezone.utc).isoformat()


@st.cache_data(ttl=SCORES_TTL_SECONDS, show_spinner=False)
def fetch_scores(api_key, days_from=SCORES_DAYS_FROM):
    """Recent NFL games with scores. Cached — settlement runs on every rerun."""
    resp = requests.get(
        SCORES_URL,
        params={"apiKey": api_key, "daysFrom": days_from},
        timeout=12,
    )
    resp.raise_for_status()
    return resp.json()


def scores_by_game_id(raw):
    """{game_id: {completed, away, home, away_score, home_score}}."""
    out = {}
    for g in raw or []:
        gid = g.get("id")
        if not gid:
            continue
        away, home = g.get("away_team"), g.get("home_team")
        pts = {}
        for s in g.get("scores") or []:
            try:
                pts[s.get("name")] = int(s.get("score"))
            except (TypeError, ValueError):
                continue
        out[gid] = {
            "completed": bool(g.get("completed")),
            "away": away,
            "home": home,
            "away_score": pts.get(away),
            "home_score": pts.get(home),
            "commence_time": g.get("commence_time"),
        }
    return out


def grade_bet(bet, game):
    """Grade one bet against a final score.

    Returns (status, note) where status is 'won' | 'lost' | 'push', or
    (None, reason) when the bet can't be graded from a game score.
    """
    market = (bet.get("market_type") or bet.get("market") or "").lower()
    if market not in SETTLEABLE_MARKETS:
        return None, f"{bet.get('market') or 'this market'} needs player stats"

    away_score, home_score = game.get("away_score"), game.get("home_score")
    if away_score is None or home_score is None:
        return None, "no final score reported"

    sel = (bet.get("selection") or "").strip()
    line = bet.get("line")

    if market == "total":
        if line is None:
            return None, "total bet has no line"
        combined = away_score + home_score
        if combined == line:
            return "push", f"total {combined:g} = line {line:g}"
        over = combined > line
        won = over if sel.lower() == "over" else not over
        return ("won" if won else "lost",
                f"total {combined:g} vs line {line:g}")

    # Moneyline and spread both resolve around which side the bet took.
    if sel == game.get("away"):
        own, opp = away_score, home_score
    elif sel == game.get("home"):
        own, opp = home_score, away_score
    else:
        return None, f"selection '{sel}' doesn't match either team"

    if market == "moneyline":
        if own == opp:
            return "push", f"tie {own}-{opp}"
        return ("won" if own > opp else "lost", f"final {own}-{opp}")

    # Spread: the bet's stored line is already signed for the side taken.
    if line is None:
        return None, "spread bet has no line"
    margin = (own + line) - opp
    if margin == 0:
        return "push", f"{own}{line:+g} vs {opp} — exact push"
    return ("won" if margin > 0 else "lost",
            f"{own}{line:+g} vs {opp}")


def steel_result_for(status, stake, profit):
    """Net Steel P/L for a graded bet.

    The stake was already deducted when the bet was placed, so this is P/L
    relative to that: a win nets the profit, a loss nets minus the stake, a
    push nets nothing.
    """
    if status == "won":
        return round(profit, 2)
    if status == "lost":
        return -round(stake, 2)
    return 0.0


def balance_credit_for(status, stake, profit):
    """Steel to return to the account balance on settlement."""
    if status == "won":
        return round(stake + profit, 2)
    if status == "push":
        return round(stake, 2)
    return 0.0
