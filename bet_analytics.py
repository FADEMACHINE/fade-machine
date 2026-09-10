"""Bet history bank + trend analysis for the Profile tab.

Reads the SQLite ledger (bet_store) rather than the JSON account, so every bet
the user has ever placed is queryable in one place.

Chart colors: profit teal #0d9488 against brand red #e10600 for loss. The
obvious choice was the app's existing green/red (#4ade80 / #f87171), but that
pair separates by only ΔE 7.9 under deuteranopia — the classic red/green trap,
effectively one color for a red-green colorblind reader. This pair measures
ΔE 13.9 and clears the lightness, chroma, contrast and normal-vision checks
too. Sign is never carried by color alone: every bar and figure is labelled.
"""
import altair as alt
import pandas as pd
import streamlit as st

import bet_store
from bet_slips import fmt_odds, american_to_implied_prob

PROFIT = "#0d9488"   # teal — validated against the loss red for CVD separation
LOSS = "#e10600"     # brand red
INK = "#f5f5f5"
MUTED = "#a6a8ad"
GRID = "#333336"
SURFACE = "#161616"

MARKET_ORDER = ["Moneyline", "Spread", "Total"]


def _base(chart_h=260):
    return {"height": chart_h}


def _theme(chart):
    """Recessive axes/grid on the app's dark surface."""
    return (
        chart.configure_view(strokeWidth=0, fill=SURFACE)
        .configure_axis(
            labelColor=MUTED, titleColor=MUTED, gridColor=GRID,
            domainColor=GRID, tickColor=GRID, labelFontSize=11, titleFontSize=11,
            gridOpacity=0.5,
        )
        .configure_legend(labelColor=MUTED, titleColor=MUTED)
        .configure_axisX(grid=False)
    )


def summarize(df):
    """Headline figures over the settled portion of a history frame."""
    settled = df[df["is_settled"]] if not df.empty else df
    staked = float(settled["stake"].sum()) if not settled.empty else 0.0
    net = float(settled["steel_result"].sum()) if not settled.empty else 0.0
    wins = int((settled["steel_result"] > 0).sum()) if not settled.empty else 0
    losses = int((settled["steel_result"] < 0).sum()) if not settled.empty else 0
    pushes = int((settled["steel_result"] == 0).sum()) if not settled.empty else 0
    decided = wins + losses
    open_n = int((~df["is_settled"]).sum()) if not df.empty else 0
    return {
        "total": int(len(df)), "open": open_n, "settled": int(len(settled)),
        "wins": wins, "losses": losses, "pushes": pushes,
        "staked": staked, "net": net,
        "roi": (net / staked * 100) if staked else 0.0,
        "win_rate": (wins / decided * 100) if decided else 0.0,
        "avg_stake": float(settled["stake"].mean()) if not settled.empty else 0.0,
        "best": float(settled["steel_result"].max()) if not settled.empty else 0.0,
        "worst": float(settled["steel_result"].min()) if not settled.empty else 0.0,
    }


def longest_streak(df):
    """(kind, length) of the longest run of wins or losses, pushes ignored."""
    seq = [r for r in df[df["is_settled"]]["steel_result"].tolist() if r != 0]
    best_kind, best_len, cur_kind, cur_len = None, 0, None, 0
    for r in seq:
        kind = "W" if r > 0 else "L"
        cur_len = cur_len + 1 if kind == cur_kind else 1
        cur_kind = kind
        if cur_len > best_len:
            best_kind, best_len = kind, cur_len
    return best_kind, best_len


def cumulative_pl_chart(df):
    """Running P/L over time — the headline trend.

    One series, so no legend: the title names it. A zero rule carries polarity
    so the line colour doesn't have to.
    """
    d = df[df["is_settled"]].copy()
    if d.empty:
        return None
    d = d.sort_values("placed_at")
    d["running_pl"] = d["steel_result"].cumsum()
    d["Bet"] = range(1, len(d) + 1)
    d["Placed"] = d["placed_at"].dt.strftime("%b %d, %Y")
    d["Play"] = d["label"].fillna(d["market"].fillna("Bet"))

    zero = alt.Chart(pd.DataFrame({"y": [0]})).mark_rule(
        color=GRID, strokeDash=[4, 4], size=1
    ).encode(y="y:Q")

    # Linear, not monotone: the running total only changes at each settled
    # bet, so a smoothed curve would invent movement between them. Integer
    # ticks for the same reason — there is no "bet 1.4".
    x_enc = alt.X(
        "Bet:Q", title="Settled bets (in order)",
        scale=alt.Scale(nice=False, domainMin=1, padding=6),
        axis=alt.Axis(tickMinStep=1, format="d"),
    )
    line = alt.Chart(d).mark_line(
        color=INK, strokeWidth=2, interpolate="linear",
    ).encode(
        x=x_enc,
        y=alt.Y("running_pl:Q", title="Cumulative Steel"),
    )
    points = alt.Chart(d).mark_circle(size=64, opacity=0).encode(
        x=x_enc, y="running_pl:Q",
        tooltip=[
            alt.Tooltip("Placed:N", title="Placed"),
            alt.Tooltip("Play:N", title="Bet"),
            alt.Tooltip("steel_result:Q", title="Result", format="+.0f"),
            alt.Tooltip("running_pl:Q", title="Running P/L", format="+.0f"),
        ],
    )
    return _theme((zero + line + points).properties(**_base(280)))


