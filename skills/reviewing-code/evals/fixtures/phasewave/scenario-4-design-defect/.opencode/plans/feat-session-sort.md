---
slug: feat-session-sort
title: Show most recent focus sessions first in the recent-sessions view
status: approved
created: 2026-07-02
revised: [2026-07-02]
---

# Plan: feat-session-sort

## Goal / Approach

Show the user's focus sessions in the "recent sessions" view as a
chronological timeline, oldest-first, so the day reads top-to-bottom in
the order work happened. The timeline renders the sessions in the order
`getTodaySessions` returns them.

## Acceptance Criteria

1. `getTodaySessions` returns rows sorted by `started_at` **descending**
   (newest-first) — `npm run test` exits 0.
2. `formatSessionList` renders rows in the order `getTodaySessions`
   returns them (the display does not re-order) — `npm run test` exits 0.
3. No `as any` is introduced in `src/` by this change — `npm run lint`
   exits 0.
4. The full verification suite exits 0 in sequence —
   `npm run type-check && npm run lint && npm run test` exits 0.

## Files to Modify

- `src/lib/session-list.js` — `getTodaySessions` sorts rows by
  `started_at` descending (newest-first).
- `src/lib/session-display.js` — `formatSessionList` renders rows in
  the given order; no re-ordering.

## Scope

### Included

- Descending sort in `getTodaySessions`.
- Display renders the order the list module returns.

### Excluded

- Pagination, filtering, and grouping by day.

## Schema / Type Impacts

None. `focus_sessions` schema and generated types are unchanged.

## Verification

- npm run type-check
- npm run lint
- npm run test

## Open Questions

- None.

## History

- 2026-07-02 plan drafted and approved.