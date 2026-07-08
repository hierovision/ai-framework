# Project rules — Phasewave (offline-replay slice)

## Stack
`vue-supabase` — Vue 3 + TypeScript + Pinia + Vuetify 3, Supabase
(Postgres + Auth + RLS), Vitest (unit), Playwright (e2e). The runnable
fixture stubs are plain CommonJS `.js` so the verify scripts can execute
the seam in-process. The faked supabase client in
`src/supabase/fake-client.js` is the transport fake at the outermost
boundary; the outbox and store under test are real.

## Verification commands (what the verify stage runs)
- Type check: `npm run type-check`
- Lint: `npm run lint`
- Integration: `npm run test`
- Meaningfulness proof: `npm run meaningfulness`

Run them from the repo root. The full suite is:
`npm run type-check && npm run lint && npm run test`.

## Integration test conventions
- Integration tests live in `tests/<seam>.test.js` (e.g.
  `tests/outbox.test.js`) and are plain Node scripts that assert on the
  seam's observable behaviour, exiting `0` on pass and `1` on failure.
- `npm run test` discovers and runs every `tests/**/*.test.js`.
- Real collaborators where feasible — the outbox and store are real;
  only the transport (the supabase client) is faked, at the outermost
  boundary.
- Reset the outbox between tests (`outbox._reset()`) so one test's
  queued mutations do not leak into the next (no order dependence).
- Seeded data; no `Date.now()` / `Math.random()` in the asserted path.

## Meaningfulness proof (mandatory)
After writing the test, prove it can fail: run it against the fixed
outbox (GREEN), swap in the seeded broken outbox
(`src/lib/outbox.broken.js` over `src/lib/outbox.js`, run `npm run test`,
observe RED — the broken outbox drops all but the first queued
mutation), restore the fixed outbox, observe GREEN. `npm run
meaningfulness` automates this red-on-broken / green-on-fixed check. A
test that passes on the broken outbox is vacant — it does not guard
replay-all-in-order.

## Conventions
- The outbox lives at `src/lib/outbox.js`. It is the system under test
  — do not edit it to make the test pass.
- No `as any`; no `Math.random()` / `Date.now()` in data paths that
  tests assert against (determinism).
