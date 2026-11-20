"""Model Board: durable, graded records of the MACHINE MODEL's CBB picks.

Two records, both in Supabase and both locked at the price first seen:

  model_plays   every game that passes the checklist (CBB Value, default rules)
  machine_top3  the 3 best-edge games each day, chosen once at TOP3_LOCK_HOUR
                ET and never changed: the "MACHINE bets 1 unit on each" tally

Rows are written by the CBB Value view when someone opens it and by the daily
job (scripts/daily_model_check.py, run by GitHub Actions), whichever is first.
They're graded from ESPN final scores. Records are flat 1 unit per pick.

If the viewer is signed in and has imported Juice Reel bets (real_bets.py),
picks they actually bet are marked.
"""
import json
from datetime import datetime

import pandas as pd
import streamlit as st

import auth_store
import cbb_data as cd
from bet_slips import fmt_odds, implied_prob_to_american

RULES_VERSION = "v1"   # bump when cbb_value.RULES change in a way that matters
TOP3_LOCK_HOUR = 10    # ET: the day's Top 3 is chosen at the first check after this
TOP_N = 3
TABLES = ("model_plays", "machine_top3")


# ---- Storage ---------------------------------------------------------------
@st.cache_resource(show_spinner=False)
def _anon_client(url, key):
    """A client that never carries a user session, so writes don't depend on
    who happens to be viewing."""
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


def _missing_table(exc, table):
    msg = str(exc)
    return table in msg and ("does not exist" in msg or "schema cache" in msg)


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


def log_plays(plays, throttle=True):
    """Insert new checklist plays; existing ones stay exactly as first logged.
    Returns (rows_sent, error). In the app, each game is sent at most once an
    hour per session so reruns don't hammer the database."""
    c = _client()
    if c is None or not plays:
        return 0, None
    rows = [play_row(r) for r in plays]
    now = datetime.now().timestamp()
    seen = st.session_state.setdefault("board_logged", {}) if throttle else {}
    rows = [r for r in rows if now - seen.get(r["id"], 0) > 3600]
    if not rows:
        return 0, None
    try:
        c.table("model_plays").upsert(rows, on_conflict="id", ignore_duplicates=True,
                                      returning="minimal").execute()
    except Exception as e:
        return 0, ("The `model_plays` table isn't set up yet. Run db/model_plays.sql in Supabase."
                   if _missing_table(e, "model_plays") else f"Couldn't log plays: {str(e)[:160]}")
    for r in rows:
        seen[r["id"]] = now
    load_table.clear()
    return len(rows), None


# ---- Machine Top 3 ---------------------------------------------------------
def top3_candidates(results):
    """The day's best-edge games: the model's side must be in a price lane with
    positive model value. Ranked by checks passed, then value (pts)."""
    pool = [r for r in results
            if r["pick"]["in_lane"] and r["pick"]["value"] is not None and r["pick"]["value"] > 0]
    return sorted(pool, key=lambda r: (-r["pick"]["passed"], -r["pick"]["value"]))[:TOP_N]


def top3_due(day, now=None):
    now = now or datetime.now(cd.ET)
    return day == now.date() and now.hour >= TOP3_LOCK_HOUR


def select_top3(results, day, force=False):
    """Lock in the day's Top 3 once. Returns (picked_count, error).
    Does nothing if the day already has picks or it's before the lock hour."""
    c = _client()
    if c is None or (not force and not top3_due(day)):
        return 0, None
    flag = f"top3_done_{day.isoformat()}"
    if not force:
        try:
            if st.session_state.get(flag):
                return 0, None
        except Exception:
            pass
    try:
        have = (c.table("machine_top3").select("id").eq("game_date", day.isoformat())
                .limit(1).execute().data) or []
    except Exception as e:
        return 0, ("The `machine_top3` table isn't set up yet. Run db/machine_top3.sql in Supabase."
                   if _missing_table(e, "machine_top3") else f"Couldn't read Top 3: {str(e)[:160]}")
    if have:
        _mark(flag)
        return 0, None
    picks = top3_candidates(results)
    if not picks:
        return 0, None
    rows = []
    for rank, r in enumerate(picks, 1):
        row = play_row(r)
        row.update({"id": f"{day.isoformat()}-{rank}", "rank": rank, "game_date": day.isoformat()})
        rows.append(row)
    try:
        c.table("machine_top3").upsert(rows, on_conflict="id", ignore_duplicates=True,
                                       returning="minimal").execute()
    except Exception as e:
        return 0, f"Couldn't save Top 3: {str(e)[:160]}"
    _mark(flag)
    load_table.clear()
    return len(rows), None


