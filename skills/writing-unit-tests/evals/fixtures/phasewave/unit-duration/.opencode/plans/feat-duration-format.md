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
Pure function in `src/lib/duration.js` — no I/O, no store, no DOM.

## Acceptance Criteria

1. `formatDuration(0)` returns `"00:00"` — `npm run test`.
2. `formatDuration(65)` returns `"01:05"` (MM:SS, both fields zero-padded)
   — `npm run test`.
3. `formatDuration(3661)` returns `"01:01:01"` (HH:MM:SS once seconds >=
   3600) — `npm run test`.
4. `formatDuration(-5)` throws a `RangeError` (negative input is a
   programmer error, not a silent `00:00`) — `npm run test`.
5. No `as any` introduced in `src/` — `npm run lint` exits 0.
6. The full verification suite exits 0 in sequence —
   `npm run type-check && npm run lint && npm run test` exits 0.

## Files to Modify

- `src/lib/duration.js` — new; exports `formatDuration(totalSeconds)`.

## Scope

### Included

- `formatDuration` pure function with MM:SS / HH:MM:SS formatting and the
  negative-input `RangeError`.

### Excluded

- Pluralized labels ("1 hour 1 minute") — separate feature
  `feat-duration-labels`.
- Sub-second precision / millisecond display.
- Wiring the formatter into the timer component (implement pass for this
  item ships the function only; the component reads it next item).

## Schema / Type Impacts

None. No table or generated-type change.

## Verification

- npm run type-check
- npm run lint
- npm run test
- npm run meaningfulness

## Open Questions

- None.

## History

- 2026-07-05 plan drafted and approved.
