"""Real Bets: import a Juice Reel export and analyse the owner's real betting.

Juice Reel has no public API, so the link is its CSV export ("one row per bet
leg"; bet-level fields repeat on every leg). Upload it on the Profile tab:

  - signed in (Supabase): legs are upserted into `real_bets` (db/real_bets.sql),
    so re-uploading a newer export only adds what's new, and nothing is lost on
    redeploy. Row-level security keeps each account's bets private.
  - guest: kept for this browser session only.

This is real money, kept fully separate from Steel play-money bets. Nothing here
is invented: every number is computed from the rows in the export.
"""
import io

import altair as alt
import pandas as pd
import streamlit as st

import auth_store

TEAL, RED, GREY = "#0d9488", "#e10600", "#6b6e75"

# Columns the export must have. Anything missing means the format changed:
# refuse the file rather than misread it.
REQUIRED = [
    "juice_bet_id", "bet_leg_id", "sportsbook", "risk_amount", "bet_result",
    "amount_won_or_lost", "odds_american", "number_of_legs", "date_placed",
    "date_settled", "if_freeplay_then_amount_actually_at_risk", "is_odds_boosted",
    "clv_percent", "leg_type", "bet_on", "bet_on_spread_total_number",
    "leg_sport", "leg_league", "leg_vig", "leg_description", "event_start_date", "event_name",
]
SETTLED = {"Won", "Lost", "Push", "CashedOut"}

# Odds lanes from docs/cbb-moneyline-handoff.md
LANES = [
    ("Heavy fav (-301 or shorter)", -100000, -301),
    ("Fav -150 to -300", -300, -150),
    ("Coin flip -149 to +149", -149, 149),
    ("Dog +150 to +300", 150, 300),
    ("Long shot (+301 or longer)", 301, 100000),
]

MARKETS = {
    "Moneyline": "Moneyline", "Moneyline3Way": "Moneyline (3-way)", "Spread": "Spread",
    "GameOu": "Game total", "TeamOu": "Team total", "PlayerTotal": "Player prop",
    "PlayerProp": "Player prop", "Prop": "Prop", "GameProp": "Prop", "Future": "Future",
}


# ---- Parse -----------------------------------------------------------------
def parse_export(data):
    """Bytes/str of a Juice Reel CSV -> (legs_df, error)."""
    try:
        text = data.decode("utf-8-sig") if isinstance(data, bytes) else data
        legs = pd.read_csv(io.StringIO(text))
    except Exception as e:
        return None, f"Couldn't read that file as CSV ({e})."
    missing = [c for c in REQUIRED if c not in legs.columns]
    if missing:
        return None, ("This doesn't look like a Juice Reel export; missing columns: "
                      + ", ".join(missing))
    legs = legs[REQUIRED].copy()
    legs = legs.drop_duplicates("bet_leg_id")
    return legs, None


def bets_frame(legs):
    """One row per bet (parlays collapsed), with the fields analysis needs."""
    if legs is None or legs.empty:
        return pd.DataFrame()
    legs = legs.copy()
    for c in ("date_placed", "date_settled", "event_start_date"):
        legs[c] = pd.to_datetime(legs[c], utc=True, errors="coerce", format="mixed")
    first = legs.sort_values("bet_leg_id").groupby("juice_bet_id", as_index=False).first()
    leagues = legs.groupby("juice_bet_id")["leg_league"].agg(
        lambda s: s.dropna().iloc[0] if s.dropna().nunique() == 1 else "Multi-league")
    b = first.drop(columns=["leg_league"]).merge(leagues.rename("league"), on="juice_bet_id")
    b["league"] = b["league"].fillna("Unknown")
    b["parlay"] = b["number_of_legs"] > 1
    free = pd.to_numeric(b["if_freeplay_then_amount_actually_at_risk"], errors="coerce")
    # Free plays/bonus bets: only what was actually at risk counts as staked.
    b["staked"] = free.where(free.notna(), b["risk_amount"])
    b["profit"] = b["amount_won_or_lost"]
    b["market"] = b.apply(lambda r: "Parlay" if r["parlay"] else MARKETS.get(r["leg_type"], r["leg_type"]), axis=1)
    b["lane"] = b["odds_american"].map(_lane)
    b["month"] = b["date_placed"].dt.tz_convert("America/New_York").dt.strftime("%Y-%m")
    b["settled"] = b["bet_result"].isin(SETTLED)
    return b.sort_values("date_placed").reset_index(drop=True)


def _lane(odds):
    for name, lo, hi in LANES:
        if lo <= odds <= hi:
            return name
    return "Other"


