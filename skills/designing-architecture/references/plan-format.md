# Plan Artifact Format

Read this when drafting the plan artifact (Step 6) and before any revision
of an existing plan. The plan is the **contract with the implement stage**:
a separate build session reads it cold, without the design conversation, and
must be able to execute it. If a section has no content for this item, write
`None.` rather than omitting it — an empty section is a signal.

## Contents

- Frontmatter
- Section order
- Section schemas
- Acceptance-criteria quality bar
- Revising an existing plan
- Path & slug rules

## Frontmatter

```yaml
---
slug: <roadmap-id-or-kebab-feature-slug>
title: <one-line imperative summary>
status: draft          # draft | approved | superseded
created: YYYY-MM-DD
revised: [YYYY-MM-DD]  # append one date per revision; never overwrite
related: [<other-slugs>]  # optional; roadmap dependencies / supersessions
---
```

`status: draft` until the user approves. On approval the plan is the gate
to the implement stage — leave status as the user confirms (the approver may
flip it to `approved`). Do not pre-approve.

## Section order

```markdown
# Plan: <slug>

## Goal / Approach
## Acceptance Criteria
## Files to Modify
## Scope
## Schema / Type Impacts
## Verification
## Open Questions
## History
```

Sections are fixed and ordered so a cold implementer (or a downstream
verify skill) can find each contract part in the same place every plan.
Subsections may be added inside `## Schema / Type Impacts` (e.g. per-table
DDL) when the item warrants it.

## Section schemas

### Goal / Approach

One short paragraph: the single sentence goal, then the technical strategy.
No implementation detail — enough that an implementer can choose the right
files without re-deriving the approach.

### Acceptance Criteria

A numbered list. Each criterion has two parts:

1. **Observable behavior** — what a user / test / query observes.
2. **Verifier** — how it is checked: a test command, a Playwright selector,
   a SQL/RLS query result, an exit code, a diff against a generated file.

Combine into one line where the verifier is short (e.g. "... —
`npm run type-check` exits 0"). Split onto two lines when the verifier is
a query or selector so both parts are readable. See the quality bar below.

### Files to Modify

One entry per file path (use repo-relative forward-slash paths), each with a
`what-changes` note:

```markdown
- src/stores/checkout.ts — add a reserve-stock action that decrements inventory optimistically
- db/schema.sql — add `coupons` table + per-user RLS policy
- types/database.types.ts — regenerated via `npm run db:types` (do not hand-edit)
- e2e/checkout.spec.ts — new; asserts an expired coupon is rejected at line-item submit
```

If a file path is not yet known precisely (a new file with an undecided
name), name the directory and a placeholder, and flag it in Open Questions.

### Scope

Two sub-lists, both non-empty:

- **Included** — what this plan delivers.
- **Excluded** — what is deliberately out of scope, including adjacent
  features a reader might assume are bundled.

The Excluded list is the boundary that lets an implementer refuse scope
creep with a citation. Write it even when it feels obvious.

### Schema / Type Impacts

For any item touching a database, generated types, or a shared schema/API
contract (RPC, event payload, config object). State `None.` only when the
item genuinely has no such impact.

- New/changed tables, columns, indexes, policies — name them.
- Generated-types implications — which file regenerates, which command
  regenerates it, and an explicit "do not hand-edit" note for generated
  files.
- Migration order / back-compat notes if a deploy is involved.

### Verification

The exact commands the **verify stage** will run, taken from the project's
rules file (`AGENTS.md` / `.opencode/agents.md`). One per line. List the
project's real commands, not a generic "run the tests." Include generated-
type regen + diff as a verification when schema is touched. e.g.:

```markdown
- npm run db:types
- git diff --exit-code -- types/   # generated types committed, no drift
- npm run type-check
- npm run lint
- npm run test
- npm run e2e
```

### Open Questions

Decisions still pending from the user that do **not** block writing the
plan but do block implementation. Each question paired with a proposed
default so the user can answer with a yes/no. If a question blocks the
plan itself, you should not have written the plan yet — see Step 5 of
SKILL.md.

### History

One bulleted entry per revision: date + one-line summary of what changed.
Never overwrite prior entries. This is the audit trail that makes
revise-don't-clobber worth doing.

## Acceptance-criteria quality bar

A criterion is acceptable only when a third party can tell, from the
verifier alone, whether it passed. Restating the feature description is
not a criterion.

| Bad (no verifier) | Good (behavior + verifier) |
|---|---|
| "Comments are moderated." | "A comment row with `status='flagged'` is absent from the public `GET /comments` response — asserted by the `moderation` suite in `npm run test`." |
| "The discount is safe." | "An anon client submitting an expired `coupons.code` to the checkout RPC receives a `coupon_expired` error and zero price reduction — asserted by `npm run test`." |
| "The page is accessible." | "The checkout dialog passes axe checks in `e2e/checkout.spec.ts` (`npm run e2e` exits 0)." |

If you cannot write the verifier for a behavior, that behavior is under-
specified — it belongs in Open Questions, not in Acceptance Criteria.

## Revising an existing plan

When a plan file already exists for the slug:

- Preserve the frontmatter. Append the new revision date to `revised:`
  (never replace the array). Bump `status` only when the user changed it.
- Preserve prior section content. Add new/changed content as a dated
  block (`### Revised 2026-07-04 — <one phrase>`) inside the relevant
  section, or append a `## Revision 2026-07-04` subsection. Do not delete
  prior criteria that still apply — mark superseded ones inline as
  `~~struck through~~ (superseded 2026-07-04)`.
- Append a one-line entry to `## History`.
- If the entire approach has changed, create a new plan under a new slug
  and set the old plan's frontmatter `status: superseded` with a `related:`
  pointer to the new slug. Do not silently replace.

The point is an audit trail: a reader can reconstruct what was decided
when. Clobbering defeats that.

## Path & slug rules

- Default plan path: `.opencode/plans/<slug>.md` (a new file per item).
- Configurable via the project rules file (`AGENTS.md` /
  `.opencode/agents.md`). Honour a `plans_dir:` or `plans:` key there if
  present. Keep the `<slug>.md` filename convention even when the
  directory is overridden.
- Slug: lowercase-kebab. Prefer the roadmap item ID when one exists
  (e.g. `feat-cart-reservation`); otherwise derive from the feature, kept
  stable across revisions.
- If the rules file is absent and no other plan directory is in use,
  write to `.opencode/plans/<slug>.md` and create the directory.
- **Git status: plans are runtime/session artifacts, not committed.**
  The library's `.gitignore` ignores `.opencode/` ("Runtime-generated
  plans/agents when this library is consumed — do not commit"), and
  consumer repos should follow suit: a plan is a working contract that
  exists on disk for the session (design → implement → review), and the
  durable residue — what changed, why, deviations — lives in the commit
  message / handoff summary / PR body, not in a plan file in history.
  Projects that deliberately want the full contract in history can
  opt in by commenting out the `.opencode/` ignore entry; if they do,
  plans are committed, never ignored.