---
slug: feat-offline-journey
title: E2E journey — start a timer offline, reconnect, see it sync
status: approved
created: 2026-07-07
revised: [2026-07-07]
---

# Plan: feat-offline-journey

## Goal / Approach

Verify the PWA offline journey through the real UI: an authenticated
user goes offline, starts a timer (the mutation queues to the outbox,
the UI shows an offline/queued indicator), comes back online, and sees
the queued mutation sync (a synced indicator). The journey drives the
browser offline via `context.setOffline` — a real network toggle, not a
mock. One journey per spec.

## Acceptance Criteria

1. While offline (`context.setOffline(true)`), the user can start a
   timer and the offline/queued indicator becomes visible —
   `npm run e2e` in `e2e/offline.spec.ts`.
2. On reconnect (`context.setOffline(false)`), the queued mutation syncs
   and the synced indicator becomes visible — `npm run e2e` in
   `e2e/offline.spec.ts`.
3. The journey drives the browser offline via `context.setOffline`
   (real offline, not a mocked network) — structural verifier.
4. Authenticated session via the auth fixture, not login UI replay —
   structural verifier.
5. No `waitForTimeout`; waits on conditions/selectors — structural
   verifier. (Service workers settle asynchronously — wait on the
   visible indicator, never a fixed timeout.)
6. Selectors by role / accessible name / data-testid, not bare CSS —
   structural verifier.

## Files to Modify

- `e2e/offline.spec.ts` — new; the offline e2e journey spec.

## Scope

### Included

- The offline -> queued -> reconnect -> synced journey via
  `context.setOffline`.
- Auth via the pre-provided auth fixture.
- One journey per spec.

### Excluded

- The online timer journey (`feat-timer-journey`).
- A unit test of the outbox queue (that is `writing-unit-tests`).
- An integration test of the outbox + client replay seam (that is
  `writing-integration-tests` — this e2e verifies the user-observable
  journey, not the seam in isolation).

## Schema / Type Impacts

None.

## Verification

- npm run type-check
- npm run lint
- npm run e2e

## Open Questions

- None.

## History

- 2026-07-07 plan drafted and approved.
