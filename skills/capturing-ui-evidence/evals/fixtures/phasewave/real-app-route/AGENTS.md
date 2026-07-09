# Project rules — Phasewave (capture, real-app-route slice)

## Stack
`vue-supabase` — Vue 3 + TypeScript + Pinia + Vuetify 3, Supabase
(Postgres + Auth + RLS), Playwright. Progressive Web App
(offline-capable, service worker). Vite dev server on port 5173.

## Verification commands (what the capture closure runs)
- Objective capture self-check (fake CDP, browser-free): `npm run test`
- Evidence schema validator (path arg): `npm run validate -- <evidence.json>`
- Real-browser capture (DEFERRED in this harness): `npm run capture`

In this harness a real browser is NOT available, so `npm run capture` is
deferred (prints a note and exits 0). The OBJECTIVE check is `npm run test`,
which imports the skill's capture.mjs `runCapture`, feeds it the bundled fake
chromium + canned CDP/DOM data, drives an app-mode capture with the auth
fixture, and asserts the artifact is schema-valid + curated + matched-styles
populated with source locations. Real screenshot + real computed CSS against
the live Vite dev server is a DEFERRED validation — documented in
evals.json notes, not silently skipped.

## Capture discipline (this slice — real-app-route)
- Both modes supported by the harness; THIS slice exercises **app mode**:
  a dev-server URL + route, auth via the e2e auth-fixture pattern at
  `auth/auth.mjs` (seeds the Supabase JWT via `context.addInitScript`,
  not by replaying the login UI).
- Targets resolve by role / accessible name (label) / data-testid in that
  preference order; a bare-CSS selector is a last resort and is flagged
  `fragile: true` in the artifact so the downstream fixer knows the target
  was fragile. This slice uses `role:button[Submit]` and `testid:submit-btn`.
- Determinism: animations + transitions disabled, fonts + load awaited, a
  layout-stability condition polled (never a fixed timeout), viewport +
  device scale factor pinned.

## The evidence artifact (contract)
The evidence.json SCHEMA is a CONTRACT — the single source of truth is the
skill's `references/evidence-schema.md` (link it, do not duplicate). It is
versioned (`schema_version`); a consumer that drifts detects it.

## Conventions
- No `waitForTimeout` (condition waits only). No `Math.random()` /
  `Date.now()` in the capture path.
- Curated computed profile — NOT all ~300 longhands; the named documented
  set. A `--profile full` escape hatch exists for the rare miss.