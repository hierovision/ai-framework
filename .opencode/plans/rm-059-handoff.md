# Handoff — RM-059 (watchdog STALLED false positive on active generation)

Working artifact (AGENTS.md rule 4). Consumed by the next session, which
dispatches a design pass. This file is only the **brief**; the plan is the
architect's deliverable — the design decisions (fix site, factoring, drills,
plan filename) are the architect's to make, not stated here.

## Goal

`scripts/watch_agent.py` must stop reporting `STALLED` for a subagent whose
session is demonstrably mid-generation, while still firing `STALLED` on genuine
silence.

Row success measure: *"watch_agent no longer reports STALLED for a subagent
whose session stream is demonstrably advancing — proven by a drill where a
generating child keeps reporting OK/active."*

**Row:** RM-059 — Now, score 6, status `open`. Detail:
`docs/roadmap-detail/RM-059.md`.

## Why it matters

The verdict's reader (the orchestrating agent) treats `STALLED` as "the child is
dead or wedged" and intervenes — killing or resuming a live run destroys paid
progress and wastes the dispatch. Siblings: RM-047 (completion predicates,
shipped), RM-049 (blocking-wait on completed children, open).

## Evidence

A generating child reads `STALLED` while its session stream is advancing:

- 2026-10-12/13 — the RM-056 design and implement passes both printed STALLED
  while `stream.jsonl` timestamps advanced.
- 2026-10-16 — a design dispatch read STALLED with a 273 KB growing stream and a
  30 s-fresh heartbeat.

RM-022 records that opencode publishes no tool durations, so no duration signal
is available.

## Receiver

- **`architect`** — a design pass (`designing-architecture`, contract
  `design-consult`) producing ONE plan artifact in `.opencode/plans/`.
- Then **`implementer`** (`implement-handoff`); the implementer may dispatch
  `test-writer` for red-first drills (depth ≤ 2 permits it).
- Not `curator` (triage), `reviewer` (independent verdict), `debugger` (no
  failing check to diagnose), or `planner` (read-only leaf).

## Constraints for the design

- Change the verdict's inputs only; do not fold in RM-049's blocking-wait work.
- Preserve the RM-058 seam: `scripts/observe_completion.py` consumes completion
  predicates from `watch_agent` and never the stall verdict — do not invert it.
- Drills must prove the false positive is gone **and** that true stalls still
  fire (AGENTS.md rule 5 — never weaken the net).
- Land via a branch/PR; the PR carries the RM-059 row flip, the horizon/counter
  updates, the detail-file update, and plan retirement (rule 6).
- The design pass branches off `main`, commits only its plan (+ any reference
  edit), and does not touch `docs/ROADMAP.md`.
- Scratch in `.scratch/rm-059-design/` only. Report contract `design-consult`.
