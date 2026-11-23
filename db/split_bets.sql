-- Underdog split bets (cbb_board.bet_plan): favourites are 1 unit on the
-- moneyline; underdogs split 1 unit between the moneyline and the spread so
-- that losing outright but covering breaks even. These columns record the
-- spread line/price and both stakes at the moment the pick is locked.
--
-- Run by hand in the Supabase SQL editor after model_plays.sql and
-- machine_top3.sql. Safe to re-run. Until it's run, picks are still saved,
-- just as plain 1-unit moneyline bets.

alter table public.model_plays  add column if not exists spread_line  numeric;
alter table public.model_plays  add column if not exists spread_odds  integer;
alter table public.model_plays  add column if not exists ml_stake     numeric;
alter table public.model_plays  add column if not exists spread_stake numeric;

alter table public.machine_top3 add column if not exists spread_line  numeric;
alter table public.machine_top3 add column if not exists spread_odds  integer;
alter table public.machine_top3 add column if not exists ml_stake     numeric;
alter table public.machine_top3 add column if not exists spread_stake numeric;
