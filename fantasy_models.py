"""Advanced Fantasy scoring models + season-long prop rankings for FADE MACHINE."""
import json
import os
import pandas as pd
import streamlit as st

SEASON_LONG_PATH = "season_long_futures.json"

# Stat columns for ranking (high → low) — season-long futures props
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

# Advanced scoring models (per unit of the season-long projection)
SCORING_MODELS = {
    "Half-PPR": {
        "pass_yds": 0.04, "pass_tds": 4.0, "pass_ints": -2.0,
        "rush_yds": 0.1, "rush_tds": 6.0,
        "rec_yds": 0.1, "receptions": 0.5, "rec_tds": 6.0,
    },
    "Full-PPR": {
        "pass_yds": 0.04, "pass_tds": 4.0, "pass_ints": -2.0,
        "rush_yds": 0.1, "rush_tds": 6.0,
        "rec_yds": 0.1, "receptions": 1.0, "rec_tds": 6.0,
    },
    "Standard (non-PPR)": {
        "pass_yds": 0.04, "pass_tds": 4.0, "pass_ints": -2.0,
        "rush_yds": 0.1, "rush_tds": 6.0,
        "rec_yds": 0.1, "receptions": 0.0, "rec_tds": 6.0,
    },
    "6-pt Pass TD": {
        "pass_yds": 0.04, "pass_tds": 6.0, "pass_ints": -2.0,
        "rush_yds": 0.1, "rush_tds": 6.0,
        "rec_yds": 0.1, "receptions": 0.5, "rec_tds": 6.0,
    },
    "TE Premium (1.5 PPR TE)": {
        "pass_yds": 0.04, "pass_tds": 4.0, "pass_ints": -2.0,
        "rush_yds": 0.1, "rush_tds": 6.0,
        "rec_yds": 0.1, "receptions": 0.5, "rec_tds": 6.0,
        "te_rec_bonus": 1.0,  # extra +1 per TE reception → 1.5 total
    },
    "Superflex / 2QB lean": {
        "pass_yds": 0.04, "pass_tds": 4.0, "pass_ints": -1.0,
        "rush_yds": 0.1, "rush_tds": 6.0,
        "rec_yds": 0.1, "receptions": 0.5, "rec_tds": 6.0,
        "qb_bonus": 1.15,  # multiply QB pts
    },
    "PPR + Bonus (100 yd)": {
        "pass_yds": 0.04, "pass_tds": 4.0, "pass_ints": -2.0,
        "rush_yds": 0.1, "rush_tds": 6.0,
        "rec_yds": 0.1, "receptions": 1.0, "rec_tds": 6.0,
        # yardage bonuses applied in calc
        "bonus_100_rush": 3.0,
        "bonus_100_rec": 3.0,
        "bonus_300_pass": 3.0,
    },
}


def load_season_long():
    """Load season-long futures JSON (repo root or local)."""
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
    """Add derived totals used for ranking."""
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
    """Project season fantasy points from season-long lines."""
    model = SCORING_MODELS.get(model_name, SCORING_MODELS["Half-PPR"])
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
    # TE premium
    if model.get("te_rec_bonus") and player.get("pos") == "TE":
        rec = player.get("receptions") or 0
        pts += float(rec) * float(model["te_rec_bonus"])
    # Superflex QB boost
    if model.get("qb_bonus") and player.get("pos") == "QB":
        pts *= float(model["qb_bonus"])
    # Yardage bonuses (PPR + Bonus model)
    if model.get("bonus_100_rush"):
        ry = player.get("rush_yds") or 0
        if float(ry) >= 1000:  # season scale approximation for ~100/game
            pts += float(model["bonus_100_rush"]) * 10  # rough season bonus
    if model.get("bonus_100_rec"):
        rcy = player.get("rec_yds") or 0
        if float(rcy) >= 1000:
            pts += float(model["bonus_100_rec"]) * 8
    if model.get("bonus_300_pass"):
        py = player.get("pass_yds") or 0
        if float(py) >= 3000:
            pts += float(model["bonus_300_pass"]) * 10
    return round(pts, 1)


