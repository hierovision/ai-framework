# Acceptance Criteria Reference (refining-issue-acceptance)

Read this when drafting the refined issue body or reviewing ACs for
implementation leaks. The script `scripts/refine-issue.mjs` enforces the rules
below mechanically; this file is the human-readable contract behind it.

Paths here are skill-relative — resolved against this skill's own directory,
not the project's.

## Contents

- The AC body template
- Test-type taxonomy (how each AC is verified)
- Good vs bad AC (behavioral/verifiable vs implementation-leaking)
- Self-check rules

## The AC body template

Write the refined issue body as a single markdown file the script will
`--apply` via `gh issue edit --body-file`. Preserve any `Roadmap ID` /
`Category` / `Score` metadata already present (from `managing-github-issues`)
so the issue stays linkable.

```markdown
## <Short, clear title or one-line summary>

<2-4 sentence description of what changes and why it matters to a user.
No implementation detail, no file or module names.>

### Acceptance Criteria

**AC1 — [e2e]** <Observable behavior a user journey through the real UI would
show.> Verify: <how an e2e test would observe it — page state, inline error,
navigation>.

**AC2 — [integration]** <Observable behavior at a seam — store+client, DB+policy,
outbox+replay, external boundary.> Verify: <how an integration test would
observe it — record persisted, event emitted, policy enforced>.

**AC3 — [unit]** <Observable behavior of isolated logic — validation/computation
rule, transformation.> Verify: <how a unit test would observe it — given input X
the result is Y>.

### Notes
<Optional: non-behavioral context, open questions, links. No code.>
```

Rules the script enforces:

- A section headed `Acceptance Criteria` (case-insensitive) must exist.
- At least one AC line must carry a test-type tag: `[unit]`, `[integration]`, or
  `[e2e]` (case-insensitive).
- The body must contain **no implementation-leak tokens** — see the denylist in
  the script (`scripts/refine-issue.mjs` → `LEAK_PATTERNS`). In short: no file
  paths (`src/...`, `app/...`), no source-file extensions attached to names
  (`Form.tsx`, `users.py`), no `function`/`class`/module declarations, no
  `import`/`export`/`const`/`def` assignments.

## Test-type taxonomy

Classify each AC by *how it is most likely verified* — this tells the
implementer which test skill proves it, without dictating the code.

| Tag | What it covers | Proving test |
|---|---|---|
| `[unit]` | Isolated logic: pure functions, validation/computation rules, transformations. No collaborators. | `../writing-unit-tests/SKILL.md` — asserts the result for given inputs. |
| `[integration]` | A seam: store+client, DB+policy, outbox+replay, an external service boundary. Real collaborators, faked transport only. | `../writing-integration-tests/SKILL.md` — asserts the interaction persisted/emitted/enforced. |
| `[e2e]` | A user journey through the real UI (browser): page state, inline errors, navigation, flows. | `../writing-e2e-tests/SKILL.md` — asserts what a user sees/experiences. |

A healthy issue usually carries ACs across two or three tags. Tag each line so
the implementer knows what kind of test proves it.

## Good vs bad AC

The dividing line: a **good** AC describes observable, external behavior a test
could assert. A **bad** AC leaks implementation (files, modules, functions, code
changes) or is too vague to test.

**BAD — implementation leak (script rejects these):**
- "Add a `validateForm()` function in `src/components/Form.tsx` that checks empty fields."
- "Update the `users` table migration to add an `email` column."
- "Refactor `AuthService.authenticate` to use JWT."

**GOOD — behavioral, verifiable (script accepts these):**
- "[e2e] Submitting a form with empty required fields shows an inline error per field and creates no record."
- "[integration] A user cannot be created without a valid email; the API returns 422 with a field-level error and no row is written."
- "[unit] Given an empty email, the sign-up validation reports an invalid-email error and does not proceed."

**BAD — unverifiable (too vague, rewrite before accepting):**
- "Make the form better." / "Improve performance." / "Handle errors gracefully."
- These name no observable outcome a test could assert.

**GOOD — verifiable:**
- "[e2e] After a failed submit, the page keeps the user's entered values and focuses the first invalid field."
- "[integration] A duplicate email sign-up is rejected and an audit event recording the rejection is emitted."
- "[unit] A password shorter than 8 characters fails validation with a too-short reason."

## Self-check rules

Before running the script, every AC must satisfy all three:

1. **Behavioral, not implementation** — no file/module/function/code references.
2. **Verifiable** — a unit, integration, or e2e test could assert the outcome.
3. **Tagged** — exactly one `[unit]` / `[integration]` / `[e2e]` tag per AC.
