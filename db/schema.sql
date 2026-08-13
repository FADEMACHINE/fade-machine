-- FADE MACHINE — Supabase schema foundation
-- Run this yourself in the Supabase SQL editor (Project → SQL Editor → New query).
-- Nothing in this repo executes DDL against your project automatically.
--
-- Scope: teams, games, and a derived ats_results view. This is the data-layer
-- foundation only — app.py / content_engine.py are not wired to this yet.
--
-- Sign conventions (confirmed against the nflverse/nflreadr schedules data
-- dictionary — the same source scripts/load_historical_data.py pulls from):
--   spread_line : positive = home team favored by that many points,
--                 negative = away team favored.
--   result      : home_score - away_score.
-- These two conventions are what the ats_results view's covering-team logic
-- below depends on. If you ever load games data from a different source,
-- re-verify the sign convention before trusting this view.

-- ============================================================
-- teams — one row per distinct team abbreviation that appears in games.
-- team_id is nflverse's own abbreviation. Relocated franchises keep their
-- historical code as a separate row rather than being collapsed into their
-- current one — e.g. 'OAK' (Oakland Raiders, through 2019) and 'LV' (Las
-- Vegas Raiders, 2020+) are both present, each with the division/conference
-- they actually played in. This is simpler and more historically accurate
-- than remapping old codes onto today's franchise identity, at the cost of
-- a handful of "duplicate" franchises under old + new names (OAK/LV,
-- SD/LAC, STL/LA). Expect ~35 rows, not exactly 32.
-- ============================================================
create table if not exists teams (
    team_id    text primary key,
    name       text not null,
    division   text not null,   -- e.g. 'AFC West'
    conference text not null    -- e.g. 'AFC'
);

-- ============================================================
-- games — one row per scheduled/played NFL game.
-- home_score/away_score/spread_line/total_line/result are nullable: future
-- games won't have scores yet, and some older games in nflverse's data have
-- no market lines. The ingestion script skips inserting rows with no
-- spread_line/total_line at all (see scripts/load_historical_data.py) rather
-- than writing fabricated placeholder numbers.
-- ============================================================
create table if not exists games (
    game_id     text primary key,          -- nflverse's own id, e.g. '2023_01_DET_KC'
    season      integer not null,
    week        integer not null,
    game_date   date,
    home_team   text not null references teams(team_id),
    away_team   text not null references teams(team_id),
    home_score  integer,
    away_score  integer,
    spread_line numeric(5,1),               -- see sign convention note above
    total_line  numeric(5,1),
    result      integer,                    -- home_score - away_score, kept as provided for audit/cross-check
    roof        text,                       -- outdoors / dome / closed / open
    surface     text,                       -- grass / turf variants as provided by nflverse
    created_at  timestamptz not null default now()
);

create index if not exists games_season_week_idx on games (season, week);
create index if not exists games_home_team_idx on games (home_team);
create index if not exists games_away_team_idx on games (away_team);

-- ============================================================
-- ats_results — derived from games, NOT a stored/duplicated table.
-- Implemented as a view rather than a table so it can never drift out of
-- sync with games: covering_team/push/covered_by_margin are always computed
-- live from whatever is currently in games. If you'd rather have this
-- materialized (e.g. for query performance at large scale), swap this for
-- `create materialized view` and add a refresh step to the ingestion script
-- — flagging that as a deliberate choice to make, not defaulting to it here.
--
-- Only rows with both spread_line and result present produce a verdict;
-- everything else (future games, games with no market line) comes through
-- with null covering_team/push/covered_by_margin instead of a guess.
-- ============================================================
create or replace view ats_results as
select
    g.game_id,
    g.season,
    g.week,
    g.home_team,
    g.away_team,
    g.spread_line,
    g.result,
    case
        when g.spread_line is null or g.result is null then null
        when g.result = g.spread_line then null           -- push: nobody covers
        when g.result > g.spread_line then g.home_team
        else g.away_team
    end as covering_team,
    case
        when g.spread_line is null or g.result is null then null
        else (g.result = g.spread_line)
    end as push,
    case
        when g.spread_line is null or g.result is null then null
        else round(abs(g.result - g.spread_line), 1)
    end as covered_by_margin
from games g;

-- ============================================================
-- Row Level Security — deliberately left OFF for this foundation phase.
-- With RLS disabled (the default for a freshly created table), any request
-- authenticated with either the anon or service_role key can read AND write
-- these tables via the Supabase API — which is what lets
-- scripts/load_historical_data.py bulk-insert using the anon key per the
-- current st.secrets setup. Before wiring a public-facing app to this data,
-- come back and add at least a read-only policy for anon:
--
--   alter table teams enable row level security;
--   alter table games enable row level security;
--   create policy "public read" on teams for select using (true);
--   create policy "public read" on games for select using (true);
--
-- (ats_results is a view over games, so it inherits games' RLS automatically
-- once you enable it there — no separate policy needed for the view itself.)
