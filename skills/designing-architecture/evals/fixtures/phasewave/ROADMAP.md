# Phasewave Roadmap

> Last triaged: 2026-07-04 · Rubric: impact-urgency

## Priority order (open)

1. `feat-offline-queue` (9) — PhaseTimer store queues session mutations while offline; sync on reconnect.
2. `feat-focus-playlist` (6) — Sequence multiple timers into a playlist with auto-advance.

## Features

| ID | Title | Impact | Urgency | Score | Status | Sources | Notes |
|---|---|---|---|---|---|---|---|
| feat-offline-queue | Queue timer session events while offline, sync on reconnect | 3 | 3 | 9 | open | pasted, roadmap | existing store mutates supabase directly; needs IndexedDB queue + conflict handling |
| feat-focus-playlist | Chain timers into a playlist with auto-advance | 2 | 3 | 6 | open | pasted | depends on focusTimer store; no schema change |

## Done

| ID | Title | Closed | Notes |
|---|---|---|---|
| feat-notifications | Local notifications on phase/activity completion | 2026-06-28 | shipped |