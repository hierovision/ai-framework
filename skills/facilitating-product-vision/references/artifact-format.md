# Vision Artifact Format

Read this when drafting the vision document (the session's primary
artifact) and before any revision of one. The artifact is the **contract
with the owner**: a separate review pass reads it cold, without the
facilitation conversation, and must be able to defend the strategy and
slice plan. If a section has no content for this item, write `None.`
rather than omitting it — an empty section is a signal.

The skill's body cites this file rather than duplicating its contents —
load it before producing or revising the artifact.

## Contents

- Two artifacts, one session
- Document conventions
- Frontmatter (lightweight; the section list IS the contract)
- Fixed section order
- Section schemas
- "Good" definitions — decision-guiding, not marketing
- Roadmap row contract (sibling)

## Two artifacts, one session

The session emits two artifacts that are governed by sibling formats:

1. **Vision document** (default name `VISION.md`, path resolved with the
   owner — see *Path* below). The fixed section list in this file
   defines its content contract.
2. **Outcome themes + provisional slices, appended to the project's
   `ROADMAP.md`**. Rows conform to the item-row schema and frontmatter
   of the sibling format
   [`../../triaging-requirements/references/roadmap-format.md`](../../triaging-requirements/references/roadmap-format.md)
   (relative path is intentional — the skill installs as a sibling set,
   so the path resolves in both the repo and the symlinked global
   layout). Now/Next/Later semantics are recorded via the roadmap's
   `rubric:` frontmatter + `Notes` cell (no private table format is
   introduced); slices carry a one-line `success measure` + a
   `blocked-by` mapping recorded in `Notes`.

The skill emits themes + provisional slices only; **`triaging-requirements`
owns scoring, ranking, and the durable merge** (the established-once
rule). The session never rebuilds an existing `ROADMAP.md` from scratch —
that violates the durable-merger contract.

## Document conventions

- **Length.** Aim for ≤2 pages per section when the vision is moderate;
  a full artifact is 6–10 pages. A page-a-section indicates *content
  fluff* — section content past two pages almost always means the
  section is doing two jobs. Split or cut.
- **Tone.** Decision-guiding, not marketing. The owner will defend the
  strategy on these pages; vague aspirational language reads as
  unprepared in that conversation.
- **Tables over prose.** Slice tables, segment tables, theme tables —
  the body keeps the artifact scannable.
- **Recorded rationale.** Every owner decision carries a one-line
  rationale in or beside the table; "decided because" without the
  *because* is not a record.
- **Open questions ≠ invented strategy.** When the artifact asks for an
  owner decision, the artifact does NOT pre-fill a recommended answer.
  It surfaces the question, lists what the session needs to proceed,
  and stops. The session never invents the strategy.
- **Path.** Vision-artifact canonical home is the consumer repo's own
  decision-doc call (ADR addendum vs `docs/vision/` vs the README — the
  owner decides). The session asks in Step 1 and stores per the
  consumer's convention. Do not assume `VISION.md`; it is the
  default that fits most repos, not a rule.

## Frontmatter

Vision documents are not ADRs and do not adopt ADR frontmatter
verbatim. Use a lightweight three-field frontmatter so a future pass
can detect provenance and revisability:

```yaml
---
owner: <owner handle / role>
created: YYYY-MM-DD
last_refreshed: YYYY-MM-DD    # append-only; bump on every session
---
```

`owner` is required — the vision has no owner, the artifact is
untethered. `last_refreshed` is append-only (never overwrite); it is
the audit trail that the artifact was actually revisited.

## Fixed section order

The order below is fixed so a cold reviewer can find each contract
part in the same place every time. Subsections may appear inside a
section when the item warrants it; the top-level sections do not
reorder.

```markdown
# Vision: <one-line title>

<frontmatter>

## Inputs & Constraints
## Vision Statement
## Segments & Jobs-to-be-Done
## Alternatives & Non-goals     (incl. anti-vision)
## Value & Business Model
## North Star + Guardrails
## Outcome Themes               (Now / Next / Later; capacity-envelope applied)
## Slices                       (per slice: AC + success measure + blocked-by + sizing)
## Compliance & Phase Gates
## Open Questions               (owner decisions, not invented strategy)
```

