# Project rules — Phasewave (share-session slice)

## Stack
`vue-supabase` — Vue 3 + Pinia + Supabase (Postgres + Auth + RLS),
Vitest (integration). Runnable stubs are CommonJS `.js`.

## Verification commands
- Type check: `npm run type-check`
- Lint: `npm run lint`
- Unit/integration: `npm run test`

## Conventions
- Stores under `src/stores/<name>.js`; faked supabase transport at
  `src/supabase/fake-client.js` (transport faked at the outermost edge;
  store + policy are REAL).
- Integration ACs name a seam: real collaborators, faked transport at
  the edge; RLS / policy isolation asserted through the authenticated
  client as the user, never a service-role bypass; seeded state per
  test.
- Mock only true externals — never the behaviour under test.
- No `as any`; determinism (injected values, no `Date.now()` /
  `Math.random()` in asserted paths).

## Meaningfulness (mandatory)
After writing a test, prove it can fail. WHEN CALLED RED-FIRST
(pre-implementation — the store action does not exist yet), the
natural failure IS the proof: run the test, observe it fail for the
RIGHT reason (the failure names the MISSING seam behaviour — e.g.
`store.shareSession is not a function`), not a harness defect. Do NOT
implement the action in this pass; close on "authored + proven red for
the right reason + mode recorded". The green suite is the caller's
downstream job.