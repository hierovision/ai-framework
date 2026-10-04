# Architecture Decision Records

Decisions that bind this framework's structure or policy live here, one
file per decision. A decision that stops being true is superseded or
reversed **in place** — never silently rewritten or deleted.

## Maturity

Every ADR carries `## Status` with one of:

- **accepted** — in force; the current truth.
- **superseded** — replaced by a named ADR (kept for the audit trail;
  readers follow the pointer).
- **reversed** — withdrawn; the file records why.

## Index

| ADR | Decision | Status |
|---|---|---|
| [ADR-0001](ADR-0001-sonnet-elimination.md) | Eliminate Claude Sonnet from all bindings | accepted 2026-09-18 |
| [ADR-0002](ADR-0002-direct-key-eval-lane.md) | CI behavioral evals on the direct-key DeepSeek lane | superseded by [ADR-0013](ADR-0013-go-first-model-policy.md) 2026-10-03 |
| [ADR-0003](ADR-0003-typed-assertion-protocol.md) | Typed-assertion protocol + the nature rule | accepted 2026-09-20 |
| [ADR-0004](ADR-0004-canary-selection-principle.md) | Canary selection principle for per-change gating | accepted 2026-09-19 |
| [ADR-0005](ADR-0005-three-layer-gating.md) | Three-layer eval gating (pre-commit / pre-push / PR) | accepted 2026-09-19 |
| [ADR-0006](ADR-0006-persona-renames.md) | Agents renamed to personas | accepted 2026-09-21 |
| [ADR-0007](ADR-0007-eval-lane-policy-amendment.md) | Eval-lane policy amendment (direct-key despite free-first default) | superseded by [ADR-0013](ADR-0013-go-first-model-policy.md) 2026-10-03 |
| [ADR-0008](ADR-0008-repo-memory-tiers.md) | Three-tier repo memory; plans tracked here; handoffs retired | accepted 2026-09-23 |
| [ADR-0009](ADR-0009-registry-manifest.md) | Machine-readable skill/agent registry, validator-enforced | accepted 2026-09-24 |
| [ADR-0010](ADR-0010-two-way-exercise-loop.md) | Two-way exercise loop — framework candidates + target-repo uplift | accepted 2026-09-24 |
| [ADR-0011](ADR-0011-license-and-ingest-policy.md) | License and ingest policy (MIT; allow-list / never-list; provenance) | accepted 2026-09-27 |
| [ADR-0012](ADR-0012-untrusted-content-security-gate.md) | Untrusted-content security gate (pre-scan, script review, sign-off) | accepted 2026-09-27 |
| [ADR-0013](ADR-0013-go-first-model-policy.md) | Go-first model policy — Go defaults, free opt-in, kimi-k3/gpt-6-luna excluded, 2026-11-01 review | accepted 2026-10-03 |

## Where a decision goes

The plan-lifecycle rule (ADR-0008) is the routing table:

| Artifact | Home | When it moves |
|---|---|---|
| Cross-session imperative | `AGENTS.md` | standing rule adopted |
| Binding/structure decision | `docs/ADRs/` | decided (this directory) |
| In-flight plan / session handoff | `.opencode/plans/` | essence extracted → deleted (git history) |
| Improvement candidate / target-repo uplift | `reference/self-improvement.md` governs; captured in the target repo's `.opencode/exercise.md` | promoted at session close (issues / target-repo memory) → archived |
| Current state + next action | `docs/ROADMAP.md` | every session boundary |
| Volatile facts (models, pricing) | `reference/*.md` | re-verified every pass |
