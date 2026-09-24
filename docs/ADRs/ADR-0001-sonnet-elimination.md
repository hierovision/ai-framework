# ADR-0001: Eliminate Claude Sonnet from all bindings

## Status: accepted 2026-09-18

## Context

The framework routes every role through `reference/model-routing.md`
(evidence-graded selection; see `docs/CONCEPTS.md` Choice 7). Claude Sonnet 5
was bound as a mid-tier default while a live 2026-09-18 side-by-side probe in
this repo (UI-mock critique + chart reading) showed DeepSeek V4.1-Flash at
parity or better — DS additionally computed WCAG contrast ratios and exact
hex values where sonnet gave qualitative critique. Sonnet is also the most
expensive mid-tier option on the Zen PAYG lane.

## Decision

Eliminate `claude-sonnet-5` (and all sonnet IDs) entirely: not bound in any
role, not retained in any alt list. Roles previously covered by sonnet move
to `deepseek/deepseek-flash` via the direct-key lane (ADR-0002). Vision
sign-off seat (`vision-critic-final`) bound to deepseek/deepseek-flash with
the first real-loop validating-ui cycle as its acceptance gate.

## Consequences

- Free/cheap tier carries more weight; the free-first policy (ADR-0007
  predecessor) stays intact.
- The eliminated ID is recorded in the hard-exclusions table
  (`reference/model-routing.md`), not deleted from history.

## Sources

- PR #20 (commit `a4216d7`): model rebind 2026-09-18
- `reference/model-routing.md` (elimination note, exclusions table, vision
  seat basis)
