"""Daily MACHINE MODEL check, run by GitHub Actions (.github/workflows/daily-model-check.yml).

Does what opening the CBB Value view does, without anyone opening it:
  1. scores today's college basketball games on the checklist
  2. logs every qualifying play to `model_plays`
  3. locks in the day's MACHINE Top 3 (first run after the lock hour)
  4. grades finished picks in both records from ESPN final scores

Reads SUPABASE_URL and SUPABASE_ANON_KEY from the environment (GitHub repo
secrets), because there's no st.secrets outside Streamlit. Run locally with:

    SUPABASE_URL=... SUPABASE_ANON_KEY=... python scripts/daily_model_check.py [--force-top3]
"""
import os
import sys
from datetime import datetime

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import cbb_board  # noqa: E402
import cbb_data as cd  # noqa: E402
import cbb_value as cv  # noqa: E402


def main():
    url, key = os.environ.get("SUPABASE_URL"), os.environ.get("SUPABASE_ANON_KEY")
    if not (url and key):
        print("SUPABASE_URL / SUPABASE_ANON_KEY are not set; add them as GitHub repo secrets.")
        return 1
    from supabase import create_client
    client = create_client(url, key)
    cbb_board._client = lambda: client

    now = datetime.now(cd.ET)
    today = now.date()
    print(f"MACHINE MODEL check {now:%Y-%m-%d %H:%M} ET")

    season = cd.season_for(today)
    games, failed = cd.load_season(season)
    tv = cv.load_torvik(season)
    problems = []
    if games.empty:
        problems.append("ESPN scoreboard unavailable, so nothing was scored")
    if tv.empty:
        problems.append(f"Torvik stats unavailable, so nothing was scored: {cv.TORVIK_LAST_ERROR['msg']}")

    if not games.empty and not tv.empty:
        ratings, model = cd.fit_ratings(games)
        events, _ = cd.fetch_events([today])
        day_games = cd.parse_events(events)
        results = cv.evaluate_day(day_games, games, tv, ratings, model) if not day_games.empty else []
        plays = [r for r in results if cv.is_play(r["pick"], True, cv.RULES["play_at"])]
        print(f"{len(day_games)} games today, {len(results)} upcoming with moneylines, {len(plays)} qualify")
        for r in plays:
            g, p = r["game"], r["pick"]
            print(f"  PLAY {g[p['side']]} {p['ml']:+d}  value {p['value']:+.1f}  checks {p['passed']}/{p['scored']}")
        n, err = cbb_board.log_plays(plays, throttle=False)
        if err:
            problems.append(err)
        force = "--force-top3" in sys.argv
        picked, err = cbb_board.select_top3(results, today, force=force)
        if err:
            problems.append(err)
        elif picked:
            print(f"Locked today's Top {picked}:")
            for i, r in enumerate(cbb_board.top3_candidates(results), 1):
                g, p = r["game"], r["pick"]
                print(f"  #{i} {g[p['side']]} {p['ml']:+d}  value {p['value']:+.1f}  checks {p['passed']}/{p['scored']}")
        elif not cbb_board.top3_due(today) and not force:
            print(f"Top 3 locks at the first check after {cbb_board.TOP3_LOCK_HOUR}:00 ET.")

    graded = cbb_board.grade_all()
    print(f"Graded: {graded}")
    for p in problems:
        print(f"PROBLEM: {p}")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
