# Project rules — Phasewave (shared-sessions slice)

## Stack
`vue-supabase` — Vue 3 + TypeScript + Pinia + Vuetify 3, Supabase
(Postgres + Auth + RLS), Vitest (unit), Playwright (e2e). The runnable
fixture stubs are plain CommonJS `.js` / `.ts` text under `src/` and
`db/schema.sql` so the review can read them; the real project uses
`.ts` compiled by vue-tsc and `npm run db:types` for generated types.

## Plan artifact
- `plans_dir: .opencode/plans/`
- Plan filename convention: `<slug>.md` (lowercase-kebab).
- Revise in place; never clobber prior History.

## Verification commands (what the verify stage runs)
- Type check: `npm run type-check`
- Lint: `npm run lint`
- Unit/integration: `npm run test`

Run them from the repo root. The full suite is all three in sequence:
`npm run type-check && npm run lint && npm run test`.

## Conventions
- `db/schema.sql` is the schema source; every new table gets a
  per-user RLS policy scoping rows to `auth.uid() = user_id` (or the
  sharing model the plan describes). A policy that grants all
  authenticated users access to every row is a cross-user data leak.
- Generated types live in `types/database.types.ts` (regenerated via
  `npm run db:types` — never hand-edited).
- Pinia state, getters, actions live under `src/stores/*.ts`.
- No `as any`; no `waitForTimeout` in e2e; no `Math.random()` /
  `Date.now()` in data paths that tests assert against (determinism).