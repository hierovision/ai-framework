---
slug: feat-export-journey
title: Export the completed focus sessions to a downloadable CSV via a UI journey
status: approved
created: 2026-07-11
revised: [2026-07-11]
---

# Plan: feat-export-journey

## Goal / Approach

A user journey: an authenticated user opens the export screen, clicks
"Export sessions", and observes a CSV download triggered. The behaviour
is only observable as a user journey through the real UI: the export
route, the button, and the download are all user-observable. (This plan
is approved but the export screen/route is NOT YET IMPLEMENTED — author
the e2e spec first, red-first against the pre-feature app.)

## Acceptance Criteria

1. An authenticated user navigating to `/export` sees the "Export
   sessions" button become visible — `npm run e2e` (real browser);
   structural verifier passes on the spec discipline in the harness.
2. Clicking "Export sessions" starts a download the user observes
   (a download event / visible "Export ready" indicator) — `npm run e2e`
   (real browser); structural verifier passes.

## Files to Modify

- `e2e/export.spec.ts` — new; one journey mapping AC1→navigate+button
  visible, AC2→click+download observed. Auth via the auth fixture.

## Scope

### Included

- The e2e spec for the export journey (role selectors, condition
  waits, auth fixture, one journey per spec).

### Excluded

- The export route/component implementation itself (that is an
  `implementing-features` pass — this plan authors the spec only,
  red-first against the pre-feature app where `/export` is absent).
- CSV column ordering / format assertions (`feat-export-columns`).
- Bulk export of other users' sessions (`feat-export-admin`).

## Schema / Type Impacts

None.

## Verification

- npm run type-check
- npm run lint
- npm run test   (structural verifier — real browser deferred)
- npm run e2e    (deferred: real browser not available in the harness)

## Open Questions

- None.

## History

- 2026-07-11 plan drafted and approved (export screen not yet implemented).