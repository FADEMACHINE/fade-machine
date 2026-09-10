"""Game- and matchup-specific betting trends from real historical results.

Everything here is computed from the `games` table in Supabase (2000-present),
not generated. ATS verdicts follow the same sign convention as the ats_results
view in db/schema.sql:

    spread_line > 0  -> home favoured by that many points
    result           -> home_score - away_score
    home covers when result > spread_line, away when result < spread_line,
    and neither on an exact match (push).

Trends are only as good as their sample, so every record carries its count and
anything thin is labelled rather than dressed up as a pattern.
"""
import pandas as pd
import streamlit as st

RECENT_GAMES = 10          # "last N" window for form trends
H2H_LIMIT = 8              # most recent meetings to summarise
MIN_SAMPLE = 4             # below this, say so instead of implying a trend


@st.cache_resource(show_spinner=False)
def _client():
    """Read-only anon client. Defined here rather than imported from app.py,
    which would be circular (app imports this module)."""
    try:
        url = st.secrets.get("SUPABASE_URL")
        key = st.secrets.get("SUPABASE_ANON_KEY")
    except Exception:
        return None
    if not (url and key):
        return None
    try:
        from supabase import create_client
        return create_client(url, key)
    except Exception:
        return None


@st.cache_data(ttl=6 * 3600, show_spinner=False)
def _load_games_raw():
    """Every historical game, paged past PostgREST's ~1000-row cap."""
    client = _client()
    if client is None:
        return []
    rows, start, page_size = [], 0, 1000
    while True:
        page = (client.table("games").select("*")
                .range(start, start + page_size - 1).execute().data)
        rows.extend(page)
        if len(page) < page_size:
            break
        start += page_size
    return rows


def games_frame():
    """Historical games with ATS and over/under verdicts derived."""
    rows = _load_games_raw()
    if not rows:
        return pd.DataFrame()
    df = pd.DataFrame(rows)
    for c in ("spread_line", "total_line", "home_score", "away_score", "result"):
        if c in df:
            df[c] = pd.to_numeric(df[c], errors="coerce")
    df = df.dropna(subset=["home_score", "away_score"])
    # result is stored, but recompute so a stale value can't skew a trend.
    df["margin"] = df["home_score"] - df["away_score"]
    df["total_points"] = df["home_score"] + df["away_score"]

    def cover(r):
        if pd.isna(r["spread_line"]):
            return None
        if r["margin"] == r["spread_line"]:
            return "push"
        return "home" if r["margin"] > r["spread_line"] else "away"

    def ou(r):
        if pd.isna(r["total_line"]):
            return None
        if r["total_points"] == r["total_line"]:
            return "push"
        return "over" if r["total_points"] > r["total_line"] else "under"

    df["cover_side"] = df.apply(cover, axis=1)
    df["ou_side"] = df.apply(ou, axis=1)
    df = df.sort_values(["season", "week"]).reset_index(drop=True)
    return df


@st.cache_data(ttl=6 * 3600, show_spinner=False)
def team_name_map():
    """{'Kansas City Chiefs': 'KC'} — The Odds API sends full names, the
    historical tables key on abbreviations."""
    client = _client()
    if client is None:
        return {}
    try:
        rows = client.table("teams").select("team_id,name").execute().data or []
    except Exception:
        return {}
    return {r["name"]: r["team_id"] for r in rows if r.get("name")}


# ---- Record helpers --------------------------------------------------------
def _rec(wins, losses, pushes=0):
    decided = wins + losses
    return {
        "w": wins, "l": losses, "p": pushes, "n": decided + pushes,
        "pct": (wins / decided * 100) if decided else 0.0,
        "thin": (decided + pushes) < MIN_SAMPLE,
    }


def _team_games(df, team_id, venue=None, last=None):
    if df.empty:
        return df
    if venue == "home":
        sub = df[df["home_team"] == team_id]
    elif venue == "away":
        sub = df[df["away_team"] == team_id]
    else:
        sub = df[(df["home_team"] == team_id) | (df["away_team"] == team_id)]
    return sub.tail(last) if last else sub


def team_ats(df, team_id, venue=None, last=RECENT_GAMES):
    sub = _team_games(df, team_id, venue, last)
    sub = sub[sub["cover_side"].notna()]
    if sub.empty:
        return _rec(0, 0)
    side = sub.apply(
        lambda r: "home" if r["home_team"] == team_id else "away", axis=1
    )
    wins = int((sub["cover_side"] == side).sum())
    pushes = int((sub["cover_side"] == "push").sum())
    return _rec(wins, len(sub) - wins - pushes, pushes)


def team_ou(df, team_id, last=RECENT_GAMES):
    sub = _team_games(df, team_id, None, last)
    sub = sub[sub["ou_side"].notna()]
    if sub.empty:
        return _rec(0, 0)
    overs = int((sub["ou_side"] == "over").sum())
    pushes = int((sub["ou_side"] == "push").sum())
    return _rec(overs, len(sub) - overs - pushes, pushes)


