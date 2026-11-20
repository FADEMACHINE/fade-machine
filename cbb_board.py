"""Model Board: a durable, graded record of every CBB Value PLAY.

When the CBB Value view finds a game that passes the checklist (with the
default rules, not whatever a viewer has set the slider to), the play is logged
to the Supabase `model_plays` table (db/model_plays.sql) with the moneyline at
that moment. It is never overwritten, so the record shows the price the model
actually found. Once the game is final, ESPN's score grades it.

Records are flat 1 unit per play at the logged price. If the viewer is signed in
and has imported Juice Reel bets (real_bets.py), plays they actually bet are
marked.
"""
import json
from datetime import datetime, timedelta

import pandas as pd
import streamlit as st

import auth_store
import cbb_data as cd
from bet_slips import fmt_odds, implied_prob_to_american

RULES_VERSION = "v1"   # bump when cbb_value.RULES change in a way that matters


# ---- Storage ---------------------------------------------------------------
@st.cache_resource(show_spinner=False)
def _anon_client(url, key):
    """A client that never carries a user session, so board writes don't
    depend on who happens to be viewing."""
    from supabase import create_client
    return create_client(url, key)


def _client():
    try:
        url, key = st.secrets.get("SUPABASE_URL"), st.secrets.get("SUPABASE_ANON_KEY")
    except Exception:
        return None
    if not (url and key):
        return None
    try:
        return _anon_client(url, key)
    except Exception:
        return None


def _missing_table(exc):
    msg = str(exc)
    return "model_plays" in msg and ("does not exist" in msg or "schema cache" in msg)


def play_row(r):
    g, p = r["game"], r["pick"]
    tip = g["date"]
    return {
        "id": f"{g['id']}-{p['side']}",
        "game_id": str(g["id"]),
        "game_date": tip.tz_convert(cd.ET).date().isoformat(),
        "tip_time": tip.isoformat(),
        "home": g["home"], "away": g["away"], "neutral": bool(g["neutral"]),
        "side": p["side"], "team": g[p["side"]], "ml": int(p["ml"]),
        "model_wp": None if p["wp"] is None else round(float(p["wp"]), 4),
        "fair_ml": None if p["wp"] is None else int(implied_prob_to_american(p["wp"])),
        "value_pts": None if p["value"] is None else round(float(p["value"]), 2),
        "checks_passed": int(p["passed"]), "checks_scored": int(p["scored"]),
        "checks": json.loads(json.dumps(p["checks"], default=str)),
        "rules_version": RULES_VERSION,
    }


def log_plays(plays):
    """Insert new plays; existing ones are left exactly as first logged.
    Returns (inserted_or_seen, error). Runs at most once per game per hour
    per server so reruns don't hammer the database."""
    c = _client()
    if c is None or not plays:
        return 0, None
    seen = st.session_state.setdefault("board_logged", {})
    now = datetime.now().timestamp()
    rows = [play_row(r) for r in plays]
    rows = [r for r in rows if now - seen.get(r["id"], 0) > 3600]
    if not rows:
        return 0, None
    try:
        c.table("model_plays").upsert(rows, on_conflict="id", ignore_duplicates=True,
                                      returning="minimal").execute()
    except Exception as e:
        return 0, ("The `model_plays` table isn't set up yet. Run db/model_plays.sql in Supabase."
                   if _missing_table(e) else f"Couldn't log plays: {str(e)[:160]}")
    for r in rows:
        seen[r["id"]] = now
    load_board.clear()
    return len(rows), None


@st.cache_data(ttl=10 * 60, show_spinner=False)
def load_board():
    """(DataFrame, error)."""
    c = _client()
    if c is None:
        return pd.DataFrame(), "no_supabase"
    rows, start = [], 0
    try:
        while True:
            page = (c.table("model_plays").select("*").order("tip_time", desc=True)
                    .range(start, start + 999).execute().data) or []
            rows.extend(page)
            if len(page) < 1000:
                break
            start += 1000
    except Exception as e:
        return pd.DataFrame(), ("missing_table" if _missing_table(e) else str(e)[:160])
    df = pd.DataFrame(rows)
    if not df.empty:
        df["tip_time"] = pd.to_datetime(df["tip_time"], utc=True, errors="coerce")
        df["game_date"] = pd.to_datetime(df["game_date"]).dt.date
    return df, None


# ---- Grading ---------------------------------------------------------------
def grade_pending(board):
    """Grade pending plays whose games have finished, from ESPN finals."""
    c = _client()
    if c is None or board.empty:
        return 0
    now = pd.Timestamp.now(tz="UTC")
    due = board[(board["status"] == "pending") & (board["tip_time"] < now - pd.Timedelta(hours=2))]
    if due.empty:
        return 0
    days = sorted(set(due["game_date"]))
    events, _ = cd.fetch_events(days)
    finals = cd.parse_events(events)
    if finals.empty:
        return 0
    finals = finals.set_index(finals["id"].astype(str))
    graded = 0
    for p in due.to_dict("records"):
        if p["game_id"] not in finals.index:
            continue
        g = finals.loc[p["game_id"]]
        if isinstance(g, pd.DataFrame):
            g = g.iloc[0]
        state = g["state"]
        if not g["completed"]:
            if state == "post":       # finished without a result: postponed/cancelled
                status = "void"
            else:
                continue
        else:
            mine, theirs = ((g["home_score"], g["away_score"]) if p["side"] == "home"
                            else (g["away_score"], g["home_score"]))
            status = "won" if mine > theirs else "lost" if mine < theirs else "push"
        try:
            (c.table("model_plays").update({
                "status": status,
                "home_score": None if pd.isna(g["home_score"]) else int(g["home_score"]),
                "away_score": None if pd.isna(g["away_score"]) else int(g["away_score"]),
                "graded_at": now.isoformat(),
            }).eq("id", p["id"]).eq("status", "pending").execute())
            graded += 1
        except Exception:
            continue
    if graded:
        load_board.clear()
    return graded


