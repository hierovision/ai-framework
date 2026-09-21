---
slug: pending-task
title: Live word count for the note editor
status: approved
created: 2026-09-21
revised: [2026-09-21]
---

# Plan: pending-task

## Goal / Approach

Show a live word count under the note editor. Two pure helpers: `countWords`
counts whitespace-separated tokens, and `renderSummary` formats the count for
display. No I/O, no store, no DOM beyond the string returned.

## Acceptance Criteria

1. `countWords("hello world")` returns `2` — `npm run test:unit`.
2. `countWords("")` and `countWords("   ")` return `0` — `npm run test:unit`.
3. `countWords(42)` throws a `TypeError` (non-string is a programmer error,
   not a silent `0`) — `npm run test:unit`.
4. `renderSummary("hello world")` returns `"2 words"` — `npm run test:e2e`.
5. No `as any` / `FIXME` / `TBD` introduced under `src/` — `npm run lint`
   exits 0.
6. All four gates exit 0 in sequence — `npm run type-check && npm run lint
   && npm run test:unit && npm run test:e2e`.

## Files to Modify

- `src/lib/word-count.js` — new; exports `countWords(text)`.
- `src/lib/summary.js` — new; exports `renderSummary(text)`.

## Scope

### Included

- `countWords` and `renderSummary` with the empty/whitespace and non-string
  edge cases.

### Excluded

- The word-frequency histogram — separate feature `feat-word-frequency`.
- Refactoring the neighbouring `src/lib/note-meta.js` helper.
- Persisting counts to Supabase.

## Schema / Type Impacts

None.

## Verification

- npm run type-check
- npm run lint
- npm run test:unit
- npm run test:e2e

## Open Questions

- None.

## History

- 2026-09-21 plan drafted and approved.
