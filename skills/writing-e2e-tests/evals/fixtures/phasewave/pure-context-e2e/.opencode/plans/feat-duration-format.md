---
slug: feat-duration-format
title: Format focus-session durations as zero-padded MM:SS / HH:MM:SS
status: approved
created: 2026-07-05
revised: [2026-07-05]
---

# Plan: feat-duration-format

## Goal / Approach

Display a focus session's elapsed seconds as a human-readable, zero-padded
timer string: `MM:SS` under one hour, `HH:MM:SS` at one hour and above.
Pure function in `src/lib/duration.js` — no I/O, no store, no DOM, no
collaborators.

## Acceptance Criteria

1. `formatDuration(0)` returns `"00:00"` — `npm run test`.
2. `formatDuration(65)` returns `"01:05"` — `npm run test`.
3. `formatDuration(3661)` returns `"01:01:01"` — `npm run test`.
4. `formatDuration(-5)` throws a `RangeError` — `npm run test`.

## Files to Modify

- `src/lib/duration.js` — exports `formatDuration(totalSeconds)`.

## Scope

### Included

- `formatDuration` pure function.

### Excluded

- Wiring the formatter into the timer component (separate item).
- A database or store change — none.

## Schema / Type Impacts

None.

## Verification

- npm run type-check
- npm run lint
- npm run test

## Open Questions

- None.

## History

- 2026-07-05 plan drafted and approved.
