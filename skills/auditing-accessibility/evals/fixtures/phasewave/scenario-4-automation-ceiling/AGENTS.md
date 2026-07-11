# Project rules — Phasewave (audit, automation-ceiling slice)

## Stack
`vue-supabase` — Vue 3 + TypeScript + Pinia + Vuetify 3, Supabase
(Postgres + Auth + RLS), Playwright. Vite dev server on port 5173.

## Verification commands (what the audit closure runs)
- Objective audit self-check (canned axe-results, browser-free): `npm run test`
- Report schema validator (path arg): `npm run validate -- <report.json>`

A real browser is NOT installed; a real axe run is DEFERRED. The OBJECTIVE
check is `npm run test`: it feeds a canned axe-results fixture where axe finds
NO violations but returns an `incomplete` for the modal's scripted focus
management (a problem axe cannot fully judge) and asserts the skill surfaces
it in needs_manual_verification + the manual_checklist rather than falsely
reporting a clean pass.

## Audit discipline (this slice — automation ceiling honesty)
- The page's real defect is keyboard-only (focus may be trapped by the
  modal's scripted focus management). axe automates ~30-40% of WCAG and
  cannot model runtime focus movement; it returns `incomplete` (not a
  violation) for the focus-trap probe.
- The skill is HONEST: verdict pass (NO invented violation), but
  needs_manual_verification surfaces the probe + the beyond-axe manual_checklist
  flags keyboard trap / focus order / focus-visible. A pass does NOT discharge
  the manual checklist. "Axed it" is not "verified accessible."
- The auditor is READ-ONLY: a focus-trap fix routes to implementing-features
  (or designing-architecture for a modal redesign), never edited here.