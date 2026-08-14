# Stack: vue-supabase (validating-ui concerns)

## Contents

- Vue dev-mode warning shapes are runtime defects
- The v-for string-ref crash class (worked example)
- Leave-transition teardown trap + layer mapping
- Project-side override pattern (pt-style)

## Vue dev-mode warning shapes are runtime defects

On a dev-server e2e gate (pt-style: `VITE_E2E_TEST=true yarn dev`), Vue
emits `[Vue warn]:` console **warnings** that production builds strip.
Two shapes are runtime defects, not noise — the validating-ui net must
block them (they only surface at the dev-server gate):

- `[Vue warn]: Unhandled error during execution of component event handler`
- `[Vue warn]: Unhandled error during execution of transition hook`

An unhandled error in an event handler or `@after-leave`/transition hook
often aborts teardown code **after** it: in the incident, the throw in a
dialog's close handler aborted `handleDialogClosed` before `reset()`,
leaving stale form state — a state no assertion on the open dialog
catches. The journey-completeness rule exists for this: exercise the
close path, assert console-clean after the close transition completes.

## The v-for string-ref crash class (worked example)

`ref<InstanceType<X> | null>` inside a `v-for` compiles clean and lies at
runtime: Vue 3 collects string refs in a `v-for` into an **array**, so
`ref.value?.stopPreview()` passes `?.` (the array is truthy) and throws
`TypeError: ... is not a function`. Invisible to `vue-tsc` and lint;
unreachable unless a journey closes the dialog with the edit form open.

Incident shape (pt): parent calls an exposed method via a template ref;
the ref binds the wrong runtime shape. Fix pattern: **function refs**
(`:ref="el => { phaseFormEditRef = el as InstanceType<typeof PhaseForm> | null }"`
— Vue nulls them on unmount, no array semantics) or typed ref arrays.

Expected natural red in the validating-ui eval: `Expected no console
errors, but found 4` (three `[Vue warn]: Unhandled error during
execution of component event handler/transition hook` + one more) —
teardown crashes must be proven red-first like any AC.

## Leave-transition teardown trap + layer mapping

Component-test harnesses (e.g. vitest-browser iframes) may never
complete Vuetify `VDialog` leave transitions (`@after-leave` never
fires; content never unmounts), making teardown crashes unreachable at
the component layer. The layer mapping when this bites:

- **Component seam (structural proxy)**: pin the mechanism at the
  nearest callable API — e.g. call `stopAllPreviews()` directly with the
  edit form open (fast, deterministic, no transitions). Pre-fix it
  throws the literal `TypeError: phaseFormEditRef.value?.stopPreview is
  not a function`.
- **Journey (real browser)**: the full user flow (upload → save →
  reopen → delete phase sound → save → close) with the console net — a
  real browser completes transitions and the pageerror/warnings fire
  exactly as the user saw.

This is the structural-proxy doctrine: when the harness cannot run the
teardown path, cover the mechanism at the nearest callable API and the
full flow at the journey layer. Both layers proved red-first in the
incident.

## Project-side override pattern (pt-style)

A vue-supabase project wires the stack-agnostic harness via its local
overrides (no library change):

- Dev server: `--target http://localhost:3001` (pt's e2e webServer runs
  `VITE_E2E_TEST=true yarn dev --port 3001 --mode test`).
- Auth: Playwright storageState from the project auth fixture
  (`e2e/auth.setup.ts` → storage state JSON) via `--auth-fixture`.
- Allowlist: `.opencode/smoke-allowlist.json` at the project root —
  dated + justified entries only; e.g. a known-benign dev-tool hint gets
  a dated entry naming its source, never a bare `console.error` pattern.
- Journey modules: `<project>/.opencode/smoke/<plan-slug>.journey.mjs`,
  reusing the project's e2e spec selectors (role/accessible-name).
- Vision opt-in: `VALIDATING_UI_VISION=1` (advisory minimax-m3 pass over
  the archived screenshot; default off — human handoff owns visual
  sign-off).