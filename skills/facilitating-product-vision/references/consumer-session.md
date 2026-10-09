# Consumer Adoption Flow

Generic flow for a consumer repo adopting this skill — the project
operates on its own roadmap items, the session is invoked against a
named entry, and the artifacts return to the consumer's own
convention. The skill's instructions are project-neutral; the
fixture-flavored example below shows one real instance and may name
that consumer's own files.

## Contents

- When to adopt
- Inputs the consumer supplies
- What the session asks
- The three-checkpoint cadence
- Artifacts returned
- The one-shot variant
- After the session

## When to adopt

A consumer adopts this skill when the next big question is *what
should the product be doing* — a strategy / vision / outcome-theme
question — and the existing `ROADMAP.md` is too lean to answer it
(wishlist items without ACs, themes without slices, no capacity
envelope, no compliance gates). The skill is the upstream of
`triaging-requirements`: it produces themes + provisional slices;
`triage` then scores, ranks, and durably merges.

If the consumer's question is *rank this backlog* or *plan this one
item*, this skill is the wrong one — the request routes to
`triaging-requirements` or `designing-architecture` (see the
boundary routing table in `SKILL.md`).

## Inputs the consumer supplies

Before the session starts, the consumer's pre-read is:

- An established `ROADMAP.md` (read at Step 1; never rebuilt).
- The consumer's decision-doc convention (an `AGENTS.md`, a `docs/`
  index, an ADR directory) so the session can ask the canonical
  home for the vision artifact against it.
- Any prior strategy / vision / ADR the strategy is built on top of
  (the session cites the source).
- The owner's pre-decided constraints: capacity envelope, regulatory
  posture, non-negotiables.

If the consumer's pre-read is missing a piece, the session surfaces
the gap in the artifact's `Open Questions` section rather than
inventing the missing input.

## What the session asks

Three batched decision points, not one pause per piece:

1. **Checkpoint 1 — strategy batch.** Vision statement, segments +
   JTBD, alternatives + non-goals + anti-vision, value & business
   model, north star + guardrails. The owner confirms or revises
   each; every call is recorded.
2. **Checkpoint 2 — roadmap batch.** Outcome themes banded
   Now/Next/Later, capacity envelope applied, slices per theme
   (each with observable AC + success measure + blocked-by +
   sizing), risk-first ordering. The owner confirms or revises.
3. **Checkpoint 3 — compliance + phase gates.** Consent / privacy
   / regulatory milestones, phase gates that unlock later segments,
   each gate's owner. The owner confirms.

Between checkpoints the facilitator drafts; at each checkpoint the
facilitator stops and presents the draft as questions-with-proposals
— never a fait accompli.

## Artifacts returned

Three artifacts land in the consumer's own paths:

1. **Vision document** at the owner-confirmed home (the canonical
   home the session asked for in Step 1). Conforms to the fixed
   section order in
   [`../artifact-format.md`](../artifact-format.md) (sibling-relative
   path; resolved against this skill's own directory). A separate
   reviewer reads it cold and must be able to defend the strategy
   and slice plan.
2. **`ROADMAP.md` rows** — themes + provisional slices appended to
   the consumer's existing file. Rows conform to the sibling format
   at
   [`../../triaging-requirements/references/roadmap-format.md`](../../triaging-requirements/references/roadmap-format.md)
   (sibling-relative path; resolves in both repo and symlinked
   install). Outcome/horizon/capacity live in the roadmap's
   `Notes` cell, not as new columns.
3. **Session record** as a working artifact under the consumer's
   plan convention — usually `.opencode/plans/`. The dated
   transcript of decisions and rationale; not a published doc.

The session is upstream of triage, not a replacement. The
`triaging-requirements` skill scores the provisional rows, ranks
them, and folds them into the published `ROADMAP.md` order on the
next pass.

## The one-shot variant

When the owner declares a one-shot session (no live back-and-forth
this turn), the session still runs the three checkpoints but
surfaces the owner's answers as a real `Open Questions` section in
the artifact rather than inventing them. The artifact lists every
owner decision the session is waiting on, the specific input needed,
and which section it will land in once answered. The session
writes what it can fill without owner input and stops; the owner
fills the Open Questions on a later pass.

A vision with no open questions has either been completely decided
(rare; record the session date and skip) or is silently inventing
strategy. The one-shot variant never invents.

## After the session

The handoff chain is contractual:

1. The session emits themes + provisional slices appended to
   `ROADMAP.md`.
2. `triaging-requirements` consumes the provisional rows on the
   next pass, scores them, and durably merges them into the
   published order. The session never does this scoring.
3. `designing-architecture` plans the top-ranked slice into a
   verifiable plan artifact, then stops at user approval.
4. `managing-github-issues` may persist the open rows as GitHub
   issues (separate skill, run on a later pass).

The session's job ends when the artifacts exist and the handoff is
named. It does not score, plan, or persist — the next skill in the
chain does.

## Example (one real instance)

A consumer adopting the skill for the first time on a small
consumer repo invoked the session against the roadmap's
"lean-and-wishlist" state and returned:

- The vision document at the consumer's chosen home (in the
  worked instance: `docs/vision/<consumer-key>-vision.md`).
- Theme + slice rows appended to the consumer's `ROADMAP.md`,
  horizon + capacity in `Notes`.
- The session record at the consumer's plan path.

The exact paths are the consumer's call, not the skill's — this
example is a flavor note from one instance, not a template for
other consumers to copy. The skill's body stays project-neutral;
the fixture / worked example may name a specific consumer.
