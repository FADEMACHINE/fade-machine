"""Bet slip grouping, blended pricing and the My Bets tab for FADE MACHINE.

Repeat bets on the same play collapse into one slip. The slip's price is the
blended price — the single number that would have produced the same profit on
the same total stake — not a mean of the American odds, which doesn't survive
the +/- discontinuity around even money.

Self-contained on purpose: app.py imports this, so importing app.py back would
be circular (and under Streamlit would re-execute the page as a second module).
The odds math therefore lives here and app.py imports it from this module.
"""
import streamlit as st

# ---- Odds math -------------------------------------------------------------
def fmt_odds(price):
    if price is None:
        return "—"
    return f"+{price}" if price > 0 else str(price)


def american_to_profit(stake, odds):
    odds = float(odds)
    if odds > 0:
        return round(stake * (odds / 100), 2)
    return round(stake * (100 / abs(odds)), 2)


def american_to_implied_prob(price):
    price = float(price)
    return 100.0 / (price + 100.0) if price > 0 else -price / (-price + 100.0)


def implied_prob_to_american(prob):
    prob = min(max(prob, 0.0001), 0.9999)
    return round(-100.0 * prob / (1.0 - prob)) if prob >= 0.5 else round(100.0 * (1.0 - prob) / prob)


def devig_two_way(price_a, price_b):
    """Strip the vig out of a book's two-sided price, returning fair
    probabilities that sum to exactly 1."""
    pa, pb = american_to_implied_prob(price_a), american_to_implied_prob(price_b)
    total = pa + pb
    return (0.5, 0.5) if total <= 0 else (pa / total, pb / total)


def decimal_to_american(dec):
    if dec is None or dec <= 1:
        return None
    return round((dec - 1) * 100) if dec >= 2.0 else round(-100 / (dec - 1))


def blended_odds(legs):
    """The single price equivalent to a set of stakes at different prices.

    Averaging American odds directly is wrong — they're a discontinuous scale
    (-110 and +110 are near-identical bets but 220 apart numerically), so a
    mean of -110 and +150 is meaningless. Instead total what the legs actually
    risk and actually return, then express that as one price. Two 10-Steel
    bets at -110 and -105 blend to -107; the same stakes at +150 and -110
    blend to +120.
    """
    total_stake = sum(l.get("stake", 0) for l in legs)
    if total_stake <= 0:
        return None
    total_profit = sum(american_to_profit(l.get("stake", 0), l.get("odds", -110)) for l in legs)
    return decimal_to_american((total_stake + total_profit) / total_stake)


# ---- Grouping --------------------------------------------------------------
def slip_key(bet):
    """Identity of a play. Two bets merge only if they're the same side of the
    same market at the same number in the same game — a different line is a
    different bet, even on the same team."""
    return (
        bet.get("game_id"),
        bet.get("market"),
        (bet.get("selection") or "").lower(),
        bet.get("line"),
        bet.get("player"),
    )


def group_bets(bets):
    """Collapse repeat bets on the same play into one slip each, newest first."""
    slips = {}
    for b in bets or []:
        k = slip_key(b)
        if k not in slips:
            slips[k] = {
                "key": k,
                "game_id": b.get("game_id"),
                "away": b.get("away"),
                "home": b.get("home"),
                "market": b.get("market"),
                "selection": b.get("selection"),
                "line": b.get("line"),
                "player": b.get("player"),
                "market_type": b.get("market_type"),
                "label": b.get("label"),
                "legs": [],
            }
        slips[k]["legs"].append(b)

    out = []
    for s in slips.values():
        s["legs"].sort(key=lambda l: l.get("placed_at") or "")
        stake = sum(l.get("stake", 0) for l in s["legs"])
        profit = sum(american_to_profit(l.get("stake", 0), l.get("odds", -110)) for l in s["legs"])
        prices = [l.get("odds") for l in s["legs"] if l.get("odds") is not None]
        s["stake"] = stake
        s["odds"] = blended_odds(s["legs"])
        s["to_win"] = round(profit, 2)
        s["payout"] = round(stake + profit, 2)
        s["leg_count"] = len(s["legs"])
        s["first_placed"] = s["legs"][0].get("placed_at") if s["legs"] else None
        s["last_placed"] = s["legs"][-1].get("placed_at") if s["legs"] else None
        # Best for the bettor is the longest price — the lowest implied
        # probability, i.e. the biggest payout per Steel staked.
        s["best_odds"] = min(prices, key=american_to_implied_prob) if prices else None
        s["worst_odds"] = max(prices, key=american_to_implied_prob) if prices else None
        s["result"] = round(sum(l.get("steel_result", 0) or 0 for l in s["legs"]), 2)
        statuses = {(l.get("status") or "open").lower() for l in s["legs"]}
        s["status"] = statuses.pop() if len(statuses) == 1 else "mixed"
        out.append(s)

    out.sort(key=lambda s: s["last_placed"] or "", reverse=True)
    return out


