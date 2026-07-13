---
slug: feat-session-score
title: Derive a per-session productivity score from elapsed focus seconds
status: approved
created: 2026-07-11
revised: [2026-07-11]
---

# Plan: feat-session-score

## Goal / Approach

Display each completed focus session's elapsed seconds as a zero-to-
200 "productivity score" so the history screen can show progress at a
glance. A pure `scoreSession(totalSeconds)` helper in
`src/lib/session-score.js` (linear: 3600 s = 100 points), and the focus
timer store exposes the derived `score` on the completed session. No
I/O; the formatter is pure for now.

## Acceptance Criteria

1. `scoreSession(0)` returns `0` (no focus time scores nothing) —
   `npm run test`.
2. `scoreSession(3600)` returns `100` (one full focus hour = 100 points)
   — `npm run test`.
3. `scoreSession(7200)` returns `200` (linear: two hours = 200 points)
   — `npm run test`.
4. The completed session's `score` is rendered on the session history
   screen with a "productivity score" label — manual (human eyes: open
   the history screen, complete a session, observe the labelled score).
5. No `as any` is introduced in `src/` — `npm run lint` exits 0.
6. The full verification suite exits 0 in sequence —
   `npm run type-check && npm run lint && npm run test` exits 0.

## Files to Modify

- `src/lib/session-score.js` — new; exports
  `scoreSession(totalSeconds)` (pure, linear; the formula maps 3600 s to
  100 points).
- `src/stores/focus-timer.js` — modify `complete(...)` so it derives
  the session's `score` via `scoreSession(elapsedSeconds)` rather than
  leaving it `null`; the store exposes the derived score on the
  completed session.

## Scope

### Included

- The `scoreSession` pure function with the linear 3600->100 mapping.
- Routing `complete(...)`'s elapsed seconds through `scoreSession(...)`
  and exposing the derived `score`.

### Excluded

- Non-linear / diminishing-returns scoring curves (separate feature
  `feat-score-curves`).
- Pluralized labels ("100 points") on the score display (the history
  screen labels it; wiring is a later UI pass).
- Persisting the score to the `focus_sessions` table column (schema
  change — a separate managing-database-changes pass).
- Negative-input handling beyond what the linear formula already
  implies (no special-casing).

## Schema / Type Impacts

None. The score is derived client-side from elapsed seconds; no table
or generated-type change.

## Verification

- npm run type-check
- npm run lint
- npm run test

## Open Questions

- None.

## History

- 2026-07-11 plan drafted and approved.