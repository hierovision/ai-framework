# Project rules — Phasewave (focus-sessions RLS slice)

## Stack
`vue-supabase` — Vue 3 + TypeScript + Pinia + Vuetify 3, Supabase
(Postgres + Auth + RLS), Vitest (unit), Playwright (e2e). The runnable
fixture stubs are plain CommonJS `.js` so the verify scripts can execute
the seam in-process; the real project uses `.ts` + a real Postgres test
DB. The faked supabase client in `src/supabase/fake-client.js` is the
transport fake at the outermost boundary; it enforces the RLS policy
from `db/policies.js` (which mirrors `db/schema.sql`).

## Verification commands (what the verify stage runs)
- Type check: `npm run type-check`
- Lint: `npm run lint`
- Integration: `npm run test`
- Meaningfulness proof: `npm run meaningfulness`

Run them from the repo root. The full suite is:
`npm run type-check && npm run lint && npm run test`.

## Integration test conventions
- Integration tests live in `tests/<seam>.test.js` (e.g.
  `tests/rls.test.js`) and are plain Node scripts that assert on the
  seam's observable behaviour, exiting `0` on pass and `1` on failure.
- `npm run test` discovers and runs every `tests/**/*.test.js`.
- Real collaborators where feasible — the store under test is the real
  store; only the transport (the supabase client) is faked, at the
  outermost boundary.
- RLS isolation is asserted through the **authenticated client as the
  user** (create `createClient({ authUid: 'user-b', seed })`). Never
  assert isolation through a service-role bypass (`serviceRole: true`)
  — that mocks away the security behaviour under test. Seeding is
  pre-provided (`seed.js`) so no bypass is needed.
- Seeded state per test; no order dependence between tests.

## Meaningfulness proof (mandatory)
After writing the test, prove it can fail: run it against the fixed
per-user policy (GREEN), swap in the seeded broken leaky policy
(`db/policies.broken.js` over `db/policies.js`, run `npm run test`,
observe RED — the wrong user now sees the other user's rows), restore
the fixed policy, observe GREEN. `npm run meaningfulness` automates
this red-on-broken / green-on-fixed check AND verifies the test does
not bypass RLS via service role. A test that passes on the leaky
policy is vacant — it does not guard isolation.

## Conventions
- The RLS policy lives in `db/policies.js` (mirrors `db/schema.sql`).
  It is the system under test — do not edit it to make the test pass.
- No `as any`; no `Math.random()` / `Date.now()` in data paths that
  tests assert against (determinism).
