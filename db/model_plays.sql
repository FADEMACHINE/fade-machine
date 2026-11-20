-- Model Board: every CBB moneyline that passed the FADE MACHINE checklist
-- (cbb_board.py). A play is logged the first time the app sees it pass, with
-- the price at that moment, and never overwritten, so the record can't be
-- rewritten with hindsight. Results are filled in from ESPN final scores.
--
-- Run by hand in the Supabase SQL editor. Safe to re-run.
--
-- Access: the board is public to read (it's a track record meant to be shown).
-- Writes come only from the Streamlit server, which holds the anon key in
-- st.secrets (never sent to the browser). Deletes are not allowed at all.

create table if not exists public.model_plays (
    id             text primary key,          -- "<espn game id>-<home|away>"
    game_id        text not null,
    game_date      date not null,             -- US Eastern date of tip-off
    tip_time       timestamptz,
    home           text not null,
    away           text not null,
    neutral        boolean default false,
    side           text not null check (side in ('home', 'away')),
    team           text not null,
    ml             integer not null,          -- price when first logged
    model_wp       numeric,                   -- Torvik model win probability
    fair_ml        integer,
    value_pts      numeric,
    checks_passed  integer not null,
    checks_scored  integer not null,
    checks         jsonb,                     -- [{name, passed, detail}]
    rules_version  text,
    logged_at      timestamptz not null default now(),
    status         text not null default 'pending'
                   check (status in ('pending', 'won', 'lost', 'push', 'void')),
    home_score     integer,
    away_score     integer,
    graded_at      timestamptz
);

create index if not exists model_plays_date on public.model_plays (game_date desc);

alter table public.model_plays enable row level security;

drop policy if exists model_plays_read on public.model_plays;
create policy model_plays_read on public.model_plays
    for select using (true);

drop policy if exists model_plays_insert on public.model_plays;
create policy model_plays_insert on public.model_plays
    for insert with check (status = 'pending');

-- Grading only: a pending play can be moved to a result, never edited after.
drop policy if exists model_plays_grade on public.model_plays;
create policy model_plays_grade on public.model_plays
    for update using (status = 'pending')
    with check (status in ('won', 'lost', 'push', 'void'));