def _mark(flag):
    try:
        st.session_state[flag] = True
    except Exception:
        pass   # outside Streamlit (the daily job) there's no session to remember it in


# ---- Load and grade --------------------------------------------------------
@st.cache_data(ttl=10 * 60, show_spinner=False)
def load_table(table):
    """(DataFrame, error) for one of TABLES."""
    c = _client()
    if c is None:
        return pd.DataFrame(), "no_supabase"
    rows, start = [], 0
    try:
        while True:
            page = (c.table(table).select("*").order("tip_time", desc=True)
                    .range(start, start + 999).execute().data) or []
            rows.extend(page)
            if len(page) < 1000:
                break
            start += 1000
    except Exception as e:
        return pd.DataFrame(), ("missing_table" if _missing_table(e, table) else str(e)[:160])
    df = pd.DataFrame(rows)
    if not df.empty:
        df["tip_time"] = pd.to_datetime(df["tip_time"], utc=True, errors="coerce")
        df["game_date"] = pd.to_datetime(df["game_date"]).dt.date
    return df, None


def grade_pending(board, table):
    """Grade pending picks whose games have finished, from ESPN finals."""
    c = _client()
    if c is None or board.empty:
        return 0
    now = pd.Timestamp.now(tz="UTC")
    due = board[(board["status"] == "pending") & (board["tip_time"] < now - pd.Timedelta(hours=2))]
    if due.empty:
        return 0
    events, _ = cd.fetch_events(sorted(set(due["game_date"])))
    finals = cd.parse_events(events)
    if finals.empty:
        return 0
    finals = finals.drop_duplicates("id").set_index(finals["id"].astype(str))
    graded = 0
    for p in due.to_dict("records"):
        if p["game_id"] not in finals.index:
            continue
        g = finals.loc[p["game_id"]]
        if not g["completed"]:
            if g["state"] != "post":
                continue
            status = "void"   # over without a result: postponed / cancelled
        else:
            mine, theirs = ((g["home_score"], g["away_score"]) if p["side"] == "home"
                            else (g["away_score"], g["home_score"]))
            status = "won" if mine > theirs else "lost" if mine < theirs else "push"
        try:
            (c.table(table).update({
                "status": status,
                "home_score": None if pd.isna(g["home_score"]) else int(g["home_score"]),
                "away_score": None if pd.isna(g["away_score"]) else int(g["away_score"]),
                "graded_at": now.isoformat(),
            }).eq("id", p["id"]).eq("status", "pending").execute())
            graded += 1
        except Exception:
            continue
    if graded:
        load_table.clear()
    return graded


def grade_all():
    """Grade both records. Returns {table: graded_count}."""
    out = {}
    for t in TABLES:
        df, err = load_table(t)
        out[t] = 0 if err else grade_pending(df, t)
    return out


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
ICON = {"won": "✅ Won", "lost": "❌ Lost", "push": "➖ Push", "void": "Void", "pending": "⏳ Pending"}


def _record(df):
    df = df.copy()
    df["units"] = [units(m, s) for m, s in zip(df["ml"], df["status"])]
    done = df[df["status"].isin(["won", "lost", "push"])]
    w, l, p = ((done["status"] == x).sum() for x in ("won", "lost", "push"))
    risked = int((done["status"] != "push").sum())
    u = float(done["units"].sum())
    return df, {"w": int(w), "l": int(l), "p": int(p), "units": u,
                "roi": u / risked * 100 if risked else 0.0,
                "pending": int((df["status"] == "pending").sum())}


def _metrics(rec):
    m = st.columns(4)
    m[0].metric("Record", f"{rec['w']}-{rec['l']}" + (f"-{rec['p']}" if rec["p"] else ""))
    m[1].metric("Units", f"{rec['units']:+.2f}")
    m[2].metric("ROI", f"{rec['roi']:+.1f}%")
    m[3].metric("Pending", rec["pending"])


