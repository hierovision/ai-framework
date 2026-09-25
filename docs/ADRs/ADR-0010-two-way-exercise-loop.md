# ADR-0010: The two-way exercise loop — framework candidates + target-repo uplift

## Status: accepted 2026-09-24

## Context

The framework's evaluation machinery is first-class (typed evals, gates,
run logs), and the triage pass already consumes live GitHub issues — but
the capture side of self-improvement was one orphaned sentence:
`authoring-skills` pointed mid-exercise sessions at a handoff-proposal
convention whose home (`docs/handoffs/`) was retired by ADR-0008. An
improvement noticed in a consumer repo had no defined artifact shape, no
home, and no route to triage. Meanwhile, an exercise left the *target*
repo with nothing durable: decisions lived in the session and evaporated,
and the next exercise re-derived the target repo's governance from zero.

## Decision

Exercising the framework on a target repo is a **two-way loop**, owned by
one contract (`reference/self-improvement.md`):

1. **Upstream (framework candidates)** — a fixed-shape candidate block
   (date, skill, observed, expected, correction, evidence, status),
   appended mid-exercise to the target repo's `.opencode/exercise.md`;
   captured, never fixed inline. At session close, evidenced candidates
   are promoted to GitHub issues on this repo (`skill-improvement`
   label), where the standing triage pass consumes them.
2. **Downstream (target-repo uplift)** — the same file carries a dated
   uplift ledger; at close, its items are converted into the target
   repo's own three-tier memory (its `AGENTS.md`, its ADRs, its
   `ROADMAP.md`) and the file is archived. The target repo ends every
   exercise governed, not just worked.

The capture-don't-fix rule is the existing authoring-skills rule made
explicit: framework tweaks never ride along in a feature PR unless
required by the feature; everything else is a candidate.

## Consequences

- Both repos accumulate durable improvement per exercise; the next
  exercise opens by reading the target repo's ledger.
- The registry's evidence-based maturity bar (ADR-0009) gains its
  evidence source — exercises.
- Two more artifact kinds have exactly one authoritative home (the
  routing tables in `CONTRIBUTING.md` and `docs/ADRs/README.md`).
- The mechanism's behavioral proof comes from real exercises (RM-012 /
  RM-014's own exercise contract); no synthetic eval harness is built
  for documentation.

## Sources

- `docs/ROADMAP.md` RM-014 (added by the 2026-09-24 triage, user
  request) and RM-012's harvest amendment
- `docs/CONCEPTS.md` Choice 4 (artifacts as contracts), Choice 2
  (capture-don't-fix keeps autonomy bounded), Choice 6 (Layer-1
  contract, citation-not-restatement)
- `.opencode/plans/archive/rm-014.md` (approved 2026-09-24)
