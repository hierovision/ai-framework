---
name: releasing-a-version
description: Cut a release for a versioned package — decide the SemVer bump from the changes merged since the last tag, update package.json and CHANGELOG.md, then, after explicit approval, tag, push, and draft GitHub release notes. Use whenever the user says "cut a release", "bump the version", "update the changelog", "tag vX.Y.Z", "draft the release notes", or "ship this" — even without saying "release". Not for CI pipeline topology (designing-cicd), GitHub issue creation (managing-github-issues), or registry publishing.
---

# Releasing a version

Take a repository from "changes merged" to "tagged release with a changelog
and release notes" without a human re-explaining the process.

## ASSUMPTIONS (made one-shot; not confirmed with the user)

This skill encodes choices that were **not** confirmed. Project conventions
win: check the repo's `AGENTS.md` / `CONTRIBUTING.md` / release config first
and override any assumption it contradicts.

1. **Versioning — Semantic Versioning** (`MAJOR.MINOR.PATCH`), bump level
   derived from Conventional Commits: `!` / `BREAKING CHANGE` → major,
   `feat` → minor, `fix` / `perf` → patch. Pre-1.0 (`0.x`): breaking → minor,
   everything else → patch.
2. **A single package at the repository root** with `package.json`. For a
   monorepo, apply the steps per workspace package and stop for guidance.
3. **Changelog — Keep a Changelog 1.1.0.** Sections `Added`, `Changed`,
   `Fixed`, `Removed`; only user-visible changes; date `YYYY-MM-DD` in UTC;
   newest release directly under an `## [Unreleased]` heading.
4. **Tag — annotated `vX.Y.Z`** (e.g. `v1.4.0`) on the release commit.
5. **Approval gate.** Version bump, changelog edit, notes draft, and a *local*
   release commit are safe to do unasked. Creating or pushing a tag and
   publishing a GitHub release require an explicit go-ahead; without one,
   prepare everything and stop.
6. **Release notes are drafted, never published** (`gh release create
   --draft`). If `gh` is unavailable or unauthenticated, write the notes to
   `RELEASE_NOTES.md` at the repo root.
7. **Tooling:** `git` present, and normally an authenticated `gh`. When either
   is missing, degrade as each step states rather than inventing output.
8. **Push target:** `origin`, current branch. Never force-push a tag; fix a bad
   tag by deleting it and re-tagging, after approval.

## Release checklist

Copy this into your response and tick items as you go:

- [ ] Preflight: clean tree, right branch, not behind `origin`
- [ ] Gather changes since the last tag (merged PRs / commits)
- [ ] Decide the SemVer bump; confirm a release is warranted
- [ ] Bump `package.json` (and lockfile)
- [ ] Update `CHANGELOG.md`
- [ ] Commit version + changelog (`chore(release): vX.Y.Z`)
- [ ] STOP: present the prepared release and request approval
- [ ] Tag `vX.Y.Z` and push commit + tag (after approval)
- [ ] Draft the GitHub release notes
- [ ] Verify tag target and draft state

### 1. Preflight

```bash
git status --porcelain            # must be empty
git rev-parse --abbrev-ref HEAD   # note the branch
git fetch --tags origin
git status -sb                    # must not be behind origin
```

A dirty tree makes the release commit ambiguous, so stop and resolve it (commit
or stash) before continuing. If the branch is behind `origin`, pull first — a
release must contain the latest merged work.

### 2. Gather changes since the last tag

Primary source is merged PRs, whose (squash-merge) titles carry the
Conventional Commit type:

```bash
LAST_TAG="$(git describe --tags --abbrev=0)"
gh pr list --state merged --limit 100 --json number,title,mergeCommit \
  --search "merged:>$(git log -1 --format=%cI "$LAST_TAG")"
```

Fall back, in order, when `gh` is unavailable or unauthenticated:

