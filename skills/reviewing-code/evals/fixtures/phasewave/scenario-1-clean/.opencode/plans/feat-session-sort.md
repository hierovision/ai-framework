---
slug: feat-session-sort
title: Show most recent focus sessions first in the recent-sessions view
status: approved
created: 2026-07-02
revised: [2026-07-02]
---

# Plan: feat-session-sort

## Goal / Approach

Show the user's most recent focus sessions at the top of the "recent
sessions" view, newest-first, so the latest work is immediately visible
without scrolling. Naive approach: `getTodaySessions` sorts rows by
`started_at` descending; the display renders rows in the order the list
module returns (no re-ordering in the display layer).

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

- A chronological oldest-first timeline view (separate feature
  `feat-timeline-chronological` — the recent-sessions view is newest-
  first by design, not chronological).
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
- 2026-07-11 implemented: `getTodaySessions` sorts by `started_at`
  descending; `formatSessionList` renders order unchanged. Red evidence
  (red-first, pre-implementation): the session-list test run before any
  source edit failed with `getTodaySessions is not defined` (the sort
  function was not yet written) — the failure names the missing
  behaviour; the display test failed with `expected descending, got
  ascending` (the list returned ascending because the sort was absent).
  Coverage-gate outcome: rebalance — none needed (both AC tests landed
  at the unit layer against pure list/display modules, the right layer);
  expand — no high-value gap found beyond the AC set (the sort has no
  error path or boundary the ACs didn't name). type-check + lint + test
  green (all exit 0).