-- MACHINE Top 3: the 3 best-edge CBB games the model picks each day
-- (cbb_board.py). Chosen once per day at the lock hour and never changed, then
-- graded from ESPN final scores. The running 1-unit tally on the Model page.
--
-- Run by hand in the Supabase SQL editor. Safe to re-run.
-- Same access rules as model_plays: public to read, written only by the app
-- server / daily job, no deletes, and a pick can only move from pending to a
-- result once.

create table if not exists public.machine_top3 (
    id             text primary key,          -- "<game date>-<rank>"
    game_date      date not null,
    rank           smallint not null check (rank between 1 and 3),
    game_id        text not null,
    tip_time       timestamptz,
    home           text not null,
    away           text not null,
    neutral        boolean default false,
    side           text not null check (side in ('home', 'away')),
    team           text not null,
    ml             integer not null,          -- price when the pick was locked
    model_wp       numeric,
    fair_ml        integer,
    value_pts      numeric,
    checks_passed  integer not null,
    checks_scored  integer not null,
    checks         jsonb,
    rules_version  text,
    logged_at      timestamptz not null default now(),
    status         text not null default 'pending'
                   check (status in ('pending', 'won', 'lost', 'push', 'void')),
    home_score     integer,
    away_score     integer,
    graded_at      timestamptz,
    unique (game_date, rank),
    unique (game_date, game_id)
);

create index if not exists machine_top3_date on public.machine_top3 (game_date desc);

alter table public.machine_top3 enable row level security;

drop policy if exists machine_top3_read on public.machine_top3;
create policy machine_top3_read on public.machine_top3
    for select using (true);

drop policy if exists machine_top3_insert on public.machine_top3;
create policy machine_top3_insert on public.machine_top3
    for insert with check (status = 'pending');

drop policy if exists machine_top3_grade on public.machine_top3;
create policy machine_top3_grade on public.machine_top3
    for update using (status = 'pending')
    with check (status in ('won', 'lost', 'push', 'void'));
