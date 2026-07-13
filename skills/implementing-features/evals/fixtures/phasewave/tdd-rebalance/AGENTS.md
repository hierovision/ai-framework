# Project rules — Phasewave (audit-log slice)

## Stack
`vue-supabase` — Vue 3 + Pinia + Supabase (Postgres + Auth + RLS),
Vitest (unit), Playwright (e2e). Runnable fixture stubs are CommonJS
`.js` so verify scripts execute in-process.

## Plan artifact
- `plans_dir: .opencode/plans/`
- Plan filename convention: `<slug>.md`.

## Verification commands (what the verify stage runs)
- Type check: `npm run type-check`
- Lint: `npm run lint`
- Unit/integration: `npm run test`

## Conventions
- Lib modules live under `src/lib/<feature>.js`; stores under
  `src/stores/<name>.js`; the faked supabase transport lives at
  `src/supabase/fake-client.js` (transport faked at the outermost edge).
- Unit tests live in `tests/<module>.test.js`, plain Node scripts that
  `assert` on the behaviour under test and exit `0`/`1`. `npm run test`
  discovers `tests/**/*.test.js` (an empty suite is red).
- Real collaborators, faked transport at the outermost boundary. RLS /
  policy isolation is asserted through the authenticated client as the
  user, never a service-role bypass. Seeded state per test.
- Mock only true externals — never the behaviour under test. A test
  that fakes the seam the behaviour lives in asserts against a stub that
  enforces nothing (vacant).
- No `as any`; no `waitForTimeout` in e2e; determinism (injected values,
  no `Date.now()` / `Math.random()` in asserted data paths).