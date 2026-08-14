---
name: reviewing-code
description: Review a change (a diff, a branch, or an implement pass's output) against the plan that authorized it and against engineering quality, then issue a verdict with actionable findings — read-only on the code. Use whenever the user says "review this", "review the diff / PR / branch", "is this ready to merge", "check my changes against the plan", or at a handoff from an implement pass — even without saying "review". Routes fixes back to implementing-features and design defects to designing-architecture (same class-3 posture as the debugger); never edits source, never re-runs the design. Not for fixing the code (implementing-features), diagnosing a failing test (debugging-test-failures), writing tests (the test trio), or a multi-lens council review (shipped as `agents/council.md`; defaults to free models, paid/Go escalation opt-in).
---

# Reviewing Code

The verdict discipline of the core loop — the final stage of triage →
design → implement → verify → **review**. It consumes what an
`implementing-features` pass hands off (a diff/changeset plus, when
present, the plan artifact that authorized it) and produces a verdict
with actionable findings. It is **read-only on the code**: it diagnoses,
it never patches. CI/CD workflow changes are in scope too: the review
checks a workflow against a `designing-cicd` plan and flags secret /
supply-chain posture per `securing-ci` (those two are the producer and the
security-discipline siblings). A review is **done** when every changed hunk has been
assessed, findings are classified by severity, each finding cites a
location + a concrete reason, and a verdict is issued. "Looks fine" is
not a review — a finding a third party cannot act on is not a finding.

This skill is the **consumer** side of two sibling contracts: the plan
artifact (defined in
[plan-format.md in designing-architecture](../designing-architecture/references/plan-format.md)
— the plan + ACs the review checks the diff against; link it, never
duplicate it) and the implement handoff (defined in
[../implementing-features/SKILL.md](../implementing-features/SKILL.md) —
files-in-scope, `## History` deviations, follow-ups, AC status; the
review consumes exactly this). Scope-discipline is a first-class review
criterion: an out-of-scope edit with no `## History` deviation is the
auditability breach the implement skill exists to prevent, and the
review is where it is caught.

Relationship to the council: `agents/council.md` (shipped) runs
  security/performance/ux/architecture/product lenses, **defaulting to free
  models with a paid/Go-escalation opt-in**. This skill is the **single-reviewer**
discipline — one reviewer, one verdict, against a plan. Note the
relationship; do not absorb the council.

## The review pass

Copy this checklist and check off items as you complete them.

```
Review Progress:
- [ ] 1. Resolve the change-under-review (the diff) + the plan (if any)
- [ ] 2. Detect stack & load the matching review-time stack reference
- [ ] 3. Plan-conformance sweep (when a plan is in play)
- [ ] 4. Inspect the diff in priority order (the checklist below)
- [ ] 5. Classify findings by severity
- [ ] 6. Issue the verdict
- [ ] 7. Write REVIEW.md at the repo root; STOP
```

### Step 1 — Resolve the diff and the plan

A review starts from a **diff/changeset** plus, when present, the plan
artifact that authorized it. Resolve the diff first; do not review from
prose. The review unit is the PR: implement passes deliver a branch +
PR per `reference/git-workflow.md`, and this review is the gate that
precedes the (user-initiated) merge to protected `main`.

- **Staged diff** → `git diff --staged` (or the harness equivalent).
- **A branch range** → `git diff <base>...HEAD` the user named; if the
  base is ambiguous, ask for the merge-base / PR base.
- **An implement pass's reported changes** → the files the pass lists in
  its handoff; reconstruct the diff via `git diff` against the pass's
  starting point, or read the reported files directly if no VCS range is
  available.
- **No diff is resolvable** (the user says "review my changes" but no
  staged files, no branch range, no file list) → **ask how to obtain it**
  (git range, staged, file paths). Do NOT guess a diff and do NOT review
  from prose — a review without a diff is not a review.

When a plan is in play, read it **before** inspecting the diff: the
frontmatter `status` (a `draft` plan under review is a finding — the
change was built against an un-approved contract), the `## Goal /
Approach`, every `## Acceptance Criteria`, `## Files to Modify`,
`## Scope` (Included + Excluded), `## Schema / Type Impacts`, and
`## Verification`. The plan is the contract the diff is checked against.
When no plan is in play (a standalone diff with no plan artifact), skip
Step 3 and proceed to Step 4 — review against engineering quality alone,
and note in REVIEW.md that no plan-conformance sweep was possible.

### Step 2 — Detect stack & load the matching review-time reference

Identify the project stack from the rules file (`AGENTS.md` /
`.opencode/agents.md`). If this skill bundles a matching stack reference
under `references/stacks/` (resolved against **this skill's own
directory** — not the project's), read it now and apply its review-time
concerns. If none exists, proceed generically and flag the gap to the
user in REVIEW.md (a missing stack reference is a finding, not a silent
"I'll improvise").

Available stack references:

- vue-supabase → [references/stacks/vue-supabase.md](references/stacks/vue-supabase.md)
  Read when the project is Vue 3 + Pinia + Supabase (Postgres + Auth +
  RLS) with Vuetify 3 + Playwright e2e. Applies review-time checks for
  RLS-policy widening on schema/policy diffs, generated-types never
  hand-edited (flag a diff that touches `types/database.types.ts` by
  hand), Vuetify semantic variables vs raw CSS, Pinia store pattern
  conformance, and e2e selector/timeout discipline in changed specs.

### Step 3 — Plan-conformance sweep (when a plan is in play)

This is the first-class check. For every hunk in the diff:

1. **Map it to `Files to Modify`.** A hunk in a file not on the list is
   out of scope. Check the plan's `## History` and `### Follow-ups` for
   a recorded deviation: a mechanical deviation (file moved/renamed,
   path alias corrected) recorded in History is legitimate; an
   **unrecorded** out-of-scope edit is a finding (see Severity → blocker).
   An out-of-scope edit recorded as a follow-up is a minor (the process
   held; the follow-up is honest).
2. **Check it against `Scope → Included`.** The change should deliver
   what Included says; a hunk that delivers something else is a finding.
3. **Check it against `Scope → Excluded`.** A hunk that delivers an
   Excluded item is a finding regardless of recording — Excluded is the
   boundary the plan drew, not a suggestion.
4. **Evidence every AC.** For each acceptance criterion: is it
   evidenced? A test asserts it (cite the test), or it is honestly
   marked `manual` in the implement handoff. An AC with **no** evidence
   — no test, no manual marker — is a finding (major). A criterion that
   asserts against the wrong layer (a unit test for an e2e-only journey)
   is the test-trio's right-layer check (see Step 4).

The auditability read: a future reader of the diff must be able to map
every hunk to a plan citation (a Files-to-Modify entry + an Included
item) or a recorded deviation. An unexplained out-of-scope hunk breaks
that — it is the breach the review exists to catch.

### Step 4 — Inspect the diff in priority order

Walk every hunk and assess, in this order (correctness and security
outrank taste — do not lead with nits):

1. **Correctness against the ACs** — does the code do what the criteria
   assert? A logic bug, a wrong sort direction, an off-by-one, a missing
   error path that an AC names. This is the top-priority check.
2. **The test net** — are the tests in the diff behaviour-asserting,
   meaningful (could-fail-red check — break the behaviour, does the test
   go red?), right-layer (unit for isolated logic; integration for a
   store+client / DB+policy seam; e2e for a user journey), and
   **additive** (a new test adds coverage; a deleted/weakened test
   removes it)? The test trio —
   [writing-unit-tests](../writing-unit-tests/SKILL.md),
   [writing-integration-tests](../writing-integration-tests/SKILL.md),
   [writing-e2e-tests](../writing-e2e-tests/SKILL.md) — defines the
   standard. **The cardinal rule (from
   [debugging-test-failures](../debugging-test-failures/SKILL.md)) is a
   review criterion**: never green by weakening the net. A diff that
   makes a failing test pass by adding `.skip`, deleting/commenting an
   assertion, widening a tolerance, guarding with try/catch, or mocking
   away the behaviour under test is a **blocker** — it hides a real
   defect instead of fixing it. Cite the exact weakening. When the
   plan's `## History` carries `implementing-features`' red evidence
   (Step 5) and coverage-gate outcome (Step 9 — rebalancing + expand/no-
   gap), **spot-check those claims**: does the recorded red evidence
   actually name the right failure (not a harness defect)? does the
   coverage-gate reasoning hold up against the diff (a cited rebalance
   or a cited gap, not padding)? Review what the record asserts against
   what the diff shows, rather than re-deriving the meaningfulness check
   from zero. See [implementing-features](../implementing-features/SKILL.md)
   Steps 5 and 9 for the contract of those records.
3. **Scope conformance** — from Step 3. An unrecorded out-of-scope hunk
   is a blocker; a noted deviation/follow-up is a minor.
4. **Error / edge handling** — unhandled error paths the ACs imply, a
   missing null/empty check, a swallow that masks a failure. Major if it
   breaks an AC; minor if it is a latent edge.
5. **Security surface** — authz (does the change widen who can act?),
   input validation, secrets (a key/log line that now exposes a token),
   injection (SQL/command from untrusted input). On a vue-supabase stack,
   an RLS policy that widens visibility (`USING (true)`,
   `auth.uid() IS NOT NULL`) is a cross-user data leak — see the stack
   reference. Security holes are blockers.
6. **Readability / maintainability** — naming, dead code, small
   duplication, clarity. These are minors/nits; they never lead.
7. **Component-instance refs** — when a parent calls an exposed method
   via a component-instance ref (template ref / view ref / ref
   attribute), verify the ref's **runtime shape**: some frameworks
   collect string refs in loops into **arrays**, so
   `ref.value?.method()` passes the optional chain and throws
   `TypeError: ... is not a function` at runtime while compiling clean.
   Prefer function/callback refs or typed ref arrays; the ref must bind
   to the component instance, not a collection. (Vue-specific
   manifestation: the vue-supabase stack reference.) This class is
   invisible to type-check and lint, so the review is its prevention
   net; the validating-ui Step-8 console net catches the runtime
   symptom.

### Step 5 — Classify findings by severity (the backbone)

Analogous to the debugger's four-class defect taxonomy, severity is what
makes the verdict mechanical rather than a vibe:

| Severity | Examples |
|---|---|
| **blocker** | correctness bug an AC catches; security hole; weakened test net (`.skip` / deleted assertion / widened tolerance / try-catch guard / mock-away); scope breach with no record |
| **major** | a missing AC (no test, no manual marker); brittle or vacant test; RLS/isolation gap below a security hole; unhandled error path an AC implies |
| **minor** | naming, dead code, small duplication; an out-of-scope urge recorded as a follow-up (the process held) |
| **nit** | style, taste, comment typos |

A finding needs a **location** (file + hunk/line) and a **concrete
reason** ("the SELECT policy is `USING (true)`, granting every
authenticated user read access to all shared_sessions rows — a cross-user
leak"), not "this feels off." A finding a third party cannot act on is
not a finding. Tag each **must-change** (blocks merge) vs **consider**
(optional) so the author knows what blocks vs what is taste — never
inflate a nit into a blocker, never bury a blocker among nits.

### Step 6 — Issue the verdict

The verdict follows the severity — it is not a separate judgement:

- **any blocker → `request-changes`** (or `blocked-on-design`, below).
- **majors but no blocker → `request-changes`.**
- **only minors / nits → `approve-with-nits`.**
- **no findings → `approve`.**
- **a design/plan defect (the code matches an AC, the AC conflicts with
  the Goal or another AC, the plan is internally contradictory) →
  `blocked-on-design`.** This is the class-3 posture shared with
  `debugging-test-failures`: the reviewer does **not** pick a side by
  editing the code or flagging the correct code as a bug. The defect is
  in the plan. Route to `designing-architecture` to reconcile the plan,
  issue zero source edits, and do not retry the code against the
  unreconciled plan.

Routing for each blocker: a code fix → `implementing-features` (the
author fixes, not the reviewer); a plan-internal contradiction →
`designing-architecture`; a non-converging test failure behind a weakened
net → `debugging-test-failures` for root-cause diagnosis before the fix.
The reviewer diagnoses; it does not patch and does not re-run the design.

### Step 7 — Write REVIEW.md; STOP

Write the review to `REVIEW.md` at the repo root (the output contract):

```markdown
# Review: <slug or branch> (<scenario / one phrase>)

## Verdict
<approve | approve-with-nits | request-changes | blocked-on-design>

## AC Coverage        (only when a plan is in play)
- AC1: satisfied | not satisfied | manual — <steps> | <conflict note>
- ...

## Findings
### Blockers
- <file:hunk> (<reason>) — MUST change. <concrete reason>. Route → ...
### Majors
### Minors
### Nits
- <file:line> (<reason>) — consider. (taste)

## Routing
- <per blocker: route → implementing-features | designing-architecture | debugging-test-failures>

## Notes
No source files were edited by this review.
```

Then **STOP**. Do not edit any source file (the review is read-only on
the code — diagnose, never patch). Do not run `git commit` / `push` /
merge / PR unless the user asks. The handoff is the gate; the user
decides whether to fix, re-plan, or merge.

## False-positive discipline (do not manufacture severity)

A clean, plan-conforming diff with only nits gets `approve-with-nits` —
not `request-changes`. Inventing a blocker to seem thorough is a defect
in the review, not diligence. Two failure modes to refuse explicitly:

- **Manufactured severity** — flagging an in-scope, AC-satisfying edit as
  a "bug" because the reviewer misread the plan (e.g. flagging a
  descending sort as wrong when AC1 says descending). Re-read the plan
  before classifying; if the code matches the AC, it is not a defect.
- **Nit inflation** — promoting a style quibble to a blocker. Severity
  follows the table; taste never blocks merge.

The same discipline that refuses false positives must not cover real ones:
a real blocker (a security hole, a weakened net, an unrecorded scope
breach) is a blocker even if the rest of the diff is clean. Never bury a
blocker among nits; lead with it.

## Closure

A review pass is done, all at once, when:

1. **Every changed hunk assessed** — no hunk skipped.
2. **Findings classified** by severity, each with location + concrete
   reason + must-change/consider tag.
3. **Verdict issued** — following the severity table.
4. **Routing stated** for each blocker (back to implement, design, or
   debug).
5. **REVIEW.md written** at the repo root.
6. **Zero source edits** — read-only on the code.

"Looks fine" without inspecting the hunks is not closure — it is a
refused review. Reopen Step 4.

## When not to use this skill

- **Fixing the code** — that is `implementing-features`. The reviewer
  diagnoses; fixes route back to the author. Do not edit source.
- **Diagnosing a failing test** — that is `debugging-test-failures`. A
  review *flags* a weakened net; it does not own the root-cause search.
- **Writing tests** — the test trio owns authoring. A review checks the
  tests are behaviour-asserting, meaningful, right-layer, additive; it
  does not author them.
- **Multi-lens council review** — `agents/council.md`
  (security/performance/ux/architecture/product lenses) is a separate
  multi-reviewer discipline, **defaulting to free models with a paid
  opt-in**. This skill is single-reviewer. Note the relationship, do not
  absorb the council.
- **Re-running the design** — a `blocked-on-design` review routes to
  `designing-architecture`; it does not rewrite the plan in a review pass.
- **Ranking a backlog or producing a plan** — `triaging-requirements` or
  `designing-architecture`.

## References

- [references/stacks/vue-supabase.md](references/stacks/vue-supabase.md)
  — review-time concerns for Vue 3 + Pinia + Supabase + Vuetify 3 +
  Playwright stacks: RLS-policy widening on schema/policy diffs,
  generated-types never hand-edited, Vuetify semantic variables vs raw
  CSS, Pinia store pattern conformance, e2e selector/timeout discipline
  in changed specs. Read at Step 2 when the project's rules file declares
  stack `vue-supabase`.
- The plan artifact contract is defined in
  [../designing-architecture/references/plan-format.md](../designing-architecture/references/plan-format.md)
  — the Goal + ACs + Files to Modify + Scope this review checks the diff
  against. Link it, never duplicate it.
- The implement handoff this review consumes is defined in
  [../implementing-features/SKILL.md](../implementing-features/SKILL.md)
  — files-in-scope, `## History` deviations, `### Follow-ups`, AC status
  (satisfied / manual). Scope-discipline is a review criterion because
  the implement skill's scope contract is what the review audits.
- The cardinal rule (never green by weakening the net) is defined in
  [../debugging-test-failures/SKILL.md](../debugging-test-failures/SKILL.md)
  — the test-net check in Step 4 cites it; a weakened net in the diff is
  a blocker.
- The test trio (right-layer + meaningful + behaviour-asserting standard):
  [../writing-unit-tests/SKILL.md](../writing-unit-tests/SKILL.md),
  [../writing-integration-tests/SKILL.md](../writing-integration-tests/SKILL.md),
  [../writing-e2e-tests/SKILL.md](../writing-e2e-tests/SKILL.md).
- CI/CD workflow changes are reviewed against the topology from
  [../designing-cicd/SKILL.md](../designing-cicd/SKILL.md), and their
  secret / supply-chain posture against
  [../securing-ci/SKILL.md](../securing-ci/SKILL.md) — the producer and
  security-discipline siblings of this review.