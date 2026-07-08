# Project rules — Phasewave (duration-format slice)

## Stack
`vue-supabase` — Vue 3 + TypeScript + Pinia + Vuetify 3, Supabase
(Postgres + Auth + RLS), Vitest (unit), Playwright (e2e). The runnable
fixture stubs are plain CommonJS `.js` under `src/lib/` so verify
scripts can execute the logic in-process; the real project uses `.ts`.

## Verification commands (what the verify stage runs)
- Type check: `npm run type-check`
- Lint: `npm run lint`
- Unit/integration: `npm run test`

## Conventions
- Lib / utility modules live under `src/lib/<feature>.js`.
- No `as any`; no `Math.random()` / `Date.now()` in data paths that
  tests assert against (determinism).
