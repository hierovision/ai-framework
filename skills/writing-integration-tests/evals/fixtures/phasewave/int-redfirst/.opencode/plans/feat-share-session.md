---
slug: feat-share-session
title: Share a focus session with a recipient user via the store + client seam
status: approved
created: 2026-07-11
revised: [2026-07-11]
---

# Plan: feat-share-session

## Goal / Approach

Let a user share one of their focus sessions with a recipient user.
The behaviour only exists at the store + client seam: the store's new
`shareSession(sessionId, recipientUid)` action drives the client to
post the share, and the recipient's subsequent read access appears as
an observable at the seam. (This plan is approved but the store action
is NOT YET IMPLEMENTED — author the integration test first, red-first.)

## Acceptance Criteria

1. `shareSession('s1', 'user-b')` as user-a posts a share so that
   user-b's `loadSessions()` includes `s1` (recipient read access
   appears at the seam) — `npm run test`.
2. A user can only share their OWN session: user-b calling
   `shareSession('s1', 'user-c')` (s1 belongs to user-a) does NOT
   grant user-c read on s1 (the share is refused at the seam) —
   `npm run test`.
3. The tested behaviour drives the REAL store through the FAKED client
   (real collaborators; faked transport at the edge); isolation is
   asserted through the authenticated client, never a service-role
   bypass — enforced by the project rules.

## Files to Modify

- `src/stores/share-store.js` — modify `createShareStore(client)` to add
  `shareSession(sessionId, recipientUid)` that posts the share via the
  client and is scope-checked to the caller's own session.

## Scope

### Included

- The store's `shareSession(sessionId, recipientUid)` action driving
  the client and the recipient-read observable at the seam.

### Excluded

- Sharing with multiple recipients at once (`feat-multi-share`).
- A standalone pure `canShare(session, user)` helper in `src/lib/` (the
  access check only has meaning at the store + client seam; pulling it
  into a pure helper would mock the seam into existence).
- Persisting share timestamps (`feat-share-audit`).

## Schema / Type Impacts

None. (In the runnable fixture the share is in-memory at the faked
transport; the real project adds a `session_shares` table — a separate
managing-database-changes pass.)

## Verification

- npm run type-check
- npm run lint
- npm run test

## Open Questions

- None.

## History

- 2026-07-11 plan drafted and approved (store action not yet implemented).