def team_ats_by_role(df, team_id, as_favorite=True, last=None):
    """ATS record specifically when favoured, or specifically as the dog."""
    sub = _team_games(df, team_id, None, None)
    sub = sub[sub["cover_side"].notna() & sub["spread_line"].notna()]
    if sub.empty:
        return _rec(0, 0)
    is_home = sub["home_team"] == team_id
    # spread_line > 0 means the home side is favoured.
    favoured = (is_home & (sub["spread_line"] > 0)) | (~is_home & (sub["spread_line"] < 0))
    sub = sub[favoured if as_favorite else ~favoured]
    if last:
        sub = sub.tail(last)
    if sub.empty:
        return _rec(0, 0)
    side = sub.apply(lambda r: "home" if r["home_team"] == team_id else "away", axis=1)
    wins = int((sub["cover_side"] == side).sum())
    pushes = int((sub["cover_side"] == "push").sum())
    return _rec(wins, len(sub) - wins - pushes, pushes)


def head_to_head(df, away_id, home_id, limit=H2H_LIMIT):
    """Recent meetings between the two teams, either venue."""
    if df.empty:
        return {"meetings": 0, "su": _rec(0, 0), "ats": _rec(0, 0),
                "ou": _rec(0, 0), "avg_total": None, "rows": []}
    pair = df[
        ((df["home_team"] == home_id) & (df["away_team"] == away_id))
        | ((df["home_team"] == away_id) & (df["away_team"] == home_id))
    ].tail(limit)
    if pair.empty:
        return {"meetings": 0, "su": _rec(0, 0), "ats": _rec(0, 0),
                "ou": _rec(0, 0), "avg_total": None, "rows": []}

    # Straight-up and ATS from the away (visiting) team's perspective.
    away_is_home = pair["home_team"] == away_id
    away_pts = pair["home_score"].where(away_is_home, pair["away_score"])
    home_pts = pair["away_score"].where(away_is_home, pair["home_score"])
    su_wins = int((away_pts > home_pts).sum())
    su_push = int((away_pts == home_pts).sum())

    graded = pair[pair["cover_side"].notna()]
    if graded.empty:
        ats = _rec(0, 0)
    else:
        side = graded.apply(
            lambda r: "home" if r["home_team"] == away_id else "away", axis=1
        )
        aw = int((graded["cover_side"] == side).sum())
        ap = int((graded["cover_side"] == "push").sum())
        ats = _rec(aw, len(graded) - aw - ap, ap)

    ou_g = pair[pair["ou_side"].notna()]
    if ou_g.empty:
        ou = _rec(0, 0)
    else:
        ov = int((ou_g["ou_side"] == "over").sum())
        op = int((ou_g["ou_side"] == "push").sum())
        ou = _rec(ov, len(ou_g) - ov - op, op)

    rows = []
    for _, r in pair.iloc[::-1].iterrows():
        rows.append({
            "season": int(r["season"]), "week": int(r["week"]),
            "label": f"{r['away_team']} {int(r['away_score'])} @ "
                     f"{r['home_team']} {int(r['home_score'])}",
            "spread": r["spread_line"], "total": r["total_line"],
            "total_points": int(r["total_points"]),
            "cover_side": r["cover_side"], "ou_side": r["ou_side"],
        })
    return {
        "meetings": len(pair),
        "su": _rec(su_wins, len(pair) - su_wins - su_push, su_push),
        "ats": ats, "ou": ou,
        "avg_total": round(float(pair["total_points"].mean()), 1),
        "rows": rows,
    }


def matchup_trends(df, away_name, home_name, name_map):
    """Everything the trends panel needs for one game, or None if either team
    can't be resolved to a historical id."""
    away_id, home_id = name_map.get(away_name), name_map.get(home_name)
    if not away_id or not home_id or df.empty:
        return None
    return {
        "away_id": away_id, "home_id": home_id,
        "h2h": head_to_head(df, away_id, home_id),
        "away": {
            "form": team_ats(df, away_id),
            "venue": team_ats(df, away_id, venue="away"),
            "ou": team_ou(df, away_id),
            "fav": team_ats_by_role(df, away_id, True, 20),
            "dog": team_ats_by_role(df, away_id, False, 20),
        },
        "home": {
            "form": team_ats(df, home_id),
            "venue": team_ats(df, home_id, venue="home"),
            "ou": team_ou(df, home_id),
            "fav": team_ats_by_role(df, home_id, True, 20),
            "dog": team_ats_by_role(df, home_id, False, 20),
        },
    }


# ---- Render ----------------------------------------------------------------
def _rec_txt(r, suffix=""):
    if r["n"] == 0:
        return "<span class='mt-none'>no data</span>"
    body = f"{r['w']}-{r['l']}" + (f"-{r['p']}" if r["p"] else "")
    tone = "mt-good" if r["pct"] >= 60 else "mt-bad" if r["pct"] <= 40 else "mt-mid"
    thin = " <span class='mt-thin'>small sample</span>" if r["thin"] else ""
    return (f"<span class='mt-rec {tone}'>{body}</span>"
            f"<span class='mt-pct'>{r['pct']:.0f}%{suffix}</span>{thin}")


