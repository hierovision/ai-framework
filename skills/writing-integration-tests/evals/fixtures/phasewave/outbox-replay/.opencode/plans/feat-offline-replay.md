---
slug: feat-offline-replay
title: Replay queued session mutations to the client in order on reconnect
status: approved
created: 2026-07-06
revised: [2026-07-06]
---

# Plan: feat-offline-replay

## Goal / Approach

While offline, session mutations queue in the outbox; on reconnect,
`sync` replays every queued mutation to the supabase client in the
order they were queued, then clears the outbox. The behaviour lives at
the outbox + client seam (a real outbox, a faked transport at the
outermost boundary), so this is an integration test, not a unit test of
the queue data structure.

## Acceptance Criteria

1. While offline, `startOffline` queues each session mutation to the
   outbox (the pending count rises per mutation) — `npm run test`.
2. On reconnect, `sync` replays **all** queued mutations to the client
   in the order they were queued — `npm run test`.
3. After replay, the outbox is empty (every queued mutation flushed,
   none dropped) — `npm run test`.
4. The full verification suite exits 0 in sequence —
   `npm run type-check && npm run lint && npm run test` exits 0.
5. The meaningfulness check exits 0 — `npm run meaningfulness` (the
   authored test is red on the broken outbox that drops mutations,
   green on the fixed outbox).

## Files to Modify

- `tests/outbox.test.js` — new; the integration test for the seam.

## Scope

### Included

- Replay-all-in-order assertion through the faked transport.
- Outbox-empty-after-replay assertion.

### Excluded

- Persistence to IndexedDB (the real app persists; the runnable fixture
  uses an in-memory queue — persistence is a separate concern).
- Conflict handling / idempotency keys on replay (separate feature
  `feat-offline-conflict`).
- A unit test of the queue data structure (that is
  `writing-unit-tests`).

## Schema / Type Impacts

None. `focus_sessions` schema is unchanged; this plan adds a test.

## Verification

- npm run type-check
- npm run lint
- npm run test
- npm run meaningfulness

## Open Questions

- None.

## History

- 2026-07-06 plan drafted and approved.
