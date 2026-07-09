---
slug: feat-offline-queue
title: Queue focus-session mutations through an offline outbox
status: approved
created: 2026-07-03
revised: [2026-07-03]
---

# Plan: feat-offline-queue

## Goal / Approach

Route focus-session mutations through a persistent offline outbox so the
timer can start/stop while offline and replay on reconnect. Queued
entries persist (localStorage), not in memory. Pinia store owns the
mutation path; components never call the supabase client directly for
these mutations.

## Acceptance Criteria

1. `start()` queues an insert via `queueSession` instead of calling
   `supabase.from('focus_sessions').insert` directly — `npm run test`
   exits 0.
2. Queued entries persist to localStorage (not held in memory only) —
   `npm run test` exits 0.
3. No `as any` is introduced in `src/` by this change — `npm run lint`
   exits 0.
4. The full verification suite exits 0 in sequence —
   `npm run type-check && npm run lint && npm run test` exits 0.

## Files to Modify

- `src/lib/offline-queue.ts` — new; exports `queueSession`, persists
  pending inserts to localStorage.
- `src/stores/focus-timer.ts` — `start()` calls `queueSession(insert)`
  and removes the direct `supabase.from(...).insert` call in `start()`.

## Scope

### Included

- `queueSession` + localStorage persistence in `src/lib/offline-queue.ts`.
- `start()` routing through the queue in the focus-timer store.

### Excluded

- Replay-on-reconnect wiring (deferred to `feat-offline-replay`).
- Any schema or generated-types change — `focus_sessions` is unchanged;
  the offline queue is a client-side concern, not a database change.
- A "last synced at" column on `focus_sessions`.

## Schema / Type Impacts

None. `focus_sessions` schema and generated types are unchanged by this
plan; any schema touch is out of scope (see Excluded).

## Verification

- npm run type-check
- npm run lint
- npm run test

## Open Questions

- None.

## History

- 2026-07-03 plan drafted and approved.