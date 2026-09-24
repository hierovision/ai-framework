# ADR-0007: Amend the eval-lane policy — direct-key lane allowed despite the free-first default

## Status: accepted 2026-09-21

## Context

ADR-0002 put CI behavioral evals on the direct-key DeepSeek lane, but the
library's standing policy was free-first: paid/direct-key lanes are
escalation only (see `docs/CONCEPTS.md` Choice 7c). Running evals on a
direct key contradicted the recorded policy — the framework does not let a
standing rule and a live practice disagree silently.

## Decision

Amend the RM-002 free-only eval policy: behavioral evals are a sanctioned
exception to free-first, running on `deepseek/deepseek-flash` at ~$0.68 per
weekly off-peak run (cron 10:30 UTC). Deciding evidence: a 24-hour free
gateway outage (2026-09-21) plus unstable canary pass-rates on free lanes —
the eval gate's job is regression signal, and lane noise destroys it.

## Consequences

- The policy text and the practice agree; the amendment is recorded here
  and in `reference/model-routing.md`, not silently absorbed.
- Every other role keeps the free default; paid escalation remains
  explicit opt-in. This does not reopen lane choice per-session.

## Sources

- User directive 2026-09-21 (recorded in the RM-003 handoff, archived at
  `.opencode/plans/handoff-rm-003-to-rm-004.md`)
- `reference/model-routing.md` (2026-09-21 amendment + budget measurement)
- `docs/ROADMAP.md` RM-003 acceptance cell