def summarize(open_slips, settled_slips):
    """Headline numbers for the summary strip."""
    at_risk = sum(s["stake"] for s in open_slips)
    potential = sum(s["to_win"] for s in open_slips)
    staked = sum(s["stake"] for s in settled_slips)
    net = sum(s["result"] for s in settled_slips)
    wins = sum(1 for s in settled_slips if s["result"] > 0)
    losses = sum(1 for s in settled_slips if s["result"] < 0)
    pushes = sum(1 for s in settled_slips if s["result"] == 0)
    decided = wins + losses
    return {
        "open_count": len(open_slips),
        "open_legs": sum(s["leg_count"] for s in open_slips),
        "at_risk": at_risk,
        "potential": potential,
        "settled_count": len(settled_slips),
        "wins": wins, "losses": losses, "pushes": pushes,
        "net": net,
        "roi": (net / staked * 100) if staked else 0.0,
        "win_rate": (wins / decided * 100) if decided else 0.0,
    }


# ---- Render ----------------------------------------------------------------
def _selection_text(s):
    """Human-readable side, e.g. 'KC -3.5' or 'Over 44.5'."""
    sel = (s.get("selection") or "").strip()
    line = s.get("line")
    pretty = {"away": s.get("away"), "home": s.get("home"),
              "over": "Over", "under": "Under"}.get(sel.lower(), sel.title())
    if line is None:
        return pretty or "—"
    if sel.lower() in ("over", "under"):
        return f"{pretty} {line:g}"
    return f"{pretty} {line:+g}" if isinstance(line, (int, float)) else f"{pretty} {line}"


def _matchup(s):
    away, home = s.get("away"), s.get("home")
    return f"{away} @ {home}" if away and home else (s.get("label") or "—")


def _inject_css():
    st.markdown("""
    <style>
    .bs-slip { display: flex; align-items: center; gap: 14px; flex-wrap: wrap; }
    .bs-main { flex: 1 1 240px; min-width: 0; }
    .bs-sel {
        font-size: 1.02rem; font-weight: 700; color: var(--text, #f5f5f5);
        line-height: 1.25;
    }
    .bs-match { font-size: 0.78rem; color: var(--muted, #a6a8ad); margin-top: 2px; }
    .bs-num { text-align: right; min-width: 78px; }
    .bs-lab {
        font-family: var(--font-display, 'Oswald', sans-serif); font-size: 0.6rem;
        font-weight: 600; letter-spacing: 0.7px; text-transform: uppercase;
        color: var(--muted, #a6a8ad);
    }
    .bs-val {
        font-family: var(--font-mono, monospace); font-size: 1rem; font-weight: 700;
        color: var(--text, #f5f5f5);
    }
    .bs-merge {
        display: inline-block; font-size: 0.66rem; font-weight: 700;
        padding: 2px 8px; border-radius: 999px; margin-left: 8px;
        background: var(--accent-bg, #2a0806); color: var(--accent-light, #ff6b60);
        border: 1px solid var(--accent-dark, #8a1c14);
    }
    .bs-res {
        display: inline-block; min-width: 46px; text-align: center;
        font-family: var(--font-display, 'Oswald', sans-serif); font-weight: 700;
        font-size: 0.78rem; padding: 3px 10px; border-radius: 999px;
        border: 1.5px solid currentColor;
    }
    .bs-won { color: var(--positive, #4ade80); }
    .bs-lost { color: var(--negative, #f87171); }
    .bs-push { color: var(--muted, #a6a8ad); }
    .bs-legs { width: 100%; border-collapse: collapse; margin-top: 2px; }
    .bs-legs th {
        text-align: left; font-family: var(--font-display, 'Oswald', sans-serif);
        font-size: 0.62rem; font-weight: 600; letter-spacing: 0.6px;
        color: var(--muted, #a6a8ad); padding: 4px 8px;
        border-bottom: 1px solid var(--border, #333336);
    }
    .bs-legs td {
        font-size: 0.82rem; padding: 6px 8px; color: var(--text, #f5f5f5);
        border-bottom: 1px solid var(--border, #333336);
        font-family: var(--font-mono, monospace);
    }
    .bs-legs tr:last-child td { border-bottom: none; }
    .bs-empty {
        text-align: center; padding: 28px 16px; color: var(--muted, #a6a8ad);
        border: 1px dashed var(--border, #333336); border-radius: var(--radius-md, 10px);
    }
    </style>
    """, unsafe_allow_html=True)