# ---- Analyse ---------------------------------------------------------------
def summary(b):
    s = b[b["settled"]]
    staked, profit = s["staked"].sum(), s["profit"].sum()
    decided = s[s["bet_result"].isin(["Won", "Lost"])]
    clv = s["clv_percent"].dropna()
    return {
        "bets": len(s), "staked": staked, "profit": profit,
        "roi": profit / staked * 100 if staked else 0.0,
        "win_pct": (decided["bet_result"] == "Won").mean() * 100 if len(decided) else 0.0,
        "clv": clv.mean() * 100 if len(clv) else None, "clv_n": len(clv),
    }


def breakdown(b, by, min_bets=1):
    s = b[b["settled"]]
    if s.empty:
        return pd.DataFrame()
    g = s.groupby(by).agg(
        Bets=("juice_bet_id", "count"), Won=("bet_result", lambda x: (x == "Won").sum()),
        Lost=("bet_result", lambda x: (x == "Lost").sum()),
        Staked=("staked", "sum"), Profit=("profit", "sum"))
    g["ROI %"] = (g["Profit"] / g["Staked"].where(g["Staked"] > 0) * 100).round(1)
    g["Record"] = g["Won"].astype(int).astype(str) + "-" + g["Lost"].astype(int).astype(str)
    g["Staked"] = g["Staked"].round(2)
    g["Profit"] = g["Profit"].round(2)
    g = g[g["Bets"] >= min_bets].reset_index()
    return g[[*([by] if isinstance(by, str) else by), "Bets", "Record", "Staked", "Profit", "ROI %"]] \
        .sort_values("Bets", ascending=False)


# ---- Storage ---------------------------------------------------------------
def _db_row(r, uid):
    def clean(v):
        if v is None or (isinstance(v, float) and pd.isna(v)):
            return None
        if hasattr(v, "item"):
            return v.item()
        return v
    row = {c: clean(r[c]) for c in REQUIRED}
    row["user_id"] = uid
    return row


def save_to_account(legs):
    """Upsert legs into Supabase. Returns (saved_count, error)."""
    uid, c = auth_store.current_user_id(), auth_store.client()
    if not uid or c is None:
        return 0, "Not signed in."
    rows = [_db_row(r, uid) for r in legs.to_dict("records")]
    try:
        for i in range(0, len(rows), 500):
            c.table("real_bets").upsert(rows[i:i + 500], on_conflict="user_id,bet_leg_id").execute()
    except Exception as e:
        msg = str(e)
        if "real_bets" in msg and ("does not exist" in msg or "schema cache" in msg):
            return 0, "The `real_bets` table isn't set up yet. Run db/real_bets.sql in the Supabase SQL editor."
        return 0, f"Couldn't save to your account: {msg[:200]}"
    return len(rows), None


def load_from_account():
    uid, c = auth_store.current_user_id(), auth_store.client()
    if not uid or c is None:
        return None
    rows, start = [], 0
    try:
        while True:
            page = (c.table("real_bets").select(",".join(REQUIRED)).eq("user_id", uid)
                    .range(start, start + 999).execute().data) or []
            rows.extend(page)
            if len(page) < 1000:
                break
            start += 1000
    except Exception:
        return None
    return pd.DataFrame(rows, columns=REQUIRED) if rows else None


# ---- View ------------------------------------------------------------------
def _profit_chart(b):
    s = b[b["settled"]].copy()
    s["cum"] = s["profit"].cumsum()
    s["date"] = s["date_placed"].dt.tz_convert("America/New_York").dt.tz_localize(None)
    line = alt.Chart(s).mark_line(color=GREY).encode(
        x=alt.X("date:T", title=None), y=alt.Y("cum:Q", title="Cumulative profit ($)"),
        tooltip=[alt.Tooltip("date:T"), alt.Tooltip("cum:Q", format="$,.2f", title="Running profit")])
    zero = alt.Chart(pd.DataFrame({"y": [0]})).mark_rule(color=GREY, strokeDash=[4, 4]).encode(y="y:Q")
    return (zero + line).properties(height=260)


def _roi_bars(df, label):
    d = df.copy()
    d["tone"] = d["ROI %"].apply(lambda v: "Profit" if v >= 0 else "Loss")
    return alt.Chart(d).mark_bar().encode(
        y=alt.Y(f"{label}:N", sort="-x", title=None), x=alt.X("ROI %:Q"),
        color=alt.Color("tone:N", scale=alt.Scale(domain=["Profit", "Loss"], range=[TEAL, RED]), legend=None),
        tooltip=[label, "Bets", "Record", alt.Tooltip("Profit:Q", format="$,.2f"), "ROI %"],
    ).properties(height=max(120, 28 * len(d)))


