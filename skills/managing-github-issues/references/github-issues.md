# GitHub Issues Reference (managing-github-issues)

Read this when you are about to run the sync script or need the exact `gh`
recipes, label taxonomy, body template, or the cleanup contract. The script
`scripts/sync-issues.mjs` encodes all of this; this file is the human-readable
contract behind it.

Paths here are skill-relative — resolved against this skill's own directory,
not the project's.

## Contents

- Label taxonomy
- `gh issue create` recipe
- `gh issue list` recipes (idempotency + audit)
- Issue body template
- ROADMAP write-back column contract
- GitHub Project (V2) ranking
- Source-doc cleanup contract
- Cross-reference (item ↔ issue parity)

## Label taxonomy

Every issue gets two kinds of labels:

| Label | Applied to | Purpose |
|---|---|---|
| `roadmap-id:<id>` | every issue | dedup / idempotency key — never reuse an id |
| `feature` | category `feature` | category |
| `bug` | category `bug` | category |
| `tech-debt` | category `debt` | category (roadmap writes `debt`; the issue label is `tech-debt`) |
| `chore` | category `chore` | category |

The `roadmap-id:<id>` label is the contract that makes re-runs idempotent: a
second run detects the existing issue by this label and skips creation instead
of duplicating. The script also treats a `Sources` cell that already carries
`owner/repo#<n>` as "backed" (the write-back signal), which is what makes the
count reach `0 to create` offline after a real run.

## `gh issue create` recipe

```
gh issue create \
  --repo owner/repo \
  --title "<Title>" \
  --label "roadmap-id:<id>,<category>" \
  --body-file /tmp/issue-body.md
```

- `--repo` is inferred from the directory containing `ROADMAP.md` via
  `gh repo view --json nameWithOwner` (override with `--repo owner/name`).
- `<category>` is one of `feature` / `bug` / `tech-debt` / `chore`.
- The script writes the body to a temp file and passes `--body-file` so
  markdown (checklists) survives shell quoting.

## `gh issue list` recipes

Idempotency / audit — find an existing issue for a row by its dedup label:

```
gh issue list --repo owner/repo \
  --label "roadmap-id:<id>" --state all \
  --json number,title,labels
```

Enumerate everything the roadmap currently owns (audit / reconciliation):

```
gh issue list --repo owner/repo \
  --label "roadmap-id:*" --state all \
  --json number,title,labels
```

(Use the script's dry-run for day-to-day enumeration; call `gh` directly only
when you need to reconcile by hand.)

## Issue body template

The script builds each body from the row plus the referenced `Sources` files:

```
## <Title>

**Roadmap ID:** `<id>`
**Category:** <category>
**Score:** <impact>×<urgency> = <score>  (status: <status>)

### Acceptance / source checklist
- [ ] <extracted sub-task bullet>
- [ ] <extracted sub-task bullet>

> Synced from ROADMAP.md via the `managing-github-issues` skill.
```

**Body detail extraction rule.** For each file named in the row's `Sources`
cell, the script reads the file (resolving relative paths against the
roadmap's directory) and finds the section whose heading best matches the
reference in `Sources` — e.g. a `Sources` entry of `todo.md (Epic 2: ...)`
points at the `## Epic 2` heading. The bullets under that heading become the
`- [ ]` checklist. If nothing matches, the body records "No source checklist
extracted" rather than guessing.

## ROADMAP write-back column contract

After a real `--apply` create, the script rewrites the row's `Sources` cell to
append the issue reference, forming the two-way link:

- Column: the `Sources` column of the open-item tables (the 8th column:
  `ID | Title | Category | Impact | Urgency | Score | Status | Sources | Notes`).
- Value appended: `owner/repo#<n>` (e.g. `acme/widgets#42`),
  separated from existing content by `; `.
- Idempotent: if the cell already contains that `owner/repo#<n>`, it is not
  appended again.

This write-back is what lets a later dry-run report `0 to create` without
needing the network.

## GitHub Project (V2) ranking

Plain issues have no native priority or rank. When `--with-project` is passed,
the script makes the roadmap's ranking visible and sortable via a Project (V2):

1. **Ensure one Project** for the repo (idempotent). Default title
   `<repoName> Roadmap`; override with `--project <number>` or
   `--project-title <title>`. Created via:
   ```
   gh project create --owner <owner> --title "<title>"
   ```
   **Link it to the repo** so it appears in the repo's Projects tab (Projects V2
   are owned by the user/org, not the repo, and are invisible there until
   linked):
   ```
   gh project link <number> --owner <owner> --repo <repo>
   ```
   The web UI path is `github.com/users/<owner>/projects/<n>` (user-owned) or
   `github.com/orgs/<owner>/projects/<n>`; linking adds it to the repo's
   Projects tab too.