def _legs_table_html(legs):
    rows = ""
    for l in legs:
        placed = (l.get("placed_at") or "")[:16].replace("T", " ")
        rows += (
            f"<tr><td>{placed}</td>"
            f"<td>{l.get('stake', 0)}</td>"
            f"<td>{fmt_odds(l.get('odds'))}</td>"
            f"<td>{american_to_profit(l.get('stake', 0), l.get('odds', -110)):.2f}</td></tr>"
        )
    return (
        "<table class='bs-legs'><thead><tr>"
        "<th>PLACED</th><th>STAKE</th><th>ODDS</th><th>TO WIN</th>"
        "</tr></thead><tbody>" + rows + "</tbody></table>"
    )


def _render_slip(s, settled=False):
    with st.container(border=True):
        merged = (
            f"<span class='bs-merge'>{s['leg_count']} bets merged</span>"
            if s["leg_count"] > 1 else ""
        )
        if settled:
            status = s["status"]
            cls = {"won": "bs-won", "lost": "bs-lost"}.get(status, "bs-push")
            word = {"won": "WON", "lost": "LOST"}.get(status, "PUSH")
            if s["result"] > 0:
                cls, word = "bs-won", "WON"
            elif s["result"] < 0:
                cls, word = "bs-lost", "LOST"
            right = (
                f"<div class='bs-num'><div class='bs-lab'>Result</div>"
                f"<div class='bs-val {cls.replace('bs-', 'bs-')}' "
                f"style='color:inherit'><span class='bs-res {cls}'>{word}</span></div></div>"
                f"<div class='bs-num'><div class='bs-lab'>Steel</div>"
                f"<div class='bs-val' style='color:"
                f"{'var(--positive,#4ade80)' if s['result'] >= 0 else 'var(--negative,#f87171)'}'>"
                f"{s['result']:+.0f}</div></div>"
            )
        else:
            right = (
                f"<div class='bs-num'><div class='bs-lab'>To win</div>"
                f"<div class='bs-val' style='color:var(--positive,#4ade80)'>"
                f"{s['to_win']:.0f}</div></div>"
                f"<div class='bs-num'><div class='bs-lab'>Payout</div>"
                f"<div class='bs-val'>{s['payout']:.0f}</div></div>"
            )

        st.markdown(
            f"<div class='bs-slip'>"
            f"<div class='bs-main'>"
            f"<div class='bs-sel'>{_selection_text(s)}{merged}</div>"
            f"<div class='bs-match'>{s.get('market') or ''} · {_matchup(s)}"
            f"{' · ' + s['player'] if s.get('player') else ''}</div>"
            f"</div>"
            f"<div class='bs-num'><div class='bs-lab'>Odds</div>"
            f"<div class='bs-val'>{fmt_odds(s['odds'])}</div></div>"
            f"<div class='bs-num'><div class='bs-lab'>Stake</div>"
            f"<div class='bs-val'>{s['stake']:.0f}</div></div>"
            f"{right}</div>",
            unsafe_allow_html=True,
        )
        if s["leg_count"] > 1:
            with st.expander(
                f"Blended from {s['leg_count']} bets · "
                f"{fmt_odds(s['worst_odds'])} to {fmt_odds(s['best_odds'])}"
            ):
                st.markdown(_legs_table_html(s["legs"]), unsafe_allow_html=True)
                st.caption(
                    "Blended price is the single number that returns the same "
                    "profit on the same total stake — not an average of the "
                    "American odds."
                )


