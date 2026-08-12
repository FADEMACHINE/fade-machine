"""Content engine for FADE MACHINE.
Turns raw sample datasets (ATS trends, fantasy projections) into computed
insights: leaderboards, movers, and dynamically generated headlines — so
Trends/Headlines/the dashboard strip show real derived content instead of
static placeholder text.
"""
import json
import os
import pandas as pd

ATS_PATH = "ats_trends.json"


def load_ats_trends():
    paths = [ATS_PATH, os.path.join(os.path.dirname(__file__), ATS_PATH)]
    for p in paths:
        if os.path.exists(p):
            with open(p, "r") as f:
                return json.load(f)
    return {"seasons": [], "divisions": [], "records": []}


def ats_dataframe(data=None):
    data = data or load_ats_trends()
    df = pd.DataFrame(data.get("records", []))
    if df.empty:
        return df
    df["games"] = df["ats_wins"] + df["ats_losses"] + df["ats_pushes"]
    return df


def aggregate_ats(df, seasons=None, divisions=None, teams=None):
    """Aggregate ATS records across the selected seasons for each team."""
    if df.empty:
        return pd.DataFrame()
    filtered = df.copy()
    if seasons:
        filtered = filtered[filtered["season"].isin(seasons)]
    if divisions:
        filtered = filtered[filtered["division"].isin(divisions)]
    if teams:
        filtered = filtered[filtered["team"].isin(teams)]
    if filtered.empty:
        return pd.DataFrame()
    grouped = filtered.groupby(["team", "team_name", "division"], as_index=False).agg(
        ats_wins=("ats_wins", "sum"),
        ats_losses=("ats_losses", "sum"),
        ats_pushes=("ats_pushes", "sum"),
        home_ats_wins=("home_ats_wins", "sum"),
        home_ats_losses=("home_ats_losses", "sum"),
        away_ats_wins=("away_ats_wins", "sum"),
        away_ats_losses=("away_ats_losses", "sum"),
    )
    grouped["games"] = grouped["ats_wins"] + grouped["ats_losses"] + grouped["ats_pushes"]
    grouped["cover_pct"] = (grouped["ats_wins"] / grouped["games"].replace(0, 1)).round(3)
    grouped["record"] = grouped["ats_wins"].astype(str) + "-" + grouped["ats_losses"].astype(str) + "-" + grouped["ats_pushes"].astype(str)
    grouped = grouped.sort_values("cover_pct", ascending=False).reset_index(drop=True)
    return grouped


def best_worst_ats(agg_df, n=5):
    if agg_df.empty:
        return [], []
    best = agg_df.sort_values("cover_pct", ascending=False).head(n).to_dict("records")
    worst = agg_df.sort_values("cover_pct", ascending=True).head(n).to_dict("records")
    return best, worst


def fantasy_value_leaders(players, rank_moves, model_calc_fn, model_name="PPR", n=5):
    """Top risers by RANK_MOVES delta, and top overall projected scorers."""
    ranked = sorted(players, key=lambda p: model_calc_fn(p, model_name), reverse=True)
    for i, p in enumerate(ranked, 1):
        p["_overall_rank"] = i
    risers = [
        {**p, "_move": rank_moves.get(p["player"], 0)}
        for p in ranked if rank_moves.get(p["player"], 0) > 0
    ]
    risers.sort(key=lambda p: p["_move"], reverse=True)
    return ranked[:n], risers[:n]


def generate_headlines(agg_df, ranked_players, risers):
    """Build a feed of dynamic headline strings from computed data."""
    headlines = []
    if not agg_df.empty:
        top = agg_df.iloc[0]
        bottom = agg_df.iloc[-1]
        headlines.append(
            f"📈 {top['team_name']} lead the league ATS at {top['record']} "
            f"({top['cover_pct']*100:.0f}% cover rate) over the selected span."
        )
        headlines.append(
            f"📉 {bottom['team_name']} are the toughest fade at {bottom['record']} ATS "
            f"({bottom['cover_pct']*100:.0f}% cover rate) — bettors have struggled backing them."
        )
        home_leader = agg_df.assign(
            home_pct=(agg_df["home_ats_wins"] / (agg_df["home_ats_wins"] + agg_df["home_ats_losses"]).replace(0, 1))
        ).sort_values("home_pct", ascending=False).iloc[0]
        headlines.append(
            f"🏟️ {home_leader['team_name']} have been the sharpest home cover in the sample "
            f"at {home_leader['home_ats_wins']}-{home_leader['home_ats_losses']} at home ATS."
        )
    if ranked_players:
        top_p = ranked_players[0]
        headlines.append(
            f"🏆 {top_p['player']} ({top_p.get('pos','')}, {top_p.get('team','')}) projects as the "
            f"overall fantasy points leader at {top_p['_overall_rank'] if '_overall_rank' in top_p else 1} overall."
        )
    if risers:
        names = ", ".join(f"{r['player']} (▲{r['_move']})" for r in risers[:3])
        headlines.append(f"🚀 Biggest risers on the board this week: {names}.")
    return headlines
