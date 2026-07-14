---
name: refining-issue-acceptance
description: Refine a GitHub issue into a proper engineering spec — a short, clear description plus well-defined acceptance criteria (AC) written as observable, external behavior a test could assert (unit, integration, or e2e). Use whenever the user says "refine this issue", "add acceptance criteria to issue N", "turn issue N into a spec", "improve/clean up the issue body", "spec out issue N", or hands over a rough issue to make shippable — even if they don't say "acceptance". Works on issues produced by managing-github-issues (carrying Roadmap ID, Category, Score, and a source checklist) and on a plain issue given only a title + raw description. Not for creating issues from a roadmap (that is managing-github-issues), ranking/triaging a backlog (triaging-requirements), or implementing/fixing the code an issue describes (implementing-features).
---

# Refining Issue Acceptance

Upgrade a rough GitHub issue into a proper engineering spec: a short, clear
description and acceptance criteria (AC) that describe *observable behavior a
test could assert* — never the files, modules, or functions that implement it.
Implementation is left to the implementer.

The judgment (writing behavioral ACs, classifying each by how it is verified)
lives here. The deterministic, re-runnable side-effect plumbing (fetch current
issue, validate the spec, render a before→after, and edit the live issue)
lives in `scripts/refine-issue.mjs`. Mirror the pattern of
`../managing-github-issues/SKILL.md`: deterministic script + confirmation-gated
live edit.

## The refinement pass

Copy this checklist and check off items as you complete them.

```
Refine Progress:
- [ ] 1. Fetch the issue (gh issue view) or read the title + raw description
- [ ] 2. Draft the refined description (2-4 sentences, user-facing, no code)
- [ ] 3. Draft ACs as observable behavior; tag each [unit]/[integration]/[e2e]
- [ ] 4. Self-check: no file/module/function leaks; every AC is verifiable
- [ ] 5. Dry-run — confirm the proposed spec and the validation result
- [ ] 6. Confirm the live edit with the user
- [ ] 7. Apply — edit the issue (external side effect, confirmation-gated)
```

### Step 1 — Get the issue

- Issues from `managing-github-issues` already carry `Roadmap ID`, `Category`,
  `Score`, and a `- [ ]` source checklist pulled from planning docs. Treat the
  checklist as raw material, not as finished AC.
- A plain issue gives you a title + body. If there is no source checklist, you
  still write ACs from the title and description — the skill does not require a
  checklist to exist.

Fetch with:

```
gh issue view <number> --repo owner/name --json title,body
```

Replace `<number>`/`<owner/name>` as the user supplies; infer the repo from the
working directory via `gh repo view --json nameWithOwner` if not given.

### Step 2 — Write the description

A short, clear description: 2–4 sentences stating what changes and why it
matters to a user. No implementation detail, no file names. Keep the existing
title if it is already good; otherwise propose a tighter one.

### Step 3 — Write the acceptance criteria

Write each AC as **observable, external behavior a test could assert**. Phrase
it from the user's or system's vantage point — what is seen, returned, created,
blocked, or emitted — not how the code achieves it.

Tag every AC with how it is most likely verified, without dictating the code:

- **`[unit]`** — isolated logic: a pure function, a validation/computation rule,
  a transformation. A unit test asserts the result for given inputs. (Maps to
  `../writing-unit-tests/SKILL.md`.)
- **`[integration]`** — a seam where collaborators meet: store+client,
  DB+policy, outbox+replay, an external boundary. An integration test asserts the
  interaction persisted/emitted correctly with real collaborators (faked
  transport only). (Maps to `../writing-integration-tests/SKILL.md`.)
- **`[e2e]`** — a user journey through the real UI (browser). An e2e test asserts
  what a user sees/experiences: page state, inline errors, navigation. (Maps to
  `../writing-e2e-tests/SKILL.md`.)

A single issue usually needs ACs spanning two or three types; tag each line so
the implementer knows which test proves it. The full AC template and the
good-vs-bad examples (behavioral/verifiable vs implementation-leaking) are in
[references/acceptance-criteria.md](references/acceptance-criteria.md). Read it
when drafting the body or reviewing for leaks.

