---
slug: feat-offline-queue
title: Queue timer session events while offline; sync on reconnect
status: approved
created: 2026-07-05
revised: [2026-07-05]
---

# Plan: feat-offline-queue

## Goal / Approach

Let the focus timer store capture session mutations into a local
persistence layer when the client is offline, then replay them to
Supabase on reconnect. Naive first pass: a `queueSession` helper that
appends the insert payload to an IndexedDB / localStorage queue with a
monotonic local sequence; the store's `start()` routes through that
helper instead of a direct `supabase.from('focus_sessions').insert`.

## Acceptance Criteria

1. `src/lib/offline-queue.ts` exists, exports a named `queueSession`
   function, and persists entries via `localStorage` or `IndexedDB`
   (not an in-memory array) — `npm run type-check` exits 0.
2. `focus-timer.ts`'s `start()` action calls `queueSession(...)` and no
   longer issues a direct `supabase.from('focus_sessions').insert(...)`;
   the queued insert survives a reload — `npm run test` exits 0.
3. No `as any` is introduced in `src/` by this change — `npm run lint`
   exits 0.
4. All three verification commands exit 0 in sequence —
   `npm run type-check && npm run lint && npm run test` exits 0.

## Files to Modify

- `src/lib/offline-queue.ts` — new; the offline queue module exposes
  `queueSession(insert: FocusSessionInsert)` that appends the insert to
  a `localStorage` / `IndexedDB` queue and returns a queued-entry
  descriptor.
- `src/stores/focus-timer.ts` — modify the `start()` action so it calls
  `queueSession(insert)` in place of the direct supabase insert; the
  direct `supabase.from('focus_sessions').insert(...)` line in `start()`
  is removed (the replay path is the queue's responsibility, wired in a
  later pass).

## Scope

### Included

- The `queueSession` helper module and its persistence (localStorage or
  IndexedDB — pick one in this pass).
- Routing `start()`'s insert through `queueSession(...)` and removing the
  direct supabase insert from `start()`.

### Excluded

- Conflict resolution beyond last-write-wins on replay.
- Service worker installation or background-sync wiring (the queue
  persists across reloads; auto-replay on reconnect is a separate pass).
- Queuing mutations from other stores (`complete()`, `abandon()`).
  Only the `start()` insert is routed in this plan.
- Session CSV export (a separate requested feature; do not build here).
- Auto-advance playlist linking between sessions (feat-focus-playlist).

## Schema / Type Impacts

None. The queue is client-side; `focus_sessions` schema and the
generated `types/database.types.ts` are unchanged in this pass.

## Verification

- npm run type-check
- npm run lint
- npm run test

## Open Questions

- localStorage vs IndexedDB for the queue store? Default: localStorage
  for the v1 since payload is small and the API is synchronous; revisit
  if queuing grows beyond session inserts.

## History

- 2026-07-05 plan drafted and approved.