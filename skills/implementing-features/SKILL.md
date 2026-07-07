---
name: implementing-features
description: Execute ONE approved plan artifact — code changes strictly within the plan's scope, verified by the plan's Verification commands — then stop at a manual-validation handoff. Use whenever the user says "implement the plan", "build feat-x", "execute the plan at .opencode/plans/<slug>.md", "the plan is approved, go", or hands off from a design pass — even without saying "implement" or "build". Refuses scope creep (cites the plan's Excluded list; records follow-ups). Mechanical plan-vs-reality mismatches proceed with a History note; contract-breaking ones stop and route back to designing-architecture. Not for: trivial single-file changes with no plan (just edit), authoring or revising plans (that is designing-architecture), or deep debugging (separate skill).
---

# Implementing Features

Execute one approved plan artifact. The plan is a contract: this skill is
the **consumer** side of `designing-architecture`'s plan format (see
[plan-format.md in designing-architecture](../designing-architecture/references/plan-format.md)
for the contract; the library installs as a set, so the sibling skill is
always present). Implement what `Files to Modify` + `Included` scope
say, run the plan's `Verification` commands until they exit 0, append a
`## History` entry, then **stop** at a manual-validation handoff. The
skill never declares success from intent — only from green verification
exit codes — and never self-certifies an acceptance criterion that
needs human eyes.

## The implement pass

Copy this checklist and check off items as you complete them.

```
Implement Progress:
- [ ] 1. Read the plan artifact (frontmatter status first)
- [ ] 2. Resolve scope contract: Files to Modify + Included + Excluded
- [ ] 3. Detect stack & load the matching stack reference
- [ ] 4. Reconcile plan vs the actual repo (deviation triage BEFORE edits)
- [ ] 5. Implement exactly Files to Modify (scope discipline)
- [ ] 6. Run the plan's Verification; fix + re-run until all exit 0
- [ ] 7. Update the plan (History entry; status per the user's convention)
- [ ] 8. Completion handoff summary + MANUAL validation steps; STOP
```

### Step 1 — Read the plan artifact

The skill starts only when given a plan artifact path. Read it before
touching any source — the prompt alone is not the spec; the plan is.

- **No plan path given** and the work is multi-file or schema-touching
  → route to `designing-architecture` and stop. This skill does not
  reverse-engineer a plan from a prompt; the design stage exists for
  that, and skipping it destroys the loop's auditability.
- **No plan path given** and the work is a single-file trivial change
  (rename a helper, tweak a constant) → just edit it. A plan costs more
  than the change; this skill is not needed (see "When not to use").

Read the frontmatter `status:` field next:

