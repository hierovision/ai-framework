---
slug: feat-clip-duration
title: Clamp a clip's elapsed seconds to a per-clip budget for display
status: approved
created: 2026-07-11
revised: [2026-07-11]
---

# Plan: feat-clip-duration

## Goal / Approach

Clamp a clip's elapsed seconds to a per-clip budget so the UI never
shows a value over the budget. A pure `clipDuration(totalSeconds,
budgetSeconds)` helper in `src/lib/clip-duration.js`: under budget
returns unchanged, over budget returns the budget. The clip store
exposes the clipped value on the rendered timer.

## Acceptance Criteria

1. `clipDuration(30, 60)` returns `30` (under budget, unchanged) —
   `npm run test`.
2. `clipDuration(90, 60)` returns `60` (over budget, clamped to the
   budget) — `npm run test`.
3. The clipped remaining value is rendered in the timer UI as
   "MM:SS remaining" — manual (human eyes: start a clip that overruns,
   observe the displayed remaining never exceeds the budget label).
4. No `as any` is introduced in `src/` — `npm run lint` exits 0.
5. The full verification suite exits 0 in sequence —
   `npm run type-check && npm run lint && npm run test` exits 0.

## Files to Modify

- `src/lib/clip-duration.js` — new; exports
  `clipDuration(totalSeconds, budgetSeconds)` (pure clamp helper).
- `src/stores/clip.js` — modify `complete(...)` so it derives the
  display remaining via `clipDuration(elapsedSeconds, budgetSeconds)`
  rather than leaving it `null`.

## Scope

### Included

- The `clipDuration` pure function with the under/over-budget clamp.
- Routing `complete(...)`'s elapsed seconds through `clipDuration(...)`
  and exposing the clipped remaining.

### Excluded

- Sub-second / fractional precision (integer seconds only this pass).
- Persisting the clipped value to a table column (schema change — a
  separate managing-database-changes pass).
- A `min(budget, max(0, totalSeconds))`-style two-sided clamp (negative
  elapsed is a programmer error per the project rules, not a silent
  clamp — ACs name only the under/over-budget happy paths).

## Schema / Type Impacts

None. The clip is derived client-side; no table or generated-type
change.

## Verification

- npm run type-check
- npm run lint
- npm run test

## Open Questions

- None.

## History

- 2026-07-11 plan drafted and approved.