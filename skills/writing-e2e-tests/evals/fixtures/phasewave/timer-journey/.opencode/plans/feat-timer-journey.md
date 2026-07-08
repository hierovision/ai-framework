---
slug: feat-timer-journey
title: E2E journey — start and complete a focus timer as an authenticated user
status: approved
created: 2026-07-07
revised: [2026-07-07]
---

# Plan: feat-timer-journey

## Goal / Approach

Verify the primary focus-timer journey through the real UI: an
authenticated user starts a timer, sees the remaining-time indicator,
completes the timer, and sees the completed state. One journey per spec.
The behaviour is only observable as a user journey through the real UI,
so this is an e2e test (Playwright), not a unit or integration test.

## Acceptance Criteria

1. An authenticated user can start a focus timer and the remaining-time
   indicator becomes visible — `npm run e2e` in `e2e/timer.spec.ts`
   (click the start button by role, assert the remaining indicator is
   visible via a condition wait).
2. The user can complete a running timer and the completed-state
   indicator becomes visible — `npm run e2e` in `e2e/timer.spec.ts`
   (click the complete button by role, assert the completed indicator is
   visible).
3. The authenticated session is set up via the e2e auth fixture
   (`e2e/fixtures/auth.ts`), NOT by replaying the login UI in the test
   body — structural verifier (`npm run test`).
4. No `waitForTimeout`; waits on Playwright conditions and selectors
   (`expect(...).toBeVisible()`, `getByRole`) — structural verifier.
5. Selectors by role / accessible name / data-testid (in that preference
   order), not bare CSS — structural verifier.

## Files to Modify

- `e2e/timer.spec.ts` — new; the e2e journey spec.

## Scope

### Included

- The start -> remaining -> complete -> completed journey.
- Auth via the pre-provided auth fixture.
- One journey per spec.

### Excluded

- The offline/PWA journey (separate spec, `feat-offline-journey`).
- A unit test of the timer store (that is `writing-unit-tests`).
- An integration test of the store + client seam (that is
  `writing-integration-tests`).

## Schema / Type Impacts

None. This plan adds an e2e spec.

## Verification

- npm run type-check
- npm run lint
- npm run e2e

## Open Questions

- None.

## History

- 2026-07-07 plan drafted and approved.
