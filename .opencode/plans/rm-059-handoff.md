# Handoff — RM-059 (watchdog STALLED false positive on active generation) → architect design pass

Working artifact (AGENTS.md rule 4). Consumed by the next session, which
dispatches an **architect** design pass. Not a plan — the plan this brief asks
for is the architect's deliverable.

## Dispatch

```
python3 scripts/dispatch_agent.py --agent architect \
  --prompt-file <this brief, adapted> --contract design-consult \
  --heartbeat .scratch/rm-059-design/heartbeat.log \
  --timeout 2400 --out .scratch/rm-059-design/result.md
```

## Goal

`scripts/watch_agent.py` must stop reporting `STALLED` for a subagent whose
session is demonstrably mid-generation, while still firing `STALLED` on genuine
silence. Row success measure: *"watch_agent no longer reports STALLED for a
subagent whose session stream is demonstrably advancing — proven by a drill
where a generating child keeps reporting OK/active."*

**Row:** RM-059 — Now, score 6, status `open`. Detail:
`docs/roadmap-detail/RM-059.md`. Siblings: RM-047 (completion predicates,
shipped), RM-049 (blocking-wait on completed children, open — do not fold in).

## Evidence

- Live 2026-10-12/13: the RM-056 design and implement passes both printed
  `STALLED` while `stream.jsonl` timestamps advanced.
- Live 2026-10-16: a design dispatch read STALLED with a 273 KB growing stream
  and a 30 s-fresh heartbeat.
- RM-022 records that opencode publishes no tool durations, so there is no
  duration signal to lean on.

## The defect, precisely

`scripts/watch_agent.py::verdict()` (≈ lines 311–350):

```
s_age = age_of(an["last_ms"])          # newest session PART timestamp
live_age = min([hb_age, s_age])        # freshest of heartbeat / part
... live_age > stall_seconds  ->  "STALLED"
```

`an["last_ms"]` is the newest *part* timestamp. During a long model call
opencode emits nothing between `step-start` and `step-finish`, so `last_ms`
freezes, `live_age` grows, and the verdict prints STALLED while the model is
working. A trailing `step-start` is the tell.

## The proven predicate (already shipped — mirror and factor it)

RM-058 shipped the right signal on 2026-10-16:
`scripts/observe_completion.py::_assistant_step_closed(parts)` — an **unclosed
assistant step** (a `step-start` with no following `step-finish`) means a model
call is mid-generation. It exists; it is module-local and already tested.

**Design decision to make:** factor that predicate into `scripts/watch_agent.py`
(one implementation, two consumers) and use it in `verdict()` so an **open step
suppresses STALLED** (report `OK` / long-call), while a *closed* step with a
stale everything still stalls. Consider the **RM-058 D6 seam**: `observe_completion`
deliberately imports only completion predicates from `watch_agent` and never
`watch_agent.verdict`; the factoring must not invert that — decide and record
whether `observe_completion` re-exports/imports the shared predicate.

## Fix direction (from the detail)

Gate `STALLED` on **state deltas, not quiet gaps**: require that *nothing in the
session stream changed of any kind* across the observation window before STALLED
may emit (not merely no tool calls). The open-step signal is the concrete,
already-proven form of that rule. Keep `BLOCKING` (in-flight call) and `DEAD`
semantics; this row changes only what may drive `STALLED`.

## Red-first drills (`scripts/test_watch_agent.py` — 13 cases today)

1. Fabricated advancing events at cadence across the window → verdict stays
   non-STALLED.
2. Fabricated **true silence** over the same window → STALLED still fires
   (over-suppression guard).
3. Open `step-start` + stale `last_ms` → **not** STALLED (the regression this
   row exists for) — the mirror of the RM-058 AC3 gate case.

## Verification & closure

- `python3 scripts/test_watch_agent.py` green; `scripts/test_session_guard.py`
  and `scripts/test_observe_completion.py` unaffected.
- Live smoke: a real dispatch whose stream advances does not flap to STALLED.
- **In-PR closure (AGENTS.md rule 6):** RM-059 row → `done` with evidence, the
  horizon strip + counters, `docs/roadmap-detail/RM-059.md`, and retirement of
  the plan the architect produces. Never weaken the watchdog net — true stalls
  must still fire (rule 5).
- On landing, the detail's interim handling (labelling stall alerts by *evidence
  basis*) is retired.

## Constraints for the architect

- Revise the `verdict` inputs only; do not fold in RM-049's blocking-wait work.
- Branch off `main`; commit the plan artifact + any reference edit; do NOT push,
  do NOT touch `main` or `docs/ROADMAP.md`.
- Scratch in `.scratch/rm-059-design/` only. Do NOT dispatch subagents.
- Report contract `design-consult` — the final report carries the `Consult
  outcome` marker (an explicit skip with a one-line reason is valid).