def rank_by_stat(players, stat_key):
    """Rank players by a single season-long prop (high → low)."""
    rows = []
    for pl in players:
        val = pl.get(stat_key)
        if val is None:
            continue
        try:
            num = float(val)
        except (TypeError, ValueError):
            continue
        rows.append({
            "Player": pl.get("player"),
            "Team": pl.get("team", "—"),
            "Pos": pl.get("pos", "—"),
            "Line / Proj": num,
        })
    if not rows:
        return pd.DataFrame()
    df = pd.DataFrame(rows).sort_values("Line / Proj", ascending=False).reset_index(drop=True)
    df.insert(0, "Rank", range(1, len(df) + 1))
    return df


def season_model_rankings(players, model_name, pos_filter="All"):
    """Full season rankings under a scoring model."""
    rows = []
    for pl in players:
        if pos_filter != "All" and pl.get("pos") != pos_filter:
            continue
        pts = calc_season_fantasy_pts(pl, model_name)
        rows.append({
            "Player": pl.get("player"),
            "Team": pl.get("team", "—"),
            "Pos": pl.get("pos", "—"),
            "Proj Pts": pts,
            "Pass Yds": pl.get("pass_yds"),
            "Pass TD": pl.get("pass_tds"),
            "INT": pl.get("pass_ints"),
            "Cmp": pl.get("pass_cmp"),
            "Rush Yds": pl.get("rush_yds"),
            "Rush TD": pl.get("rush_tds"),
            "Rush Att": pl.get("rush_att"),
            "Rec": pl.get("receptions"),
            "Rec Yds": pl.get("rec_yds"),
            "Rec TD": pl.get("rec_tds"),
            "Targets": pl.get("targets"),
            "Total Yds": pl.get("total_yds"),
            "Total TD": pl.get("total_tds"),
        })
    if not rows:
        return pd.DataFrame()
    df = pd.DataFrame(rows).sort_values("Proj Pts", ascending=False).reset_index(drop=True)
    df.insert(0, "Rank", range(1, len(df) + 1))
    return df


