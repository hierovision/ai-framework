# Vision Artifact Format

Read this when drafting the vision document (the session's primary
artifact) and before any revision of one. The artifact is the **contract
with the owner**: a separate review pass reads it cold, without the
facilitation conversation, and must be able to defend the strategy and
roadmap-item set. If a section has no content for this item, write `None.`
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
   defines its content contract. It carries **strategy only** — no
   operational slice tables and no per-item work breakdown.
2. **Outcome themes + roadmap items, appended to the project's
   `ROADMAP.md`**. Themes are strategy and live in the vision document;
   the *items* the session emits are roadmap rows that conform to the
   item-row schema and frontmatter of the sibling format
   [`../../triaging-requirements/references/roadmap-format.md`](../../triaging-requirements/references/roadmap-format.md)
   (relative path is intentional — the skill installs as a sibling set,
   so the path resolves in both the repo and the symlinked global
   layout). `Outcome`, `Horizon`, and the other item fields are defined
   in that schema; the session does not introduce a private table format.

The skill emits themes + roadmap items only; **`triaging-requirements`
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
- **Tables over prose.** Theme tables, segment tables, and the other
  structured blocks keep the artifact scannable.
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
## Outcome Themes               (Now / Next / Later; strategy-only)
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

The product strategy's themes — what the product is *trying to make true
for users* — grouped under three horizon subheads: **Now** (this
quarter), **Next** (this half), **Later** (this year, may slip). This
section is **strategy-only**: a theme name and a one-line observable
outcome. Columns:

| Theme | Outcome (observable, one line) |

The three subheads (`### Now`, `### Next`, `### Later`) order the theme
list by horizon — the strategy question "what does the strategy pursue
now vs next vs later" is answered by the grouping, not by a per-theme
field. There is no Horizon column, no capacity band, and no slice list in
this section: those are roadmap-item fields (see *Roadmap row contract*
below). The capacity envelope (the throughput ceiling the owner gives) is
a captured *Input / Constraint* — record it in this section's prose at
theme level, never as a table column. A theme with no one-line observable
outcome is not a theme; cut or rewrite it.

### Compliance & Phase Gates

Any regulatory, security, or phase-gate constraint the strategy
must satisfy to ship (e.g., "FERPA review before any student-data
item ships"; "SOC 2 Type II before the Next horizon opens").
Each gate names the roadmap item(s) it gates and the entity that owns
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
| Outcome Themes | Each theme is one line and observable, grouped under Now/Next/Later; strategy-only — no Horizon column, no capacity band, no slice list. |
| Compliance & Phase Gates | Every regulatory/security gate is named with its owner; no implicit gate. |
| Open Questions | Every open question is a real owner decision; nothing silently invented. |

If a section fails its "good" test, the owner sees a red flag in
the strategy conversation and the artifact loses defensibility.
The session revises the section before declaring the artifact
ready.

## Roadmap row contract (sibling)

When the session emits outcome-theme / roadmap-item rows to the
project's `ROADMAP.md`, the rows conform to the item-row schema at
[`../../triaging-requirements/references/roadmap-format.md`](../../triaging-requirements/references/roadmap-format.md)
— read that file and conform to the item-row schema there; this file does
not restate it. The session APPENDS rows; ranking, scoring, and the durable
merge are owned by `triaging-requirements` on the next pass.