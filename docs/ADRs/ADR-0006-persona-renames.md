# ADR-0006: Agents renamed to personas (architect / curator / implementer / planner)

## Status: accepted 2026-09-21

## Context

The framework's thin agent definitions (`agents/*.md` — role lens, skill
pointer, model line; see `docs/CONCEPTS.md` Choice 3) were named after
process stages (designer, reviewer, …). As the library grew, the names
collided with the skills they point at and did not say what the *session
binding* is for.

## Decision

Rename the agent definitions to persona names that describe the binding's
role in the loop: `architect` (design), `curator` (docs/memory), `planner`
(added), `implementer` (build) — the review and test personas unchanged.
Skills carry the process knowledge; personas remain thin bindings and never
acquire process text.

## Consequences

- One vocabulary across agents, plans, and ROADMAP (the Layer-1 role
  vocabulary in `docs/CONCEPTS.md` Choice 6).
- All references to the old agent names are updated in the same change;
  a stale name is a bug, not a synonym.

## Sources

- PR #22 (commit `fdf0ecd`): rename agents to personas + add planner
- `agents/*.md` (current persona set)
