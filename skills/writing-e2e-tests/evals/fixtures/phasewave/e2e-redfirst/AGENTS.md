# Project rules — Phasewave (export-journey slice)

## Stack
`vue-supabase` — Vue 3 + TypeScript + Pinia + Vuetify 3, Supabase
(Postgres + Auth + RLS), Playwright (e2e). Progressive Web App.

## Verification commands (what the verify stage runs)
- Type check: `npm run type-check`
- Lint: `npm run lint`
- e2e: `npm run e2e` (real browser — DEFERRED in this harness)
- Structural spec verifier: `npm run test`

In this harness a real browser is NOT available, so `npm run e2e` is
deferred and `npm run test` runs the STRUCTURAL verifier
(`scripts/verify-spec.js`) that parses every `e2e/*.spec.ts` and fails
objectively on the e2e discipline violations below. Real-browser
execution is a deferred validation.

## E2E conventions
- One journey per spec. `e2e/export.spec.ts` is this slice's journey.
- Selectors by **role / accessible name / data-testid** (in that
  preference order): `getByRole`, `getByLabelText`, `getByTestId`,
  `getByText`. NOT bare CSS selectors (`.locator('.btn')`,
  `page.$('.foo')`).
- Waits on **conditions and selectors**, NEVER `waitForTimeout`.
- Authenticated session via the **auth fixture**
  (`e2e/fixtures/auth.ts`), NOT by replaying the login UI. Import
  `{ test, expect }` from the fixture and use the `authedPage` fixture.
- Assertions on **user-observable outcomes** (visible text, visible
  indicators). `await expect(...).toBeVisible()` — web-first assertions
  MUST be awaited.
- Trace on failure: `playwright.config.ts` sets `trace: 'retain-on-
  failure'`; do not override to `'off'`.

## Meaningfulness (mode-branched; real browser deferred)
- **Coverage-expansion / standalone mode** (code already exists): break
  the guarded journey, restore, see green (real browser; structural
  verifier for the proxy).
- **Red-first mode** (THIS slice — pre-implementation): the export
  screen/route does NOT exist yet, so a real-browser run would navigate
  to `/export` and go red (route/modal absent). The natural failure IS
  the proof: confirm it names the missing UI behaviour (the absent
  `/export` route / the un-resolving "Export sessions" button), not a
  spec-harness defect. Close on "spec authored + proven red for the
  right reason + mode recorded"; defer the real-browser red as the SAME
  kind of deferral already in place. Do NOT implement the route.

## Conventions
- No `as any`; no `waitForTimeout`; no `Math.random()` / `Date.now()` in
  data paths the test asserts against (determinism).