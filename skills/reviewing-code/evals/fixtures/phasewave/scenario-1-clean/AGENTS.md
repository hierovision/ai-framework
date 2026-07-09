# Project rules — Phasewave (recent-sessions slice)

## Stack
`vue-supabase` — Vue 3 + TypeScript + Pinia + Vuetify 3, Supabase
(Postgres + Auth + RLS), Vitest (unit), Playwright (e2e). The runnable
fixture stubs are plain CommonJS `.js` under `src/lib/` so the verify
scripts can execute the logic in-process; the real project uses `.ts`.

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
- Lib / utility modules live under `src/lib/<feature>.js`.
- Supabase queries return rows in no guaranteed order without an
  explicit `ORDER BY`; code that needs an order must sort itself.
- No `as any`; no `waitForTimeout` in e2e; no `Math.random()` /
  `Date.now()` in data paths that tests assert against (determinism).