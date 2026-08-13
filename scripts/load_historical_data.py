"""One-time ingestion: load real NFL schedule/odds history from nflverse
(via nfl_data_py's import_schedules) into the Supabase `games` and `teams`
tables defined in db/schema.sql.

This is a standalone script, not part of the live app — app.py and
content_engine.py are untouched by this phase.

Prerequisites (both are on you, not this script):
  1. Run db/schema.sql yourself in the Supabase SQL editor.
  2. Add SUPABASE_URL and SUPABASE_KEY to .streamlit/secrets.toml:
        SUPABASE_URL = "https://xxxx.supabase.co"
        SUPABASE_KEY = "your-anon-key"

Usage:
    python scripts/load_historical_data.py --dry-run   # fetch + report only, no writes, no credentials needed
    python scripts/load_historical_data.py              # actually upserts into Supabase

Data integrity rule this script follows: only real nflverse-provided values
are loaded. Any game missing spread_line or total_line is skipped (not
inserted with a fabricated/guessed line) and counted in the skip report.
"""
import argparse
import sys

import nfl_data_py as nfl
import pandas as pd

# nflverse's schedules data starts at 1999. Pull a wide range and let the
# missing-line filter decide what's actually usable, rather than hardcoding
# an assumed "lines start here" year.
FIRST_SEASON = 1999
LAST_SEASON = pd.Timestamp.now().year + 1  # covers whatever season is currently being scheduled

BATCH_SIZE = 500

GAME_COLUMNS = [
    "game_id", "season", "week", "gameday", "home_team", "away_team",
    "home_score", "away_score", "spread_line", "total_line", "result",
    "roof", "surface",
]


def fetch_schedules():
    years = list(range(FIRST_SEASON, LAST_SEASON + 1))
    df = nfl.import_schedules(years)
    return df[GAME_COLUMNS].copy()


def split_valid_and_skipped(df):
    """A game is only loaded if nflverse actually provided both a spread and
    a total line for it. Everything else is skipped and reported, never
    filled in with a placeholder."""
    missing_lines = df["spread_line"].isna() | df["total_line"].isna()
    valid = df[~missing_lines].copy()
    skipped = df[missing_lines].copy()
    return valid, skipped


def _none_if_nan(val):
    return None if pd.isna(val) else val


def _none_or_int(val):
    # Careful: a shutout score of 0 is falsy but NOT missing — this must not
    # collapse to None, and must actually convert to int (not stay a float).
    return None if pd.isna(val) else int(val)


def build_games_records(df):
    records = []
    for row in df.itertuples(index=False):
        records.append({
            "game_id": row.game_id,
            "season": int(row.season),
            "week": int(row.week),
            "game_date": row.gameday,
            "home_team": row.home_team,
            "away_team": row.away_team,
            "home_score": _none_or_int(row.home_score),
            "away_score": _none_or_int(row.away_score),
            "spread_line": float(row.spread_line),
            "total_line": float(row.total_line),
            "result": _none_or_int(row.result),
            "roof": _none_if_nan(row.roof),
            "surface": _none_if_nan(row.surface),
        })
    return records


def build_teams_records(valid_games_df):
    """Teams referenced by the games actually being loaded, described using
    nflverse's own team_desc data (name/division/conference) — not hand-typed."""
    codes = sorted(set(valid_games_df["home_team"]) | set(valid_games_df["away_team"]))
    desc = nfl.import_team_desc().set_index("team_abbr")
    records = []
    missing_desc = []
    for code in codes:
        if code not in desc.index:
            missing_desc.append(code)
            continue
        row = desc.loc[code]
        records.append({
            "team_id": code,
            "name": row["team_name"],
            "division": row["team_division"],
            "conference": row["team_conf"],
        })
    return records, missing_desc


def chunked(seq, size):
    for i in range(0, len(seq), size):
        yield seq[i:i + size]


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--dry-run", action="store_true", help="Fetch and report only; don't write to Supabase or require credentials")
    args = parser.parse_args()

    print(f"Pulling nflverse schedules for {FIRST_SEASON}-{LAST_SEASON} via nfl_data_py...")
    raw = fetch_schedules()
    print(f"  {len(raw)} games returned across {raw['season'].nunique()} seasons")

    valid, skipped = split_valid_and_skipped(raw)
    print(f"  {len(valid)} games have both spread_line and total_line -> will be loaded")
    print(f"  {len(skipped)} games missing a line -> skipped (not fabricated)")
    if len(skipped):
        by_season = skipped.groupby("season").size()
        print("  Skipped-by-season:")
        for season, count in by_season.items():
            print(f"    {season}: {count} games skipped")

    games_records = build_games_records(valid)
    teams_records, missing_desc = build_teams_records(valid)
    if missing_desc:
        print(f"  WARNING: no team_desc entry found for: {missing_desc} -- excluded from teams_records")

    print(f"\nWill upsert {len(teams_records)} teams and {len(games_records)} games.")

    if args.dry_run:
        print("\n--dry-run set: no writes performed. Sample of what would be loaded:")
        for r in games_records[:5]:
            print(" ", r)
        return

    # Imported here (not at module load) so --dry-run never needs streamlit
    # secrets or the supabase package configured.
    import streamlit as st
    from supabase import create_client

    supabase_url = st.secrets.get("SUPABASE_URL")
    supabase_key = st.secrets.get("SUPABASE_KEY")
    if not supabase_url or not supabase_key:
        print(
            "\nERROR: SUPABASE_URL and/or SUPABASE_KEY not found in st.secrets "
            "(.streamlit/secrets.toml). Add them and re-run.",
            file=sys.stderr,
        )
        sys.exit(1)

    client = create_client(supabase_url, supabase_key)

    print("\nUpserting teams...")
    client.table("teams").upsert(teams_records, on_conflict="team_id").execute()
    print(f"  done ({len(teams_records)} teams)")

    print(f"Upserting games in batches of {BATCH_SIZE}...")
    total = 0
    for batch in chunked(games_records, BATCH_SIZE):
        client.table("games").upsert(batch, on_conflict="game_id").execute()
        total += len(batch)
        print(f"  {total}/{len(games_records)}")

    print("\nVerifying against Supabase...")
    teams_count = client.table("teams").select("team_id", count="exact").execute()
    games_count = client.table("games").select("game_id", count="exact").execute()
    print(f"  teams table now has {teams_count.count} rows")
    print(f"  games table now has {games_count.count} rows")

    sample = (
        client.table("games")
        .select("*")
        .order("season", desc=True)
        .order("week", desc=True)
        .limit(5)
        .execute()
    )
    print("\nSample rows (most recent games loaded):")
    for row in sample.data:
        print(" ", row)


if __name__ == "__main__":
    main()
