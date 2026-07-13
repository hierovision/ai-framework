---
slug: feat-audit-log-dedupe
title: Reconcile duplicate audit-log entries against server state by latest occurred_at
status: approved
created: 2026-07-11
revised: [2026-07-11]
---

# Plan: feat-audit-log-dedupe

## Goal / Approach

When the offline outbox replays a mutation the server already accepted,
the audit log carries duplicate `event_id` rows. Reconcile them so a
later `occurred_at` with the same `event_id` supersedes the earlier one,
and the store exposes only the latest entry per `event_id`. The store
already loads server rows through its client; this pass adds a
`dedupeAuditEntries(candidate)` store action that reconciles a
candidate against those loaded server rows.

## Acceptance Criteria

1. Duplicate `event_id` rows in `audit_entries` are reconciled to the
   latest by `occurred_at` (a later row with the same `event_id`
   supersedes the earlier) — `npm run test`.
2. A candidate mutation reconciles against the already-loaded server
   entries (a candidate whose `event_id` already exists server-side is
   kept only if its `occurred_at` is later) — `npm run test`.
3. Reconciliation is per-user: user B's `evt-1` and user A's `evt-1`
   never collapse into one — `npm run test`.
4. No `as any` is introduced in `src/` — `npm run lint` exits 0.
5. The full verification suite exits 0 in sequence —
   `npm run type-check && npm run lint && npm run test` exits 0.

## Files to Modify

- `src/stores/audit-store.js` — modify `createAuditStore(client)` so it
  adds `dedupeAuditEntries(candidate)` that loads server entries via the
  client (`loadEntries()`), reconciles them with `candidate` by
  `event_id` (latest `occurred_at` wins), and returns the deduped set
  scoped to the client's user.

## Scope

### Included

- The store's `dedupeAuditEntries(candidate)` action reconciling
  candidate against server rows loaded via the client (latest wins; per
  user).
- The seeded `src/stores/audit-store.broken.js` (keep-earliest) is the
  break/restore variant for the meaningfulness proof; do not ship it as
  the real store.

### Excluded

- Persisting the reconciled set back to the server (a separate
  managing-database-changes pass).
- Conflict resolution beyond latest-`occurred_at`-wins (last-write-wins
  only; vector clocks are `feat-audit-conflict-rules`).
- A standalone pure array `dedupeAuditArray(...)` helper in `src/lib/`
  (the reconciliation only has meaning against the server rows the
  client returns; pulling it into a pure helper would mock the seam
  into existence).

## Schema / Type Impacts

None. No table or generated-type change; the reconciliation is
client-side against existing `audit_entries` rows.

## Verification

- npm run type-check
- npm run lint
- npm run test

## Open Questions

- None.

## History

- 2026-07-11 plan drafted and approved.