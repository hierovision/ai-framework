---
name: managing-github-issues
description: Persist an established ROADMAP.md as GitHub issues — one issue per open roadmap row, enriched from its source files, tagged with a stable roadmap-id label for idempotent re-runs, written back into the roadmap for a two-way link, and (optionally, via --with-project) ranked in a GitHub Project (V2) with a Priority field. Use whenever the user says "sync the roadmap to GitHub issues", "create issues for the roadmap", "turn ROADMAP.md into issues", "persist the roadmap as issues", "rank the roadmap issues in a project", or wants a shared, assignable, sortable backlog from an existing roadmap — even if they don't say "issue". Not for ranking/triaging the backlog itself (that is triaging-requirements), one-way issue→roadmap edits, or child sub-issues.
---

# Managing GitHub Issues

Turn an established `ROADMAP.md` into a shared, assignable GitHub backlog. The
roadmap is the source of truth; this skill pushes it out to issues. It is the
second half of the triage chain — `triaging-requirements` ranks a backlog into
`ROADMAP.md`, this skill persists those ranked items as issues.

Deterministic, re-runnable work (markdown parse, `gh` calls, dry-run,
write-back, source-doc audit) lives in `scripts/sync-issues.mjs`. The judgment
(what detail to pull, confirming the live run and any cleanup with the user)
lives here.

## The sync pass

Copy this checklist and check off items as you complete them.

```
Sync Progress:
- [ ] 1. Locate ROADMAP.md and resolve the target repo
- [ ] 2. Dry-run — confirm the planned-create set
- [ ] 3. Confirm the live run with the user
- [ ] 4. Apply — create issues, write back refs
- [ ] 5. Re-run dry-run — confirm idempotency (0 to create)
- [ ] 5b. (Optional) Rank in a GitHub Project — `--with-project` (needs `project` token scope)
- [ ] 6. Close the loop — offer source-doc cleanup (confirmation-gated)
```

### Step 1 — Locate ROADMAP.md and resolve the repo

The roadmap is wherever the user points (default: `ROADMAP.md` at the repo
root). Resolve the target GitHub repo:

- Default: infer from the directory containing `ROADMAP.md` via
  `gh repo view --json nameWithOwner` (works for any repo dir, e.g.
  `~/repos/my-app` → `acme/my-app`).
- Override: explicit `--repo owner/name`.

Read the four **open** tables — `## Features`, `## Bugs`, `## Tech Debt`,
`## Chores`. Rows there are the work to sync. `## Done`, `## Skipped`, and
`## Proposed (cut)` are excluded (one-way sync; open items only).

### Step 2 — Dry-run (default-safe)

Run the script with `--dry-run` (the default if neither flag is given):

```
node skills/managing-github-issues/scripts/sync-issues.mjs \
  --dry-run --roadmap <path-to-ROADMAP.md>
```

It prints one planned `gh issue create` per open row, each carrying
`--label "roadmap-id:<id>,<category-label>"`, and a summary
`<N> to create, <M> already backed`. Verify the count matches the open rows and
that Done/Skipped produced nothing. Detail the planned bodies by reading the
script output or its reference.

### Step 3 — Confirm the live run

Creating real issues is an **external side effect**. Do not run `--apply`
without explicit user confirmation. Show the dry-run summary and the target
repo, then ask. Only after the user confirms, run:

```
node skills/managing-github-issues/scripts/sync-issues.mjs \
  --apply --roadmap <path-to-ROADMAP.md>
```

### Step 4 — Apply and write back

`--apply` creates each issue, then rewrites the row's `Sources` cell to append
`owner/repo#<n>` (e.g. `acme/widgets#42`). That write-back is the
two-way link and the idempotency signal.

### Step 5 — Confirm idempotency

Re-run the dry-run. It should now report `0 to create` — every open row is
detected via its `roadmap-id:<id>` label / written-back `Sources` ref. If any
row still shows as "to create", investigate (missing label, parse miss) before
proceeding.

### Step 5b — Rank in a GitHub Project (optional, `--with-project`)

Plain GitHub issues have **no native priority or rank field**. To make the
roadmap's `impact×urgency` ranking visible and sortable in GitHub (the
GitHub-prescribed mechanism), pass `--with-project`. This ensures one Project
(V2) for the repo (idempotent; default title `<repoName> Roadmap`, override with
`--project <number>` or `--project-title <title>`), adds each open issue to it,
and sets a `Priority` single-select from the score buckets:

| Score | Priority |
|---|---|
| ≥ 6 | High |
| 3–5 | Medium |
| ≤ 2 | Low |

```
node skills/managing-github-issues/scripts/sync-issues.mjs \
  --apply --with-project --roadmap <path-to-ROADMAP.md>
```

**Prerequisite — token scope.** Managing Projects requires the `project` OAuth
scope. If `gh project` fails with `missing required scopes [read:project]`, the
user must run `gh auth refresh -s project` first. This is a user-auth action;
the script will not do it.

**Manual order is UI-only.** The `Priority` field is sortable, but the exact
1–N drag-order is set in the Project UI, not via `gh` — `ROADMAP.md` remains the
authoritative total order. Idempotent: re-running adds nothing new and
re-applies `Priority`.

### Step 6 — Close the loop: source-doc cleanup (confirmation-gated)

Once the roadmap is current (re-run reports `0 to create`), the legacy planning
docs named in the roadmap's `sources:` frontmatter are redundant. The script
audits them:

```
node skills/managing-github-issues/scripts/sync-issues.mjs \
  --check-cleanup --roadmap <path-to-ROADMAP.md>
```

This **lists the candidate docs and stops** — it performs no file changes. It
only fires after a sync where no open row lacks an issue ref; if some rows are
still unbacked, it reports which and skips the prompt.

Removal is **never automatic**. On explicit user confirmation, run:

```
node skills/managing-github-issues/scripts/sync-issues.mjs \
  --apply-cleanup --roadmap <path-to-ROADMAP.md>
```

This `git mv`s each candidate under `archive/roadmap-source/` (git-tracked,
history preserved) — never a hard `rm`. `ROADMAP.md` itself is never a
candidate. See
[references/github-issues.md](references/github-issues.md#source-doc-cleanup-contract)
for the full contract.

## Dedup-label contract

Every issue carries `roadmap-id:<id>`, where `<id>` is the roadmap row's stable
slug (e.g. `feat-dark-mode`). This label is the idempotency key: a
re-run detects the existing issue by label and skips creation instead of
duplicating. Never reuse an id across issues. The category label
(`enhancement` / `bug` / `tech-debt` / `chore`) is added alongside it; note the
roadmap writes `feature` but the issue label is `enhancement` (reusing
GitHub's default), and writes `debt` but the issue label is `tech-debt`.

## Body-enrichment rule

Each issue body carries the row's score, category, and a sourced checklist. The
script reads each file named in the row's `Sources` cell, finds the section
whose heading matches the `Sources` reference (e.g. `todo.md (Epic 2: ...)` →
`## Epic 2`), and emits that section's bullets as a `- [ ]` checklist. If
nothing matches, the body says so rather than guessing. Full template and
extraction rule:
[references/github-issues.md](references/github-issues.md#issue-body-template).

## When to use this skill

- "Sync the roadmap to GitHub issues" / "create issues for the roadmap".
- The user has a current `ROADMAP.md` and wants a shared, assignable backlog.
- After a `triaging-requirements` pass, to persist the ranked items.

## When not to use this skill

- Ranking or triaging a raw backlog → that is `triaging-requirements`.
- Editing an issue in GitHub and expecting the roadmap to update → this is a
  one-way sync (roadmap is source of truth).
- Creating child sub-issues / parent-child hierarchy → one issue per row; the
  breakdown lives in the body checklist.
- Closing issues when a row moves to Done, or labeling Skipped as `wontfix` →
  out of scope for this plan.
- Milestones or assignees → not set by this skill. Ranking via a GitHub
  Project (V2) **is** set, but only when `--with-project` is passed; the exact
  1–N manual order is set in the Project UI, not by the script.

## References

- [references/github-issues.md](references/github-issues.md) — `gh` recipes,
  label taxonomy, body template, ROADMAP write-back column contract, and the
  source-doc cleanup contract. Read when running the script or resolving a
  sync/write-back/cleanup question.
- Upstream: [../triaging-requirements/SKILL.md](../triaging-requirements/SKILL.md)
  — the ranking half of the chain (rank → persist). This skill consumes its
  output.