def _rows(df, bet, with_rank=False):
    rows = []
    for r in df.to_dict("records"):
        score = ("" if r.get("home_score") is None or pd.isna(r.get("home_score")) else
                 f"{int(r['away_score'])}-{int(r['home_score'])}")
        row = {"Date": r["game_date"].strftime("%b %-d")}
        if with_rank:
            row["#"] = int(r["rank"])
        row.update({
            "Pick": f"{r['team']} {fmt_odds(int(r['ml']))}",
            "Matchup": f"{r['away']} {'vs' if r.get('neutral') else '@'} {r['home']}",
            "Model %": None if r.get("model_wp") is None else round(100 * float(r["model_wp"]), 1),
            "Value": None if r.get("value_pts") is None else round(float(r["value_pts"]), 1),
            "Checks": f"{r['checks_passed']}/{r['checks_scored']}",
            "Result": ICON.get(r["status"], r["status"]),
            "Score": score,
            "Units": round(r["units"], 2) if r["status"] != "pending" else None,
        })
        if bet:
            row["You bet it"] = "💵" if (r["game_date"], str(r["team"]).lower()) in bet else ""
        rows.append(row)
    return pd.DataFrame(rows)


def _load_or_explain(table, sql_file):
    df, err = load_table(table)
    if err == "no_supabase":
        st.info("Needs Supabase (`SUPABASE_URL`, `SUPABASE_ANON_KEY`) to keep a record.")
    elif err == "missing_table":
        st.info(f"This table isn't set up yet. Run `{sql_file}` in the Supabase SQL editor.")
    elif err:
        st.error(f"Couldn't load: {err}")
    else:
        if grade_pending(df, table):
            df, _ = load_table(table)
        return df
    return None


def render_board():
    bet = _bet_keys()

    st.markdown("### 🎯 MACHINE Top 3")
    st.caption(f"Every day at {TOP3_LOCK_HOUR} AM ET the MACHINE MODEL locks in its 3 best-edge "
               "games (in a price lane with model value, ranked by checks passed, then value) "
               "and bets 1 unit on each. The picks never change after that.")
    top = _load_or_explain("machine_top3", "db/machine_top3.sql")
    if top is not None:
        if top.empty:
            st.info("No Top 3 picks yet. The first set locks in at the next daily check.")
        else:
            top, rec = _record(top)
            _metrics(rec)
            today = datetime.now(cd.ET).date()
            todays = top[top["game_date"] == today].sort_values("rank")
            if not todays.empty:
                st.markdown("**Today's Top 3**")
                st.dataframe(_rows(todays, bet, with_rank=True), hide_index=True, width="stretch")
            by_day = top.groupby("game_date").agg(
                Picks=("id", "count"), Won=("status", lambda s: (s == "won").sum()),
                Lost=("status", lambda s: (s == "lost").sum()), Units=("units", "sum"))
            by_day = by_day.sort_index()
            by_day["Running units"] = by_day["Units"].cumsum().round(2)
            by_day["Units"] = by_day["Units"].round(2)
            by_day.index = [d.strftime("%b %-d") for d in by_day.index]
            with st.expander("Day by day"):
                st.dataframe(by_day.iloc[::-1], width="stretch")
            with st.expander("Every Top 3 pick"):
                st.dataframe(_rows(top.sort_values(["game_date", "rank"], ascending=[False, True]),
                                   bet, with_rank=True), hide_index=True, width="stretch")

    st.markdown("### 📋 Every checklist play")
    st.caption("Every game that met the checklist, logged at the price the model found it. "
               "Flat 1 unit per play.")
    board = _load_or_explain("model_plays", "db/model_plays.sql")
    if board is None:
        return
    if board.empty:
        st.info("No plays logged yet. They appear as soon as a game meets the checklist.")
        return
    board, rec = _record(board)
    _metrics(rec)
    st.dataframe(_rows(board, bet), hide_index=True, width="stretch")
    if not auth_store.signed_in():
        st.caption("Sign in and import your Juice Reel bets (Profile → Real Bets) to see which picks you bet.")

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
