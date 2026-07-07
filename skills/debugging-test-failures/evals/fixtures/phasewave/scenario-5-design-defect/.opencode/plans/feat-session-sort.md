---
slug: feat-session-sort
title: Show today's focus sessions chronologically in the timeline view
status: approved
created: 2026-07-02
revised: [2026-07-02]
---

# Plan: feat-session-sort

## Goal / Approach

The "today" timeline view shows the user's focus sessions in
**chronological order, oldest-first**, so the day reads top-to-bottom
from the first session of the day to the most recent. Naive approach:
`getTodaySessions` sorts rows by `started_at`; the display renders rows
in the order the list module returns (no re-ordering in the display
layer).

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
  `started_at`.
- `src/lib/session-display.js` — `formatSessionList` renders rows in the
  given order; no re-ordering.

## Scope

### Included

- Sorting in `getTodaySessions`.
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
