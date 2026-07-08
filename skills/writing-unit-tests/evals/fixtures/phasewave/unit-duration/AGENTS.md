# Project rules — Phasewave (duration-format slice)

## Stack
`vue-supabase` — Vue 3 + TypeScript + Pinia + Vuetify 3, Supabase
(Postgres + Auth + RLS), Vitest (unit), Playwright (e2e). The runnable
fixture stubs are plain CommonJS `.js` under `src/lib/` so the verify
scripts can execute the logic in-process; the real project uses `.ts`.

## Verification commands (what the verify stage runs)
- Type check: `npm run type-check`
- Lint: `npm run lint`
- Unit/integration: `npm run test`
- Meaningfulness proof: `npm run meaningfulness`

Run them from the repo root. The full suite is:
`npm run type-check && npm run lint && npm run test`.

## Test conventions
- Unit tests live in `tests/<module>.test.js` (e.g.
  `tests/duration.test.js`) and are plain Node scripts that `assert`
  on the module under test, exiting `0` on pass and `1` on failure.
- `npm run test` discovers and runs every `tests/**/*.test.js`.
- Mock only true externals (a clock, a network boundary) — never the
  module under test. A unit test that stubs the function it is testing
  has vacated its assertion.
- Seeded data, injected values — no `Date.now()` / `Math.random()` in
  a data path the test asserts against.

## Meaningfulness proof (mandatory)
After writing a test, demonstrate it can fail: run it against the
seeded broken variant (`src/lib/duration.broken.js` — copy it over
`src/lib/duration.js`, run `npm run test`, observe RED), then restore
the real module and observe GREEN. `npm run meaningfulness` automates
this red-on-broken / green-on-fixed check. A test that has never been
seen red proves nothing.

## Conventions
- Lib / utility modules live under `src/lib/<feature>.js`.
- No `as any`; no `waitForTimeout` in e2e; no `Math.random()` /
  `Date.now()` in data paths that tests assert against (determinism).
