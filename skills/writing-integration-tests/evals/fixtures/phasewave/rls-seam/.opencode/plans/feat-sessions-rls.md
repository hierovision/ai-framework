---
slug: feat-sessions-rls
title: Isolate focus_sessions per user via RLS — assert wrong user gets zero rows
status: approved
created: 2026-07-06
revised: [2026-07-06]
---

# Plan: feat-sessions-rls

## Goal / Approach

Guarantee that a user querying `focus_sessions` through the store only
ever sees their own rows: user B receives zero of user A's sessions.
The isolation is enforced by the `focus_sessions owner only` Row-Level
Security policy in `db/schema.sql` (`auth.uid() = user_id`), triggered
when the supabase client issues an authenticated `select`. The store is
a thin passthrough; the behaviour lives at the DB + client seam, so this
is an integration test (real store, faked transport at the outermost
boundary), not a unit test.

## Acceptance Criteria

1. As user A (auth uid `user-a`), `loadSessions` returns only A's rows
   and zero of B's — `npm run test`.
2. As user B (auth uid `user-b`), `loadSessions` returns only B's rows
   and **zero of A's** (the wrong-user-gets-zero-rows shape) —
   `npm run test`.
3. The isolation is asserted through the authenticated client as the
   user, never through a service-role bypass (service-role in the
   isolation assertion mocks away the security behaviour under test) —
   `npm run test` (the test does not pass `serviceRole: true` to assert
   isolation; seeding is pre-provided, no bypass needed).
4. The full verification suite exits 0 in sequence —
   `npm run type-check && npm run lint && npm run test` exits 0.
5. The meaningfulness check exits 0 — `npm run meaningfulness` (the
   authored test is red on the leaky broken policy, green on the fixed
   per-user policy).

## Files to Modify

- `tests/rls.test.js` — new; the integration test for the seam.

## Scope

### Included

- RLS isolation assertion through the authenticated client as user A
  and user B (wrong user gets zero rows).
- Seeded state: A's sessions and B's sessions pre-provided.

### Excluded

- Service-role seeding inside the test (seeding is pre-provided).
- Policy edits — the policy in `db/policies.js` is the system under
  test; do not change it to make the test pass.
- A unit test of the store's assignment logic (that is
  `writing-unit-tests`).

## Schema / Type Impacts

None for this test item. The `focus_sessions` policy already exists in
`db/schema.sql`; this plan adds a test, not a schema change.

## Verification

- npm run type-check
- npm run lint
- npm run test
- npm run meaningfulness

## Open Questions

- None.

## History

- 2026-07-06 plan drafted and approved.
