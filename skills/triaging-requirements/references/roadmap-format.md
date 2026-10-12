# ROADMAP.md Format & Merge Rules

Read this when initializing ROADMAP.md or before any merge that isn't a
trivial append. The format is a contract: a future pass (or a fresh agent)
must be able to read the file and reproduce the current state.

## Contents

- Frontmatter
- Section order
- Item row schema
- What a roadmap item must NOT carry
- Confidence-gated detail by horizon
- Merge table
- Done history
- Sizing
- Re-triage cadence
- Rubric & threshold record

## Frontmatter

```yaml
---
title: <project> Roadmap
last_triaged: YYYY-MM-DD
rubric: impact-urgency        # or the user-supplied rubric name
threshold: null              # or a number if the user set a cut threshold
sources:
  - pasted
  - docs/feature-ideas.md
  - jira:PROJ
---
```

`rubric` and `threshold` are recorded so a future pass knows what was in
effect. Update them whenever the user changes the rubric.

## Section order

```markdown
# <project> Roadmap

> Last triaged: YYYY-MM-DD · Rubric: impact-urgency

## Summary

One-paragraph narrative of where the project is and what comes next.

## Priority order (1–N)

A ranked list of the open items, highest first. Mirrors the tables below;
kept here for at-a-glance reading.

## Features
<table of open feature items>

## Bugs
<table>

## Tech Debt
<table>

## Chores
<table>

## Review (category: review)
Flagged items that don't cleanly fit a category — awaiting user decision.

## Proposed (cut)
Items below the rubric threshold. Not committed; awaiting confirmation.

## Done
Closed items kept as history, newest first. Do not delete.

## Skipped
Items deliberately not added, each with a one-line reason.
```

## Item row schema

Each table row is an *item* and has exactly these thirteen columns, in
this order:

| ID | Title | Outcome | Horizon | Category | Impact | Urgency | Score | Status | Success measure | Blocked-by | Sources | Notes |

| Column | Meaning |
|---|---|
| ID | Stable slug (e.g. `feat-phase-colors`). Never renumber — IDs persist across passes. |
| Title | Short imperative summary |
| Outcome | The vision-document theme name this item advances. `—` when the item maps to no theme. Themes live in the vision document (see `facilitating-product-vision`); a theme is **never** a roadmap row. |
| Horizon | `Now` / `Next` / `Later` — the confidence horizon (see *Confidence-gated detail* below). |
| Category | `feature` / `bug` / `debt` / `chore` / `review` |
| Impact | 1–3 (default rubric) |
| Urgency | 1–3 (default rubric) |
| Score | product / derived value, used for ranking |
| Status | `proposed` / `open` / `waiting` / `in-progress` / `done` / `skipped`. (`waiting` = the trigger or dated gate has not been reached; it replaced the older `blocked`.) |
| Success measure | One line, outcome-phrased, testable — the deferred-success boundary the row promises ("what must be true"), not a build-time acceptance criterion. See *What a roadmap item must NOT carry*. |
| Blocked-by | First-class dependency: the item(s) or external gate this item cannot start without; `—` when none. The dependency graph lets the owner sequence work. |
| Sources | where this item came from (file refs, ticket IDs, "pasted") |
| Notes | trigger, rationale/history, sizing, ambiguity, or cross-reference. Sizing (S/M/L or person-weeks) lives here — it is not a first-class column. |

Under a custom rubric, replace the Impact/Urgency columns with one column
per rubric component (e.g. Reach | Confidence | Effort), keeping Score as
the derived ranking value. The component columns exist so the user can
sanity-check the ranking — collapsing them into Score alone defeats that.

## What a roadmap item must NOT carry

A roadmap item carries **no acceptance criteria, no detailed
requirements, and no idea/bug dumps** — the roadmap is a strategy artifact,
not a spec and not a backlog dump.

- **No acceptance criteria.** Detailed requirements — the full
  observable-behavior + verifier criteria, edge cases, and verification
  commands — live in the item's **plan artifact**, authored at plan time by
  `designing-architecture`. The row carries only the one-line `Success
  measure` (the outcome lock). If a row has no defensible one-line outcome,
  detail does not belong in the row — cite a trigger in `Notes` and let the
  design pass produce the detail.
- **No ideas, backlogs, or bug lists.** "Keep these planning artifacts
  separate from your roadmap" (Aha!, *What should a product roadmap
  include?*, must-not-include list; hand-taken from the 2026-10-09 consumer
  handoff — see the plan's History for the honest-limits residual, not
  re-fetched in this contract pass).
- **No detailed requirements.** "Detailed requirements are weighing down
  the roadmap" is the warning sign (Atlassian, *Agile roadmaps*, verified
  live 2026-10-11).
- The roadmap "is not intended to be a spec, and it's not a laundry list
  of features" (SVPG, Marty Cagan 2009; hand-taken from the 2026-10-09
  handoff).

## Confidence-gated detail by horizon

