# Project rules — Phasewave (offline-queue slice)

## Stack
`vue-supabase` — Vue 3 + TypeScript + Pinia + Vuetify 3, Supabase
(Postgres + Auth + RLS), Vitest (unit), Playwright (e2e). The runnable
fixture stubs are plain CommonJS `.js` / `.ts` text under `src/` so the
review can read them; the real project uses `.ts` compiled by vue-tsc.

## Plan artifact
- `plans_dir: .opencode/plans/`
- Plan filename convention: `<slug>.md` (lowercase-kebab).
- Revise in place; never clobber prior History. A deviation from
  `Files to Modify` belongs in a dated `## History` entry (mechanical)
  or a stop-and-route (contract-breaking) — never silent.

## Verification commands (what the verify stage runs)
- Type check: `npm run type-check`
- Lint: `npm run lint`
- Unit/integration: `npm run test`

Run them from the repo root. The full suite is all three in sequence:
`npm run type-check && npm run lint && npm run test`.

## Conventions
- Lib / utility modules live under `src/lib/<feature>.ts`.
- Pinia state, getters, actions live under `src/stores/*.ts`.
- `db/schema.sql` is the schema source; generated types live in
  `types/database.types.ts` (regenerated via `npm run db:types` —
  never hand-edited).
- No `as any`; no `waitForTimeout` in e2e; no `Math.random()` /
  `Date.now()` in data paths that tests assert against (determinism).