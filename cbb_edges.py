"""FADE MACHINE college basketball edges: the file to edit as the season goes.

Each edge is a flag shown on the Power Ratings table and the March Madness
cheat sheet. Add, remove or retune them here; nothing else needs to change.

Every test receives one team row from cbb_data.fit_ratings() with these fields:

    team_id, team
    rank, net, off, def          MACHINE ratings (points vs an average D1 team)
    games, wins, losses
    last10_w, last10_n           form
    close_w, close_n             games decided by 5 or fewer
    ats_w, ats_l, ats_p          against the spread (ESPN's posted line)
    fav_ats_w, fav_ats_l         ATS as a favourite
    dog_ats_w, dog_ats_l         ATS as an underdog
    over, under                  totals record
    avg_margin, sos              average margin and opponents' average net rating

Tests also get `ranks`: {"net"|"off"|"def"|"sos"|"winpct": {team_id: rank}},
where 1 is best.

Keep them grounded in those numbers. Real data only.

"tone" controls the badge colour: "edge" (back them) or "fade" (bet against).
"""


def _pct(w, l):
    return w / (w + l) if (w + l) else 0.0


EDGES = [
    {
        "name": "Two-way elite",
        "tone": "edge",
        "why": "Top-25 offence and top-25 defence. Title winners almost always are.",
        "test": lambda t, ranks: ranks["off"][t["team_id"]] <= 25 and ranks["def"][t["team_id"]] <= 25,
    },
    {
        "name": "Battle-tested",
        "tone": "edge",
        "why": "Schedule in the top 40 by opponents' MACHINE rating.",
        "test": lambda t, ranks: ranks["sos"][t["team_id"]] <= 40,
    },
    {
        "name": "ATS machine",
        "tone": "edge",
        "why": "Covering 60%+ of lines over 10 or more graded games.",
        "test": lambda t, ranks: (t["ats_w"] + t["ats_l"]) >= 10 and _pct(t["ats_w"], t["ats_l"]) >= 0.60,
    },
    {
        "name": "Heating up",
        "tone": "edge",
        "why": "8+ wins in the last 10.",
        "test": lambda t, ranks: t["last10_n"] >= 10 and t["last10_w"] >= 8,
    },
    {
        "name": "Close-game luck",
        "tone": "fade",
        "why": "Winning 75%+ of 5-point games (6+ of them). Tends not to last.",
        "test": lambda t, ranks: t["close_n"] >= 6 and _pct(t["close_w"], t["close_n"] - t["close_w"]) >= 0.75,
    },
    {
        "name": "Record > rating",
        "tone": "fade",
        "why": "Win% ranks 50+ spots better than their MACHINE rating: the record flatters them.",
        "test": lambda t, ranks: t["games"] >= 10 and ranks["net"][t["team_id"]] - ranks["winpct"][t["team_id"]] >= 50,
    },
]


def team_flags(team, ranks):
    """List of (name, tone, why) edges this team triggers."""
    out = []
    for e in EDGES:
        try:
            if e["test"](team, ranks):
                out.append((e["name"], e["tone"], e["why"]))
        except Exception:
            continue
    return out