### Step 4 — Self-check (the hard requirements)

Before running the script, verify each AC against these rules:

- **Behavioral, not implementation.** No file paths (`src/...`), module names,
  function/method names, or code snippets. Say "submitting an empty form shows
  an inline error and creates no record", not "add `validateForm()` in
  `src/components/Form.tsx`".
- **Verifiable.** A test — unit, integration, or e2e — could assert the stated
  outcome. If you cannot imagine a test for it, rewrite it.
- **Tagged.** Every AC carries exactly one `[unit]`/`[integration]`/`[e2e]` tag.

### Step 5 — Dry-run (default-safe)

Write the refined body to a file following the template, then run the script
with `--dry-run` (the default if neither flag is given). It fetches the current
issue (or uses `--current-body`/`--current-title` for an offline check), prints
the before→after, validates the AC rules, and prints `VALIDATION: PASS` or
`VALIDATION: FAIL` with the specific violations.

```
node skills/refining-issue-acceptance/scripts/refine-issue.mjs \
  --issue <number> --repo owner/name \
  --refined-body /tmp/refined-body.md --dry-run
```

Offline / no-`gh` alternative (used by evals and local drafts):

```
node skills/refining-issue-acceptance/scripts/refine-issue.mjs \
  --current-title "Original title" --current-body /tmp/current.md \
  --refined-body /tmp/refined-body.md --dry-run
```

Confirm the proposed title and body read well and the validation passed.

### Step 6 — Confirm the live edit

Editing a live issue is an **external side effect**. Do not run `--apply`
without explicit user confirmation. Show the dry-run output (proposed spec +
`VALIDATION: PASS`) and the target issue, then ask. Only after the user
confirms, run `--apply`.

### Step 7 — Apply (confirmation-gated)

```
node skills/refining-issue-acceptance/scripts/refine-issue.mjs \
  --issue <number> --repo owner/name \
  --refined-body /tmp/refined-body.md --title "<proposed title>" --apply
```

`--apply` re-runs the same validation; if it fails, the script refuses to push
the edit (exits non-zero) so a bad spec never reaches the live issue. On pass it
runs `gh issue edit <number> --title "<proposed title>" --body-file
<refined-body>`. Re-run the dry-run afterward to confirm the issue now reflects
the refined spec.

## When to use this skill

- "Refine issue #42", "add acceptance criteria to issue N", "spec out this
  issue", "clean up the issue body".
- An issue from `managing-github-issues` needs its source checklist turned into
  real, testable AC.
- A rough or vague issue needs to become a shippable engineering spec.

## When not to use this skill

- Creating issues from `ROADMAP.md` → `managing-github-issues`.
- Ranking/triaging a raw backlog → `triaging-requirements`.
- Turning the refined AC into a build plan → `designing-architecture` (it
  produces the approved plan artifact `implementing-features` requires). Do not
  jump straight from AC to implementation.
- Implementing or fixing the code the issue describes → `implementing-features`
  (executes a plan produced by `designing-architecture`).
- Writing the actual tests for the AC → `writing-unit-tests`,
  `writing-integration-tests`, `writing-e2e-tests` (referenced by the AC tags).

## References

- [references/acceptance-criteria.md](references/acceptance-criteria.md) — the
  AC template, the test-type taxonomy, and good-vs-bad examples (behavioral/
  verifiable vs implementation-leaking). Read when drafting or reviewing ACs.
- Upstream: [../managing-github-issues/SKILL.md](../managing-github-issues/SKILL.md)
  — the skill that produces the rough issues this one refines.
- Sibling test skills (what each AC tag maps to):
  [../writing-unit-tests/SKILL.md](../writing-unit-tests/SKILL.md),
  [../writing-integration-tests/SKILL.md](../writing-integration-tests/SKILL.md),
  [../writing-e2e-tests/SKILL.md](../writing-e2e-tests/SKILL.md).
- Downstream planning: [../designing-architecture/SKILL.md](../designing-architecture/SKILL.md)
  — turns this issue's AC into an approved implementation plan that
  `implementing-features` then executes.
