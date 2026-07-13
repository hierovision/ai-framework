# Project rules — Phasewave (session-score slice)

## Stack
`vue-supabase` — Vue 3 + TypeScript + Pinia + Vuetify 3, Supabase
(Postgres + Auth + RLS), Vitest (unit), Playwright (e2e). The runnable
fixture stubs are plain CommonJS `.js` under `src/lib/` so the verify
scripts can execute the logic in-process; the real project uses `.ts`.

## Plan artifact
- `plans_dir: .opencode/plans/`
- Plan filename convention: `<slug>.md`.

## Verification commands (what the verify stage runs)
- Type check: `npm run type-check`
- Lint: `npm run lint`
- Unit/integration: `npm run test`

## Conventions
- Lib / utility modules live under `src/lib/<feature>.js` (hyphenated).
- Unit tests live in `tests/<module>.test.js` and are plain Node scripts
  that `assert` on the module under test, exiting `0` on pass and `1` on
  failure. `npm run test` discovers and runs every `tests/**/*.test.js`
  (an empty suite is red).
- Mock only true externals — never the module under test.
- No `as any`; no `waitForTimeout` in e2e; no `Math.random()` /
  `Date.now()` in data paths that tests assert against (determinism).
- Numeric lib inputs that are negative are programmer errors: throw
  `RangeError`, never silently clamp or return 0.