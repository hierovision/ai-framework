# Project rules — Phasewave (capture, determinism/curation slice)

## Stack
`vue-supabase` — Vue 3 + TypeScript + Pinia + Vuetify 3, Supabase, Playwright.

## Verification commands (what the capture closure runs)
- Objective capture self-check (fake CDP, browser-free): `npm run test`
- Evidence schema validator (path arg): `npm run validate -- <evidence.json>`
- Structural determinism grep (no live browser): `npm run determinism`
- Real-browser capture (DEFERRED in this harness): `npm run capture`

In this harness a real browser is NOT available, so `npm run capture` is
deferred (prints a note and exits 0). The OBJECTIVE checks are `npm run test`
(drives runCapture TWICE against the bundled fake CDP and asserts the two
artifacts are BYTE-EQUAL — determinism — plus the bare-CSS target is flagged
fragile + curated profile) and `npm run determinism` (structural grep of the
skill's capture.mjs for the determinism knobs: animations frozen, fonts+
load awaited as conditions, no `waitForTimeout`, viewport + scale pinned).
Real screenshot + real computed CSS against the live harness is a DEFERRED
validation — documented in evals.json notes, not silently skipped.

## Capture discipline (this slice — determinism/curation)
- This slice foregrounds the TWO load-bearing properties of any capture harness:
  (1) **determinism** — the same input must yield the same computed values,
  or the downstream diff is meaningless; the objective self-check runs capture
  twice and asserts byte-equal artifacts. (2) **curation** — the captured
  computed profile is a named, documented set (~80 longhands), NOT all ~300,
  so the fixer reads signal, not noise. (3) **fragility flagging** — a
  bare-CSS target (`css:.legacy-action`) is flagged `fragile: true` so the
  fixer knows the target address was a last resort.
- The harness here is a STABLE target (one authored rule, no overrides, no
  inline), so the determinism and curation checks are foregrounded rather
  than the cascade chain (exercised in the other two slices).

## The evidence artifact (contract)
The evidence.json SCHEMA is a CONTRACT — the single source of truth is the
skill's `references/evidence-schema.md` (link it, do not duplicate). It is
versioned (`schema_version`); a consumer that drifts detects it.

## Conventions
- No `waitForTimeout` (condition waits only). Curated computed profile; a
  `--profile full` escape hatch exists for the rare miss.