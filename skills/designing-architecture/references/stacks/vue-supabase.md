# Stack: vue-supabase (design-time planning concerns)

Read this when Step 3 of the design pass detects the project stack is
`vue-supabase` (Vue 3 + TypeScript + Pinia + Vuetify, Supabase Postgres +
Auth + RLS, Vitest + Playwright, offline-capable PWA). This is *reference*
for planning — what to look for and what to flag in the plan artifact —
not a script to execute. Project specifics (verification commands,
generated-types path) come from the project's rules file; this file holds
the stack-wide concerns that apply regardless of project.

If the project declares a different stack, do not read this file — read
the matching `references/stacks/<stack>.md`. If no matching reference
exists, proceed generically and flag the gap in the plan's Open Questions.

## Contents

- Schema-first planning
- Generated DB types
- Row-Level Security
- Offline / PWA
- Acceptance-criteria shapes that recur on this stack

## Schema-first planning

On this stack `db/schema.sql` (or the project's migration files) is the
source of truth. Client code references the **generated** types; the
schema is what you design against.

- Plan schema changes as DDL in `## Schema / Type Impacts`, not only as
  "add a column" prose. Name the table, column, type, FK action, and any
  index.
- A new feature that needs persistence does not get a free pass on RLS.
  Design the table and its policies together; "we'll add RLS later" is a
  finding, not a plan.
- Cascade behaviour: decide `on delete cascade` vs `set null` vs
  `restrict` per FK in the plan, because Supabase/Postgres will enforce
  whatever you write. Don't leave it to the implementer's guess.

## Generated DB types

The generated types file (`types/database.types.ts` by convention; verify
the path in the rules file) is a build artifact.

- Flag regen in the plan when the schema changes: name the command from
  the rules file (commonly `npm run db:types`) and assert **do not
  hand-edit** the generated file.
- Acceptance criterion for schema changes should include a "generated
  types compile" check (`npm run type-check` exits 0) and, when the
  project commits generated types, a `git diff --exit-code` against the
  regenerated file (no drift between schema and committed types).
- A design that requires hand-editing generated types is a design smell
  — surface it in Open Questions, do not bury it.

## Row-Level Security

PWA + multi-user means RLS is the security boundary, not the client.
Planning concerns to surface for every new table with user data:

- Default to per-user isolation: `auth.uid() = user_id` (or the
  project's convention). State the default in the plan.
- "Shared" data (workspaces, memberships, grants) needs a policy that joins
  through a membership table — write the `using` clause in the plan so
  the verifier can later test it.
- Relaxing an existing single-user policy to accommodate a shared table
  is a regression risk. The plan must say which existing policies are
  **unchanged** and which are **extended**, and the acceptance criteria
  must include an explicit "users who should not see this row get zero
  rows" check (a SQL or RPC assertion).
- Service-role bypass (`service_role`) is not a planning answer. If a
  feature seems to require it, that is an Open Question, not a default.

## Offline / PWA

The skill always produces a check, never an implicit "we'll handle
offline": for a feature touching the Pinia store / supabase client:

- Does the new feature route mutations through the offline outbox, or
  does it bypass it? State which.
- Do queued rows carry enough context to replay correctly after a
  schema change? (A new nullable column may turn "replay fine" into
  "replay with null where the new schema expects a value.")
- Shared-ownership rows: can they ever be created or mutated
  offline? If yes, the replay must not break ownership invariants; if
  no, that is an explicit Excluded item, not a silent gap.
- A read-only feature (e.g. viewing a shared link) still needs an
  offline decision: cached last-known state, or "requires online."
  Pick one and write it into Scope.

## Acceptance-criteria shapes that recur on this stack

Templates the design pass may reuse — adapt the placeholders, do not copy
them verbatim into the plan.

- **RLS isolation:** `A client that is not the owner querying <table>
  returns 0 rows — asserted by <unit/e2e> in <file>.`
- **Generated types compile:** `After `npm run db:types`, `npm run type-
  check` exits 0.`
- **No type drift:** `git diff --exit-code -- types/ is clean (generated
  types match the regenerated file).`
- **Offline mutation queued:** `With `navigator.onLine === false`,
  <action> resolves, an outbox entry keyed <field> exists in the local
  outbox (the outbox reader returns it), and zero Supabase requests are
  issued — asserted by `npm run test`.`
- **Offline read fallback:** `Offline, <route> renders last-known state
  from cache; <route> with no cache renders the "requires online" state
  — asserted by `npm run e2e` in <file>.`
- **Privilege revoked server-side (not client trust):** `After the owner
  revokes <relation>, the formerly-privileged client's next <query>
  returns 0 rows without a page reload — asserted by <unit/e2e>.`