2. **Ensure a `Priority` single-select field.** The script reads existing fields
   (`gh project field-list --format json`), and if `Priority` is absent creates
   it with options High / Medium / Low:
   ```
   gh project field-create <number> --owner <owner> --name Priority \
     --data-type SINGLE_SELECT --single-select-options "High,Medium,Low"
   ```
3. **Add every open issue to the Project.** `gh project item-add <number>
   --owner <owner> --url <issue-url>` (deduped by checking the item list).
4. **Set `Priority` per score bucket:**

   | Score | Priority |
   |---|---|
   | ≥ 6 | High |
   | 3–5 | Medium |
   | ≤ 2 | Low |

   ```
   gh project item-edit --project-id <project-node-id> \
     --field-id <priority-field-node-id> \
     --single-select-option-id <option-node-id> --item-id <item-node-id>
   ```

**Critical `gh project` quirks (learned the hard way):**

- `gh project` subcommands use **`--format json --jq <expr>`** (NOT `--json`).
- `gh project item-list` / `field-list` return an object with an `items` /
  `fields` array — index with `.items[]?` / `.fields[]?` and group/sort with
  `group_by` / `sort_by` (no array-at-top-level).
- `gh project item-edit` requires **`--project-id`** (the Project node id, from
  `gh project view <n> --format json --jq .id`) — NOT `--project <n>`.
- The `Priority` field id and each option id come from `field-list`; the option
  id depends on its name, so resolve `High`/`Medium`/`Low` dynamically.
- **Token scope.** `gh project` needs the `project` OAuth scope. If you hit
  `missing required scopes [read:project]`, the *user* must run
  `gh auth refresh -s project` — the script never does auth.

**Manual order is UI-only.** The `Priority` field is sortable, but the exact
1–N drag order is set in the Project UI, not via `gh`. `ROADMAP.md` remains the
authoritative total order. Re-running `--with-project` adds nothing new and
re-applies `Priority` (idempotent).

## Source-doc cleanup contract

Once the roadmap is current (a re-run reports `0 to create`), the legacy
planning docs named in the roadmap's `sources:` frontmatter are redundant. The
cleanup step:

1. Lists every entry in `sources:` (e.g. `REQUIREMENTS.md`,
   `docs/REQUIREMENTS.md`, `todo.md`).
2. Prompts the user — **confirmation-gated, never automatic.**
3. On explicit `--apply-cleanup`, `git mv`s each file (preserving its relative
   path) under `archive/roadmap-source/` in the repo root. This is a
   git-tracked move, not a hard delete — history survives.
4. Never candidates: `ROADMAP.md` itself, and any file not listed in
   `sources:`.

Trigger rule: the cleanup prompt only fires after a sync where **no open row
lacks an issue ref**. If some rows are still unbacked, the script reports which
ones and skips the prompt.

## Cross-reference (item ↔ issue parity)

For the GitHub issue → roadmap-item mapping (field parity, label inference),
see the sibling reference
[../triaging-requirements/references/stacks/github.md](../triaging-requirements/references/stacks/github.md).
This skill is the *reverse* direction of that mapping: it pushes ranked roadmap
items out to issues, whereas `triaging-requirements` pulls issues *into* the
roadmap. Together they form the chain: rank → persist.
