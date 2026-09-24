# ADR-0003: Typed-assertion protocol and the nature rule for eval assertions

## Status: accepted 2026-09-20

## Context

Legacy eval assertions were free-text `expected_behavior` lists graded by an
LLM or by hand — unverifiable mechanically, and unable to fail in a
deterministic CI gate. RM-003 pass 5 introduced typed assertions, and the
first CI shakedown surfaced a deeper question: what class of assertion fits
what kind of behavior?

## Decision

Two coupled rules:

1. **Typed-assertion protocol.** Every eval carries a closed-shape `expect`
   block over three classes — `action` (tool-event predicates over the
   `opencode run --format json` stream), `artifact` (a written file + key
   phrases), and `text` (a key phrase in the final response). Layer 1
   enforces the closed shape (`scripts/check_typed_evals.py`, mirrored
   hermetically by `scripts/verify.mjs`); a new or changed eval must carry
   `expect` in the same change (migrate-on-touch); ~75 legacy evals migrate
   on touch, never in bulk.
2. **The nature rule.** An assertion's class must match the behavior's
   nature: what the agent must DO → `action`; PRODUCE (a durable file) →
   `artifact`; SAY (speech, e.g. a verdict or a stop statement) → `text`.
   Demanding a file for speech (or vice versa) is an assertion defect — the
   reviewing-code verdict is SPEECH, so it asserts text, not a REVIEW.md
   artifact.

## Consequences

- Assertions are mechanically checkable and the gate is Layer-1 enforced.
- Mis-typed assertions are a migration/correction target, not a gate failure
  of the behavior itself (the reviewing-code canary was retyped artifact →
  text under this rule).

## Sources

- `.opencode/plans/rm-003.md` pass 5 (2026-09-20)
- `scripts/check_typed_evals.py` (closed-shape validator + Layer-1 gate)
- `skills/authoring-skills/references/eval-assertions.md`