def units(ml, status):
    """Profit for a flat 1-unit stake."""
    if status == "won":
        return ml / 100 if ml > 0 else 100 / abs(ml)
    if status == "lost":
        return -1.0
    return 0.0


# ---- Real bets cross-check -------------------------------------------------
def _bet_keys():
    """{(ET date, team name lower)} of the signed-in user's Juice Reel
    moneyline bets, for the 'You bet it' marker."""
    if not auth_store.signed_in():
        return set()
    try:
        import real_bets
        legs = real_bets.load_from_account()
    except Exception:
        return set()
    if legs is None or legs.empty:
        return set()
    ml = legs[legs["leg_type"] == "Moneyline"].copy()
    ml["d"] = pd.to_datetime(ml["event_start_date"], utc=True, errors="coerce",
                             format="mixed").dt.tz_convert(cd.ET).dt.date
    return {(d, str(t).lower()) for d, t in zip(ml["d"], ml["bet_on"]) if pd.notna(d) and pd.notna(t)}


# ---- View ------------------------------------------------------------------
def render_board():
    st.caption("Every game that passed the FADE MACHINE checklist, logged at the price the model "
               "found it and graded from final scores. Flat 1 unit per play.")
    board, err = load_board()
    if err == "no_supabase":
        st.info("The Model Board needs Supabase (`SUPABASE_URL`, `SUPABASE_ANON_KEY`) to keep its record.")
        return
    if err == "missing_table":
        st.info("The Model Board table isn't set up yet. Run `db/model_plays.sql` in the Supabase SQL editor.")
        return
    if err:
        st.error(f"Couldn't load the board: {err}")
        return
    if board.empty:
        st.info("No plays logged yet. They appear here as soon as the CBB Value view finds one.")
        return
    if grade_pending(board):
        board, _ = load_board()

    board = board.copy()
    board["units"] = [units(m, s) for m, s in zip(board["ml"], board["status"])]
    done = board[board["status"].isin(["won", "lost", "push"])]
    w, l, p = ((done["status"] == x).sum() for x in ("won", "lost", "push"))
    risked = len(done[done["status"] != "push"])
    u = done["units"].sum()
    m = st.columns(4)
    m[0].metric("Record", f"{w}-{l}" + (f"-{p}" if p else ""))
    m[1].metric("Units", f"{u:+.2f}")
    m[2].metric("ROI", f"{(u / risked * 100) if risked else 0:+.1f}%")
    m[3].metric("Pending", int((board["status"] == "pending").sum()))

    bet = _bet_keys()
    icon = {"won": "✅ Won", "lost": "❌ Lost", "push": "➖ Push", "void": "Void", "pending": "⏳ Pending"}
    rows = []
    for r in board.to_dict("records"):
        score = ("" if r.get("home_score") is None or pd.isna(r.get("home_score")) else
                 f"{int(r['away_score'])}-{int(r['home_score'])}")
        rows.append({
            "Date": r["game_date"].strftime("%b %-d"),
            "Play": f"{r['team']} {fmt_odds(int(r['ml']))}",
            "Matchup": f"{r['away']} {'vs' if r.get('neutral') else '@'} {r['home']}",
            "Model %": None if r.get("model_wp") is None else round(100 * float(r["model_wp"]), 1),
            "Value": None if r.get("value_pts") is None else round(float(r["value_pts"]), 1),
            "Checks": f"{r['checks_passed']}/{r['checks_scored']}",
            "Result": icon.get(r["status"], r["status"]),
            "Score": score,
            "Units": round(r["units"], 2) if r["status"] != "pending" else None,
            "You bet it": "💵" if (r["game_date"], str(r["team"]).lower()) in bet else "",
        })
    df = pd.DataFrame(rows)
    if not bet:
        df = df.drop(columns=["You bet it"])
    st.dataframe(df, hide_index=True, width="stretch")
    if not auth_store.signed_in():
        st.caption("Sign in and import your Juice Reel bets (Profile → Real Bets) to see which plays you bet.")

    with st.expander("Why each play qualified"):
        for r in board.head(30).to_dict("records"):
            st.markdown(f"**{r['game_date']:%b %-d} · {r['team']} {fmt_odds(int(r['ml']))}** "
                        f"({r['checks_passed']}/{r['checks_scored']})")
            checks = r.get("checks") or []
            if isinstance(checks, str):
                checks = json.loads(checks)
            st.markdown("\n".join(
                f"- {'✅' if c.get('passed') is True else '❌' if c.get('passed') is False else '➖'} "
                f"{c.get('name')}: {c.get('detail')}" for c in checks))