def render_fantasy_tab(game_props=None):
    """Streamlit UI for advanced fantasy + season-long rankings."""
    st.header("🏆 Fantasy Rankings · Season-Long Futures")
    st.caption("Rank by season-long prop lines · Advanced scoring models · High → low")

    data = load_season_long()
    players = enrich_players(data.get("players", []))
    season = data.get("season", "2026")

    if not players:
        st.warning("season_long_futures.json not found or empty. Redeploy so the file is on the server.")
        return

    st.info(f"**{season} season-long futures** loaded · **{len(players)} players** · Lines are projection midpoints for ranking")

    sub_overall, sub_by_stat, sub_models, sub_game = st.tabs([
        "Season Overall", "Rank by Prop Stat", "Scoring Models", "Game Props (weekly)"
    ])

    # ---- Overall season rankings ----
    with sub_overall:
        model = st.selectbox("Scoring model", list(SCORING_MODELS.keys()), key="ff_overall_model")
        pos = st.selectbox("Position", ["All", "QB", "RB", "WR", "TE"], key="ff_overall_pos")
        df = season_model_rankings(players, model, pos)
        st.dataframe(df, use_container_width=True, hide_index=True)
        st.caption(f"Sorted by projected season fantasy points · {model}")

    # ---- Rank by individual prop (user request) ----
    with sub_by_stat:
        st.subheader("Rank players by season-long prop")
        st.caption("Receiving yards · Rushing yards · Catches · Passing yards · Touchdowns · Completions · Targets · more")
        stat_label = st.selectbox("Prop / Stat", list(STAT_RANK_OPTIONS.keys()), key="ff_stat_pick")
        stat_key = STAT_RANK_OPTIONS[stat_label]
        pos2 = st.selectbox("Position filter", ["All", "QB", "RB", "WR", "TE"], key="ff_stat_pos")

        filtered = players if pos2 == "All" else [p for p in players if p.get("pos") == pos2]
        df_stat = rank_by_stat(filtered, stat_key)
        if df_stat.empty:
            st.warning(f"No players with a **{stat_label}** line for this filter.")
        else:
            st.dataframe(df_stat, use_container_width=True, hide_index=True)
            top = df_stat.iloc[0]
            st.success(f"**#1 {stat_label}:** {top['Player']} ({top['Team']}) — {top['Line / Proj']}")

        # Quick multi-stat leaderboard strip
        st.markdown("---")
        st.markdown("**Leaders snapshot (season-long)**")
        cols = st.columns(4)
        highlights = [
            ("Receiving Yards", "rec_yds"),
            ("Rushing Yards", "rush_yds"),
            ("Passing Yards", "pass_yds"),
            ("Receptions", "receptions"),
            ("Total TDs", "total_tds"),
            ("Total Yards", "total_yds"),
            ("Targets", "targets"),
            ("Completions", "pass_cmp"),
        ]
        for i, (label, key) in enumerate(highlights):
            d = rank_by_stat(players, key)
            with cols[i % 4]:
                if not d.empty:
                    st.metric(label, f"{d.iloc[0]['Player']}", f"{d.iloc[0]['Line / Proj']}")

    # ---- Model comparison ----
    with sub_models:
        st.subheader("Advanced scoring model comparison")
        st.caption("Same season-long lines · different league settings")
        player_names = [p["player"] for p in players]
        pick = st.selectbox("Compare player", player_names, key="ff_compare_player")
        pl = next(p for p in players if p["player"] == pick)
        cmp_rows = []
        for mname in SCORING_MODELS:
            cmp_rows.append({
                "Model": mname,
                "Proj Pts": calc_season_fantasy_pts(pl, mname),
            })
        st.dataframe(pd.DataFrame(cmp_rows).sort_values("Proj Pts", ascending=False), use_container_width=True, hide_index=True)

        with st.expander("Model formulas"):
            st.markdown("""
            | Model | Notes |
            |-------|--------|
            | Half-PPR | 0.5 pts/catch (default most leagues) |
            | Full-PPR | 1.0 pts/catch |
            | Standard | 0 pts/catch |
            | 6-pt Pass TD | Pass TDs worth 6 (vs standard 4) |
            | TE Premium | TE catches +1.5 each |
            | Superflex | QB points × 1.15 |
            | PPR + Bonus | Full-PPR + yardage bonuses |
            """)

        st.markdown("---")
        st.subheader("Side-by-side model rankings (Top 15)")
        model_a = st.selectbox("Model A", list(SCORING_MODELS.keys()), index=0, key="ff_side_a")
        model_b = st.selectbox("Model B", list(SCORING_MODELS.keys()), index=1, key="ff_side_b")
        c1, c2 = st.columns(2)
        with c1:
            st.markdown(f"**{model_a}**")
            st.dataframe(season_model_rankings(players, model_a).head(15)[["Rank", "Player", "Pos", "Proj Pts"]],
                         use_container_width=True, hide_index=True)
        with c2:
            st.markdown(f"**{model_b}**")
            st.dataframe(season_model_rankings(players, model_b).head(15)[["Rank", "Player", "Pos", "Proj Pts"]],
                         use_container_width=True, hide_index=True)

    # ---- Optional weekly game props rankings ----
    with sub_game:
        st.subheader("Weekly / game props rankings")
        if not game_props:
            st.caption("No game-level props loaded. Season-long rankings above are the primary model.")
            return
        st.caption("Built from single-game O/U lines when available")
        by_p = {}
        for p in game_props:
            name = p.get("player", "?")
            by_p.setdefault(name, {"player": name, "team": p.get("team", ""), "pos": p.get("pos", ""), "props": []})
            by_p[name]["props"].append(p)
        half = SCORING_MODELS["Half-PPR"]
        rows = []
        for name, data in by_p.items():
            pts = 0.0
            for pr in data["props"]:
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
            rows.append({"Player": name, "Pos": data.get("pos") or "—", "Team": data.get("team") or "—", "Game Proj Pts": round(pts, 2)})
        if rows:
            gdf = pd.DataFrame(rows).sort_values("Game Proj Pts", ascending=False).reset_index(drop=True)
            gdf.insert(0, "Rank", range(1, len(gdf) + 1))
            st.dataframe(gdf, use_container_width=True, hide_index=True)
