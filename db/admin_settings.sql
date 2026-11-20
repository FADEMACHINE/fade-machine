-- Admin accounts and the Master Settings they control (app_settings.py).
-- Run by hand in the Supabase SQL editor. Safe to re-run.
--
-- 1) Run this whole file.
-- 2) Then make your account an admin by running the line at the bottom with
--    the email you sign in to FADE MACHINE with.

create table if not exists public.admin_users (
    user_id    uuid primary key references auth.users(id) on delete cascade,
    added_at   timestamptz not null default now()
);

alter table public.admin_users enable row level security;

-- An account can only see whether IT is an admin. Nobody can add or remove
-- admins from the app; that's done here in the SQL editor.
drop policy if exists admin_users_self on public.admin_users;
create policy admin_users_self on public.admin_users
    for select using (user_id = auth.uid());

create table if not exists public.app_settings (
    id          text primary key default 'global' check (id = 'global'),
    settings    jsonb not null default '{}'::jsonb,
    updated_at  timestamptz not null default now(),
    updated_by  uuid references auth.users(id)
);

alter table public.app_settings enable row level security;

-- Everyone (including the daily job) can read the settings; only admins can
-- change them.
drop policy if exists app_settings_read on public.app_settings;
create policy app_settings_read on public.app_settings
    for select using (true);

drop policy if exists app_settings_admin_insert on public.app_settings;
create policy app_settings_admin_insert on public.app_settings
    for insert with check (exists (select 1 from public.admin_users a where a.user_id = auth.uid()));

drop policy if exists app_settings_admin_update on public.app_settings;
create policy app_settings_admin_update on public.app_settings
    for update using (exists (select 1 from public.admin_users a where a.user_id = auth.uid()))
    with check (exists (select 1 from public.admin_users a where a.user_id = auth.uid()));

-- Make yourself an admin (edit the email, then run just this line):
-- insert into public.admin_users (user_id) select id from auth.users where email = 'you@example.com' on conflict do nothing;
