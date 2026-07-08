# Stack: vue-supabase (e2e-testing concerns)

Read this when Step 3 of the authoring pass detects the project stack is
`vue-supabase` (Vue 3 + TypeScript + Pinia + Vuetify 3, Supabase
Postgres + Auth + RLS, Playwright). This file is *e2e-testing-time* —
the conventions you apply when authoring Playwright specs for user
journeys — and is the complement of the unit-time reference at
[../../writing-unit-tests/references/stacks/vue-supabase.md](../../writing-unit-tests/references/stacks/vue-supabase.md)
and the integration-time reference at
[../../writing-integration-tests/references/stacks/vue-supabase.md](../../writing-integration-tests/references/stacks/vue-supabase.md).
Project specifics come from the project's rules file (`AGENTS.md` /
`.opencode/agents.md`); this file holds the stack-wide e2e concerns.

If the project declares a different stack, do not read this file — read
the matching `references/stacks/<stack>.md`. If no matching reference
exists, proceed generically and flag the gap in the handoff.

## Contents

- Selector discipline (role / accessible name / testid)
- Condition waits, never `waitForTimeout`
- Auth-fixture session setup
- PWA / offline testing via `context.setOffline`
- Service-worker caching caveats
- Trace on failure
- Where this stack trips an e2e pass

## Selector discipline (role / accessible name / testid)

- Prefer `getByRole` / `getByLabelText` / `getByTestId` / `getByText`
  over CSS selectors. Vuetify 3 components expose roles and accessible
  names; use them. `getByRole('button', { name: /place order/i })`
  survives a refactor that swaps the button's classes or nesting; a CSS
  selector tied to `.v-btn--variant-tonal` breaks on the next Vuetify
  release.
- If no role or accessible name is available for an element the journey
  must target, add a `data-testid` to the component rather than reaching
  for a CSS class. A testid is a stable contract; a class name is an
  implementation detail.
- CSS selectors are acceptable only for layout assertions where a role
  does not exist (`toHaveCSS` on a specific element) — never for
  finding the element to interact with.

## Condition waits, never `waitForTimeout`

- `await expect(locator).toBeVisible()` / `await page.waitForSelector(...)`
  poll on a condition and settle when the UI catches up. A test using
  these that fails is failing because the condition never became true —
  investigate the condition, not the wait.
- `await page.waitForTimeout(<ms>)` does **not** wait on anything — it
  sleeps. In an e2e it is the prime `debugging-test-failures` class 4
  suspect: it passes when the machine is fast enough and fails when CI
  is slow. Replace the fixed timeout with a condition wait on the actual
  UI state the test depends on. Do not lengthen the timeout — that
  hides the flake for one more CI cycle.
- A test that "passes locally, fails in CI" almost always has a
`waitForTimeout` or an unwaited async update in its path. Reproduce by
rerunning under `playwright test --repeat-each=10` or by throttling
CPU; the discriminating experiment is the rerun, not a longer sleep.

## Auth-fixture session setup

Supabase auth is a JWT in localStorage. Replay it once via a fixture,
not per test:

- Build a fixture that grants an authenticated page: `context.addInitScript`
  that seeds `supabase.auth.token` (or `test.use({ storageState })`
  pointing at a saved storage state). Import `{ test, expect }` from the
  fixture in every spec.
- A spec that fills a password field and clicks "sign in" is authoring
  the auth flow, not the journey under test — it couples every journey
  to auth and burns run time. Set up the session in the fixture; assert
  the journey, not the login.
- For multi-user journeys (user A acts, user B observes), seed two
  storage states and run two contexts — do not log out and back in
  inside one journey.

## PWA / offline testing via `context.setOffline`

- Drive the browser offline with `await context.setOffline(true)` and
  back online with `await context.setOffline(false)` — a real network
  toggle at the Playwright context boundary. Do NOT mock the network
  inside the app (a faked `navigator.onLine`, a stubbed fetch); mocking
  the network inside the app vacates the offline behaviour under test.
- After `setOffline`, wait on the **visible indicator** the app shows
  when offline/queued — `await expect(getByText(/queued|offline/i)).toBeVisible()`
  — never a fixed timeout. The service worker and the offline queue
  settle asynchronously; the indicator is the condition, the timeout is
  the flake.
- Reconnect with `setOffline(false)` and wait on the synced/online
  indicator. Assert the user-observable outcome (the indicator), not the
  outbox internals.

## Service-worker caching caveats

- The service worker may serve a cached page on reload while offline —
  this is correct PWA behaviour, not a bug. If the journey asserts a
  fresh network state, reload and wait on the indicator rather than
  assuming the cache state.
- A service worker registration is asynchronous; on first load it may
  not yet be active. `await expect(...)` on the app's offline-ready
  signal rather than assuming the SW is installed after `goto`.
- `context.setOffline` toggles the network for the whole context,
  including the SW's fetches. An SW that falls back to cache while
  offline should still serve the app shell — assert the app renders,
  not that the network request was made.

## Trace on failure

- `playwright.config.ts` sets `trace: 'retain-on-failure'` (or
  `'on-first-retry'`). Do not override to `'off'`. A failing e2e is a
  perception problem — the trace (DOM snapshots at each step, network
  log, console errors) is the discriminating evidence for
  `debugging-test-failures` Step 4.
- Open a trace with `npx playwright show-trace <path>`. The trace at
  the failing step shows the DOM the assertion actually saw — often
  different from the DOM assumed.
- Console errors in the trace are a frequent root cause: a Supabase
  query throwing, a Vuetify component failing to register an icon
  (renders silently blank), a Pinia action rejecting. The assertion
  fails downstream; the error is upstream in the console log.

## Where this stack trips an e2e pass

- **`waitForTimeout` in a flaky e2e.** Passes locally, fails on slow
  CI. Replace with a condition wait; do not lengthen.
- **Bare CSS selectors tied to Vuetify classes.** Break on the next
  Vuetify release; use role/accessible-name/testid.
- **Replaying the login UI in every test.** Slow, coupled to auth; use
  an auth fixture.
- **A bare `expect(locator).toBeVisible()` without `await`.** A no-op
  flake that passes regardless of UI state. `await expect(...)`.
- **Mocking the network inside the app for an offline journey.**
  Vacates the offline behaviour; use `context.setOffline`.
- **Trace disabled.** A failing e2e produces no evidence; leave trace
  on.

Each of these is a flaky-or-wrong-layer test dressed up as coverage —
the selector/wait discipline (Step 5) and the right-layer check (Step 2)
catch them before they reach the suite.
