# Project rules — Notely

## Stack
Vue 3 + TypeScript + Pinia. Vitest (unit) and Playwright (e2e) in the real
project; the runnable fixture stubs here are plain CommonJS `.js` so the
verify scripts run in-process with no install step.

## Commands
Run from the repo root. The four gates, in order:

- Type check: `npm run type-check`
- Lint: `npm run lint`
- Unit tests: `npm run test:unit`
- E2E: `npm run test:e2e`

The full suite is all four chained with `&&`.

## Conventions
- Feature helpers live under `src/lib/<feature>.js`.
- Unit tests are `tests/*.test.js`; e2e journeys are `tests/*.e2e.js`. Both
  are plain Node scripts that exit non-zero on failure.
- No `as any`; no `FIXME`/`TBD` markers; no `waitForTimeout` in journeys.
- Plans live in `.opencode/plans/`. Execute exactly the named files; the
  `Excluded` list is binding.
