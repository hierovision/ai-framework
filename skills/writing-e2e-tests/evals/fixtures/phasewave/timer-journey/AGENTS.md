# Project rules — Phasewave (timer-journey slice)

## Stack
`vue-supabase` — Vue 3 + TypeScript + Pinia + Vuetify 3, Supabase
(Postgres + Auth + RLS), Playwright (e2e). Progressive Web App
(offline-capable, service worker).

## Verification commands (what the verify stage runs)
- Type check: `npm run type-check`
- Lint: `npm run lint`
- e2e: `npm run e2e` (real browser — see deferral note below)
- Structural spec verifier: `npm run test`

In this harness a real browser is NOT available, so `npm run e2e` is
deferred and `npm run test` runs the STRUCTURAL verifier
(`scripts/verify-spec.js`) that parses `e2e/timer.spec.ts` and fails
objectively on the e2e discipline violations below. Real-browser
execution is a deferred validation.

## E2E conventions
- One journey per spec. `e2e/timer.spec.ts` is the spec file.
- Selectors by **role / accessible name / data-testid** (in that
  preference order): `getByRole`, `getByLabelText`, `getByTestId`,
  `getByText`. NOT bare CSS selectors (`.locator('.btn')`,
  `page.$('.foo')`) — CSS tied to markup/classes breaks on the next
  refactor and bypasses the accessibility check role selectors give.
- Waits on **conditions and selectors**, NEVER `waitForTimeout`.
  `expect(locator).toBeVisible()` / `getByRole(...).click()` poll on a
  condition and settle when the UI catches up. `waitForTimeout` sleeps
  and masks flakiness — it is a `debugging-test-failures` class 4
  patient authored into the suite.
- Authenticated session via the **auth fixture**
  (`e2e/fixtures/auth.ts`), NOT by replaying the login UI in every test.
  Replaying login per test is slow and couples every journey to the
  auth flow. Import `{ test, expect }` from the fixture and use the
  `authedPage` fixture.
- Assertions on **user-observable outcomes** (visible text, visible
  indicators), not implementation state. `await expect(...).toBeVisible()`
  — web-first assertions MUST be awaited (a bare `expect(...).toBeVisible()`
  without `await` does not actually wait and is a no-op flake).
- Trace on failure: `playwright.config.ts` sets `trace: 'retain-on-
  failure'`; do not override to `'off'`.

## Meaningfulness (structural, real browser deferred)
The structural verifier checks the spec asserts on user-observable
outcomes via awaited web-first assertions — assertions that WOULD go red
if the guarded UI behaviour broke. Real-browser red-on-broken is the
deferred validation (evals.json notes).

## Conventions
- No `as any`; no `waitForTimeout`; no `Math.random()` / `Date.now()` in
  data paths the test asserts against (determinism).
