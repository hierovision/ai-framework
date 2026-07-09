-- Phasewave schema. The focus_sessions table backs the timer.
create table if not exists public.focus_sessions (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references auth.users(id) on delete cascade,
  started_at timestamptz not null,
  label text not null default ''
);

-- Per-user isolation: a user can read/write only their own sessions.
create policy "users see own sessions"
  on public.focus_sessions for select
  using (auth.uid() = user_id);
create policy "users insert own sessions"
  on public.focus_sessions for insert
  with check (auth.uid() = user_id);
create policy "users update own sessions"
  on public.focus_sessions for update
  using (auth.uid() = user_id);

-- Added during the offline-queue feature pass: track when a queued
-- session was last synced to the server.
alter table public.focus_sessions
  add column if not exists last_synced_at timestamptz;