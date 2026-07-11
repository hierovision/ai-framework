# Project rules — Phasewave (audit, violations-present slice)

## Stack
`vue-supabase` — Vue 3 + TypeScript + Pinia + Vuetify 3, Supabase
(Postgres + Auth + RLS), Playwright. Vite dev server on port 5173.

## Verification commands (what the audit closure runs)
- Objective audit self-check (canned axe-results, browser-free): `npm run test`
- Report schema validator (path arg): `npm run validate -- <report.json>`

In this harness a real browser (Playwright/chromium + axe-core runtime) is NOT
installed, so a real axe run against the live dev server is DEFERRED. The
OBJECTIVE check is `npm run test` (scripts/verify-audit.js), which imports the
skill's audit.mjs `runAudit`, feeds it the bundled canned axe-results fixture
(an exact representation of what axe WOULD return on harness/index.html), and
asserts the emitted report.json is schema-valid + every planted violation is
caught at the right severity + WCAG SC + verdict violations-found + routed to
the right sibling + ZERO source edits. Real axe run is a DEFERRED validation
— documented in evals.json notes, not silently skipped.

## Audit discipline (this slice)
- Proactive audit: the skill FINDS violations and reports them with severity +
  WCAG SC + a fix pointer + routing, then STOPs. It is READ-ONLY on the code
  — a fix routes to correcting-ui (contrast/spacing) or implementing-features
  (markup/role/label) or designing-architecture (redesign).
- WCAG scoping: default WCAG 2.2 AA; AAA on request. Every rule runs for the
  chosen level; NO rule excluded by default (debugging-test-failures cardinal
  rule — never green by suppressing a rule).
- Honesty about automation's ceiling: axe automates ~30-40% of WCAG; a
  beyond-axe manual checklist (keyboard trap, focus order, focus-visible,
  reduced-motion, live-regions, form-error association) is ALWAYS emitted and
  OUTSTANDING, never discharged by a pass verdict.

## Planted violations (for a future real-axe run, mirrored in axe-results.json)
- `img alt=""` -> image-alt (blocker, SC 1.1.1)
- `.btn` #9e9e9e on #f5f5f5 -> color-contrast (major, SC 1.4.3)
- `#search` no `<label>` -> label (blocker, SC 1.3.1/3.3.2/4.1.2)
- `h1` then `h3` -> heading-order (minor, SC 1.3.1)

## Conventions
- No `waitForTimeout` (condition waits only). No `Math.random()` /
  `Date.now()` in the audit path. Viewport + device scale factor pinned.