Detail scales with confidence across the `Horizon` column — a `Now` item
is a specific solution in flight, a `Next` item is an opportunity under
validation, and a `Later` item states an outcome only (Teresa Torres,
*producttalk.org/product-roadmaps*, verified live 2026-10-11):

- **Now** — specific solutions in progress. The row may name the solution
  and the work in flight.
- **Next** — opportunities (customer needs and pain points), not yet
  committed solutions. The row names the opportunity, not a chosen
  solution.
- **Later** — outcomes only: the measurable results the work is driving
  toward. The row names the outcome; it does not pre-commit a solution.

An item whose detail exceeds its horizon's confidence is over-planned:
move the solution detail to the plan artifact and leave the outcome in the
row.

## Item detail files

Roadmap detail that does not fit one row cell lives in
`docs/roadmap-detail/<ID>.md` — one file per ID, created by migration or
merge passes by **byte-exact relocation** (never reworded, never truncated):

- open rows: the trigger evidence and pre-migration acceptance drafts;
- done rows: the acceptance-as-delivered history (audit record).

The roadmap's `Notes` cell references it (`detail: docs/roadmap-detail/<ID>.md`).
Lifecycle: a detail file is *consumed* when the item reaches a design pass
(the plan artifact becomes the detail's home) and pruned by the quarterly
ALM review — never silently; provenance rows keep a dated note.

Cell-length discipline is **guidance, best effort** — the automated check
(`scripts/check_roadmap_verbatim.py`) prints length as a WARNING and exits
0; the agent surfaces the option to shorten to the owner. Hard contract
failures (parse errors, delimiter/table mismatches, roadmap-ID ↔ detail-file
bijection breaks, missing sections) still exit 1.

## Merge table

Applies when `ROADMAP.md` already exists. "Incoming" = a freshly gathered
item; "Existing" = a row already in the roadmap.

| Incoming | Existing | Action |
|---|---|---|
| new | (none) | append as `proposed`, `Horizon` from the item's trigger state |
| new | same ID or clear duplicate | merge sources into existing; bump Notes |
| new item arrives for an existing theme | existing row with the same `Outcome` | keep one row per logical item; set/confirm `Outcome` on the surviving row |
| Horizon moved (e.g. `Next` → `Now`) | open row | update the `Horizon` cell; never renumber the ID |
| now done | open row | move to Done with date (see *Done history*) |
| now done | (none) | add directly to Done (don't lose shipped history) |
| below threshold | (none) | add to Proposed (cut); do not rank-list |
| below threshold | existing open row | leave existing; note the cut recommendation |
| user confirms cut | in Proposed (cut) | move to Skipped with reason |
| source gone / deleted | existing open row | leave; note source no longer references it |

Preserve IDs and prior scores on existing open rows unless their status
moved — re-scoring everything from zero each pass erases the history that
makes the roadmap worth keeping.

## Done history

Done items stay in `## Done`, newest first, with the close date **if
known**. This is the record of what shipped; deleting it defeats the point
of a durable roadmap. A two-year-old Done list is correct, not clutter.

When a source carries no close date (a `✅` marker in a requirements doc,
a `- [x]` checkbox with no timestamp), do **not** invent one — record
`pre <last-triage-date>` (e.g. `pre 2026-07-03`). That signals "closed
before the first pass that saw it" without fabricating precision the
source doesn't have. If a later pass learns the real date from a tracker,
update the cell.

**Done rows are acceptance-as-history.** A Done row adopts the
thirteen-column set; its `Success measure` cell carries the one-line
delivered outcome. The historical acceptance prose moves **verbatim** to
the item's detail file (`docs/roadmap-detail/<ID>.md`, see *Item detail
files*) — byte-exact, never reworded or truncated; this is an amendment of
2026-10-11 (owner ruling: massive detail never lives inside the roadmap
file). Where a historical annotation was appended to a moved cell (e.g. a
`(YYYY-MM-DD triage: …)` suffix), preserve it verbatim so the annotation
and the original text stay separable.

## Sizing

Sizing (S/M/L or person-weeks) lives in the `Notes` column, not as a
first-class column — it is the owner's rough call and does not need its own
width. Do not invent hours from nothing; the owner sizes or the row's
sizing is left open in `Notes`.

## Re-triage cadence

Re-triage the roadmap **quarterly**, paired with the standing quarterly
ALM review — one sitting, two reviews: the ALM stage-gate review and the
roadmap prune. "Review … quarterly, adjust as needed" (Atlassian, *Agile
roadmaps*, verified live 2026-10-11). Between cadences a pass is still run
whenever a named source or a fired trigger demands it; the quarterly
cadence is the floor, not the ceiling.

## Rubric & threshold record

When the user supplies a rubric or threshold, record it in frontmatter AND
echo the rubric name in the Summary header line. A future agent reading
ROADMAP.md cold must be able to tell "we switched to RICE on 2026-03-14 with
a 0.4 cut" without re-deriving it.
