-- Phasewave schema. The focus_sessions table backs the timer.
create table if not exists public.focus_sessions (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references auth.users(id) on delete cascade,
  started_at timestamptz not null,
  label text not null default ''
);

create policy "users see own sessions"
  on public.focus_sessions for select
  using (auth.uid() = user_id);

-- feat-shared-sessions: per-session read-only share grants.
create table if not exists public.shared_sessions (
  id uuid primary key default gen_random_uuid(),
  owner_id uuid not null references auth.users(id) on delete cascade,
  sharee_id uuid not null references auth.users(id) on delete cascade,
  session_id uuid not null references public.focus_sessions(id) on delete cascade,
  created_at timestamptz not null default now(),
  unique (session_id, sharee_id)
);

-- RLS SELECT policy for shared_sessions.
alter table public.shared_sessions enable row level security;

create policy "owner or sharee can read shared rows"
  on public.shared_sessions for select
  using (true);