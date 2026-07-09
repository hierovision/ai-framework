---
slug: feat-shared-sessions
title: Let a user share individual focus sessions with other users (read-only)
status: approved
created: 2026-07-04
revised: [2026-07-04]
---

# Plan: feat-shared-sessions

## Goal / Approach

Allow a focus-session owner to mark a session as shared with one or more
specific other users (read-only). Sharing is per-session and opt-in; an
unshared session is private to its owner. RLS enforces privacy: the owner
can read/write their sessions; a sharee can read only sessions explicitly
shared with them.

## Acceptance Criteria

1. A `shared_sessions` table records per-session share grants with an
   owner_id and a sharee_id — `npm run test` exits 0.
2. The RLS SELECT policy scopes reads so the owner sees their own
   sessions and a sharee sees only sessions explicitly shared with them
   (never every user's shared rows) — `npm run test` exits 0.
3. No `as any`; no service-role bypass in client code — `npm run lint`
   exits 0.
4. The full verification suite exits 0 in sequence —
   `npm run type-check && npm run lint && npm run test` exits 0.

## Files to Modify

- `db/schema.sql` — add `shared_sessions` table + per-user RLS SELECT
  policy scoping reads to `owner_id = auth.uid()` OR an explicit share
  row `sharee_id = auth.uid()`.
- `src/stores/sessions.ts` — add `shareSession(sessionId, shareeId)`
  action inserting a `shared_sessions` row.

## Scope

### Included

- `shared_sessions` table + scoped RLS SELECT policy.
- `shareSession` store action.

### Excluded

- Bulk sharing; public/unauthenticated sharing links.
- A "shared with me" list view (separate feature `feat-shared-inbox`).
- Write/delete grants on shared sessions (sharee is read-only).

## Schema / Type Impacts

- New table `shared_sessions(id uuid, owner_id uuid, sharee_id uuid,
  session_id uuid, created_at timestamptz)`.
- Generated types (`types/database.types.ts`) regenerate via
  `npm run db:types` after the schema change — do not hand-edit.
- RLS policy on `shared_sessions`: SELECT where
  `owner_id = auth.uid() OR sharee_id = auth.uid()`.

## Verification

- npm run type-check
- npm run lint
- npm run test

## Open Questions

- None.

## History

- 2026-07-04 plan drafted and approved.