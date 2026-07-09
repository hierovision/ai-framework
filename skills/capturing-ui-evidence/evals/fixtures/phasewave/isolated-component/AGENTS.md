# Project rules — Phasewave (capture, isolated-component slice)

## Stack
`vue-supabase` — Vue 3 + TypeScript + Pinia + Vuetify 3, Supabase, Playwright.

## Verification commands (what the capture closure runs)
- Objective capture self-check (fake CDP, browser-free): `npm run test`
- Evidence schema validator (path arg): `npm run validate -- <evidence.json>`
- Real-browser capture (DEFERRED in this harness): `npm run capture`

In this harness a real browser is NOT available, so `npm run capture` is
deferred (prints a note and exits 0). The OBJECTIVE check is `npm run test`,
which imports the skill's capture.mjs `runCapture`, feeds it the bundled fake
chromium + canned CDP/DOM data, drives a **component-mode** capture against
`harness/index.html`, and asserts the artifact is schema-valid + curated +
matched-styles populated with source locations. Real screenshot + real computed
CSS against the live harness is a DEFERRED validation — documented in
evals.json notes, not silently skipped.

## Capture discipline (this slice — isolated-component)
- Bot modes supported by the harness; THIS slice exercises **component mode**:
  an isolated component harness (Storybook-style `harness/index.html`) loaded
  via `file://` — no dev server, no auth fixture. Use it to capture a single
  component out of app context (focus the diagnosis on the component, not
  the layout around it).
- The override demonstration in this slice is SOURCE ORDER (two `.btn` rules of
  equal specificity; the later density `<style>` block wins), vs the real-app
  slice's specificity override. Same artifact shape either way.
- Targets resolve by role / accessible name / data-testid in that preference
  order; a bare-CSS selector is a last resort and is flagged `fragile: true`.
- Determinism: animations + transitions disabled, fonts + load awaited, a
  layout-stability condition polled (never a fixed timeout), viewport +
  device scale factor pinned.

## The evidence artifact (contract)
The evidence.json SCHEMA is a CONTRACT — the single source of truth is the
skill's `references/evidence-schema.md` (link it, do not duplicate). It is
versioned (`schema_version`); a consumer that drifts detects it.

## Conventions
- No `waitForTimeout` (condition waits only). Curated computed profile — NOT
  all ~300 longhands; a `--profile full` escape hatch exists for the rare miss.