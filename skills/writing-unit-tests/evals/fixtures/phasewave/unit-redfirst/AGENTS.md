# Project rules — Phasewave (pomodoro-label slice)

## Stack
`vue-supabase` — Vue 3 + Pinia + Supabase + Vitest (unit). Runnable
fixture stubs are plain CommonJS `.js` under `src/lib/`.

## Verification commands
- Type check: `npm run type-check`
- Lint: `npm run lint`
- Unit/integration: `npm run test`

## Conventions
- Lib modules live under `src/lib/<feature>.js`.
- Unit tests live in `tests/<module>.test.js`, plain Node scripts that
  `assert` on the module under test, exit `0` on pass and `1` on
  failure. `npm run test` discovers `tests/**/*.test.js` (an empty
  suite is red).
- Mock only true externals — never the module under test.
- No `as any`; no `Date.now()` / `Math.random()` in asserted data paths.

## Meaningfulness (mandatory)
After writing a test, prove it can fail. WHEN CALLED RED-FIRST
(pre-implementation — the module does not exist yet), the natural
failure IS the proof: run the test, observe it fail for the RIGHT
reason (the failure names the MISSING behaviour — e.g. a
`MODULE_NOT_FOUND` for `src/lib/<feature>`), not a harness defect. Do
NOT implement the module in this pass; close the pass on "authored +
proven red for the right reason + mode recorded". The green suite is
the caller's downstream job.