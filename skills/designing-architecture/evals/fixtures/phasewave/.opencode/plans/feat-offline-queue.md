---
slug: feat-offline-queue
title: Queue timer session events while offline; sync on reconnect
status: draft
created: 2026-07-02
revised: [2026-07-02]
---

# Plan: feat-offline-queue

## Goal / Approach

Let the focus timer store capture session mutations to IndexedDB while
offline and replay them to Supabase on reconnect. Naive first pass: queue
inserts and updates with a monotonic local sequence, replay in order on
reconnect.

## Acceptance Criteria

1. User can start a timer while offline and it persists locally.
2. On reconnect, queued sessions sync to Supabase.

## Scope

Included: store changes, IndexedDB queue.
Excluded: conflict resolution beyond last-write-wins.

## Schema / Type Impacts

None expected.

## Verification

- npm run test && npm run e2e

## History

- 2026-07-02 initial draft.