## Section schemas

### Inputs & Constraints

The session-recap the owner can verify in 60 seconds: ambition,
constraints (team capacity, regulatory ceilings, time horizons),
existing decisions the session is built on top of (cite source —
"from ADR-NNN" or "from the 2026-Q3 strategy doc"), and any
constraint the owner has already flagged as non-negotiable. No
"Goals" prose here — goals go in *Vision Statement*; this section
captures the pre-decided inputs the strategy is constrained by.

### Vision Statement

One paragraph (≤120 words) stating what the product is, who it is for
in one breath, and the change it is making. Two pages of prose here
is a smell — the owner cannot quote the vision in a hallway. If the
owner cannot quote the section, the section is too long.

### Segments & Jobs-to-be-Done

A table of segments × jobs-to-be-done. Columns:

| Segment | JTBD (one line) | Today workaround | Reach estimate |

Segments are the durable user-types (not personas); JTBD is the
verb-form job the segment hires the product to do. The
*Today workaround* column is non-optional — every segment's job
should be visibly underserved today, otherwise the segment does not
belong in the strategy.

### Alternatives & Non-goals (incl. anti-vision)

Three sub-blocks, in this order:

1. **Alternatives considered** — the strategic options the session
   weighed and the one-line reason each was set aside.
2. **Non-goals** — the explicit things this product is *not* doing
   (with a one-line reason each). Non-goals force the discussion of
   scope; without them, every feature looks in-scope.
3. **Anti-vision** — the *opposite* outcome the strategy is designed
   to prevent (the "we will know we failed when…" clause). One
   paragraph, concrete, not generic ("we are not the cheapest" beats
   "we are great"). An anti-vision without a concrete failure mode
   is not an anti-vision.

### Value & Business Model

How value is captured: revenue model, pricing posture, the unit
economics that make the strategy viable. One paragraph or one
short table — long enough that an owner can defend "we make money
because X" in a board meeting, short enough that a reader can
verify the math without a calculator.

### North Star + Guardrails

- **North Star** — the single metric that captures the strategy's
  value capture (not vanity). State the metric and the *direction*
  (raise it / lower it / hit a target).
- **Guardrails** — 2–4 metrics that the strategy must not regress,
  even at the cost of the North Star (a margin floor, a quality
  floor, a regulatory ceiling). Without guardrails, every
  optimization becomes a temptation to harm the long term for the
  short.

### Outcome Themes (Now / Next / Later)

A table of outcome themes — what the product is *trying to make
true for users* over each horizon — placed under three horizon
labels: **Now** (this quarter), **Next** (this half), **Later**
(this year, may slip). The capacity envelope (throughput ceiling
per horizon) is applied *here*, not at the slice level — themes
are sized to fit the team's reach. Themes without slices in the
*Slices* section are not themes; cut or rewrite. Columns:

| Theme | Outcome (observable) | Horizon | Capacity band |

"Capacity band" is a one-word tag (`S` / `M` / `L`) reflecting the
team's pre-agreed capacity envelope — themes sized `L` do not land
in `Now`. The envelope is owned by the owner (a team cannot
redefine its own reach); the session records the band the owner
gave.

### Slices

One short table per outcome theme (or one combined table for small
artifacts). Each row is a slice — the smallest unit of work that
ships user-visible value and is independently testable. Columns:

| Slice | Outcome theme | AC (observable) | Success measure | Blocked-by | Sizing |

- **AC (observable)** — the user-observable behavior the slice
  delivers; "a teacher can publish a worksheet and a student can
  complete it" beats "implement the worksheet feature".
- **Success measure** — the *metric* that proves the slice
  delivered value, not just the build AC. Slices that lack a
  success measure are not slices; they are features. "Adoption: ≥30%
  of teachers publish a worksheet in the first month" is a success
  measure; "ships" is not.
