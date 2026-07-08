# Project rules — Phasewave (duration-format slice)

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
- Lib / utility modules live under `src/lib/<feature>.js`.
- No `as any`; no `waitForTimeout` in e2e; no `Math.random()` /
  `Date.now()` in data paths that tests assert against (determinism).
