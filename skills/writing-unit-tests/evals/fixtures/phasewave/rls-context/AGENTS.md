# Project rules — Phasewave (focus-sessions slice)

## Stack
`vue-supabase` — Vue 3 + TypeScript + Pinia + Vuetify 3, Supabase
(Postgres + Auth + RLS), Vitest (unit), Playwright (e2e). Progressive
Web App (offline-capable, service worker).

## Verification commands (what the verify stage runs)
- Type check: `npm run type-check`
- Lint: `npm run lint`
- Unit/integration: `npm run test`
- e2e: `npm run e2e`

## Conventions
- Generated DB types live at `types/database.types.ts` — never hand-edit;
  regenerate via `npm run db:types` after schema changes. Schema is the
  source of truth (`db/schema.sql`); code references the generated types.
- Every table with user data gets Row-Level Security; default to
  per-user isolation (`auth.uid() = user_id`).
- Offline mutations go through the Pinia store, which queues to
  IndexedDB and syncs via the supabase client when back online.
- No `as any`; no `waitForTimeout` in e2e; no `Math.random()` /
  `Date.now()` in data paths that tests assert against (determinism).
