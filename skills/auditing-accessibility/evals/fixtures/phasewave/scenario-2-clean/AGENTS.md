# Project rules — Phasewave (audit, clean-page slice)

## Stack
`vue-supabase` — Vue 3 + TypeScript + Pinia + Vuetify 3, Supabase
(Postgres + Auth + RLS), Playwright. Vite dev server on port 5173.

## Verification commands (what the audit closure runs)
- Objective audit self-check (canned axe-results, browser-free): `npm run test`
- Report schema validator (path arg): `npm run validate -- <report.json>`

A real browser is NOT installed in this harness; a real axe run is DEFERRED.
The OBJECTIVE check is `npm run test` (scripts/verify-audit.js): imports the
skill's audit.mjs `runAudit`, feeds it the canned axe-results fixture for a
GENUINELY ACCESSIBLE page (axe finds nothing), and asserts a clean report —
pass, ZERO violations, ZERO severity inflated, the manual checklist STILL
present (a pass does NOT discharge manual verification), and NO manufactured
violations. Real axe is a DEFERRED validation — documented in evals.json notes.

## Audit discipline (this slice — false-positive discipline)
- A genuinely accessible page yields a CLEAN report. Do NOT manufacture a
  violation to seem thorough; do NOT inflate a nit into a blocker (reviewing-
  code false-positive discipline). Severity follows axe impact + WCAG level
  mechanically.
- The auditor is READ-ONLY: a fix never happens in the audit. The manual
  checklist is the automation ceiling — honest, not faked.

## The page (genuinely accessible — mirrored in axe-results.json)
- alt text present; labelled input; h1 then h2; sufficient contrast; skip link.