- `git log --no-merges --pretty='%s' "$LAST_TAG..HEAD"`
- a change list the user provides
- the bundled helper `scripts/collect-release-inputs.sh` — resolved against
  this skill's own directory, not the project's. Run it (execute, not read)
  from the target repo: it prints the last tag, commit subjects since, and a
  suggested bump.

Do not invent changes. If no source yields user-visible entries, there is
nothing to release (see step 3).

### 3. Decide the bump

| Highest change since last tag | Bump |
|---|---|
| `!` or `BREAKING CHANGE` | MAJOR (`0.x` → MINOR) |
| `feat` | MINOR (`0.x` → PATCH) |
| `fix`, `perf`, any other user-visible change | PATCH |
| only `docs`, `chore`, `ci`, `test`, `refactor`, `style` | none — do not release |

If nothing user-visible changed, report "nothing to release" and stop. Never
bump only to bump.

### 4. Bump `package.json`

Prefer the tool, which updates the manifest and lockfile without committing or
tagging:

```bash
npm version --no-git-tag-version X.Y.Z
```

Avoid plain `npm version` here: it creates a commit and tag, bypassing the
approval gate below. For other stacks, edit the manifest's `version` field and
any lockfile entry directly.

### 5. Update `CHANGELOG.md`

Move the `Unreleased` entries into a dated section, add a fresh empty
`Unreleased`, and update the compare links. Keep only user-visible changes and
reference PR numbers:

```markdown
## [Unreleased]

## [X.Y.Z] - YYYY-MM-DD
### Added
- Magic-link sign-in (#214)
### Fixed
- Tax rounding on partial refunds (#218)

[Unreleased]: https://github.com/OWNER/REPO/compare/vX.Y.Z...HEAD
[X.Y.Z]: https://github.com/OWNER/REPO/compare/vPREV...vX.Y.Z
```

Use the UTC date: `date -u +%F`.

### 6. Commit locally

```bash
git add package.json package-lock.json CHANGELOG.md
git commit -m "chore(release): vX.Y.Z"
```

This commit is local and reversible.

### 7. Approval gate — stop here by default

Present the prepared release: the chosen bump and rationale, the changelog
diff, the drafted release notes, and the exact tag / push / release commands
you intend to run. Then ask for explicit approval. Do **not** tag, push, or
publish before that.

The gate is satisfied only if the user already authorized these actions
("cut and push v1.4.0"). Even then, draft the notes before publishing.

### 8. Tag and push (after approval)

```bash
git tag -a vX.Y.Z -m "vX.Y.Z"
git push origin HEAD
git push origin vX.Y.Z
```

If the tag already exists, stop and ask — never force-move a tag. If the push
is rejected because the remote moved, repeat preflight; a release must include
the latest `main`.

### 9. Draft the release notes

```bash
gh release create vX.Y.Z --draft --title "vX.Y.Z" --notes-file RELEASE_NOTES.md
```

The notes are the changelog section for this version plus a one-line summary.
Without `gh`, write `RELEASE_NOTES.md` and report the draft step as pending.
The release stays a draft; publishing is a separate, approved action.

### 10. Verify

```bash
git show --stat vX.Y.Z    # tag peels to the release commit
gh release view vX.Y.Z    # state: draft
```

Report the version, tag, draft URL, and that publishing still needs approval.

## Failure modes

- **Dirty tree or behind `origin`** → stop, resolve, restart preflight.
- **No tag exists** → first release: use the initial version; ask which version
  rather than guessing its magnitude.
- **No user-visible changes** → nothing to release; stop.
- **Tag already exists** → stop; never force.
- **`gh` unavailable** → still produce `RELEASE_NOTES.md`; tag/push proceed
  only with approval, and the draft step is reported pending.

## Bundled script

`scripts/collect-release-inputs.sh` — execute it (do not read it as reference)
from the target repo to print the last tag, the commit subjects since, and a
suggested bump. Resolved against this skill's own directory, not the project's.
