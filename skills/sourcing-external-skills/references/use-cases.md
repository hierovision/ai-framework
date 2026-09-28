# Use cases — the inventory this skill serves

Resolved against this skill's own directory — not the project's.
The library rule: evals must cover ≥80% of this inventory, so every
use case listed here carries its eval mapping. Read this file when
scoping a screening pass that doesn't obviously fit a listed case —
if the pass serves a need not listed here, extend this inventory and
the eval set in the same change.

## Contents

- The inventory (with eval mappings)
- Coverage math
- Boundary notes

## The inventory

| # | Use case | Eval |
|---|---|---|
| 1 | Screen a single skill package with an embedded injection attempt (prompt-injection treated as data; the critical finding overrides the allow-list license → reject/security-gate) | eval 1 |
| 2 | Screen a candidate whose scripts require the security gate (credential/beacon findings → reject/security-gate; no execution) | eval 2 |
| 3 | Batch-screen several candidates → register completeness: per-license verdicts (unlicensed → inspire; CC-BY-SA never-list → inspire; MIT → shortlist capability), full row schema | eval 3 |
| 4 | Mixed sweep: paywalled/no-license asset (reject) + Apache-2.0 with NOTICE obligations (allow-list w/ NOTICE condition) | eval 4 |
| 5 | Adaptation provenance pass: full provenance row, orchestrator note for ATTRIBUTION.md (never edit it directly), MIT obligations stated | eval 5 |
| 6 | Curated bundle with an unreviewable binary row separated from 11 screenable markdown packages (security-gate posture; README claims are data) | eval 6 (bundle conveyed by the prompt description; the graded behavior is the binary's row + no-execution posture) |
| 7 | Unreachable source during a sweep: complete reachable sources, report the gap, pass stays incomplete, no fabricated candidates | eval 7 |

## Coverage math

7 evals / 7 use cases = 100% inventory coverage by mapping. The ≥80%
library bar means: when a new use case is added here, the eval set must
grow within the same change (or the addition is deferred with a dated
note and the mapping below stays honest).

## Boundary notes

- "Authoring a new house skill from scratch" is `authoring-skills`'s
  use-case inventory, not this one.
- Head-to-head adoption evals (Phase C) are a program-plan concern;
  they consume this skill's shortlist but are graded by the fresh-agent
  protocol, not listed here.
- Plain citation of a tutorial/reference (tier 3) needs no register
  row; ingest/adapt of the same material does.
