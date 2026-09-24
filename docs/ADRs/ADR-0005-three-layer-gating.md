# ADR-0005: Three-layer eval gating (pre-commit / pre-push / required PR check)

## Status: accepted 2026-09-19

## Context

Behavioral evals are the framework's regression gate, but a single CI-only
gate pushes every mistake to the PR and pays model cost to discover it;
pure-local gates alone would let untested changes reach the PR. RM-003
needed the gate split so each layer pays for what it is good at.

## Decision

Three layers, in escalation order:

1. **Pre-commit (hermetic, local):** validators and offline verifiers —
   shape, syntax, closed-`expect` schema. No model, no network, seconds.
2. **Advisory pre-push (local, model-bearing):** the changed-skill canaries
   run locally before push; advisory, because a local lane is not the CI
   lane and the developer may reasonably defer.
3. **Required PR check (CI):** `eval-per-change.yml` matrix (one canary per
   changed skill) + the weekly full suite as the coverage backstop. A red
   canary blocks merge.

Fail-fast is `false` during the shakedown phase (one run reports all legs);
it flips back to `true` after two consecutive fully-green CI runs.

## Consequences

- Cheap mistakes die cheaply; model cost is spent where the signal is real.
- The layers' model/text truth lives in `reference/three-layer-gating.md`
  and `reference/per-change-eval-sla.md` — this ADR records the decision,
  not the volatile details.

## Sources

- `.opencode/plans/rm-003.md` (pass 4, 2026-09-19)
- `reference/three-layer-gating.md`; `reference/per-change-eval-sla.md`
- `.github/workflows/eval-per-change.yml`, `.github/workflows/ci.yml`
