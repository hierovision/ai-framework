# Git workflow contract

The library's branch / commit / merge discipline for implement loops.
Consumed by `implementing-features` (Step 1 + Step 11), `reviewing-code`
(the PR is the review unit), `designing-architecture` (branch derives
from the plan slug), and the `build` / `design` agents. Projects may
override the *naming* via their rules file; the *discipline* is fixed.

## Trunk policy: main is protected

- **Only PRs merge to main.** No direct pushes, no force-push anywhere
  (not even on feature branches), no local fast-forward shortcuts that
  bypass the PR.
- The merge itself is **user-initiated**: the agent pushes the branch,
  opens the PR, and the handoff reports "PR #N ready". The human (or an
  explicit "merge it" request) is the gate on the protected action.

## All work requires a branch

- Work touching tracked files — implement passes, trivial single-file
  edits, test authoring, docs edits — happens on a branch, never on
  main. *Trivial* skips the plan, never the branch.
- **Branch name derives from the plan slug**: `<type>/<name>` where
  `type` ∈ {`feat`, `fix`, `refactor`, `docs`, `chore`} comes from the
  slug's leading token (`feat-*`, `fix-*`, `refactor-*`, `docs-*`,
  `chore-*`; default `feat`), and `name` is the slug minus that prefix.
  Examples: `fix-activity-image-delete` → `fix/activity-image-delete`;
  `feat-cart-reservation` → `feat/cart-reservation`;
  `runtime-ui-validation-step` → `feat/runtime-ui-validation-step`.
  No plan (trivial edit) → `<type>/<short-description>`, e.g.
  `docs/agents-md-skill-list`. A project's rules file may define its
  own `branch_prefix:` / branch naming key; honor it.
- Design-only passes write gitignored artifacts (`.opencode/plans/`) and
  need no branch unless the project tracks plans (opt-in consumers).

## Commit discipline

- **Commits do not require an explicit user request** — committing and
  pushing the feature branch are a natural part of the pass. Only the
  merge is gated.
- **One commit per implement pass**, after the plan's Verification is
  green (Step 7 precedes). Message: `<slug>: <one-line summary>` (no
  plan → `<type>: <short summary>`). Match the repo's message style
  when it diverges.
- **Never commit runtime artifacts**: `.opencode/evidence/`,
  `.opencode/smoke/`, `.opencode/plans/` (gitignored by default),
  screenshots, generated scratch. `git status` must show only the
  plan's `Files to Modify` (plus the test files the AC layer added).
- Commit on the branch in logical steps if a pass spans long; the PR
  squash-merge collapses it to one main-history commit.

## Push, PR, merge

1. After the green verification (and before/with the handoff), push the
   branch: `git push -u origin <branch>`.
2. Open the PR against `main` (gh or the project's host): title =
   `<slug>: <summary>`, body = plan path + AC summary + verification
   results + handoff excerpt.
3. `reviewing-code` reviews the PR against the plan; fixes from review
   land as additional commits on the same branch (re-review), not as
   new PRs.
4. Handoff reports the PR URL. Merging waits for the user ("merge it" /
   the human clicks merge). Multi-session work resumes on the pushed
   branch, never on a fresh one.