def render_real_bets():
    st.caption("Your real-money betting, imported from Juice Reel. Separate from Steel. "
               "In Juice Reel, export your bet history as CSV, then upload it here. "
               "Re-upload a newer export any time: duplicates are skipped.")
    signed_in = auth_store.signed_in()
    if not signed_in:
        st.info("You're not signed in to a Fade Machine account, so an import lasts for this "
                "session only. Sign in on the Account tab to keep it.")

    up = st.file_uploader("Juice Reel export (.csv)", type=["csv"], key="rb_upload")
    if up is not None and st.session_state.get("rb_last_upload") != up.file_id:
        legs, err = parse_export(up.getvalue())
        if err:
            st.error(err)
        else:
            st.session_state["rb_last_upload"] = up.file_id
            if signed_in:
                n, err = save_to_account(legs)
                if err:
                    st.error(err)
                    st.session_state["rb_legs"] = legs
                else:
                    st.success(f"Saved {n:,} bet legs to your account.")
                    st.session_state.pop("_bet_keys_cache", None)   # refresh the Machine Model's 💵 markers
                    st.session_state.pop("rb_legs", None)
            else:
                st.session_state["rb_legs"] = legs
                st.success(f"Loaded {len(legs):,} bet legs for this session.")

    legs = st.session_state.get("rb_legs")
    if legs is None and signed_in:
        legs = load_from_account()
    if legs is None or legs.empty:
        return

    b = bets_frame(legs)
    if b.empty or not b["settled"].any():
        st.info("No settled bets in that export yet.")
        return

    lo, hi = b["date_placed"].min(), b["date_placed"].max()
    st.caption(f"{len(b):,} bets placed {lo:%b %-d, %Y} to {hi:%b %-d, %Y}")
    s = summary(b)
    m = st.columns(4)
    m[0].metric("Settled bets", f"{s['bets']:,}")
    m[1].metric("Profit", f"${s['profit']:,.2f}", f"{s['roi']:+.1f}% ROI")
    m[2].metric("Win rate", f"{s['win_pct']:.1f}%", "wins vs losses", delta_color="off")
    m[3].metric("Avg CLV", "—" if s["clv"] is None else f"{s['clv']:+.2f}%",
                f"on {s['clv_n']:,} bets", delta_color="off")
    st.altair_chart(_profit_chart(b), width="stretch")

    straight = b[~b["parlay"]]
    t1, t2, t3, t4, t5 = st.tabs(["🏀 CBB moneylines", "By league", "By bet type", "By odds lane", "More"])
    with t1:
        cbb = straight[straight["league"] == "CBB"]
        st.markdown("The checklist in CBB Value is built on these lanes. Straight bets only.")
        ml = breakdown(cbb[cbb["market"] == "Moneyline"], "lane")
        if ml.empty:
            st.caption("No CBB moneyline bets in this export.")
        else:
            st.dataframe(ml, hide_index=True, width="stretch")
            st.altair_chart(_roi_bars(ml, "lane"), width="stretch")
        st.markdown("**CBB by bet type**")
        st.dataframe(breakdown(cbb, "market"), hide_index=True, width="stretch")
    with t2:
        min_n = st.slider("Hide groups with fewer bets than", 1, 30, 10, key="rb_min_league")
        lg = breakdown(b, "league", min_n)
        st.dataframe(lg, hide_index=True, width="stretch")
        if not lg.empty:
            st.altair_chart(_roi_bars(lg, "league"), width="stretch")
    with t3:
        bt = breakdown(b, "market")
        st.dataframe(bt, hide_index=True, width="stretch")
        if not bt.empty:
            st.altair_chart(_roi_bars(bt, "market"), width="stretch")
    with t4:
        st.caption("Straight bets only, by the price you got.")
        lane = breakdown(straight, "lane")
        st.dataframe(lane, hide_index=True, width="stretch")
        if not lane.empty:
            st.altair_chart(_roi_bars(lane, "lane"), width="stretch")
    with t5:
        st.markdown("**By sportsbook**")
        st.dataframe(breakdown(b, "sportsbook"), hide_index=True, width="stretch")
        st.markdown("**By month**")
        st.dataframe(breakdown(b, "month").sort_values("month"), hide_index=True, width="stretch")
        st.markdown("**Odds boosts**")
        boost = b.assign(boost=b["is_odds_boosted"].map({True: "Boosted", False: "Regular"}))
        st.dataframe(breakdown(boost, "boost"), hide_index=True, width="stretch")