def _row(label, value):
    return f"<div class='mt-row'><span class='mt-lab'>{label}</span>{value}</div>"


def trends_html(t, away_name, home_name):
    h = t["h2h"]
    away_abbr, home_abbr = t["away_id"], t["home_id"]

    if h["meetings"]:
        h2h_block = (
            _row(f"{away_abbr} straight up", _rec_txt(h["su"]))
            + _row(f"{away_abbr} ATS", _rec_txt(h["ats"]))
            + _row("Over/Under", _rec_txt(h["ou"], " over"))
            + _row("Avg combined points", f"<span class='mt-rec mt-mid'>{h['avg_total']}</span>")
        )
        h2h_head = f"HEAD-TO-HEAD · LAST {h['meetings']} MEETING{'S' if h['meetings'] != 1 else ''}"
    else:
        h2h_block = "<div class='mt-row'><span class='mt-none'>No previous meetings on record.</span></div>"
        h2h_head = "HEAD-TO-HEAD"

    def side_block(key, abbr, venue_label):
        s = t[key]
        return (
            f"<div class='mt-col'><div class='mt-team'>{abbr}</div>"
            + _row(f"ATS last {RECENT_GAMES}", _rec_txt(s["form"]))
            + _row(f"ATS {venue_label}", _rec_txt(s["venue"]))
            + _row(f"Over last {RECENT_GAMES}", _rec_txt(s["ou"], " over"))
            + _row("ATS as favourite", _rec_txt(s["fav"]))
            + _row("ATS as underdog", _rec_txt(s["dog"]))
            + "</div>"
        )

    recent = ""
    if h["rows"]:
        items = "".join(
            f"<div class='mt-hist'><span class='mt-hist-yr'>{r['season']} W{r['week']}</span>"
            f"<span class='mt-hist-sc'>{r['label']}</span>"
            f"<span class='mt-hist-ou'>{(r['ou_side'] or '—').upper()} "
            f"{r['total_points']}</span></div>"
            for r in h["rows"]
        )
        recent = f"<div class='mt-head'>RECENT MEETINGS</div>{items}"

    return (
        f"<div class='mt-wrap'>"
        f"<div class='mt-head'>{h2h_head}</div>{h2h_block}"
        f"<div class='mt-cols'>"
        f"{side_block('away', away_abbr, 'on the road')}"
        f"{side_block('home', home_abbr, 'at home')}"
        f"</div>{recent}</div>"
    )


def inject_css():
    st.markdown("""
    <style>
    .mt-wrap { font-size: 0.84rem; }
    .mt-head {
        font-family: var(--font-display, 'Oswald', sans-serif); font-size: 0.62rem;
        font-weight: 600; letter-spacing: 0.8px; text-transform: uppercase;
        color: var(--muted, #a6a8ad); margin: 10px 0 4px 0;
    }
    .mt-head:first-child { margin-top: 0; }
    .mt-row {
        display: flex; align-items: baseline; gap: 8px; padding: 3px 0;
        border-bottom: 1px solid var(--border, #333336);
    }
    .mt-row:last-child { border-bottom: none; }
    .mt-lab { flex: 1; color: var(--muted, #a6a8ad); }
    .mt-rec { font-family: var(--font-mono, monospace); font-weight: 700; }
    .mt-good { color: var(--positive, #4ade80); }
    .mt-bad  { color: var(--negative, #f87171); }
    .mt-mid  { color: var(--text, #f5f5f5); }
    .mt-pct  { font-family: var(--font-mono, monospace); color: var(--muted, #a6a8ad); font-size: 0.76rem; }
    .mt-thin { color: var(--gold, #f0b429); font-size: 0.68rem; }
    .mt-none { color: var(--muted-dim, #7d7f84); }
    .mt-cols { display: flex; gap: 18px; flex-wrap: wrap; margin-top: 6px; }
    .mt-col { flex: 1 1 210px; min-width: 0; }
    .mt-team {
        font-family: var(--font-display, 'Oswald', sans-serif); font-weight: 700;
        font-size: 0.9rem; color: var(--text, #f5f5f5); margin-bottom: 2px;
    }
    .mt-hist {
        display: flex; gap: 10px; align-items: baseline; padding: 3px 0;
        border-bottom: 1px solid var(--border, #333336); font-size: 0.78rem;
    }
    .mt-hist:last-child { border-bottom: none; }
    .mt-hist-yr { font-family: var(--font-mono, monospace); color: var(--muted-dim, #7d7f84); width: 64px; }
    .mt-hist-sc { flex: 1; color: var(--text, #f5f5f5); }
    .mt-hist-ou { font-family: var(--font-mono, monospace); color: var(--muted, #a6a8ad); }
    </style>
    """, unsafe_allow_html=True)
