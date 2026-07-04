-- Phasewave schema (source of truth). Regenerate types via `npm run db:types`.

create table if not exists public.activities (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references auth.users(id) on delete cascade,
  name text not null,
  duration_seconds int not null default 1500,
  deleted_at timestamptz
);

create table if not exists public.focus_sessions (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references auth.users(id) on delete cascade,
  activity_id uuid references public.activities(id) on delete set null,
  duration_seconds int not null,
  started_at timestamptz not null,
  ended_at timestamptz,
  status text not null default 'running'  -- running | completed | abandoned
);

-- Row-Level Security
alter table public.activities enable row level security;
alter table public.focus_sessions enable row level security;

create policy "activities owner only" on public.activities
  for all using (auth.uid() = user_id) with check (auth.uid() = user_id);

create policy "focus_sessions owner only" on public.focus_sessions
  for all using (auth.uid() = user_id) with check (auth.uid() = user_id);