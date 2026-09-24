# ADR-0004: Canary selection principle for per-change eval gating

## Status: accepted 2026-09-19

## Context

RM-003's per-change gating maps changed files → skills and runs one eval per
skill as a CI matrix. Which single eval represents a skill matters: a wrong
pick runs an eval unrelated to the change (weak gate) or a known-risky one
(noisy gate). The first provisional picks (alphabetical first-5) were
replaced during RM-003 pass 4.

## Decision

Each skill's manifest declares a `default: true` canary — the eval chosen
for the per-change gate, picked by signal (highest-surface, real-path
behavior), not position. Skill-level explicit `default` markers are the
mechanism; the five core skills not yet marked fall back to their first
eval as the documented interim. When an eval proves brittle in shakedown
(e.g. authoring-skills#1), migrate the canary pick to a stable eval with
harvested fixtures rather than weakening the assertion. Harness changes run
the fixed six-core set; relevance-list selection is deleted.

## Consequences

- The gate is auditable: one file (`evals.json`) owns each skill's canary.
- Canary migration is a deliberate, recorded act — never a quiet re-pick.

## Sources

- `.opencode/plans/rm-003.md` pass 4 (2026-09-19)
- `reference/per-change-eval-sla.md` (selection rules)
- `scripts/changed-files-to-skills.py`
