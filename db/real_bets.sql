-- Real Bets: the owner's real-money bet history imported from Juice Reel CSV
-- exports (real_bets.py). One row per bet leg, exactly as Juice Reel exports it.
-- Run by hand in the Supabase SQL editor after auth_schema.sql. Safe to re-run.
--
-- Row level security: an account can only ever see, add or change its own
-- rows (auth.uid()), same as the bets table.

create table if not exists public.real_bets (
    user_id          uuid    not null references auth.users(id) on delete cascade,
    bet_leg_id       bigint  not null,
    juice_bet_id     bigint  not null,
    sportsbook       text,
    risk_amount      numeric,
    bet_result       text,
    amount_won_or_lost numeric,
    odds_american    integer,
    number_of_legs   integer,
    date_placed      timestamptz,
    date_settled     timestamptz,
    if_freeplay_then_amount_actually_at_risk numeric,
    is_odds_boosted  boolean,
    clv_percent      numeric,
    leg_type         text,
    bet_on           text,
    bet_on_spread_total_number numeric,
    leg_sport        text,
    leg_league       text,
    leg_vig          numeric,
    leg_description  text,
    event_start_date timestamptz,
    event_name       text,
    imported_at      timestamptz not null default now(),
    primary key (user_id, bet_leg_id)
);

create index if not exists real_bets_user_bet on public.real_bets (user_id, juice_bet_id);

alter table public.real_bets enable row level security;

drop policy if exists real_bets_select_own on public.real_bets;
create policy real_bets_select_own on public.real_bets
    for select using (auth.uid() = user_id);

drop policy if exists real_bets_insert_own on public.real_bets;
create policy real_bets_insert_own on public.real_bets
    for insert with check (auth.uid() = user_id);

drop policy if exists real_bets_update_own on public.real_bets;
create policy real_bets_update_own on public.real_bets
    for update using (auth.uid() = user_id) with check (auth.uid() = user_id);

drop policy if exists real_bets_delete_own on public.real_bets;
create policy real_bets_delete_own on public.real_bets
    for delete using (auth.uid() = user_id);