- **Blocked-by** — the slice(s) or external dependency this slice
  cannot start without; `[]` if none. A roadmap of mutually independent
  slices is suspicious; the blocked-by column surfaces the dependency
  graph that lets the owner sequence the work.
- **Sizing** — rough (S/M/L or person-weeks), the owner's call. Do
  not invent hours from nothing; the owner sizes or the section is
  incomplete.

Slices inherit the horizon + capacity band of their outcome theme;
a slice in `Now` whose theme is `L` is a mis-fit the table exposes.

### Compliance & Phase Gates

Any regulatory, security, or phase-gate constraint the strategy
must satisfy to ship (e.g., "FERPA review before any student-data
slice ships"; "SOC 2 Type II before the Next horizon opens").
Each gate names the slice(s) it gates and the entity that owns
the gate (security review, legal, the owner). A strategy that
ships without naming its gates is a strategy the team will
discover its gates inside an incident.

### Open Questions

Every owner decision the session is waiting on, recorded with:
the question (one line), what the session needs to proceed (the
specific input), and which section it will land in once answered.
The artifact does NOT recommend an answer; it surfaces the
question. A vision with no open questions has either been
completely decided (rare; record the session date and skip) or is
silently inventing strategy (the cardinal failure mode).

## "Good" definitions — decision-guiding, not marketing

A section is "good" when an owner can use it in a strategy
conversation without re-deriving it. Tests:

| Section | "Good" means |
|---|---|
| Inputs & Constraints | An owner can verify the recap in 60 seconds and flag any missing constraint. |
| Vision Statement | An owner can quote it verbatim in a hallway. |
| Segments & JTBD | Every segment's job is visibly underserved today; no segment without a workaround. |
| Alternatives & Non-goals | The owner can defend each non-goal; the anti-vision names a concrete failure mode. |
| Value & Business Model | An owner can defend "we make money because X" in a board meeting. |
| North Star + Guardrails | The North Star captures value capture (not vanity); guardrails are concrete regressions the strategy will refuse. |
| Outcome Themes | Capacity envelope applied; every theme has ≥1 slice; no `Now` theme sized `L`. |
| Slices | Every slice carries an observable AC + a success measure + a blocked-by + a sizing; no slice ships in a vacuum. |
| Compliance & Phase Gates | Every regulatory/security gate is named with its owner; no implicit gate. |
| Open Questions | Every open question is a real owner decision; nothing silently invented. |

If a section fails its "good" test, the owner sees a red flag in
the strategy conversation and the artifact loses defensibility.
The session revises the section before declaring the artifact
ready.

## Roadmap row contract (sibling)

When the session emits theme/slice rows to the project's
`ROADMAP.md`, the rows conform to the sibling format
[`../../triaging-requirements/references/roadmap-format.md`](../../triaging-requirements/references/roadmap-format.md)
— specifically:

- The frontmatter is the roadmap's (not the vision document's):
  `rubric:` + `threshold:` are recorded so a future triage pass
  can tell what was in effect.
- Each theme row uses the standard `feature` category with the
  outcome theme name as the title; the horizon (`Now` / `Next` /
  `Later`) and capacity band are recorded in `Notes` (e.g.
  `horizon: Now; capacity: M`), not as new columns — the existing
  schema is the contract, and a fresh column is a separate ADR.
- Each slice row uses `feature` category with the slice title;
  the slice's `success measure` and `blocked-by` map are recorded
  in `Notes` (e.g. `success: ≥30% teacher adoption in 30 days;
  blocked-by: feat-auth-flow`), not as new columns.
- The session APPENDS rows; it never edits existing open rows
  unless the owner directs a re-scoring under a rubric change.
  Ranking, scoring, and the durable merge are owned by
  `triaging-requirements` and happen on the next triage pass.

The roadmap's existing schema is the single source of truth for
row shape. Any extension (first-class Now/Next/Later columns, a
success-measure column, etc.) is an ADR-gated change and is
explicitly excluded from this skill's v1 — see the plan's OQ2.