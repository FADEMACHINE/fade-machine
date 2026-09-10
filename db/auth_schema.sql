-- FADE MACHINE — accounts, bets and Steel ledger (durable storage)
-- Run this yourself in the Supabase SQL editor (Project → SQL Editor → New query).
-- Nothing in this repo executes DDL against your project automatically — same
-- convention as db/schema.sql. Safe to re-run: every statement is idempotent.
--
-- Why this exists: users_db.json and the local bets.db both live on the app's
-- filesystem, which Streamlit Community Cloud wipes on every redeploy. Anything
-- that has to survive — your account, your Steel balance, your bet history —
-- has to live here instead.
--
-- Passwords are NOT stored by these tables. Supabase Auth owns them in
-- auth.users, hashed server-side; the app only ever sees an access token. That
-- is also why every policy below keys off auth.uid() rather than a username
-- string: with row level security on, a signed-in account can only ever read
-- or write its own rows, even though the app ships the public anon key.

-- ============================================================
-- profiles — one row per auth user. Steel balance lives here.
-- id is the auth.users id, so a deleted account takes its data with it.
-- ============================================================
create table if not exists public.profiles (
    id            uuid primary key references auth.users(id) on delete cascade,
    display_name  text,
    steel_balance numeric not null default 0,
    created_at    timestamptz not null default now(),
    updated_at    timestamptz not null default now()
);

-- ============================================================
-- bets — the durable bet ledger. Mirrors the local SQLite table in
-- bet_store.py so the same code shapes work against either backend.
-- id stays text: it's the app-generated bet id ("bet_<timestamp>"), which
-- also makes re-importing the same bet a no-op.
-- ============================================================
create table if not exists public.bets (
    id            text primary key,
    user_id       uuid not null references auth.users(id) on delete cascade,
    game_id       text,
    away          text,
    home          text,
    market        text,
    market_type   text,
    selection     text,
    line          numeric,
    odds          integer,
    stake         numeric not null default 0,
    player        text,
    label         text,
    placed_at     timestamptz not null default now(),
    commence_time timestamptz,
    status        text not null default 'open',
    steel_result  numeric not null default 0,
    settled_at    timestamptz,
    away_score    integer,
    home_score    integer,
    settle_note   text
);

create index if not exists idx_bets_user        on public.bets(user_id);
create index if not exists idx_bets_user_status on public.bets(user_id, status);
create index if not exists idx_bets_game        on public.bets(game_id);
create index if not exists idx_bets_placed      on public.bets(user_id, placed_at desc);

-- ============================================================
-- steel_transactions — every Steel movement (purchase, bet, settlement),
-- so a balance can always be reconciled against its history.
-- ============================================================
create table if not exists public.steel_transactions (
    id           bigserial primary key,
    user_id      uuid not null references auth.users(id) on delete cascade,
    type         text not null,
    steel_amount numeric not null,
    note         text,
    created_at   timestamptz not null default now()
);

create index if not exists idx_steel_tx_user on public.steel_transactions(user_id, created_at desc);

-- ============================================================
-- Row level security.
-- Without these policies the anon key the app ships could read every
-- account's rows. With them, a request can only touch rows whose user id
-- matches the signed-in token, and an anonymous (signed-out) request matches
-- nothing at all.
-- ============================================================
alter table public.profiles           enable row level security;
alter table public.bets               enable row level security;
alter table public.steel_transactions enable row level security;

drop policy if exists profiles_select_own on public.profiles;
create policy profiles_select_own on public.profiles
    for select using (auth.uid() = id);

drop policy if exists profiles_insert_own on public.profiles;
create policy profiles_insert_own on public.profiles
    for insert with check (auth.uid() = id);

drop policy if exists profiles_update_own on public.profiles;
create policy profiles_update_own on public.profiles
    for update using (auth.uid() = id) with check (auth.uid() = id);

drop policy if exists bets_select_own on public.bets;
create policy bets_select_own on public.bets
    for select using (auth.uid() = user_id);

drop policy if exists bets_insert_own on public.bets;
create policy bets_insert_own on public.bets
    for insert with check (auth.uid() = user_id);

drop policy if exists bets_update_own on public.bets;
create policy bets_update_own on public.bets
    for update using (auth.uid() = user_id) with check (auth.uid() = user_id);

drop policy if exists steel_tx_select_own on public.steel_transactions;
create policy steel_tx_select_own on public.steel_transactions
    for select using (auth.uid() = user_id);

drop policy if exists steel_tx_insert_own on public.steel_transactions;
create policy steel_tx_insert_own on public.steel_transactions
    for insert with check (auth.uid() = user_id);

-- ============================================================
-- Auto-create a profile the moment an account is created, so the app never
-- has to handle a signed-in user with no profile row. security definer is
-- required: the trigger runs as the auth system, not as the new user.
-- ============================================================
create or replace function public.handle_new_user()
returns trigger
language plpgsql
security definer
set search_path = public
as $$
begin
    insert into public.profiles (id, display_name, steel_balance)
    values (
        new.id,
        coalesce(new.raw_user_meta_data->>'display_name', split_part(new.email, '@', 1)),
        0
    )
    on conflict (id) do nothing;
    return new;
end;
$$;

drop trigger if exists on_auth_user_created on auth.users;
create trigger on_auth_user_created
    after insert on auth.users
    for each row execute function public.handle_new_user();

-- ============================================================
-- Verify (optional). After running the above, this should return three rows
-- with rowsecurity = true.
-- ============================================================
-- select tablename, rowsecurity from pg_tables
--  where schemaname = 'public'
--    and tablename in ('profiles', 'bets', 'steel_transactions');
