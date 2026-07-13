---
slug: feat-pomodoro-label
title: Label pomodoro intervals as Work or Break by index parity
status: approved
created: 2026-07-11
revised: [2026-07-11]
---

# Plan: feat-pomodoro-label

## Goal / Approach

Label a pomodoro interval by its zero-based index: even indices are
"Work", odd indices are "Break". A pure `pomodoroLabel(index)` helper
in `src/lib/pomodoro-label.js`. No I/O, no store, no DOM. (This plan is
approved but the module is NOT YET IMPLEMENTED — author the unit tests
first, red-first.)

## Acceptance Criteria

1. `pomodoroLabel(0)` returns `"Work"` (the first interval is a work
   interval) — `npm run test`.
2. `pomodoroLabel(1)` returns `"Break"` (index-1 is a break) —
   `npm run test`.
3. `pomodoroLabel(3)` returns `"Break"` (odd indices are breaks) —
   `npm run test`.
4. No `as any` introduced in `src/` — `npm run lint` exits 0.
5. The full verification suite exits 0 in sequence —
   `npm run type-check && npm run lint && npm run test` exits 0.

## Files to Modify

- `src/lib/pomodoro-label.js` — new; exports `pomodoroLabel(index)`.

## Scope

### Included

- The `pomodoroLabel` pure function with the even-Work / odd-Break
  labelling.

### Excluded

- Long-break after N work intervals (`feat-pomodoro-long-break`).
- Localized labels ("Travail" / "Pause") — `feat-pomodoro-label-i18n`.
- Persisting the label on the session row (`feat-pomodoro-persist`).

## Schema / Type Impacts

None.

## Verification

- npm run type-check
- npm run lint
- npm run test

## Open Questions

- None.

## History

- 2026-07-11 plan drafted and approved (module not yet implemented).