def pl_by_market_chart(df):
    """Net Steel by market. Diverging fill by sign, every bar direct-labelled
    so the sign never depends on colour."""
    d = df[df["is_settled"]]
    if d.empty:
        return None
    g = (d.groupby(d["market"].fillna("Other"))
           .agg(net=("steel_result", "sum"), bets=("id", "count"))
           .reset_index().rename(columns={"market": "Market"}))
    if g.empty:
        return None
    g["sign"] = g["net"].apply(lambda v: "Profit" if v >= 0 else "Loss")
    g["lab"] = g["net"].apply(lambda v: f"{v:+.0f}")

    # Explicit category order, and the *same* y encoding on every layer. A
    # sort of "-x" can't resolve across layers, and layering in a rule with no
    # y encoding collapses the shared band scale — both put every bar on one
    # row instead of its own.
    order = g.sort_values("net", ascending=False)["Market"].tolist()
    y_enc = alt.Y("Market:N", title=None, sort=order)

    # Headroom on both ends so the direct labels sit clear of the bar and,
    # on the negative side, don't collide with the y-axis category names.
    lo, hi = float(g["net"].min()), float(g["net"].max())
    span = max(abs(lo), abs(hi), 1.0)
    domain = [min(0.0, lo) - span * 0.22, max(0.0, hi) + span * 0.15]

    bars = alt.Chart(g).mark_bar(cornerRadiusEnd=4, height=22).encode(
        y=y_enc,
        x=alt.X("net:Q", title="Net Steel",
                scale=alt.Scale(domain=domain, nice=False)),
        color=alt.Color(
            "sign:N",
            scale=alt.Scale(domain=["Profit", "Loss"], range=[PROFIT, LOSS]),
            legend=alt.Legend(title=None, orient="top"),
        ),
        tooltip=[
            alt.Tooltip("Market:N"),
            alt.Tooltip("bets:Q", title="Bets"),
            alt.Tooltip("net:Q", title="Net Steel", format="+.0f"),
        ],
    )
    # Two label layers so a negative bar's value sits outside its left end
    # rather than on top of the bar.
    pos = alt.Chart(g).transform_filter(alt.datum.net >= 0).mark_text(
        align="left", dx=6, color=INK, fontSize=11, fontWeight="bold",
    ).encode(y=y_enc, x=alt.X("net:Q"), text="lab:N")
    neg = alt.Chart(g).transform_filter(alt.datum.net < 0).mark_text(
        align="right", dx=-6, color=INK, fontSize=11, fontWeight="bold",
    ).encode(y=y_enc, x=alt.X("net:Q"), text="lab:N")

    return _theme(
        (bars + pos + neg).properties(height=alt.Step(40))
    )


def market_breakdown_table(df):
    """Record, stake, P/L and ROI per market."""
    d = df[df["is_settled"]]
    if d.empty:
        return pd.DataFrame()
    rows = []
    for market, grp in d.groupby(d["market"].fillna("Other")):
        w = int((grp["steel_result"] > 0).sum())
        l = int((grp["steel_result"] < 0).sum())
        p = int((grp["steel_result"] == 0).sum())
        staked = float(grp["stake"].sum())
        net = float(grp["steel_result"].sum())
        rows.append({
            "Market": market,
            "Bets": len(grp),
            "Record": f"{w}-{l}" + (f"-{p}" if p else ""),
            "Win %": round(w / (w + l) * 100, 1) if (w + l) else 0.0,
            "Staked": round(staked, 1),
            "Net Steel": round(net, 1),
            "ROI %": round(net / staked * 100, 1) if staked else 0.0,
        })
    return pd.DataFrame(rows).sort_values("Net Steel", ascending=False)


