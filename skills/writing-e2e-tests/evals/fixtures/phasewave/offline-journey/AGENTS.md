# Project rules — Phasewave (offline-journey slice)

## Stack
`vue-supabase` — Vue 3 + TypeScript + Pinia + Vuetify 3, Supabase
(Postgres + Auth + RLS), Playwright (e2e). Progressive Web App
(offline-capable, service worker).

## Verification commands (what the verify stage runs)
- Type check: `npm run type-check`
- Lint: `npm run lint`
- e2e: `npm run e2e` (real browser — deferred in this harness)
- Structural spec verifier: `npm run test` (runs with `--offline`,
  requiring `context.setOffline` usage)

Real-browser execution is DEFERRED in this harness; `npm run test` runs
the STRUCTURAL verifier that parses `e2e/offline.spec.ts` and fails
objectively on the e2e discipline violations. Real-browser
red-on-broken is the deferred validation (evals.json notes).

## E2E conventions (shared with the timer journey)
- One journey per spec. `e2e/offline.spec.ts` is the spec file.
- Selectors by **role / accessible name / data-testid** (preference
  order): `getByRole`, `getByLabelText`, `getByTestId`, `getByText`.
  NOT bare CSS selectors.
- Waits on **conditions and selectors**, NEVER `waitForTimeout`.
- Authenticated session via the **auth fixture**
  (`e2e/fixtures/auth.ts`), NOT by replaying the login UI. Import
  `{ test, expect }` from the fixture and use `authedPage`.
- Assertions on **user-observable outcomes**; web-first assertions
  MUST be awaited.
- Trace on failure: `playwright.config.ts` sets `trace: 'retain-on-
  failure'`; do not override to `'off'`.

## PWA / offline conventions (this journey)
- Drive the browser offline with `await context.setOffline(true)` and
  back online with `await context.setOffline(false)` — a real network
  toggle at the Playwright context boundary, NOT a mocked network layer
  inside the app. Mocking the network inside the app vacates the
  offline behaviour under test.
- Service workers settle asynchronously: after `setOffline`, wait on
  the **visible indicator** (`expect(getByText(/offline|queued/i)).toBeVisible()`),
  never a fixed timeout. A `waitForTimeout` here is the canonical
  `debugging-test-failures` class 4 flake — it passes when the SW
  happens to settle fast enough and fails on slow CI.
- Service-worker caching caveat: the SW may serve a cached page on
  reload while offline. If the journey asserts a fresh network state,
  reload and wait on the indicator rather than assuming the cache
  state.

## Meaningfulness (structural, real browser deferred)
The structural verifier checks the spec asserts on user-observable
outcomes via awaited web-first assertions AND drives the browser
offline via `context.setOffline`. Real-browser red-on-broken is the
deferred validation.

## Conventions
- No `as any`; no `waitForTimeout`; no `Math.random()` / `Date.now()` in
  data paths the test asserts against (determinism).
