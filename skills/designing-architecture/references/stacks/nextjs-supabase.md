# Stack: nextjs-supabase (design-time planning concerns)

Read this when Step 3 of the design pass detects the project stack is
`nextjs-supabase` (Next.js App Router + TypeScript, Supabase Postgres +
Auth + RLS, `@supabase/ssr` cookie sessions; test runner per the
project's rules file — commonly Vitest + Playwright). This is *reference*
for planning — what to look for and what to flag in the plan artifact —
not a script to execute. Project specifics (verification commands,
generated-types path, middleware location) come from the project's rules
file (`AGENTS.md` / `.opencode/agents.md`); this file holds the
stack-wide concerns that apply regardless of project.

If the project declares a different stack, do not read this file — read
the matching `references/stacks/<stack>.md`. If no matching reference
exists, proceed generically and flag the gap in the plan's Open Questions.

## Contents

- Schema-first planning
- Generated DB types
- Auth: SSR cookie sessions via `@supabase/ssr`
- Row-Level Security
- Rendering + data access: the hybrid pattern
- Acceptance-criteria shapes that recur on this stack

## Schema-first planning

On this stack the migration files (or the linked Supabase schema) are the
source of truth. Client code references the **generated** types; the
schema is what you design against.

- Plan schema changes as DDL in `## Schema / Type Impacts`, not only as
  "add a column" prose. Name the table, column, type, FK action, and any
  index.
- A new feature that needs persistence does not get a free pass on RLS.
  Design the table and its policies together; "we'll add RLS later" is a
  finding, not a plan.
- Cascade behaviour: decide `on delete cascade` vs `set null` vs
  `restrict` per FK in the plan, because Postgres will enforce whatever
  you write. Don't leave it to the implementer's guess.

## Generated DB types

The generated types file is a build artifact (path varies by project —
verify it in the rules file; commonly regenerated with
`supabase gen types typescript`).

- Flag regen in the plan when the schema changes: name the command from
  the rules file and assert **do not hand-edit** the generated file.
- Acceptance criterion for schema changes should include a "generated
  types compile" check (the project's type-check command exits 0) and,
  when the project commits generated types, a `git diff --exit-code`
  against the regenerated file (no drift between schema and committed
  types).
- A design that requires hand-editing generated types is a design smell
  — surface it in Open Questions, do not bury it.

## Auth: SSR cookie sessions via `@supabase/ssr`

The session lives in cookies managed by `@supabase/ssr`, and the same
project mixes browser and server contexts. Planning concerns:

- **Name the client per context.** A feature touches a browser client
  (client components), a server client bound to the request's cookies
  (server components / route handlers / server actions), and possibly
  middleware. The plan states which context each call runs in; mixing
  them (e.g. a browser client in server code) is a finding.
- **Per-request clients.** Server-side clients are created per request
  from the request cookies. A module-level singleton server client is a
  finding: it bleeds sessions across requests and users.
- **Authorization checks use a server-verified identity — `getUser()`,
  or `getClaims()` where the project's Supabase guidance adopts it —
  never `getSession()`**: cookie contents are user-controlled; only a
  verified identity is a trust boundary. State this in the plan for any
  server-side gate.
- **Cookie writes have one home.** Cookies cannot be set while
  rendering; refresh/rotation belongs to middleware, route handlers, or
  server actions. The plan names the middleware file when session
  refresh is in scope.
- **Route protection is explicit.** Decide in the plan which routes are
  protected, where the redirect check lives (middleware or layout), and
  that client-side checks are UX only — RLS is the enforcement.
- **Never `service_role` in the request path.** If a feature seems to
  require it, that is an Open Question, not a default.

## Row-Level Security

RLS is the security boundary, not the client. Planning concerns to
surface for every new table with user data:

- Default to per-user isolation: `auth.uid() = user_id` (or the
  project's convention). State the default in the plan.
- "Shared" data (workspaces, memberships, grants) needs a policy that
  joins through a membership table — write the `using` clause in the
  plan so the verifier can later test it.
- Relaxing an existing single-user policy to accommodate a shared table
  is a regression risk. The plan must say which existing policies are
  **unchanged** and which are **extended**, and the acceptance criteria
  must include an explicit "users who should not see this row get zero
  rows" check (a SQL or RPC assertion).
- Server-side helpers that fan out queries still run **as the user**
  unless explicitly elevated; elevation is a recorded decision, never
  implicit.

## Rendering + data access: the hybrid pattern

Next.js features mix server and client data access. The plan must state
the split per feature — "the component fetches what it needs" is not a
decision:

- **Server components** — initial data, secrets-safe reads, SEO-visible
  content. Per-user reads must be request-dynamic; do not rely on
  cross-request caching for authenticated data.
- **Route handlers / server actions** — mutations and cookie work.
  Treat every server action as a public HTTP endpoint: validate input
  server-side and re-check authorization; a hidden UI control is not an
  authorization boundary.
- **Client components** — realtime subscriptions, optimistic UI, local
  interaction. Plan the subscription lifecycle (subscribe on mount,
  clean up on unmount) and which client it uses.
- **Realtime authorization** follows the subscriber's token and RLS —
  plan which tables are streamed and verify the project's realtime
  setup rather than assuming it is enabled.
- **Cache safety for per-user data** is a planning concern: flag any
  fetch whose result differs per user and name the cache/dynamic
  decision in the plan (or raise it as an Open Question).

## Acceptance-criteria shapes that recur on this stack

Templates the design pass may reuse — adapt the placeholders, do not copy
them verbatim into the plan.

- **RLS isolation:** `A client that is not the owner querying <table>
  returns 0 rows — asserted by <unit/integration> in <file>.`
- **Generated types compile:** `After regenerating types, the type-check
  command exits 0.`
- **No type drift:** `git diff --exit-code -- <types path> is clean.`
- **Unauthenticated redirect:** `Requesting <protected route> without a
  session redirects to <login> — asserted by <e2e> in <file>.`
- **SSR session:** `A signed-in server-rendered request to <route>
  renders <user-scoped data>; the same request without a cookie renders
  the redirect — asserted by <e2e>.`
- **Server action is not client-trusted:** `A request to <action>
  without the required role is rejected server-side with no row change —
  asserted by <integration> in <file>.`
- **No cross-user cache reuse:** `Two sessions requesting <route>
  concurrently each receive their own rows — asserted by <test>.`
- **Sign-out clears access:** `After sign-out, <route> redirects and no
  cached user data is served — asserted by <e2e>.`
