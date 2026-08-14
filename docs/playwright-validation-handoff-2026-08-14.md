# Handoff: Playwright validation step — console/pageerror net and teardown-path coverage

Date: 2026-08-14
Source incident: PhaseTimer (pt) — "deleting the phase sound crashed the dialog close"
Status: recommendations for the in-flight Playwright validation step; no code changes in this repo.

---

## 1. The incident (one paragraph)

In `pt`, deleting a phase sound and saving threw `Uncaught TypeError: phaseFormEditRef.value?.stopPreview is not a function` on every dialog close with a phase edit form open. The delete *visually* worked, so it was reported as "errors that should not be present" rather than a functional break. Root cause: `phaseFormEditRef` was a **string template ref inside a `v-for`**; Vue 3 collects string refs in v-for into an **array**, so `ref.value.stopPreview` was `undefined` — the `?.` passed (array is truthy) and the call threw. The throw aborted `handleDialogClosed` **before `reset()`**, leaving stale form state. Same ref also crashed Escape-with-edit-open and delete-the-edited-phase. It was invisible to `vue-tsc` (the `ref<InstanceType<typeof PhaseForm> | null>` annotation is a lie Vue overwrites at runtime), invisible to lint, and unreachable by the existing suite because no journey or component test closed the dialog with the edit form open.

Evidence (verbatim): stack `at Proxy.stopAllPreviews (PhaseList.vue:332:27) at handleDialogClosed (ActivityDialog.vue:269:23) ... at onAfterLeave`; debug dump `edit= Proxy(Array) editKeys= [] editingIndex= 0`; pre-fix e2e failure `Expected no console errors, but found 4` (three `[Vue warn]: Unhandled error during execution of component event handler/transition hook` + one more).

## 2. What the current skill library lacks

- `writing-e2e-tests/SKILL.md` — **no mention of console errors, warnings, or pageerrors**. Monitoring helpers existed in the project (`setupConsoleErrorMonitoring`/`expectNoConsoleErrors`) but only ~5 of 20+ specs opted in, and the journeys that used them never walked the crashing path (one asserted with the dialog still open; the other never opened the phase edit form).
- `reviewing-code` — no checklist item for the v-for/string-ref gotcha.
- `debugging-test-failures` — no documented technique for console-visible defects.

## 3. Recommendations for the validation step (the meat)

### R1 — Default-on global net, not opt-in per spec
The single highest-leverage change. A global fixture (test.beforeEach on the page) that collects `page.on('pageerror')` + `page.on('console')` for types `error` **and** `warning`, and fails the test at the end unless every message matches a dated, justified allowlist. The opt-in pattern is the failure mode this incident exposed: helpers existed, coverage didn't reach the path, and nothing forced it. Default-on means *any* journey is a net for stray crashes.
- Allowlist discipline: entries must be dated + justified (e.g. `Vue Devtools` download hint); no blanket `console.error` suppression.
- In dev-mode runs, Vue's `[Vue warn]: Unhandled error during execution of component event handler` / `...transition hook` are **runtime defects, not noise** — treat them as failures (they silently vanish in production builds, so the dev-server e2e gate is the only place they surface).

### R2 — Journey-completeness rule: a journey that opens a dialog/form must exercise its close
The exact gap: the AC6 journey asserted console-clean **with the dialog still open**; the close path (after-leave → teardown) never ran. Rule: before the console assertion, a journey must either close what it opened (including closing with forms in an open/edited state) or explicitly justify why the close path is out of scope. Assert console-clean **after the close transition completes**, not mid-journey.

### R3 — Teardown-path red-first proof
The validation step's own proof discipline: teardown crashes must be proven red-first like any AC. In the incident, the new journey failed pre-fix with `Expected no console errors, but found 4` — that is the natural failure naming the missing behaviour (crash-free close). Document it as the expected red in the eval/skill example.

### R4 — Layer mapping when harnesses can't run teardown paths (structural-proxy doctrine, real example)
Documented environment limitation hit during the fix: the vitest-browser **iframe never completes VDialog leave transitions**, so `@after-leave` teardown crashes are unreachable at the component-test layer (the dialog DOM stalls mid-leave forever; we verified `v-dialog--active` was gone but content never unmounted). The workable layering:
- **Component seam**: pin the mechanism at the nearest callable API — `PhaseList` exposes `stopAllPreviews()`; a component test calling it with the edit form open failed pre-fix with the literal `TypeError: phaseFormEditRef.value?.stopPreview is not a function` and passes post-fix (fast, deterministic, no transitions).
- **Journey**: the full user flow (upload → save → reopen → delete phase sound → save → close) as an e2e journey with the net from R1 — real browser completes transitions, and the pageerror/warnings fire exactly as the user saw.
This is a concrete instance of the skill's existing "real-browser, deferred to a structural proxy without one" doctrine — worth citing in the step as a worked example.

### R5 — The static blind spot is not a Playwright problem, but the step should name it
`ref<InstanceType<X> | null>` inside a `v-for` compiles clean and lies at runtime (Vue collects string refs in v-for into arrays). No lint/type rule catches it. The fix pattern: **function refs** (`:ref="el => { phaseFormEditRef = el as InstanceType<typeof PhaseForm> | null }"` — Vue nulls them on unmount, no array semantics). Add a one-line checklist item to `reviewing-code`: "string template refs inside v-for collect into arrays — use function refs or typed ref arrays; when a parent calls an exposed method via ref, the ref must bind to the component instance." This prevents the class; the validation step catches its runtime symptoms.

### R6 — Troubleshooting tooling: standalone repro script as the first-line diagnostic
Before theorizing about a console-visible defect, run a standalone Playwright script (library API, `chromium.launch` + `storageState` from the project auth fixture, `page.on('pageerror')` + `page.on('console')`, walk the exact user flow, print captures). This produced ground truth in one run (stack + `edit= Proxy(Array)`) in minutes, where component-harness reproduction was misdirecting. Suggest documenting this technique in `debugging-test-failures` ("reproduce via scripted browser flow with error listeners before hypothesizing").

### R7 — Optional: ship an eval for the step
The repo has per-skill `evals.json`; a natural eval: a fixture spec whose journey closes a dialog with an open inline form and asserts the net fires on a synthetic teardown error, plus a passing variant. Ensures the step's own net is red-capable (it will catch its own regressions).

## 4. Acceptance criteria for the step (testable)

1. A journey that leaves a dialog open mid-assertion fails review unless the close path is explicitly out of scope (R2).
2. A synthetic `pageerror` or console error in any journey fails the run with the message text in the report (R1, default-on).
3. Allowlist entries are dated and justified; the default allowlist contains no `console.error` matches (R1).
4. The step documents the layer mapping from R4 (harness seam vs journey) with the worked example.
5. `reviewing-code` gains the v-for/string-ref checklist item (R5) — the prevention net.

## 5. Files referenced (in pt, for reproduction)

- Crash site: `pt/src/components/PhaseList.vue` (`stopAllPreviews` ~line 331; ref declaration line 187; template line 47)
- Handler aborted pre-reset: `pt/src/components/ActivityDialog.vue` (`handleDialogClosed` line 267)
- Regression tests: `pt/src/components/PhaseList.test.ts` (component seam), `pt/e2e/activity-sound.spec.ts` (journey, 3rd test)
- Repro script: `/tmp/opencode/repro-phase-sound-delete.cjs`
- Existing (insufficient) net: `pt/e2e/test-helpers.ts` `setupConsoleErrorMonitoring` / `expectNoConsoleErrors`
