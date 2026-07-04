# ROADMAP.md Format & Merge Rules

Read this when initializing ROADMAP.md or before any merge that isn't a
trivial append. The format is a contract: a future pass (or a fresh agent)
must be able to read the file and reproduce the current state.

## Contents

- Frontmatter
- Section order
- Item row schema
- Merge table
- Done history
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

Each table row has these columns:

| Column | Meaning |
|---|---|
| ID | Stable slug (e.g. `feat-phase-colors`). Never renumber — IDs persist across passes. |
| Title | Short imperative summary |
| Category | `feature` / `bug` / `debt` / `chore` / `review` |
| Impact | 1–3 (default rubric) |
| Urgency | 1–3 (default rubric) |
| Score | product / derived value, used for ranking |
| Status | `proposed` / `open` / `in-progress` / `blocked` / `done` / `skipped` |
| Sources | where this item came from (file refs, ticket IDs, "pasted") |
| Notes | one-line rationale, ambiguity, or cross-reference |

Under a custom rubric, replace the Impact/Urgency columns with one column
per rubric component (e.g. Reach | Confidence | Effort), keeping Score as
the derived ranking value. The component columns exist so the user can
sanity-check the ranking — collapsing them into Score alone defeats that.

## Merge table

Applies when `ROADMAP.md` already exists. "Incoming" = a freshly gathered
item; "Existing" = a row already in the roadmap.

| Incoming | Existing | Action |
|---|---|---|
| new | (none) | append as `proposed` |
| new | same ID or clear duplicate | merge sources into existing; bump notes |
| now done | open row | move to Done with date |
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

## Rubric & threshold record

When the user supplies a rubric or threshold, record it in frontmatter AND
echo the rubric name in the Summary header line. A future agent reading
ROADMAP.md cold must be able to tell "we switched to RICE on 2026-03-14 with
a 0.4 cut" without re-deriving it.