- `status: approved` → proceed.
- `status: draft` → the plan has not been approved yet. **Stop and
  confirm with the user** before editing code ("the plan at
  `<path>` is `status: draft` — should I treat it as approved and
  implement, or hand back to design?"). Do not silently treat a draft
  as approved; the audit trail says the user has not green-lit it.
- `status: superseded` → the plan has been replaced; do not implement
  it. Surface the `related:` pointer to the supersedes and switch to
  that plan.

If the plan exists but is missing required sections (`Files to Modify`,
`Verification`, `Scope`), that is a contract defect — route back to
`designing-architecture` rather than improvising the missing pieces.

### Step 2 — Resolve the scope contract

The scope contract is three lists, read together:

1. **Files to Modify** — the only files you may create or edit. A file
   not on this list is out of scope; do not "tidy" it, do not refactor
   it, do not fix a pre-existing bug in it on the way past.
2. **Scope → Included** — what the plan delivers. Confirms intent when
   a file's `what-changes` note is ambiguous.
3. **Scope → Excluded** — the boundary you cite when refusing scope
   creep. Non-empty by plan-format contract.

Hold these three in working memory for the whole pass; they are what
every "should I do this too?" temptation is checked against.

### Step 3 — Detect stack & load the matching stack reference

Identify the project stack from the rules file (`AGENTS.md` /
`.opencode/agents.md`). If this skill bundles a matching stack reference
under `references/stacks/` (resolved against this skill's own directory
— not the project's), read it now and apply its implementation-time
concerns. If none exists, proceed generically and flag the gap to the
user in the handoff (a missing stack reference is a finding, not a
silent "I'll improvise").

Available stack references:

- vue-supabase → [references/stacks/vue-supabase.md](references/stacks/vue-supabase.md)
  Read when the project is Vue 3 + Pinia + Supabase (Postgres + Auth +
  RLS) with offline / PWA. Applies generated-types handling, RLS-aware
  edits, offline-outbox wiring, and e2e selector/condition conventions.

### Step 4 — Reconcile plan vs the actual repo (BEFORE editing)

Before editing, match every `Files to Modify` entry against what's
actually on disk. Read each file the plan names. Mismatches are not
unusual — the plan was written in a design pass; the repo may have
moved since. Classify each mismatch immediately:

- **Small mechanical deviation** — the feature is unchanged; only a
  mechanical detail differs (file moved/renamed, exact import alias
  differs, a path the plan named as `src/lib/foo.ts` is conventionally
  `src/lib/bar.ts` here). Proceed with the corrected detail and add a
  dated `## History` entry recording the correction and the reason.
- **Contract-breaking deviation** — the mismatch changes what is being
  built: a different feature, a schema that differs from the plan's
  `Schema / Type Impacts`, or an acceptance criterion that is untestable
  as written (references a file / service / table the plan does not add
  and Files to Modify does not include). **STOP**. Do not edit source.
  Report the specific mismatch to the user and route back to
  `designing-architecture` to revise the plan. The implementer never
  silently improvises a different design — that is design work, and
  doing it inside an implement pass makes the audit trail lie.

The distinction is *does the difference change the feature being
built?* A moved file does not; a different feature, schema, or
criterion does. When in doubt, treat it as contract-breaking and stop —
a stop is recoverable, a built-wrong-feature is not.

### Step 5 — Implement exactly Files to Modify (scope discipline)

Edit only the files named in `Files to Modify`, and only the changes
the per-file `what-changes` note plus `Included` scope describe. Treat
every "while I'm in there, also…" impulse — whether from the user or
from the code — as scope creep until checked against the plan:

- The **user** asks for an adjacent extra ("also add a notification
  badge to the icon — should be a one-liner") that is not in
  `Files to Modify`:
  refuse, citing the plan's `Excluded` list if it names the extra, or
  the absence from `Files to Modify` otherwise. Record the request as a
  follow-up note (a `### Follow-ups` block under `## History`, or an
  `## Open Questions` entry) so the next triage / design pass can pick
  it up without re-deriving it. Do not build it.
- The **code** tempts a refactor ("the neighbor function is messy, clean
  it up"): refuse unless that refactor is the change the plan names.
  Record it as a follow-up. An implementer that quietly expands scope
  destroys the loop's auditability — the next reader of the diff cannot
  tell what was the plan and what was improvisation.

Why this is rigid: the loop's value is that a reviewer (or a council)
can read the diff and check it against the plan one-to-one. Every
in-scope edit has a plan citation; every out-of-scope urge either got
cited-and-refused or recorded as a follow-up. No silent expansion.

### Step 6 — Run the plan's Verification (objective closure)

Run the commands from the plan's `## Verification` section — not a
generic `npm test`, and not a subset you chose yourself. The plan's
Verification section is the contract; the design stage pulled these
commands from the project's rules file.

The loop:

1. Run each verification command.
2. On failure: read the failure, fix the code (within scope), re-run.
3. Only when **all** verification commands exit 0 is the implement pass
   green. Success is the exit codes, never intent — "I think it works"
   is not closure.

Two honest-stop conditions:

- **N reasonable fix attempts have not converged.** If a single
  verification failure resists a small number of focused fix attempts
  (each grounded in the failure output, not random edits), stop and
  report — do not thrash the codebase. A separate debug stage will own
  deep debugging; folding it into the implement pass produces brittle
  changes no one can audit.
- **The failure reveals the plan itself is wrong** (a verifier that
  can't pass for any in-scope implementation because the plan omits a
  dependency, or asserts behaviour the plan doesn't add). That is a
  contract-breaking deviation (Step 4): stop, report, route to design.
  Do not "win" the verifier by silently adding the missing dependency
  out of scope.

Exit codes are the only success signal. Lint warnings you "didn't get
to" still count as failing — fix them or report.

### Step 7 — Update the plan artifact

Once verification is green, **append** to the plan — do not rewrite
prior sections, do not clobber the History:

- Append a dated `## History` entry: the date + a one-line summary of
  what was implemented + the verification result ("implemented; type-
  check + lint + test green"). If you recorded a mechanical deviation
  in Step 4, its one-line note also lives here.
- Append a `### Follow-ups` block (under `## History`) for any
  out-of-scope requests you recorded in Step 5, so the next design pass
  can pick them up.
- Flip the frontmatter `status` only per the user's stated convention —
  some projects keep plans `approved` throughout; others flip to
  `implemented` or `done`. If the convention is unknown, leave status
  alone and surface the question in the handoff. Do not pre-flip.
- Append the revision date to `revised:` (never replace the array).

The plan is the audit trail. A future reader must be able to
reconstruct "what was the plan, what did the implementer actually do,
where did it diverge and why" from the plan file alone.

### Step 8 — Completion handoff summary; STOP

Present a **concise** handoff to the user and wait:

- **What changed** — which files were edited / created, in one line per
  file, referencing the plan's `Files to Modify`.
- **Acceptance-criteria status** — per criterion, the status as
  evidenced by the verifier that greened. Criteria whose verifier is a
  command that greened: mark them satisfied (with the command). Criteria
  whose verifier requires human judgement (visible behaviour, a manual
  workflow like "go offline, start a timer, reload, come back online,
  watch the replay"): mark them `manual — steps below`. **Do not
  self-certify criteria that require human eyes.**
- **MANUAL validation steps** — the concrete sequence the human should
  run to green the human-only criteria. Numbered, in the order the user
  would perform them, ending with "what you should observe".
- **Plan state** — the plan's path, the History entry you appended, the
  status (flipped or not).
- **Follow-ups** — any recorded scope-creep requests, surfaced so the
  user can decide whether to hand them to triage / design.

Then **STOP** and wait. Do not run `git add` / `commit` / `push` /
merge / open a PR unless the user asks. Do not move on to the next
roadmap item. Do not run `reviewing-code` on yourself. The handoff is
the gate; the user decides what comes next (review, more work, commit,
or hand off to another session).

## Scope discipline (the heart of this skill)

Stated again because it is the most-violated rule: implement what
`Files to Modify` + `Included` say, nothing more. Scope creep is the
single most common way an implement pass goes wrong. Three pressures
to watch for:

1. **The user is "helpful"** — "while you're in there, also add…".
   Cite the Excluded list or the absence from Files to Modify, record
   the ask as a follow-up, do not build it. Helpful does not equal
   in-scope.
2. **The code is "ugly"** — a neighbouring function or file tempts a
   refactor that is not the plan. Refusing is not perfectionism; the
   audit trail needs every diff hunk to map to a plan citation. Record
   it as a follow-up; the next design pass can adopt it.
3. **The plan is "incomplete"** — a verifier needs a thing Files to
   Modify does not include. That is a contract-breaking deviation
   (Step 4), not a licence to extend scope silently. Stop and route to
   design.

The escape hatch for all three is the same: record the urge (History
follow-up or a stop-and-route), do not extend scope. An implementer
that expands scope destroys the loop's auditability — the diff no
longer maps one-to-one to the plan, and a reviewer cannot tell what
was decided vs improvised.

## Deviation protocol (summary)

| Mismatch type | Action |
|---|---|
| File moved / renamed / path alias differs | Mechanical: proceed at the corrected path; add dated `## History` note with reason |
| Exact line numbers / import specifiers drift | Mechanical: proceed; record in History |
| Different feature than the plan's Goal | Contract-breaking: STOP, report, route to designing-architecture |
| Schema / Type Impacts differ from `db/schema.sql` | Contract-breaking: STOP, report, route to design |
| Acceptance criterion untestable as written (references a file / service / table the plan does not add) | Contract-breaking: STOP, report, route to design |
| Verifier cannot pass for any in-scope implementation | Contract-breaking (plan-omits-dependency): STOP, report, route to design |
| N reasonable fix attempts do not converge | Honest-stop: STOP, report, hand to the debug stage (do not thrash) |

A moved file is mechanical; a moved feature is contract-breaking.
Recorded deviations are honest; silent ones are not. When in doubt,
stop — stops are recoverable, a built-wrong-feature is not.

## When not to use this skill

- **Single-file trivial change** (rename a helper, tweak a constant,
  fix a typo) — just edit it. Designing a plan costs more than the
  change.
- **No plan exists and the work is multi-file or schema-touching** —
  route to `designing-architecture` first. This skill is the consumer
  of a plan, not its author.
- **Authoring or revising the plan itself** — that is
  `designing-architecture`. This skill never edits the plan's Goal,
  Acceptance Criteria, Files to Modify, Scope, or Schema sections;
  it only appends History / follow-ups (mechanical deviations and
  scope-creep requests) and (optionally) flips status per convention.
- **Deep multi-session debugging** — a failure that resists N fix
  attempts in Step 6 is a stop, not a thrash session. The debug stage
  will own that; the implement pass's job is to converge, not to debug
  indefinitely.
- **Pure research / explanation** ("what does this code do?",
  "why is this slow?") with no plan to execute — answer; do not
  implement.
- **Ranking a backlog or producing a plan** — `triaging-requirements`
  or `designing-architecture`. This skill sits after both.

## References

- [references/stacks/vue-supabase.md](references/stacks/vue-supabase.md)
  — implementation-time concerns for Vue 3 + Pinia + Supabase + offline
  / PWA stacks: generated-types handling (regen, never hand-edit), RLS-
  aware edits, offline-outbox wiring, e2e selector/condition conventions
  over fixed timeouts, Vuetify semantic variables over raw CSS, and
  following existing store/composable patterns. Read at Step 3 when the
  project's rules file declares stack `vue-supabase`.
- The plan artifact contract is defined upstream in
  [../designing-architecture/references/plan-format.md](../designing-architecture/references/plan-format.md)
  — frontmatter, section order, section schemas, and the acceptance-
  criteria quality bar. This skill is its consumer; when a plan is
  missing required sections or contradicts itself, route back to
  `designing-architecture` rather than improvising.