def _filter_sort(slips, key_prefix, settled=False):
    """Search / market filter / sort controls. Returns the visible slips."""
    markets = sorted({s.get("market") for s in slips if s.get("market")})
    c1, c2, c3 = st.columns([2, 1.4, 1.4])
    with c1:
        q = st.text_input("Search", key=f"{key_prefix}_q",
                          placeholder="Team, player or market…")
    with c2:
        mkt = st.multiselect("Market", markets, default=[], key=f"{key_prefix}_mkt",
                             placeholder="All markets")
    with c3:
        sort_opts = ["Newest", "Biggest stake", "Best odds"]
        if settled:
            sort_opts += ["Biggest win", "Biggest loss"]
        sort = st.selectbox("Sort", sort_opts, key=f"{key_prefix}_sort")

    ql = (q or "").lower()
    shown = [
        s for s in slips
        if (not mkt or s.get("market") in mkt)
        and (not ql or ql in " ".join(str(v).lower() for v in (
            s.get("away"), s.get("home"), s.get("player"),
            s.get("market"), s.get("selection"), s.get("label")) if v))
    ]
    if sort == "Biggest stake":
        shown.sort(key=lambda s: s["stake"], reverse=True)
    elif sort == "Best odds":
        # Longest price first — lowest implied probability.
        shown.sort(key=lambda s: american_to_implied_prob(s["odds"]) if s["odds"] else 1)
    elif sort == "Biggest win":
        shown.sort(key=lambda s: s["result"], reverse=True)
    elif sort == "Biggest loss":
        shown.sort(key=lambda s: s["result"])
    return shown


def render_my_bets_tab(open_bets, settled_bets):
    """Open and settled bets as merged slips. Both lists come from the SQLite
    ledger (bet_store), which is the source of truth for bets."""
    _inject_css()
    open_slips = group_bets(open_bets)
    settled_slips = group_bets(settled_bets)
    s = summarize(open_slips, settled_slips)

    # delta_color="off" on the contextual lines: a green up-arrow next to
    # "7 bets" or a win-loss record would imply movement over time, which
    # these aren't. Only the profit figure is a real gain.
    m = st.columns(4)
    m[0].metric("Open slips", s["open_count"],
                f"{s['open_legs']} bet{'s' if s['open_legs'] != 1 else ''} merged"
                if s["open_legs"] != s["open_count"] else None,
                delta_color="off")
    m[1].metric("Steel at risk", f"{s['at_risk']:.0f}")
    m[2].metric("Potential return", f"{s['at_risk'] + s['potential']:.0f}",
                f"+{s['potential']:.0f} profit" if s["potential"] else None)
    if s["settled_count"]:
        m[3].metric(
            "Settled P/L", f"{s['net']:+.0f}",
            f"{s['wins']}-{s['losses']}"
            + (f"-{s['pushes']}" if s["pushes"] else "")
            + f" · {s['roi']:+.1f}% ROI",
            delta_color="off",
        )
    else:
        m[3].metric("Settled P/L", "—", "No settled bets", delta_color="off")

    open_tab, settled_tab = st.tabs(
        [f"Open Bets ({len(open_slips)})", f"Settled History ({len(settled_slips)})"]
    )
    with open_tab:
        if not open_slips:
            st.markdown(
                "<div class='bs-empty'>No open bets yet.<br>"
                "Place Steel from the Betting or Props tab and your slips land here.</div>",
                unsafe_allow_html=True,
            )
        else:
            for slip in _filter_sort(open_slips, "bs_open"):
                _render_slip(slip, settled=False)
    with settled_tab:
        if not settled_slips:
            st.markdown(
                "<div class='bs-empty'>Nothing settled yet.</div>",
                unsafe_allow_html=True,
            )
        else:
            st.caption(
                f"{s['wins']}-{s['losses']}"
                + (f"-{s['pushes']}" if s["pushes"] else "")
                + f" · {s['win_rate']:.0f}% win rate · {s['net']:+.0f} Steel · "
                f"{s['roi']:+.1f}% ROI"
            )
            for slip in _filter_sort(settled_slips, "bs_settled", settled=True):
                _render_slip(slip, settled=True)