def _history_view(df):
    """The raw ledger, shaped for reading."""
    v = pd.DataFrame({
        "Placed": df["placed_at"],
        "Bet": df["label"].fillna(""),
        "Market": df["market"].fillna(""),
        "Selection": df["selection"].fillna(""),
        "Line": df["line"],
        "Odds": df["odds"].apply(lambda o: fmt_odds(int(o)) if pd.notna(o) else "—"),
        "Stake": df["stake"],
        "Status": df["status"].str.upper(),
        "Result": df["steel_result"],
        "Score": [
            f"{a:.0f}-{h:.0f}" if pd.notna(a) and pd.notna(h) else "—"
            for a, h in zip(df["away_score"], df["home_score"])
        ],
        "Settled": df["settled_at"],
    })
    return v


def render_bet_history_section(username):
    """Full bet bank + trends, rendered under the Profile tab."""
    df = bet_store.history_frame(username)
    st.markdown(
        "<div style='font-size:0.7rem;color:var(--muted,#a6a8ad);font-weight:600;"
        "letter-spacing:0.8px;margin:4px 0 2px 0'>BET BANK</div>",
        unsafe_allow_html=True,
    )
    if df.empty:
        st.caption("No bets recorded yet. Every Steel bet you place is banked here.")
        return

    s = summarize(df)
    kind, streak = longest_streak(df)

    m = st.columns(4)
    m[0].metric("Bets banked", s["total"],
                f"{s['open']} still open" if s["open"] else None, delta_color="off")
    m[1].metric("Record", f"{s['wins']}-{s['losses']}"
                + (f"-{s['pushes']}" if s["pushes"] else ""),
                f"{s['win_rate']:.0f}% win rate" if s["settled"] else None,
                delta_color="off")
    m[2].metric("Net Steel", f"{s['net']:+.0f}",
                f"{s['roi']:+.1f}% ROI" if s["staked"] else None, delta_color="off")
    m[3].metric("Longest streak",
                f"{streak}{kind}" if kind else "—",
                f"best {s['best']:+.0f} · worst {s['worst']:+.0f}" if s["settled"] else None,
                delta_color="off")

    if s["settled"] == 0:
        st.info(
            "Nothing has settled yet, so there's no trend to chart. Game-line "
            "bets settle automatically once the game finishes."
        )
    else:
        t1, t2 = st.tabs(["📈 Running P/L", "📊 By market"])
        with t1:
            c = cumulative_pl_chart(df)
            if c is not None:
                st.caption("Cumulative Steel across settled bets, in the order they were placed.")
                st.altair_chart(c, use_container_width=True)
        with t2:
            c = pl_by_market_chart(df)
            if c is not None:
                st.caption("Net Steel won or lost per market.")
                st.altair_chart(c, use_container_width=True)
            bd = market_breakdown_table(df)
            if not bd.empty:
                st.dataframe(bd, use_container_width=True, hide_index=True)

    st.markdown(
        "<div style='font-size:0.7rem;color:var(--muted,#a6a8ad);font-weight:600;"
        "letter-spacing:0.8px;margin:14px 0 2px 0'>FULL HISTORY</div>",
        unsafe_allow_html=True,
    )
    f1, f2, f3 = st.columns([2, 1.3, 1.3])
    with f1:
        q = st.text_input("Search", key="bh_q", placeholder="Team, player, market…")
    with f2:
        statuses = sorted(df["status"].dropna().unique().tolist())
        pick = st.multiselect("Status", statuses, default=[], key="bh_status",
                              placeholder="Any status")
    with f3:
        markets = sorted(df["market"].dropna().unique().tolist())
        mpick = st.multiselect("Market", markets, default=[], key="bh_market",
                               placeholder="Any market")

    view = df
    if pick:
        view = view[view["status"].isin(pick)]
    if mpick:
        view = view[view["market"].isin(mpick)]
    if q:
        ql = q.lower()
        hay = (view["label"].fillna("") + " " + view["player"].fillna("") + " "
               + view["market"].fillna("") + " " + view["away"].fillna("") + " "
               + view["home"].fillna("") + " " + view["selection"].fillna(""))
        view = view[hay.str.lower().str.contains(ql, regex=False)]

    st.caption(f"{len(view)} of {len(df)} bets")
    st.dataframe(
        _history_view(view.sort_values("placed_at", ascending=False)),
        use_container_width=True, hide_index=True,
        column_config={
            "Placed": st.column_config.DatetimeColumn("Placed", format="MMM DD, YYYY HH:mm"),
            "Settled": st.column_config.DatetimeColumn("Settled", format="MMM DD, YYYY HH:mm"),
            "Stake": st.column_config.NumberColumn("Stake", format="%.0f"),
            "Result": st.column_config.NumberColumn("Result", format="%+.0f"),
            "Line": st.column_config.NumberColumn("Line", format="%g"),
        },
    )
    st.download_button(
        "⬇ Export history (CSV)",
        _history_view(view).to_csv(index=False).encode("utf-8"),
        file_name=f"fade_machine_bets_{username}.csv",
        mime="text/csv",
        key="bh_csv",
    )
